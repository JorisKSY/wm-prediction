import json
from datetime import date

import pandas as pd
from sqlalchemy import text

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.feature_ablation_poisson_mvp import evaluate_split, make_model
from wm_prediction.modeling.poisson_regressor_mvp import add_temporal_split, load_model_input


EXPERIMENT_RUN_ID = "poisson_alpha_tuning_v1_phase_b_2026_06_06"
MODEL_NAME = "sklearn_poisson_regressor"

ALPHAS = [0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]

FEATURE_SETS = {
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
    "cleaned_14_candidate": [
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
        "prev5_goal_diff_per_match_diff",
        "prev10_goal_diff_per_match_diff",
        "prev5y_goal_diff_per_match_diff",
    ],
}

METRIC_COLUMNS = [
    "home_deviance",
    "away_deviance",
    "home_mae",
    "away_mae",
    "wdl_log_loss",
    "wdl_brier",
]


def split_date_bounds(data: pd.DataFrame) -> tuple[date, date]:
    return (
        data["match_date"].min().date(),
        data["match_date"].max().date(),
    )


def build_metric_rows(df: pd.DataFrame) -> list[dict]:
    rows = []

    for feature_set_name, feature_columns in FEATURE_SETS.items():
        missing_features = int(df[feature_columns].isna().sum().sum())
        if missing_features:
            raise ValueError(
                f"{feature_set_name}: selected features contain {missing_features} NULL values."
            )

        train = df[df["split"] == "train_pre_2018"].copy()
        train_start, train_end = split_date_bounds(train)

        for alpha in ALPHAS:
            home_model = make_model(feature_columns)
            away_model = make_model(feature_columns)

            home_model.named_steps["model"].set_params(alpha=alpha)
            away_model.named_steps["model"].set_params(alpha=alpha)

            home_model.fit(train[feature_columns], train["home_goals"])
            away_model.fit(train[feature_columns], train["away_goals"])

            alpha_label = str(alpha).replace(".", "p")
            model_name = f"{MODEL_NAME}_alpha_{alpha_label}"

            for split_name, data in df.groupby("split", sort=False):
                eval_start, eval_end = split_date_bounds(data)

                metrics = evaluate_split(
                    ablation_name=feature_set_name,
                    split_name=split_name,
                    data=data,
                    feature_columns=feature_columns,
                    home_model=home_model,
                    away_model=away_model,
                )

                for metric_name in METRIC_COLUMNS:
                    rows.append(
                        {
                            "experiment_run_id": EXPERIMENT_RUN_ID,
                            "model_name": model_name,
                            "feature_set_name": feature_set_name,
                            "target_name": "match_goals_and_wdl",
                            "split": split_name,
                            "metric_name": metric_name,
                            "metric_value": float(metrics[metric_name]),
                            "train_start_date": train_start,
                            "train_end_date": train_end,
                            "eval_start_date": eval_start,
                            "eval_end_date": eval_end,
                            "n_train_rows": int(len(train)),
                            "n_eval_rows": int(len(data)),
                            "params_json": json.dumps(
                                {
                                    "alpha": alpha,
                                    "max_iter": 1000,
                                    "feature_count": len(feature_columns),
                                    "features": feature_columns,
                                }
                            ),
                            "notes": (
                                "Phase B alpha tuning for current MVP 18-feature set "
                                "and cleaned 14-feature candidate."
                            ),
                        }
                    )

    return rows


def write_rows(rows: list[dict]) -> None:
    delete_sql = text(
        """
        DELETE FROM experiments.model_evaluation_results
        WHERE experiment_run_id = :experiment_run_id
        """
    )

    insert_sql = text(
        """
        INSERT INTO experiments.model_evaluation_results (
            experiment_run_id,
            model_name,
            feature_set_name,
            target_name,
            split,
            metric_name,
            metric_value,
            train_start_date,
            train_end_date,
            eval_start_date,
            eval_end_date,
            n_train_rows,
            n_eval_rows,
            params_json,
            notes
        )
        VALUES (
            :experiment_run_id,
            :model_name,
            :feature_set_name,
            :target_name,
            :split,
            :metric_name,
            :metric_value,
            :train_start_date,
            :train_end_date,
            :eval_start_date,
            :eval_end_date,
            :n_train_rows,
            :n_eval_rows,
            CAST(:params_json AS jsonb),
            :notes
        )
        """
    )

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete_sql, {"experiment_run_id": EXPERIMENT_RUN_ID})
        conn.execute(insert_sql, rows)


def main() -> None:
    df = add_temporal_split(load_model_input())
    rows = build_metric_rows(df)
    write_rows(rows)

    print("Wrote alpha tuning experiment rows")
    print("experiment_run_id:", EXPERIMENT_RUN_ID)
    print("rows:", len(rows))


if __name__ == "__main__":
    main()
