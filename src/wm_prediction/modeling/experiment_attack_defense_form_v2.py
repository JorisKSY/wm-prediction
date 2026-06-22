import json
from datetime import date

import pandas as pd
from sqlalchemy import text

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.feature_ablation_poisson_mvp import evaluate_split, make_model
from wm_prediction.modeling.poisson_regressor_mvp import add_temporal_split


EXPERIMENT_RUN_ID = "poisson_attack_defense_v2_form_ablation_2026_06_06"
MODEL_NAME = "sklearn_poisson_regressor_alpha_0p03"
ALPHA = 0.03


BASE_CONTEXT_FEATURES = [
    "is_neutral",
    "is_friendly",
    "is_world_cup",
    "is_world_cup_qualifier",
    "is_major_continental_tournament",
    "is_continental_qualifier",
    "is_nations_league",
]

FIFA_FEATURES = [
    "home_fifa_rank",
    "away_fifa_rank",
    "home_fifa_ranking_age_days",
    "away_fifa_ranking_age_days",
    "fifa_rank_diff_home_minus_away",
]

MVP_FORM_FEATURES = [
    "prev5_points_per_match_diff",
    "prev5_goal_diff_per_match_diff",
    "prev10_points_per_match_diff",
    "prev10_goal_diff_per_match_diff",
    "prev5y_points_per_match_diff",
    "prev5y_goal_diff_per_match_diff",
]

ATTACK_DEFENSE_FORM_FEATURES = [
    "home_prev5_goals_for_per_match",
    "home_prev5_goals_against_per_match",
    "away_prev5_goals_for_per_match",
    "away_prev5_goals_against_per_match",

    "home_prev10_goals_for_per_match",
    "home_prev10_goals_against_per_match",
    "away_prev10_goals_for_per_match",
    "away_prev10_goals_against_per_match",

    "home_prev5y_goals_for_per_match",
    "home_prev5y_goals_against_per_match",
    "away_prev5y_goals_for_per_match",
    "away_prev5y_goals_against_per_match",
]


GOAL_DIFF_FORM_FEATURES = [
    "prev5_goal_diff_per_match_diff",
    "prev10_goal_diff_per_match_diff",
    "prev5y_goal_diff_per_match_diff",
]

POINTS_FORM_FEATURES = [
    "prev5_points_per_match_diff",
    "prev10_points_per_match_diff",
    "prev5y_points_per_match_diff",
]


FEATURE_SETS = {
    "current_mvp_all_18": (
        BASE_CONTEXT_FEATURES
        + FIFA_FEATURES
        + MVP_FORM_FEATURES
    ),
    "attack_defense_plus_mvp_form": (
        BASE_CONTEXT_FEATURES
        + FIFA_FEATURES
        + MVP_FORM_FEATURES
        + ATTACK_DEFENSE_FORM_FEATURES
    ),
    "attack_defense_only": (
        BASE_CONTEXT_FEATURES
        + FIFA_FEATURES
        + ATTACK_DEFENSE_FORM_FEATURES
    ),
    "attack_defense_plus_goal_diff": (
        BASE_CONTEXT_FEATURES
        + FIFA_FEATURES
        + GOAL_DIFF_FORM_FEATURES
        + ATTACK_DEFENSE_FORM_FEATURES
    ),
    "attack_defense_plus_points": (
        BASE_CONTEXT_FEATURES
        + FIFA_FEATURES
        + POINTS_FORM_FEATURES
        + ATTACK_DEFENSE_FORM_FEATURES
    ),
}


METRIC_COLUMNS = [
    "home_deviance",
    "away_deviance",
    "home_mae",
    "away_mae",
    "wdl_log_loss",
    "wdl_brier",
]

def load_attack_defense_model_input() -> pd.DataFrame:
    all_feature_columns = sorted(
        {
            column
            for feature_columns in FEATURE_SETS.values()
            for column in feature_columns
        }
    )

    query = f"""
    SELECT
        historical_match_id,
        match_date,
        home_team_name,
        away_team_name,
        home_goals,
        away_goals,
        result_label,
        {", ".join(all_feature_columns)}
    FROM features.model_input_mvp_v1
    ORDER BY match_date, historical_match_id
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn, parse_dates=["match_date"])


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

        home_model = make_model(feature_columns)
        away_model = make_model(feature_columns)

        home_model.named_steps["model"].set_params(alpha=ALPHA)
        away_model.named_steps["model"].set_params(alpha=ALPHA)

        home_model.fit(train[feature_columns], train["home_goals"])
        away_model.fit(train[feature_columns], train["away_goals"])

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
                        "model_name": MODEL_NAME,
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
                                "alpha": ALPHA,
                                "max_iter": 1000,
                                "feature_count": len(feature_columns),
                                "features": feature_columns,
                            }
                        ),
                        "notes": (
                            "Phase C v2 candidate. Adds separate attack/defense form "
                            "features that already exist in model_input_mvp_v1."
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
    df = add_temporal_split(load_attack_defense_model_input())
    rows = build_metric_rows(df)
    write_rows(rows)

    print("Wrote attack/defense v2 experiment rows")
    print("experiment_run_id:", EXPERIMENT_RUN_ID)
    print("rows:", len(rows))


if __name__ == "__main__":
    main()
