"""
Small rolling hyperparameter tuning for Phase H.

Purpose:
The first model-class comparison showed that both HistGradientBoosting and
XGBoost beat the tuned Poisson GLM on rolling validation. This script performs a
small, controlled rolling search so we do not compare a tuned GLM against
arbitrary boosting defaults.

Selection guidance:
- Primary signal for this project: mean goal deviance, because tournament
  simulation samples goals from lambdas.
- WDL log-loss / Brier are guardrails: do not accept a model that wins deviance
  only by hurting WDL calibration materially.
- 2022+ holdout is not touched here.
"""
import json

import pandas as pd
from sqlalchemy import text

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from xgboost import XGBRegressor

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.feature_ablation_poisson_mvp import evaluate_split
from wm_prediction.modeling.model_class_comparison_phase_h_2026_06_07 import (
    FEATURE_SET_NAME,
    TARGET_NAME,
    METRIC_COLUMNS,
    load_complete_data,
)
from wm_prediction.modeling.v2_candidate_features import V2_CANDIDATE_FEATURES


EXPERIMENT_RUN_ID = "tune_boosting_phase_h_2026_06_07"


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


def make_poisson_reference():
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("model", PoissonRegressor(alpha=0.03, max_iter=1000)),
        ]
    )


def make_hist_gb(params):
    return HistGradientBoostingRegressor(
        loss="poisson",
        random_state=42,
        **params,
    )


def make_xgb(params):
    return XGBRegressor(
        objective="count:poisson",
        eval_metric="poisson-nloglik",
        tree_method="hist",
        random_state=42,
        n_jobs=4,
        **params,
    )


CANDIDATES = [
    {
        "model_name": "poisson_glm_alpha_0p03_reference",
        "family": "poisson_glm",
        "factory": lambda: make_poisson_reference(),
        "params": {"alpha": 0.03, "max_iter": 1000, "standard_scaler": True},
    },

    {
        "model_name": "histgb_pois_lr005_iter300_leaf15_min30_l2_001",
        "family": "histgb",
        "factory": lambda: make_hist_gb({
            "learning_rate": 0.05,
            "max_iter": 300,
            "max_leaf_nodes": 15,
            "min_samples_leaf": 30,
            "l2_regularization": 0.01,
        }),
        "params": {
            "learning_rate": 0.05,
            "max_iter": 300,
            "max_leaf_nodes": 15,
            "min_samples_leaf": 30,
            "l2_regularization": 0.01,
        },
    },
    {
        "model_name": "histgb_pois_lr003_iter500_leaf15_min30_l2_001",
        "family": "histgb",
        "factory": lambda: make_hist_gb({
            "learning_rate": 0.03,
            "max_iter": 500,
            "max_leaf_nodes": 15,
            "min_samples_leaf": 30,
            "l2_regularization": 0.01,
        }),
        "params": {
            "learning_rate": 0.03,
            "max_iter": 500,
            "max_leaf_nodes": 15,
            "min_samples_leaf": 30,
            "l2_regularization": 0.01,
        },
    },
    {
        "model_name": "histgb_pois_lr003_iter500_leaf31_min50_l2_01",
        "family": "histgb",
        "factory": lambda: make_hist_gb({
            "learning_rate": 0.03,
            "max_iter": 500,
            "max_leaf_nodes": 31,
            "min_samples_leaf": 50,
            "l2_regularization": 0.1,
        }),
        "params": {
            "learning_rate": 0.03,
            "max_iter": 500,
            "max_leaf_nodes": 31,
            "min_samples_leaf": 50,
            "l2_regularization": 0.1,
        },
    },
    {
        "model_name": "histgb_pois_lr002_iter700_leaf15_min50_l2_01",
        "family": "histgb",
        "factory": lambda: make_hist_gb({
            "learning_rate": 0.02,
            "max_iter": 700,
            "max_leaf_nodes": 15,
            "min_samples_leaf": 50,
            "l2_regularization": 0.1,
        }),
        "params": {
            "learning_rate": 0.02,
            "max_iter": 700,
            "max_leaf_nodes": 15,
            "min_samples_leaf": 50,
            "l2_regularization": 0.1,
        },
    },

    {
        "model_name": "xgb_pois_lr003_n500_d3_child5_sub90_col90_l2_1",
        "family": "xgboost",
        "factory": lambda: make_xgb({
            "n_estimators": 500,
            "learning_rate": 0.03,
            "max_depth": 3,
            "min_child_weight": 5,
            "subsample": 0.90,
            "colsample_bytree": 0.90,
            "reg_lambda": 1.0,
            "reg_alpha": 0.0,
        }),
        "params": {
            "n_estimators": 500,
            "learning_rate": 0.03,
            "max_depth": 3,
            "min_child_weight": 5,
            "subsample": 0.90,
            "colsample_bytree": 0.90,
            "reg_lambda": 1.0,
            "reg_alpha": 0.0,
        },
    },
    {
        "model_name": "xgb_pois_lr002_n800_d3_child5_sub90_col90_l2_2",
        "family": "xgboost",
        "factory": lambda: make_xgb({
            "n_estimators": 800,
            "learning_rate": 0.02,
            "max_depth": 3,
            "min_child_weight": 5,
            "subsample": 0.90,
            "colsample_bytree": 0.90,
            "reg_lambda": 2.0,
            "reg_alpha": 0.0,
        }),
        "params": {
            "n_estimators": 800,
            "learning_rate": 0.02,
            "max_depth": 3,
            "min_child_weight": 5,
            "subsample": 0.90,
            "colsample_bytree": 0.90,
            "reg_lambda": 2.0,
            "reg_alpha": 0.0,
        },
    },
    {
        "model_name": "xgb_pois_lr003_n500_d2_child10_sub90_col90_l2_2",
        "family": "xgboost",
        "factory": lambda: make_xgb({
            "n_estimators": 500,
            "learning_rate": 0.03,
            "max_depth": 2,
            "min_child_weight": 10,
            "subsample": 0.90,
            "colsample_bytree": 0.90,
            "reg_lambda": 2.0,
            "reg_alpha": 0.0,
        }),
        "params": {
            "n_estimators": 500,
            "learning_rate": 0.03,
            "max_depth": 2,
            "min_child_weight": 10,
            "subsample": 0.90,
            "colsample_bytree": 0.90,
            "reg_lambda": 2.0,
            "reg_alpha": 0.0,
        },
    },
    {
        "model_name": "xgb_pois_lr002_n800_d2_child10_sub85_col85_l2_5",
        "family": "xgboost",
        "factory": lambda: make_xgb({
            "n_estimators": 800,
            "learning_rate": 0.02,
            "max_depth": 2,
            "min_child_weight": 10,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "reg_lambda": 5.0,
            "reg_alpha": 0.0,
        }),
        "params": {
            "n_estimators": 800,
            "learning_rate": 0.02,
            "max_depth": 2,
            "min_child_weight": 10,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "reg_lambda": 5.0,
            "reg_alpha": 0.0,
        },
    },
]


def compute_results(df):
    results = []

    for split in ROLLING_SPLITS:
        train_end = pd.Timestamp(split["train_end"])
        valid_start = pd.Timestamp(split["valid_start"])
        valid_end = pd.Timestamp(split["valid_end"])

        train = df[df["match_date"] <= train_end].copy()
        valid = df[
            (df["match_date"] >= valid_start)
            & (df["match_date"] <= valid_end)
        ].copy()

        train_start_date = train["match_date"].min().date()
        train_end_date = train["match_date"].max().date()
        eval_start_date = valid["match_date"].min().date()
        eval_end_date = valid["match_date"].max().date()

        print(f"Window {split['split_name']}: train={len(train)}, valid={len(valid)}")

        for candidate in CANDIDATES:
            print("  fitting", candidate["model_name"])

            home_model = candidate["factory"]()
            away_model = candidate["factory"]()

            home_model.fit(train[V2_CANDIDATE_FEATURES], train["home_goals"])
            away_model.fit(train[V2_CANDIDATE_FEATURES], train["away_goals"])

            metrics = evaluate_split(
                ablation_name=FEATURE_SET_NAME,
                split_name=split["split_name"],
                data=valid,
                feature_columns=V2_CANDIDATE_FEATURES,
                home_model=home_model,
                away_model=away_model,
            )

            metrics["model_name"] = candidate["model_name"]
            metrics["family"] = candidate["family"]
            metrics["split"] = split["split_name"]
            metrics["n_train_rows"] = len(train)
            metrics["n_eval_rows"] = len(valid)
            metrics["train_start_date"] = train_start_date
            metrics["train_end_date"] = train_end_date
            metrics["eval_start_date"] = eval_start_date
            metrics["eval_end_date"] = eval_end_date
            metrics["window"] = split
            metrics["model_params"] = candidate["params"]

            results.append(metrics)

    return results


def print_summary(results):
    df = pd.DataFrame(results)
    df["mean_goal_deviance"] = (df["home_deviance"] + df["away_deviance"]) / 2.0

    print()
    print("Per-window tuning results:")
    display_columns = [
        "split",
        "family",
        "model_name",
        "rows",
        "mean_goal_deviance",
        "home_deviance",
        "away_deviance",
        "wdl_log_loss",
        "wdl_brier",
    ]
    print(
        df[display_columns]
        .sort_values(["split", "mean_goal_deviance", "wdl_log_loss"])
        .round(4)
        .to_string(index=False)
    )

    print()
    print("Mean across rolling splits, sorted by mean_goal_deviance:")
    mean_cols = ["mean_goal_deviance", "home_deviance", "away_deviance", "wdl_log_loss", "wdl_brier"]
    summary = (
        df.groupby(["family", "model_name"])[mean_cols]
        .mean()
        .sort_values(["mean_goal_deviance", "wdl_log_loss"])
        .round(5)
    )
    print(summary.to_string())

    print()
    print("Best per family by mean_goal_deviance:")
    flat = summary.reset_index()
    best = flat.loc[flat.groupby("family")["mean_goal_deviance"].idxmin()]
    print(best.sort_values("mean_goal_deviance").to_string(index=False))


def build_metric_rows(results, n_dropped):
    rows = []

    for r in results:
        params = dict(r["model_params"])
        params.update(
            {
                "family": r["family"],
                "feature_count": len(V2_CANDIDATE_FEATURES),
                "features": V2_CANDIDATE_FEATURES,
                "train_end": r["window"]["train_end"],
                "valid_start": r["window"]["valid_start"],
                "valid_end": r["window"]["valid_end"],
                "dropped_rows_for_sos_or_momentum": n_dropped,
                "rolling_tuning": True,
            }
        )

        for metric_name in METRIC_COLUMNS:
            rows.append(
                {
                    "experiment_run_id": EXPERIMENT_RUN_ID,
                    "model_name": r["model_name"],
                    "feature_set_name": FEATURE_SET_NAME,
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
                    "params_json": json.dumps(params),
                    "notes": (
                        "Phase H small rolling hyperparameter tuning for HistGB and "
                        "XGBoost on frozen v2 candidate features. Includes Poisson GLM "
                        "alpha=0.03 as reference. Selection should prioritize goal "
                        "deviance with WDL metrics as calibration guardrails. 2022+ "
                        "holdout untouched."
                    ),
                }
            )

    return rows


def write_rows(rows):
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


def main():
    df, n_dropped = load_complete_data()

    print("Loaded complete v2 candidate data")
    print("rows:", len(df))
    print("dropped rows for SOS or momentum:", n_dropped)
    print("candidates:", len(CANDIDATES))
    print()

    results = compute_results(df)
    print_summary(results)

    rows = build_metric_rows(results, n_dropped)
    write_rows(rows)

    print()
    print("Wrote Phase H boosting tuning rows")
    print("experiment_run_id:", EXPERIMENT_RUN_ID)
    print("rows:", len(rows))


if __name__ == "__main__":
    main()
