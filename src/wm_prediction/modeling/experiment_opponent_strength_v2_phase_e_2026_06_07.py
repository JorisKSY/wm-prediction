import json
from datetime import date

import pandas as pd
from sqlalchemy import text

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.feature_ablation_poisson_mvp import evaluate_split, make_model
from wm_prediction.modeling.poisson_regressor_mvp import add_temporal_split

# Reuse the EXACT feature-set definitions from Phase C so the baselines here are
# identical to what was measured there. Importing (not copying) prevents a silent
# divergence that would invalidate the comparison.
from wm_prediction.modeling.experiment_attack_defense_form_v2 import (
    BASE_CONTEXT_FEATURES,
    FIFA_FEATURES,
    MVP_FORM_FEATURES,
    ATTACK_DEFENSE_FORM_FEATURES,
    POINTS_FORM_FEATURES,
)


EXPERIMENT_RUN_ID = "poisson_opponent_strength_v2_phase_e_2026_06_07"
MODEL_NAME = "sklearn_poisson_regressor_alpha_0p03"
ALPHA = 0.03


# New Phase E block: opponent-adjusted form (strength-of-schedule).
# These live in features.team_opponent_strength_before_match (team-level) and are
# joined to the match-level model input as home_*/away_* below. mean = avg opponent
# rank percentile faced; coverage = share of window matches that had a rank.
SOS_FEATURES = [
    "home_prev5_opp_strength_mean",
    "home_prev5_opp_strength_coverage",
    "away_prev5_opp_strength_mean",
    "away_prev5_opp_strength_coverage",

    "home_prev10_opp_strength_mean",
    "home_prev10_opp_strength_coverage",
    "away_prev10_opp_strength_mean",
    "away_prev10_opp_strength_coverage",

    "home_prev365d_opp_strength_mean",
    "home_prev365d_opp_strength_coverage",
    "away_prev365d_opp_strength_mean",
    "away_prev365d_opp_strength_coverage",
]
# Mean-only SOS: drops the coverage columns. Coverage correlates with calendar
# year (early years = sparse rankings), so it risks acting as a time proxy under
# a time-based split. If the gain survives WITHOUT coverage, it's real strength
# signal; if it largely vanishes, the gain was a coverage/time confound.
SOS_MEAN_ONLY = [c for c in SOS_FEATURES if c.endswith("_mean")]


CURRENT_MVP_ALL_18 = (
    BASE_CONTEXT_FEATURES
    + FIFA_FEATURES
    + MVP_FORM_FEATURES
)

ATTACK_DEFENSE_PLUS_POINTS = (
    BASE_CONTEXT_FEATURES
    + FIFA_FEATURES
    + POINTS_FORM_FEATURES
    + ATTACK_DEFENSE_FORM_FEATURES
)


FEATURE_SETS = {
    "current_mvp_all_18": CURRENT_MVP_ALL_18,
    "current_mvp_all_18_plus_sos": CURRENT_MVP_ALL_18 + SOS_FEATURES,
    "current_mvp_all_18_plus_sos_mean_only": CURRENT_MVP_ALL_18 + SOS_MEAN_ONLY,
    "attack_defense_plus_points": ATTACK_DEFENSE_PLUS_POINTS,
    "attack_defense_plus_points_plus_sos": ATTACK_DEFENSE_PLUS_POINTS + SOS_FEATURES,
    "attack_defense_plus_points_plus_sos_mean_only": ATTACK_DEFENSE_PLUS_POINTS + SOS_MEAN_ONLY,
}


METRIC_COLUMNS = [
    "home_deviance",
    "away_deviance",
    "home_mae",
    "away_mae",
    "wdl_log_loss",
    "wdl_brier",
]


def load_model_input_with_sos() -> pd.DataFrame:
    # Columns needed from model_input_mvp_v1: everything referenced by any feature
    # set EXCEPT the SOS columns (those come from the join), plus the keys/targets.
    base_feature_columns = sorted(
        {
            column
            for feature_columns in FEATURE_SETS.values()
            for column in feature_columns
            if column not in SOS_FEATURES
        }
    )

    query = f"""
    SELECT
        mi.historical_match_id,
        mi.match_date,
        mi.home_team_name,
        mi.away_team_name,
        mi.home_goals,
        mi.away_goals,
        mi.result_label,
        {", ".join("mi." + c for c in base_feature_columns)},

        h.prev5_opp_strength_mean       AS home_prev5_opp_strength_mean,
        h.prev5_opp_strength_coverage   AS home_prev5_opp_strength_coverage,
        a.prev5_opp_strength_mean       AS away_prev5_opp_strength_mean,
        a.prev5_opp_strength_coverage   AS away_prev5_opp_strength_coverage,

        h.prev10_opp_strength_mean      AS home_prev10_opp_strength_mean,
        h.prev10_opp_strength_coverage  AS home_prev10_opp_strength_coverage,
        a.prev10_opp_strength_mean      AS away_prev10_opp_strength_mean,
        a.prev10_opp_strength_coverage  AS away_prev10_opp_strength_coverage,

        h.prev365d_opp_strength_mean      AS home_prev365d_opp_strength_mean,
        h.prev365d_opp_strength_coverage  AS home_prev365d_opp_strength_coverage,
        a.prev365d_opp_strength_mean      AS away_prev365d_opp_strength_mean,
        a.prev365d_opp_strength_coverage  AS away_prev365d_opp_strength_coverage
    FROM features.model_input_mvp_v1 mi
    LEFT JOIN features.team_opponent_strength_before_match h
        ON h.historical_match_id = mi.historical_match_id
       AND h.team_id = mi.home_team_id
    LEFT JOIN features.team_opponent_strength_before_match a
        ON a.historical_match_id = mi.historical_match_id
       AND a.team_id = mi.away_team_id
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


def build_metric_rows(df: pd.DataFrame) -> tuple[list[dict], int]:
    # Option B: restrict ALL feature sets to the same SOS-complete row set so the
    # comparison is fair (identical rows for every set). Drop any match with a NULL
    # in any SOS column.
    n_before = len(df)
    df = df.dropna(subset=SOS_FEATURES).copy()
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
                                "option_b_sos_complete_rows": n_after,
                                "option_b_dropped_rows": n_dropped,
                            }
                        ),
                        "notes": (
                            "Phase E opponent-adjusted form (SOS). Adds avg opponent "
                            "rank percentile faced over prev5/prev10/prev365d windows. "
                            "All sets restricted to SOS-complete rows (Option B), so "
                            "row count differs slightly from Phase B/C/D runs."
                        ),
                    }
                )

    return rows, n_dropped


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
    df = add_temporal_split(load_model_input_with_sos())
    rows, n_dropped = build_metric_rows(df)
    write_rows(rows)

    print("Wrote opponent-strength (SOS) Phase E experiment rows")
    print("experiment_run_id:", EXPERIMENT_RUN_ID)
    print("rows:", len(rows))
    print("Option B dropped rows (NULL SOS):", n_dropped)


if __name__ == "__main__":
    main()
