import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import log_loss, mean_absolute_error, mean_poisson_deviance
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

from wm_prediction.db.connection import get_engine


SKLEARN_LABELS = ["AWAY_WIN", "DRAW", "HOME_WIN"]
MAX_GOALS = 20

# MVP feature groups:
# - Match context flags
# - Historical FIFA rank features with ranking_date < match_date
# - Pre-match team-form difference features only
#
# Explicitly excluded for leakage control:
# - Current FIFA/Elo snapshots
# - Current squad/market-value snapshots
# - Target-derived outlier flags
FEATURE_COLUMNS = [
    "is_neutral",
    "is_friendly",
    "is_world_cup",
    "is_world_cup_qualifier",
    "is_major_continental_tournament",
    "is_continental_qualifier",
    "is_nations_league",
    "home_fifa_rank",
    "away_fifa_rank",
    "home_fifa_ranking_age_days",
    "away_fifa_ranking_age_days",
    "fifa_rank_diff_home_minus_away",
    "prev5_points_per_match_diff",
    "prev5_goal_diff_per_match_diff",
    "prev10_points_per_match_diff",
    "prev10_goal_diff_per_match_diff",
    "prev5y_points_per_match_diff",
    "prev5y_goal_diff_per_match_diff",
]


def load_model_input() -> pd.DataFrame:
    query = f"""
    SELECT
        historical_match_id,
        match_date,
        home_team_name,
        away_team_name,
        home_goals,
        away_goals,
        result_label,
        {", ".join(FEATURE_COLUMNS)}
    FROM features.model_input_mvp_v1
    ORDER BY match_date, historical_match_id
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn, parse_dates=["match_date"])


def add_temporal_split(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["split"] = np.select(
        [
            df["match_date"] < "2018-01-01",
            df["match_date"] < "2022-01-01",
        ],
        [
            "train_pre_2018",
            "valid_2018_2021",
        ],
        default="test_2022_plus",
    )

    return df


def make_model() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), FEATURE_COLUMNS),
        ],
        remainder="drop",
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", PoissonRegressor(alpha=1.0, max_iter=1000)),
        ]
    )


def poisson_result_probs_home_draw_away(
    lambda_home: np.ndarray,
    lambda_away: np.ndarray,
) -> np.ndarray:
    goals = np.arange(MAX_GOALS + 1)
    all_probs = []

    for lh, la in zip(lambda_home, lambda_away):
        home_pmf = poisson.pmf(goals, lh)
        away_pmf = poisson.pmf(goals, la)

        score_matrix = np.outer(home_pmf, away_pmf)

        p_home = np.tril(score_matrix, k=-1).sum()
        p_draw = np.trace(score_matrix)
        p_away = np.triu(score_matrix, k=1).sum()

        probs = np.array([p_home, p_draw, p_away], dtype=float)
        all_probs.append(probs / probs.sum())

    return np.vstack(all_probs)


def reorder_home_draw_away_to_sklearn(probs: np.ndarray) -> np.ndarray:
    # HOME_WIN, DRAW, AWAY_WIN -> AWAY_WIN, DRAW, HOME_WIN
    return probs[:, [2, 1, 0]]


def multiclass_brier_score(y_true: pd.Series, probs_sklearn_order: np.ndarray) -> float:
    y_onehot = np.zeros_like(probs_sklearn_order)
    label_to_idx = {label: idx for idx, label in enumerate(SKLEARN_LABELS)}

    for row_idx, label in enumerate(y_true):
        y_onehot[row_idx, label_to_idx[label]] = 1.0

    return float(np.mean(np.sum((probs_sklearn_order - y_onehot) ** 2, axis=1)))


def evaluate_split(
    split_name: str,
    data: pd.DataFrame,
    home_model: Pipeline,
    away_model: Pipeline,
) -> dict:
    x = data[FEATURE_COLUMNS]

    lambda_home = np.clip(home_model.predict(x), 0.01, 20.0)
    lambda_away = np.clip(away_model.predict(x), 0.01, 20.0)

    probs_home_draw_away = poisson_result_probs_home_draw_away(lambda_home, lambda_away)
    probs_sklearn = reorder_home_draw_away_to_sklearn(probs_home_draw_away)

    return {
        "split": split_name,
        "rows": len(data),
        "home_lambda_avg": lambda_home.mean(),
        "away_lambda_avg": lambda_away.mean(),
        "home_mae": mean_absolute_error(data["home_goals"], lambda_home),
        "away_mae": mean_absolute_error(data["away_goals"], lambda_away),
        "home_poisson_deviance": mean_poisson_deviance(data["home_goals"], lambda_home),
        "away_poisson_deviance": mean_poisson_deviance(data["away_goals"], lambda_away),
        "wdl_log_loss": log_loss(data["result_label"], probs_sklearn, labels=SKLEARN_LABELS),
        "wdl_brier": multiclass_brier_score(data["result_label"], probs_sklearn),
    }


def summarize_standardized_coefficients(
    home_model: Pipeline,
    away_model: Pipeline,
) -> pd.DataFrame:
    summary = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "home_coef_std": home_model.named_steps["model"].coef_,
            "away_coef_std": away_model.named_steps["model"].coef_,
        }
    )

    summary["max_abs_coef_std"] = summary[
        ["home_coef_std", "away_coef_std"]
    ].abs().max(axis=1)

    return summary.sort_values(
        ["max_abs_coef_std", "feature"],
        ascending=[False, True],
    )



def main() -> None:
    df = add_temporal_split(load_model_input())

    missing_features = int(df[FEATURE_COLUMNS].isna().sum().sum())
    if missing_features:
        raise ValueError(f"Selected model features contain {missing_features} NULL values.")

    train = df[df["split"] == "train_pre_2018"].copy()

    home_model = make_model()
    away_model = make_model()

    home_model.fit(train[FEATURE_COLUMNS], train["home_goals"])
    away_model.fit(train[FEATURE_COLUMNS], train["away_goals"])

    metrics = pd.DataFrame(
        [
            evaluate_split(split_name, data, home_model, away_model)
            for split_name, data in df.groupby("split", sort=False)
        ]
    )

    print("PoissonRegressor MVP")
    print("Training split: train_pre_2018 only")
    print("Feature count:", len(FEATURE_COLUMNS))
    print()
    print(metrics.round(4).to_string(index=False))

    coefficient_summary = summarize_standardized_coefficients(home_model, away_model)

    print()
    print("Standardized feature coefficients")
    print("Interpretation: +1 std feature change effect on log(lambda_home/lambda_away)")
    print(coefficient_summary.round(4).to_string(index=False))



if __name__ == "__main__":
    main()
