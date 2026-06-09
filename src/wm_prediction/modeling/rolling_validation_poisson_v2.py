"""
Rolling (anchored / expanding-window) validation for Poisson v2 candidates.

Prints the diagnostic table, then writes metrics to
experiments.model_evaluation_results (idempotent on experiment_run_id).

The final test split (2022+) is deliberately NOT touched here; it stays a clean holdout.
"""
import json

import pandas as pd
from sqlalchemy import text

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.feature_ablation_poisson_mvp import evaluate_split, make_model
from wm_prediction.modeling.experiment_attack_defense_form_v2 import (
    FEATURE_SETS,
    load_attack_defense_model_input,
)

EXPERIMENT_RUN_ID = "rolling_validation_v2_phase_d_2026_06_06"
MODEL_NAME = "sklearn_poisson_regressor_alpha_0p03"
TARGET_NAME = "match_goals_and_wdl"
ALPHA = 0.03

ROLLING_FEATURE_SETS = [
    "current_mvp_all_18",
    "attack_defense_only",
    "attack_defense_plus_mvp_form",
    "attack_defense_plus_points",
]

# Anchored expanding-window splits.
# train: match_date <= train_end ; valid: valid_start <= match_date <= valid_end
# IMPORTANT: valid windows stop at 2021-12-31. 2022+ stays an untouched final holdout.
ROLLING_SPLITS = [
    {
        "split_name": "rolling_train_le_2010_valid_2011_2014",
        "train_end": "2010-12-31",
        "valid_start": "2011-01-01",
        "valid_end": "2014-12-31",
    },
    {
        "split_name": "rolling_train_le_2014_valid_2015_2018",
        "train_end": "2014-12-31",
        "valid_start": "2015-01-01",
        "valid_end": "2018-12-31",
    },
    {
        "split_name": "rolling_train_le_2018_valid_2019_2021",
        "train_end": "2018-12-31",
        "valid_start": "2019-01-01",
        "valid_end": "2021-12-31",
    },
]

METRIC_COLUMNS = [
    "home_deviance",
    "away_deviance",
    "home_mae",
    "away_mae",
    "wdl_log_loss",
    "wdl_brier",
]


def make_fitted_models(train, feature_columns):
    home_model = make_model(feature_columns)
    away_model = make_model(feature_columns)
    home_model.named_steps["model"].set_params(alpha=ALPHA)
    away_model.named_steps["model"].set_params(alpha=ALPHA)
    home_model.fit(train[feature_columns], train["home_goals"])
    away_model.fit(train[feature_columns], train["away_goals"])
    return home_model, away_model


def compute_results(df):
    # NULL guard across all features we will use.
    all_features = sorted({c for name in ROLLING_FEATURE_SETS for c in FEATURE_SETS[name]})
    missing = int(df[all_features].isna().sum().sum())
    if missing:
        raise ValueError(f"Selected features contain {missing} NULL values.")

    results = []
    for split in ROLLING_SPLITS:
        train_end = pd.Timestamp(split["train_end"])
        valid_start = pd.Timestamp(split["valid_start"])
        valid_end = pd.Timestamp(split["valid_end"])

        # Leakage guard: training must end strictly before validation begins.
        assert train_end < valid_start, "train_end must be before valid_start"

        train = df[df["match_date"] <= train_end].copy()
        valid = df[(df["match_date"] >= valid_start) & (df["match_date"] <= valid_end)].copy()

        train_start_date = train["match_date"].min().date()
        train_end_date = train["match_date"].max().date()
        eval_start_date = valid["match_date"].min().date()
        eval_end_date = valid["match_date"].max().date()

        for feature_set_name in ROLLING_FEATURE_SETS:
            feature_columns = FEATURE_SETS[feature_set_name]
            home_model, away_model = make_fitted_models(train, feature_columns)

            metrics = evaluate_split(
                ablation_name=feature_set_name,
                split_name=split["split_name"],
                data=valid,
                feature_columns=feature_columns,
                home_model=home_model,
                away_model=away_model,
            )
            metrics["n_train_rows"] = len(train)
            metrics["n_eval_rows"] = len(valid)
            metrics["train_start_date"] = train_start_date
            metrics["train_end_date"] = train_end_date
            metrics["eval_start_date"] = eval_start_date
            metrics["eval_end_date"] = eval_end_date
            metrics["window"] = split
            results.append(metrics)

    return results


def print_diagnostic(results):
    df = pd.DataFrame(results)
    print("Rolling validation (anchored expanding window), alpha =", ALPHA)
    print()
    display_columns = [
        "split",
        "ablation",
        "n_train_rows",
        "rows",
        "home_deviance",
        "away_deviance",
        "wdl_log_loss",
        "wdl_brier",
    ]
    print(
        df[display_columns]
        .sort_values(["split", "wdl_log_loss", "ablation"])
        .round(4)
        .to_string(index=False)
    )
    print()
    print("Mean across rolling splits per feature set (robustness signal):")
    mean_cols = ["home_deviance", "away_deviance", "wdl_log_loss", "wdl_brier"]
    print(
        df.groupby("ablation")[mean_cols].mean().sort_values("wdl_log_loss").round(4).to_string()
    )


def build_metric_rows(results):
    rows = []
    for r in results:
        feature_columns = FEATURE_SETS[r["ablation"]]
        params = json.dumps(
            {
                "alpha": ALPHA,
                "max_iter": 1000,
                "feature_count": len(feature_columns),
                "features": feature_columns,
                "train_end": r["window"]["train_end"],
                "valid_start": r["window"]["valid_start"],
                "valid_end": r["window"]["valid_end"],
            }
        )
        for metric_name in METRIC_COLUMNS:
            rows.append(
                {
                    "experiment_run_id": EXPERIMENT_RUN_ID,
                    "model_name": MODEL_NAME,
                    "feature_set_name": r["ablation"],
                    "target_name": TARGET_NAME,
                    "split": r["split"],
                    "metric_name": metric_name,
                    "metric_value": float(r[metric_name]),
                    "train_start_date": r["train_start_date"],
                    "train_end_date": r["train_end_date"],
                    "eval_start_date": r["eval_start_date"],
                    "eval_end_date": r["eval_end_date"],
                    "n_train_rows": int(r["n_train_rows"]),
                    "n_eval_rows": int(r["n_eval_rows"]),
                    "params_json": params,
                    "notes": (
                        "Phase D rolling validation. Anchored expanding windows, "
                        "alpha=0.03. 2022+ holdout untouched."
                    ),
                }
            )
    return rows


def write_rows(rows):
    delete_sql = text(
        "DELETE FROM experiments.model_evaluation_results "
        "WHERE experiment_run_id = :experiment_run_id"
    )
    insert_sql = text(
        """
        INSERT INTO experiments.model_evaluation_results (
            experiment_run_id, model_name, feature_set_name, target_name, split,
            metric_name, metric_value, train_start_date, train_end_date,
            eval_start_date, eval_end_date, n_train_rows, n_eval_rows, params_json, notes
        ) VALUES (
            :experiment_run_id, :model_name, :feature_set_name, :target_name, :split,
            :metric_name, :metric_value, :train_start_date, :train_end_date,
            :eval_start_date, :eval_end_date, :n_train_rows, :n_eval_rows,
            CAST(:params_json AS jsonb), :notes
        )
        """
    )
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete_sql, {"experiment_run_id": EXPERIMENT_RUN_ID})
        conn.execute(insert_sql, rows)


def main():
    df = load_attack_defense_model_input()
    results = compute_results(df)
    print_diagnostic(results)

    rows = build_metric_rows(results)
    write_rows(rows)
    print()
    print("Wrote rolling validation rows")
    print("experiment_run_id:", EXPERIMENT_RUN_ID)
    print("rows:", len(rows))


if __name__ == "__main__":
    main()
