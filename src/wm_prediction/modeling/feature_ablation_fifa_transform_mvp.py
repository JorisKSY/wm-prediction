import numpy as np
import pandas as pd

from wm_prediction.modeling.feature_ablation_poisson_mvp import evaluate_split, make_model
from wm_prediction.modeling.poisson_regressor_mvp import (
    add_temporal_split,
    load_model_input,
)


CONTEXT_COLUMNS = [
    "is_neutral",
    "is_friendly",
    "is_world_cup",
    "is_world_cup_qualifier",
    "is_major_continental_tournament",
    "is_continental_qualifier",
    "is_nations_league",
]

FIFA_AGE_COLUMNS = [
    "home_fifa_ranking_age_days",
    "away_fifa_ranking_age_days",
]

GOAL_DIFF_FORM_COLUMNS = [
    "prev5_goal_diff_per_match_diff",
    "prev10_goal_diff_per_match_diff",
    "prev5y_goal_diff_per_match_diff",
]

FEATURE_SETS = {
    "raw_rank_diff_goaldiff_form": (
        CONTEXT_COLUMNS
        + FIFA_AGE_COLUMNS
        + ["fifa_rank_diff_home_minus_away"]
        + GOAL_DIFF_FORM_COLUMNS
    ),
    "raw_home_away_rank_goaldiff_form": (
        CONTEXT_COLUMNS
        + FIFA_AGE_COLUMNS
        + ["home_fifa_rank", "away_fifa_rank"]
        + GOAL_DIFF_FORM_COLUMNS
    ),
    "raw_all_rank_goaldiff_form": (
        CONTEXT_COLUMNS
        + FIFA_AGE_COLUMNS
        + ["home_fifa_rank", "away_fifa_rank", "fifa_rank_diff_home_minus_away"]
        + GOAL_DIFF_FORM_COLUMNS
    ),
    "log_home_away_rank_goaldiff_form": (
        CONTEXT_COLUMNS
        + FIFA_AGE_COLUMNS
        + ["home_fifa_rank_log1p", "away_fifa_rank_log1p"]
        + GOAL_DIFF_FORM_COLUMNS
    ),
    "log_rank_diff_goaldiff_form": (
        CONTEXT_COLUMNS
        + FIFA_AGE_COLUMNS
        + ["fifa_rank_log1p_diff_home_minus_away"]
        + GOAL_DIFF_FORM_COLUMNS
    ),
    "rank_strength_diff_goaldiff_form": (
        CONTEXT_COLUMNS
        + FIFA_AGE_COLUMNS
        + ["fifa_rank_strength_diff_home_minus_away"]
        + GOAL_DIFF_FORM_COLUMNS
    ),
}


def add_rank_transforms(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["home_fifa_rank_log1p"] = np.log1p(df["home_fifa_rank"])
    df["away_fifa_rank_log1p"] = np.log1p(df["away_fifa_rank"])
    df["fifa_rank_log1p_diff_home_minus_away"] = (
        df["home_fifa_rank_log1p"] - df["away_fifa_rank_log1p"]
    )

    # Higher value = stronger team. This avoids estimating a percentile from the full dataset.
    df["home_fifa_rank_strength"] = 1.0 / df["home_fifa_rank"]
    df["away_fifa_rank_strength"] = 1.0 / df["away_fifa_rank"]
    df["fifa_rank_strength_diff_home_minus_away"] = (
        df["home_fifa_rank_strength"] - df["away_fifa_rank_strength"]
    )

    return df


def run_one(df: pd.DataFrame, feature_set_name: str, feature_columns: list[str]) -> list[dict]:
    missing_features = int(df[feature_columns].isna().sum().sum())
    if missing_features:
        raise ValueError(
            f"{feature_set_name}: selected features contain {missing_features} NULL values."
        )

    train = df[df["split"] == "train_pre_2018"].copy()

    home_model = make_model(feature_columns)
    away_model = make_model(feature_columns)

    home_model.fit(train[feature_columns], train["home_goals"])
    away_model.fit(train[feature_columns], train["away_goals"])

    return [
        evaluate_split(feature_set_name, split_name, data, feature_columns, home_model, away_model)
        for split_name, data in df.groupby("split", sort=False)
    ]


def main() -> None:
    df = add_rank_transforms(add_temporal_split(load_model_input()))

    rows = []
    for feature_set_name, feature_columns in FEATURE_SETS.items():
        rows.extend(run_one(df, feature_set_name, feature_columns))

    metrics = pd.DataFrame(rows)

    print("PoissonRegressor MVP FIFA-rank transformation ablation")
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
