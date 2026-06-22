import json
from datetime import date

import pandas as pd
from sqlalchemy import text

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from xgboost import XGBRegressor

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.feature_ablation_poisson_mvp import evaluate_split
from wm_prediction.modeling.poisson_regressor_mvp import add_temporal_split
from wm_prediction.modeling.v2_candidate_features import (
    V2_CANDIDATE_FEATURES,
    V2_REQUIRED_JOINED_FEATURES,
    load_v2_candidate_model_input,
)


EXPERIMENT_RUN_ID = "model_class_comparison_phase_h_2026_06_07"
FEATURE_SET_NAME = "v2_candidate_35_features"
TARGET_NAME = "match_goals_and_wdl"


METRIC_COLUMNS = [
    "home_deviance",
    "away_deviance",
    "home_mae",
    "away_mae",
    "wdl_log_loss",
    "wdl_brier",
]


def make_poisson_glm():
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "model",
                PoissonRegressor(
                    alpha=0.03,
                    max_iter=1000,
                ),
            ),
        ]
    )


def make_hist_gradient_boosting():
    return HistGradientBoostingRegressor(
        loss="poisson",
        learning_rate=0.05,
        max_iter=300,
        max_leaf_nodes=15,
        min_samples_leaf=30,
        l2_regularization=0.01,
        random_state=42,
    )


def make_xgboost_poisson():
    return XGBRegressor(
        objective="count:poisson",
        eval_metric="poisson-nloglik",
        n_estimators=500,
        learning_rate=0.03,
        max_depth=3,
        min_child_weight=5,
        subsample=0.90,
        colsample_bytree=0.90,
        reg_lambda=1.0,
        reg_alpha=0.0,
        tree_method="hist",
        random_state=42,
        n_jobs=4,
    )


MODEL_SPECS = {
    "poisson_glm_alpha_0p03": {
        "factory": make_poisson_glm,
        "params": {
            "alpha": 0.03,
            "max_iter": 1000,
            "standard_scaler": True,
        },
    },
    "hist_gradient_boosting_poisson_v0": {
        "factory": make_hist_gradient_boosting,
        "params": {
            "loss": "poisson",
            "learning_rate": 0.05,
            "max_iter": 300,
            "max_leaf_nodes": 15,
            "min_samples_leaf": 30,
            "l2_regularization": 0.01,
            "random_state": 42,
        },
    },
    "xgboost_poisson_v0": {
        "factory": make_xgboost_poisson,
        "params": {
            "objective": "count:poisson",
            "eval_metric": "poisson-nloglik",
            "n_estimators": 500,
            "learning_rate": 0.03,
            "max_depth": 3,
            "min_child_weight": 5,
            "subsample": 0.90,
            "colsample_bytree": 0.90,
            "reg_lambda": 1.0,
            "reg_alpha": 0.0,
            "tree_method": "hist",
            "random_state": 42,
            "n_jobs": 4,
        },
    },
}


def split_date_bounds(data: pd.DataFrame) -> tuple[date, date]:
    return (
        data["match_date"].min().date(),
        data["match_date"].max().date(),
    )


def load_complete_data() -> tuple[pd.DataFrame, int]:
    df = load_v2_candidate_model_input()
    df = add_temporal_split(df)

    n_before = len(df)
    df = df.dropna(subset=V2_REQUIRED_JOINED_FEATURES).copy()
    n_dropped = n_before - len(df)

    missing_selected = int(df[V2_CANDIDATE_FEATURES].isna().sum().sum())
    if missing_selected:
        raise ValueError(f"Selected v2 features contain {missing_selected} NULL values.")

    return df, n_dropped


def compute_results(df: pd.DataFrame) -> list[dict]:
    train = df[df["split"] == "train_pre_2018"].copy()
    train_start, train_end = split_date_bounds(train)

    results = []

    for model_name, spec in MODEL_SPECS.items():
        home_model = spec["factory"]()
        away_model = spec["factory"]()

        home_model.fit(train[V2_CANDIDATE_FEATURES], train["home_goals"])
        away_model.fit(train[V2_CANDIDATE_FEATURES], train["away_goals"])

        for split_name, data in df.groupby("split", sort=False):
            eval_start, eval_end = split_date_bounds(data)

            metrics = evaluate_split(
                ablation_name=FEATURE_SET_NAME,
                split_name=split_name,
                data=data,
                feature_columns=V2_CANDIDATE_FEATURES,
                home_model=home_model,
                away_model=away_model,
            )

            metrics["model_name"] = model_name
            metrics["split"] = split_name
            metrics["n_train_rows"] = len(train)
            metrics["n_eval_rows"] = len(data)
            metrics["train_start_date"] = train_start
            metrics["train_end_date"] = train_end
            metrics["eval_start_date"] = eval_start
            metrics["eval_end_date"] = eval_end
            metrics["model_params"] = spec["params"]

            results.append(metrics)

    return results


def print_summary(results: list[dict]) -> None:
    df = pd.DataFrame(results)

    print("Phase H fixed-split model-class comparison")
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
    print("Valid 2018-2021 deltas vs Poisson GLM. Negative = better.")
    valid = df[df["split"] == "valid_2018_2021"].copy()
    baseline = valid.set_index("model_name").loc["poisson_glm_alpha_0p03"]

    for model_name in valid["model_name"].sort_values():
        row = valid.set_index("model_name").loc[model_name]
        if model_name == "poisson_glm_alpha_0p03":
            continue

        print()
        print(model_name)
        for metric in ["home_deviance", "away_deviance", "wdl_log_loss", "wdl_brier"]:
            delta = row[metric] - baseline[metric]
            print(f"  {metric}: {delta:.4f}")


def build_metric_rows(results: list[dict], n_dropped: int) -> list[dict]:
    rows = []

    for r in results:
        params = dict(r["model_params"])
        params.update(
            {
                "feature_count": len(V2_CANDIDATE_FEATURES),
                "features": V2_CANDIDATE_FEATURES,
                "complete_rows_after_drop": int(r["n_train_rows"]),
                "dropped_rows_for_sos_or_momentum": n_dropped,
                "fixed_split": True,
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
                        "Phase H fixed-split model-class comparison on frozen "
                        "v2 candidate feature set. Compares tuned Poisson GLM, "
                        "sklearn HistGradientBoostingRegressor with poisson loss, "
                        "and XGBoost with count:poisson. Test 2022+ is diagnostic "
                        "because rank momentum coverage is reduced by FIFA rankings "
                        "ending at 2024-07-01."
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
    df, n_dropped = load_complete_data()

    print("Loaded complete v2 candidate data")
    print("rows:", len(df))
    print("dropped rows for SOS or momentum:", n_dropped)
    print("split counts:")
    print(df["split"].value_counts().sort_index().to_string())
    print()

    results = compute_results(df)
    print_summary(results)

    rows = build_metric_rows(results, n_dropped)
    write_rows(rows)

    print()
    print("Wrote Phase H fixed-split model comparison rows")
    print("experiment_run_id:", EXPERIMENT_RUN_ID)
    print("rows:", len(rows))


if __name__ == "__main__":
    main()
