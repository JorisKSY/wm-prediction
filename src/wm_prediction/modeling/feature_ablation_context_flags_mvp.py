import pandas as pd

from wm_prediction.modeling.feature_ablation_poisson_mvp import evaluate_split, make_model
from wm_prediction.modeling.poisson_regressor_mvp import (
    add_temporal_split,
    load_model_input,
)


FIFA_RAW_ALL_COLUMNS = [
    "home_fifa_rank",
    "away_fifa_rank",
    "home_fifa_ranking_age_days",
    "away_fifa_ranking_age_days",
    "fifa_rank_diff_home_minus_away",
]

GOAL_DIFF_FORM_COLUMNS = [
    "prev5_goal_diff_per_match_diff",
    "prev10_goal_diff_per_match_diff",
    "prev5y_goal_diff_per_match_diff",
]

CONTEXT_SETS = {
    "all_context": [
        "is_neutral",
        "is_friendly",
        "is_world_cup",
        "is_world_cup_qualifier",
        "is_major_continental_tournament",
        "is_continental_qualifier",
        "is_nations_league",
    ],
    "no_nations_league": [
        "is_neutral",
        "is_friendly",
        "is_world_cup",
        "is_world_cup_qualifier",
        "is_major_continental_tournament",
        "is_continental_qualifier",
    ],
    "neutral_friendly_only": [
        "is_neutral",
        "is_friendly",
    ],
    "neutral_only": [
        "is_neutral",
    ],
    "no_context": [],
}


def run_one(df: pd.DataFrame, ablation_name: str, feature_columns: list[str]) -> list[dict]:
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
    for context_name, context_columns in CONTEXT_SETS.items():
        feature_columns = context_columns + FIFA_RAW_ALL_COLUMNS + GOAL_DIFF_FORM_COLUMNS
        rows.extend(run_one(df, context_name, feature_columns))

    metrics = pd.DataFrame(rows)

    print("PoissonRegressor MVP context-flag ablation")
    print("Base features: raw FIFA rank features + goal-diff form")
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
