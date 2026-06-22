import json
from datetime import date

import pandas as pd
from sqlalchemy import text

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.feature_ablation_poisson_mvp import evaluate_split, make_model
from wm_prediction.modeling.poisson_regressor_mvp import add_temporal_split

from wm_prediction.modeling.experiment_attack_defense_form_v2 import (
    BASE_CONTEXT_FEATURES,
    FIFA_FEATURES,
    ATTACK_DEFENSE_FORM_FEATURES,
    POINTS_FORM_FEATURES,
)


EXPERIMENT_RUN_ID = "poisson_rank_momentum_phase_f_2026_06_07"
MODEL_NAME = "sklearn_poisson_regressor_alpha_0p03"
ALPHA = 0.03


# Phase E qualified block: mean-only SOS. Coverage columns are intentionally not
# model features because Phase E showed they add no real signal and can act as a
# time/coverage proxy.
SOS_MEAN_ONLY = [
    "home_prev5_opp_strength_mean",
    "away_prev5_opp_strength_mean",
    "home_prev10_opp_strength_mean",
    "away_prev10_opp_strength_mean",
    "home_prev365d_opp_strength_mean",
    "away_prev365d_opp_strength_mean",
]


# Phase F candidate: FIFA rank momentum over 1 year.
# Use home + away only. Do NOT add rank_improve_1yr_diff here because it is an
# exact linear combination of these two columns and would be redundant/collinear
# in the current linear PoissonRegressor setup.
RANK_MOMENTUM_FEATURES = [
    "home_rank_improve_1yr",
    "away_rank_improve_1yr",
]


ATTACK_DEFENSE_PLUS_SOS = (
    BASE_CONTEXT_FEATURES
    + FIFA_FEATURES
    + POINTS_FORM_FEATURES
    + ATTACK_DEFENSE_FORM_FEATURES
    + SOS_MEAN_ONLY
)


FEATURE_SETS = {
    "attack_defense_plus_sos_mean_only": ATTACK_DEFENSE_PLUS_SOS,
    "attack_defense_plus_sos_plus_rank_momentum": (
        ATTACK_DEFENSE_PLUS_SOS + RANK_MOMENTUM_FEATURES
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


def load_model_input_with_sos_and_momentum() -> pd.DataFrame:
    joined_feature_columns = set(SOS_MEAN_ONLY + RANK_MOMENTUM_FEATURES)
    base_feature_columns = sorted(
        {
            column
            for feature_columns in FEATURE_SETS.values()
            for column in feature_columns
            if column not in joined_feature_columns
        }
    )

    query = f"""
    SELECT
        mi.historical_match_id,
        mi.match_date,
        mi.home_team_id,
        mi.away_team_id,
        mi.home_team_name,
        mi.away_team_name,
        mi.home_goals,
        mi.away_goals,
        mi.result_label,
        {", ".join("mi." + c for c in base_feature_columns)},

        h_sos.prev5_opp_strength_mean    AS home_prev5_opp_strength_mean,
        a_sos.prev5_opp_strength_mean    AS away_prev5_opp_strength_mean,
        h_sos.prev10_opp_strength_mean   AS home_prev10_opp_strength_mean,
        a_sos.prev10_opp_strength_mean   AS away_prev10_opp_strength_mean,
        h_sos.prev365d_opp_strength_mean AS home_prev365d_opp_strength_mean,
        a_sos.prev365d_opp_strength_mean AS away_prev365d_opp_strength_mean,

        h_mom.rank_improve_1yr AS home_rank_improve_1yr,
        a_mom.rank_improve_1yr AS away_rank_improve_1yr
    FROM features.model_input_mvp_v1 mi
    LEFT JOIN features.team_opponent_strength_before_match h_sos
        ON h_sos.historical_match_id = mi.historical_match_id
       AND h_sos.team_id = mi.home_team_id
    LEFT JOIN features.team_opponent_strength_before_match a_sos
        ON a_sos.historical_match_id = mi.historical_match_id
       AND a_sos.team_id = mi.away_team_id
    LEFT JOIN features.team_rank_momentum_before_match h_mom
        ON h_mom.historical_match_id = mi.historical_match_id
       AND h_mom.team_id = mi.home_team_id
    LEFT JOIN features.team_rank_momentum_before_match a_mom
        ON a_mom.historical_match_id = mi.historical_match_id
       AND a_mom.team_id = mi.away_team_id
    ORDER BY mi.match_date, mi.historical_match_id
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn, parse_dates=["match_date"])


def split_date_bounds(data: pd.DataFrame) -> tuple[date, date]:
    return (
        data["match_date"].min().date(),
        data["match_date"].max().date(),
    )


def build_metric_rows(df: pd.DataFrame) -> tuple[list[dict], int, int]:
    # Fair comparison: both feature sets use exactly the same rows.
    # This means we drop rows missing either Phase-E SOS means or Phase-F momentum.
    complete_row_required_columns = SOS_MEAN_ONLY + RANK_MOMENTUM_FEATURES

    n_before = len(df)
    df = df.dropna(subset=complete_row_required_columns).copy()
    n_after = len(df)
    n_dropped = n_before - n_after

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
                                "complete_rows_after_drop": n_after,
                                "dropped_rows_for_sos_or_momentum": n_dropped,
                                "rank_momentum_max_snapshot_age_days": 240,
                            }
                        ),
                        "notes": (
                            "Phase F fixed-split test for FIFA rank momentum. "
                            "Compares Phase-E qualified attack/defense + SOS mean-only "
                            "against the same set plus home/away rank_improve_1yr. "
                            "All sets restricted to SOS+momentum complete rows. "
                            "Test 2022+ is diagnostic only because FIFA rankings currently "
                            "end at 2024-07-01, reducing holdout momentum coverage."
                        ),
                    }
                )

    return rows, n_dropped, n_after


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


def print_summary() -> None:
    query = text(
        """
        SELECT
            feature_set_name,
            split,
            MAX(n_train_rows) AS n_train_rows,
            MAX(n_eval_rows) AS n_eval_rows,
            ROUND(MAX(metric_value) FILTER (WHERE metric_name = 'home_deviance')::numeric, 4) AS home_dev,
            ROUND(MAX(metric_value) FILTER (WHERE metric_name = 'away_deviance')::numeric, 4) AS away_dev,
            ROUND(MAX(metric_value) FILTER (WHERE metric_name = 'wdl_log_loss')::numeric, 4) AS wdl_log_loss,
            ROUND(MAX(metric_value) FILTER (WHERE metric_name = 'wdl_brier')::numeric, 4) AS wdl_brier
        FROM experiments.model_evaluation_results
        WHERE experiment_run_id = :experiment_run_id
        GROUP BY feature_set_name, split
        ORDER BY split, feature_set_name
        """
    )

    engine = get_engine()
    with engine.connect() as conn:
        summary = pd.read_sql_query(
            query,
            conn,
            params={"experiment_run_id": EXPERIMENT_RUN_ID},
        )

    print(summary.to_string(index=False))


def main() -> None:
    df = load_model_input_with_sos_and_momentum()
    df = add_temporal_split(df)

    rows, n_dropped, n_after = build_metric_rows(df)
    write_rows(rows)

    print(f"Wrote {len(rows)} metric rows for {EXPERIMENT_RUN_ID}")
    print(f"Complete rows after SOS+momentum drop: {n_after}")
    print(f"Dropped rows for SOS or momentum missingness: {n_dropped}")
    print_summary()


if __name__ == "__main__":
    main()
