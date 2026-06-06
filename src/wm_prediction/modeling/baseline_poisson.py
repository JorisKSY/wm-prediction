import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.metrics import log_loss, mean_absolute_error, mean_poisson_deviance
from sqlalchemy import text

from wm_prediction.db.connection import get_engine


SKLEARN_LABELS = ["AWAY_WIN", "DRAW", "HOME_WIN"]
MAX_GOALS = 20


def load_model_input() -> pd.DataFrame:
    query = """
    SELECT
        historical_match_id,
        match_date,
        home_goals,
        away_goals,
        result_label
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


def poisson_result_probs_home_draw_away(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = MAX_GOALS,
) -> np.ndarray:
    goals = np.arange(max_goals + 1)

    home_pmf = poisson.pmf(goals, lambda_home)
    away_pmf = poisson.pmf(goals, lambda_away)

    score_matrix = np.outer(home_pmf, away_pmf)

    p_home = np.tril(score_matrix, k=-1).sum()
    p_draw = np.trace(score_matrix)
    p_away = np.triu(score_matrix, k=1).sum()

    probs = np.array([p_home, p_draw, p_away], dtype=float)
    return probs / probs.sum()


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
    lambda_home: float,
    lambda_away: float,
    base_probs_home_draw_away: np.ndarray,
) -> dict:
    n_rows = len(data)

    pred_home_goals = np.full(n_rows, lambda_home)
    pred_away_goals = np.full(n_rows, lambda_away)

    pred_probs_home_draw_away = np.tile(base_probs_home_draw_away, (n_rows, 1))
    pred_probs_sklearn = reorder_home_draw_away_to_sklearn(pred_probs_home_draw_away)

    return {
        "split": split_name,
        "rows": n_rows,
        "home_mae": mean_absolute_error(data["home_goals"], pred_home_goals),
        "away_mae": mean_absolute_error(data["away_goals"], pred_away_goals),
        "home_poisson_deviance": mean_poisson_deviance(data["home_goals"], pred_home_goals),
        "away_poisson_deviance": mean_poisson_deviance(data["away_goals"], pred_away_goals),
        "wdl_log_loss": log_loss(
            data["result_label"],
            pred_probs_sklearn,
            labels=SKLEARN_LABELS,
        ),
        "wdl_brier": multiclass_brier_score(data["result_label"], pred_probs_sklearn),
        "pred_home_win": base_probs_home_draw_away[0],
        "pred_draw": base_probs_home_draw_away[1],
        "pred_away_win": base_probs_home_draw_away[2],
    }


def main() -> None:
    df = add_temporal_split(load_model_input())

    train = df[df["split"] == "train_pre_2018"].copy()

    lambda_home = float(train["home_goals"].mean())
    lambda_away = float(train["away_goals"].mean())

    base_probs_home_draw_away = poisson_result_probs_home_draw_away(
        lambda_home=lambda_home,
        lambda_away=lambda_away,
    )

    metrics = pd.DataFrame(
        [
            evaluate_split(split_name, data, lambda_home, lambda_away, base_probs_home_draw_away)
            for split_name, data in df.groupby("split", sort=False)
        ]
    )

    print("Train-only baseline lambdas")
    print(f"lambda_home = {lambda_home:.4f}")
    print(f"lambda_away = {lambda_away:.4f}")
    print()
    print(metrics.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
