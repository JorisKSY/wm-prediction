import argparse

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sqlalchemy import text

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.final_model_candidates_phase_h_2026_06_07 import make_xgb_best
from wm_prediction.modeling.poisson_regressor_mvp import add_temporal_split
from wm_prediction.modeling.v2_candidate_features import (
    V2_CANDIDATE_FEATURES,
    V2_REQUIRED_JOINED_FEATURES,
    load_v2_candidate_model_input,
)


MAX_GOALS = 20
MODEL_NAME = "xgboost_v2_full_35"
FEATURE_SET_NAME = "v2_full_35"
TRAINED_UNTIL = "2017-12-31"


def load_training_data() -> pd.DataFrame:
    df = load_v2_candidate_model_input()
    df = add_temporal_split(df)

    df = df.dropna(subset=V2_REQUIRED_JOINED_FEATURES).copy()
    df = df[df["split"] == "train_pre_2018"].copy()

    missing_features = int(df[V2_CANDIDATE_FEATURES].isna().sum().sum())
    if missing_features:
        raise ValueError(f"Training input contains {missing_features} missing feature values.")

    return df


def load_prediction_input() -> pd.DataFrame:
    query = """
    SELECT *
    FROM features.match_prediction_v2_full_35
    ORDER BY match_date, historical_match_id
    """

    engine = get_engine()
    with engine.connect() as conn:
        pred = pd.read_sql_query(text(query), conn, parse_dates=["match_date"])

    missing_columns = [
        c for c in V2_CANDIDATE_FEATURES
        if c not in pred.columns
    ]
    if missing_columns:
        raise ValueError(f"Prediction input is missing columns: {missing_columns}")

    missing_features = int(pred[V2_CANDIDATE_FEATURES].isna().sum().sum())
    if missing_features:
        raise ValueError(f"Prediction input contains {missing_features} missing feature values.")

    return pred


def poisson_result_probs_home_draw_away(
    lambda_home: np.ndarray,
    lambda_away: np.ndarray,
) -> np.ndarray:
    goals = np.arange(MAX_GOALS + 1)
    rows = []

    for lh, la in zip(lambda_home, lambda_away):
        home_pmf = poisson.pmf(goals, lh)
        away_pmf = poisson.pmf(goals, la)
        score_matrix = np.outer(home_pmf, away_pmf)

        p_home = np.tril(score_matrix, k=-1).sum()
        p_draw = np.trace(score_matrix)
        p_away = np.triu(score_matrix, k=1).sum()

        probs = np.array([p_home, p_draw, p_away], dtype=float)
        rows.append(probs / probs.sum())

    return np.vstack(rows)


def predict_fixtures(train: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    home_model = make_xgb_best()
    away_model = make_xgb_best()

    home_model.fit(
        train[V2_CANDIDATE_FEATURES],
        train["home_goals"],
    )
    away_model.fit(
        train[V2_CANDIDATE_FEATURES],
        train["away_goals"],
    )

    out = pred[
        [
            "historical_match_id",
            "match_date",
            "home_team_id",
            "away_team_id",
            "home_team_name",
            "away_team_name",
        ]
    ].copy()

    out["lambda_home"] = np.clip(
        home_model.predict(pred[V2_CANDIDATE_FEATURES]),
        0.01,
        20.0,
    )
    out["lambda_away"] = np.clip(
        away_model.predict(pred[V2_CANDIDATE_FEATURES]),
        0.01,
        20.0,
    )

    probs = poisson_result_probs_home_draw_away(
        out["lambda_home"].to_numpy(),
        out["lambda_away"].to_numpy(),
    )

    out["p_home_win"] = probs[:, 0]
    out["p_draw"] = probs[:, 1]
    out["p_away_win"] = probs[:, 2]

    out["model_name"] = MODEL_NAME
    out["feature_set_name"] = FEATURE_SET_NAME
    out["trained_until"] = pd.Timestamp(TRAINED_UNTIL).date()
    out["is_technical_dry_run"] = False
    out["dry_run_reason"] = None

    return out


def write_predictions_to_db(predictions: pd.DataFrame) -> None:
    output = predictions.copy()
    output["created_at"] = pd.Timestamp.utcnow()

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS features.match_predictions_v2_full_35"))

    output.to_sql(
        name="match_predictions_v2_full_35",
        con=engine,
        schema="features",
        if_exists="replace",
        index=False,
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_match_predictions_v2_full_35_match_id
                    ON features.match_predictions_v2_full_35 (historical_match_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_match_predictions_v2_full_35_match_date
                    ON features.match_predictions_v2_full_35 (match_date)
                """
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write-db",
        action="store_true",
        help="Write predictions to features.match_predictions_v2_full_35.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    train = load_training_data()
    pred = load_prediction_input()

    predictions = predict_fixtures(train=train, pred=pred)

    if args.write_db:
        write_predictions_to_db(predictions)

    print("World Cup fixture predictions v2 full 35")
    print("Model:", MODEL_NAME)
    print("Feature set:", FEATURE_SET_NAME)
    print("Training split: train_pre_2018")
    print("Training rows:", len(train))
    print("Prediction rows:", len(predictions))
    print("Technical dry run:", False)
    print()

    display_columns = [
        "match_date",
        "home_team_name",
        "away_team_name",
        "lambda_home",
        "lambda_away",
        "p_home_win",
        "p_draw",
        "p_away_win",
    ]

    display = predictions[display_columns].copy()
    numeric_columns = [
        "lambda_home",
        "lambda_away",
        "p_home_win",
        "p_draw",
        "p_away_win",
    ]
    display[numeric_columns] = display[numeric_columns].round(4)

    print(display.to_string(index=False))

    print()
    print("Probability sum min/max:")
    prob_sum = predictions["p_home_win"] + predictions["p_draw"] + predictions["p_away_win"]
    print(prob_sum.agg(["min", "max"]).round(8).to_string())

    print()
    print("Lambda summary:")
    print(
        predictions[["lambda_home", "lambda_away"]]
        .agg(["min", "mean", "median", "max"])
        .round(4)
        .to_string()
    )


if __name__ == "__main__":
    main()
