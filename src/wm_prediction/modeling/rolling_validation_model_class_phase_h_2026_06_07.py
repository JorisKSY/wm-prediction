"""
Rolling validation for Phase H model-class comparison.

Compares the frozen v2 candidate feature set across:
  - tuned Poisson GLM alpha=0.03
  - sklearn HistGradientBoostingRegressor(loss="poisson")
  - XGBoost count:poisson

The fixed split showed only modest non-linear gains and some train overfit,
so this rolling check is required before choosing a model class.
The 2022+ holdout is deliberately NOT touched here.
"""
import json

import pandas as pd
from sqlalchemy import text

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.feature_ablation_poisson_mvp import evaluate_split
from wm_prediction.modeling.model_class_comparison_phase_h_2026_06_07 import (
    MODEL_SPECS,
    FEATURE_SET_NAME,
    TARGET_NAME,
    METRIC_COLUMNS,
    load_complete_data,
)
from wm_prediction.modeling.v2_candidate_features import V2_CANDIDATE_FEATURES


EXPERIMENT_RUN_ID = "rolling_validation_v2_full_35_fresh_fifa_2026_06_09"


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


def compute_results(df: pd.DataFrame) -> list[dict]:
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

        for model_name, spec in MODEL_SPECS.items():
            home_model = spec["factory"]()
            away_model = spec["factory"]()

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

            metrics["model_name"] = model_name
            metrics["split"] = split["split_name"]
            metrics["n_train_rows"] = len(train)
            metrics["n_eval_rows"] = len(valid)
            metrics["train_start_date"] = train_start_date
            metrics["train_end_date"] = train_end_date
            metrics["eval_start_date"] = eval_start_date
            metrics["eval_end_date"] = eval_end_date
            metrics["window"] = split
            metrics["model_params"] = spec["params"]

            results.append(metrics)

    return results


def print_summary(results: list[dict]) -> None:
    df = pd.DataFrame(results)

    print("Phase H rolling model-class comparison")
    print("Feature set:", FEATURE_SET_NAME)
    print("Feature count:", len(V2_CANDIDATE_FEATURES))
    print()

    display_columns = [
        "split",
        "model_name",
        "n_train_rows",
        "rows",
        "home_deviance",
        "away_deviance",
        "wdl_log_loss",
        "wdl_brier",
    ]

    print(
        df[display_columns]
        .sort_values(["split", "wdl_log_loss", "model_name"])
        .round(4)
        .to_string(index=False)
    )

    print()
    print("Deltas vs Poisson GLM per rolling split. Negative = better.")
    baseline_model = "poisson_glm_alpha_0p03"

    for split_name in [s["split_name"] for s in ROLLING_SPLITS]:
        print()
        print(split_name)
        one = df[df["split"] == split_name].set_index("model_name")
        baseline = one.loc[baseline_model]

        for model_name in sorted(one.index):
            if model_name == baseline_model:
                continue

            print(" ", model_name)
            for metric in ["home_deviance", "away_deviance", "wdl_log_loss", "wdl_brier"]:
                delta = one.loc[model_name, metric] - baseline[metric]
                print(f"    {metric}: {delta:.4f}")

    print()
    print("Mean across rolling splits:")
    mean_cols = ["home_deviance", "away_deviance", "wdl_log_loss", "wdl_brier"]
    print(
        df.groupby("model_name")[mean_cols]
        .mean()
        .sort_values("wdl_log_loss")
        .round(4)
        .to_string()
    )


def build_metric_rows(results: list[dict], n_dropped: int) -> list[dict]:
    rows = []

    for r in results:
        params = dict(r["model_params"])
        params.update(
            {
                "feature_count": len(V2_CANDIDATE_FEATURES),
                "features": V2_CANDIDATE_FEATURES,
                "train_end": r["window"]["train_end"],
                "valid_start": r["window"]["valid_start"],
                "valid_end": r["window"]["valid_end"],
                "dropped_rows_for_sos_or_momentum": n_dropped,
                "rolling_validation": True,
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
                        "Phase H rolling validation for model-class comparison on frozen "
                        "v2 candidate feature set. Compares tuned Poisson GLM, sklearn "
                        "HistGradientBoostingRegressor poisson loss, and XGBoost count:poisson. "
                        "2022+ holdout untouched."
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


def report_window_rows(df: pd.DataFrame) -> None:
    print("Rolling row counts on complete v2 candidate rows:")
    for split in ROLLING_SPLITS:
        train_end = pd.Timestamp(split["train_end"])
        valid_start = pd.Timestamp(split["valid_start"])
        valid_end = pd.Timestamp(split["valid_end"])

        n_train = int((df["match_date"] <= train_end).sum())
        n_valid = int(
            ((df["match_date"] >= valid_start) & (df["match_date"] <= valid_end)).sum()
        )

        print(
            f"  {split['split_name']}: train={n_train}, valid={n_valid}"
        )
    print()


def main() -> None:
    df, n_dropped = load_complete_data()

    print("Loaded complete v2 candidate data")
    print("rows:", len(df))
    print("dropped rows for SOS or momentum:", n_dropped)
    print()

    report_window_rows(df)

    results = compute_results(df)
    print_summary(results)

    rows = build_metric_rows(results, n_dropped)
    write_rows(rows)

    print()
    print("Wrote Phase H rolling model comparison rows")
    print("experiment_run_id:", EXPERIMENT_RUN_ID)
    print("rows:", len(rows))


if __name__ == "__main__":
    main()
