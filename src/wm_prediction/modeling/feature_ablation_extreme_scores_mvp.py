import pandas as pd

from wm_prediction.modeling.feature_ablation_poisson_mvp import (
    ABLATION_SETS,
    evaluate_split,
    make_model,
)
from wm_prediction.modeling.poisson_regressor_mvp import (
    add_temporal_split,
    load_model_input,
)


FEATURE_SET_NAMES = [
    "current_mvp_all_18",
    "goal_diff_form_no_ppm",
]


TRAIN_FILTERS = {
    "full_train": lambda df: df,
    "drop_team_8plus_from_train": lambda df: df[
        df[["home_goals", "away_goals"]].max(axis=1) < 8
    ],
    "drop_total_10plus_from_train": lambda df: df[
        (df["home_goals"] + df["away_goals"]) < 10
    ],
}


def run_one(
    df: pd.DataFrame,
    feature_set_name: str,
    train_filter_name: str,
) -> list[dict]:
    feature_columns = ABLATION_SETS[feature_set_name]

    missing_features = int(df[feature_columns].isna().sum().sum())
    if missing_features:
        raise ValueError(
            f"{feature_set_name}: selected features contain {missing_features} NULL values."
        )

    train_full = df[df["split"] == "train_pre_2018"].copy()
    train = TRAIN_FILTERS[train_filter_name](train_full).copy()

    home_model = make_model(feature_columns)
    away_model = make_model(feature_columns)

    home_model.fit(train[feature_columns], train["home_goals"])
    away_model.fit(train[feature_columns], train["away_goals"])

    rows = []
    for split_name, data in df.groupby("split", sort=False):
        row = evaluate_split(
            ablation_name=feature_set_name,
            split_name=split_name,
            data=data,
            feature_columns=feature_columns,
            home_model=home_model,
            away_model=away_model,
        )
        row["train_filter"] = train_filter_name
        row["train_rows_used"] = len(train)
        row["train_rows_excluded"] = len(train_full) - len(train)
        rows.append(row)

    return rows


def main() -> None:
    df = add_temporal_split(load_model_input())

    rows = []
    for feature_set_name in FEATURE_SET_NAMES:
        for train_filter_name in TRAIN_FILTERS:
            rows.extend(run_one(df, feature_set_name, train_filter_name))

    metrics = pd.DataFrame(rows)

    print("PoissonRegressor MVP extreme-score training sensitivity")
    print("Extreme-score filters are applied to TRAINING ONLY.")
    print("Validation/test rows stay unchanged.")
    print("No DB writes")
    print()

    display_columns = [
        "ablation",
        "train_filter",
        "split",
        "train_rows_used",
        "train_rows_excluded",
        "home_deviance",
        "away_deviance",
        "wdl_log_loss",
        "wdl_brier",
    ]

    print(
        metrics[display_columns]
        .sort_values(["split", "ablation", "train_filter"])
        .round(4)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
