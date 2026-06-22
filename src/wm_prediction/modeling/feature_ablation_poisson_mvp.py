import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import log_loss, mean_absolute_error, mean_poisson_deviance
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from wm_prediction.modeling.poisson_regressor_mvp import (
    SKLEARN_LABELS,
    add_temporal_split,
    load_model_input,
    multiclass_brier_score,
    poisson_result_probs_home_draw_away,
    reorder_home_draw_away_to_sklearn,
)


ABLATION_SETS = {
    "current_mvp_all_18": [
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
    ],
    "fifa_diff_only_plus_context_form": [
        "is_neutral",
        "is_friendly",
        "is_world_cup",
        "is_world_cup_qualifier",
        "is_major_continental_tournament",
        "is_continental_qualifier",
        "is_nations_league",
        "home_fifa_ranking_age_days",
        "away_fifa_ranking_age_days",
        "fifa_rank_diff_home_minus_away",
        "prev5_points_per_match_diff",
        "prev5_goal_diff_per_match_diff",
        "prev10_points_per_match_diff",
        "prev10_goal_diff_per_match_diff",
        "prev5y_points_per_match_diff",
        "prev5y_goal_diff_per_match_diff",
    ],
    "fifa_home_away_only_plus_context_form": [
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
        "prev5_points_per_match_diff",
        "prev5_goal_diff_per_match_diff",
        "prev10_points_per_match_diff",
        "prev10_goal_diff_per_match_diff",
        "prev5y_points_per_match_diff",
        "prev5y_goal_diff_per_match_diff",
    ],
    "goal_diff_form_no_ppm": [
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
        "prev5_goal_diff_per_match_diff",
        "prev10_goal_diff_per_match_diff",
        "prev5y_goal_diff_per_match_diff",
    ],
    "ppm_form_no_goal_diff": [
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
        "prev10_points_per_match_diff",
        "prev5y_points_per_match_diff",
    ],
    "no_nations_league": [
        "is_neutral",
        "is_friendly",
        "is_world_cup",
        "is_world_cup_qualifier",
        "is_major_continental_tournament",
        "is_continental_qualifier",
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
    ],
}


def make_model(feature_columns: list[str]) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), feature_columns),
        ],
        remainder="drop",
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", PoissonRegressor(alpha=1.0, max_iter=1000)),
        ]
    )


def evaluate_split(
    ablation_name: str,
    split_name: str,
    data: pd.DataFrame,
    feature_columns: list[str],
    home_model: Pipeline,
    away_model: Pipeline,
) -> dict:
    x = data[feature_columns]

    lambda_home = np.clip(home_model.predict(x), 0.01, 20.0)
    lambda_away = np.clip(away_model.predict(x), 0.01, 20.0)

    probs_home_draw_away = poisson_result_probs_home_draw_away(lambda_home, lambda_away)
    probs_sklearn = reorder_home_draw_away_to_sklearn(probs_home_draw_away)

    return {
        "ablation": ablation_name,
        "split": split_name,
        "n_features": len(feature_columns),
        "rows": len(data),
        "home_deviance": mean_poisson_deviance(data["home_goals"], lambda_home),
        "away_deviance": mean_poisson_deviance(data["away_goals"], lambda_away),
        "home_mae": mean_absolute_error(data["home_goals"], lambda_home),
        "away_mae": mean_absolute_error(data["away_goals"], lambda_away),
        "wdl_log_loss": log_loss(data["result_label"], probs_sklearn, labels=SKLEARN_LABELS),
        "wdl_brier": multiclass_brier_score(data["result_label"], probs_sklearn),
    }


def run_ablation(df: pd.DataFrame, ablation_name: str, feature_columns: list[str]) -> list[dict]:
    missing_features = int(df[feature_columns].isna().sum().sum())
    if missing_features:
        raise ValueError(
            f"{ablation_name}: selected features contain {missing_features} NULL values."
        )

    train = df[df["split"] == "train_pre_2018"].copy()

    home_model = make_model(feature_columns)
    away_model = make_model(feature_columns)

    home_model.fit(train[feature_columns], train["home_goals"])
    away_model.fit(train[feature_columns], train["away_goals"])

    return [
        evaluate_split(ablation_name, split_name, data, feature_columns, home_model, away_model)
        for split_name, data in df.groupby("split", sort=False)
    ]


def main() -> None:
    df = add_temporal_split(load_model_input())

    rows = []
    for ablation_name, feature_columns in ABLATION_SETS.items():
        rows.extend(run_ablation(df, ablation_name, feature_columns))

    metrics = pd.DataFrame(rows)

    print("PoissonRegressor MVP feature ablation")
    print("Training split: train_pre_2018 only")
    print("No DB writes")
    print()

    display_columns = [
        "ablation",
        "split",
        "n_features",
        "rows",
        "home_deviance",
        "away_deviance",
        "wdl_log_loss",
        "wdl_brier",
    ]

    print(
        metrics[display_columns]
        .sort_values(["split", "wdl_log_loss", "wdl_brier", "ablation"])
        .round(4)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
