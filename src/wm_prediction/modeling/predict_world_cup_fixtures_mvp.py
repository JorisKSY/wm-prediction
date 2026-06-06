import argparse

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sqlalchemy import text

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.poisson_regressor_mvp import FEATURE_COLUMNS, make_model


MAX_GOALS = 20
MODEL_NAME = "poisson_regressor_mvp_v1"
TRAINED_UNTIL = "2017-12-31"


def load_training_data() -> pd.DataFrame:
    query = f"""
    SELECT
        match_date,
        home_goals,
        away_goals,
        {", ".join(FEATURE_COLUMNS)}
    FROM features.model_input_mvp_v1
    WHERE match_date < DATE '2018-01-01'
    ORDER BY match_date, historical_match_id
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn, parse_dates=["match_date"])


def load_prediction_input() -> pd.DataFrame:
    query = f"""
    SELECT
        historical_match_id,
        match_date,
        home_team_name,
        away_team_name,
        {", ".join(FEATURE_COLUMNS)}
    FROM features.match_prediction_mvp_v1
    ORDER BY match_date, historical_match_id
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn, parse_dates=["match_date"])


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
    missing_features = int(pred[FEATURE_COLUMNS].isna().sum().sum())
    if missing_features:
        raise ValueError(f"Prediction input contains {missing_features} missing feature values.")

    home_model = make_model()
    away_model = make_model()

    home_model.fit(train[FEATURE_COLUMNS], train["home_goals"])
    away_model.fit(train[FEATURE_COLUMNS], train["away_goals"])

    out = pred[
        [
            "historical_match_id",
            "match_date",
            "home_team_name",
            "away_team_name",
        ]
    ].copy()

    out["lambda_home"] = np.clip(home_model.predict(pred[FEATURE_COLUMNS]), 0.01, 20.0)
    out["lambda_away"] = np.clip(away_model.predict(pred[FEATURE_COLUMNS]), 0.01, 20.0)

    probs = poisson_result_probs_home_draw_away(
        out["lambda_home"].to_numpy(),
        out["lambda_away"].to_numpy(),
    )

    out["p_home_win"] = probs[:, 0]
    out["p_draw"] = probs[:, 1]
    out["p_away_win"] = probs[:, 2]

    out["model_name"] = MODEL_NAME
    out["trained_until"] = pd.Timestamp(TRAINED_UNTIL).date()

    return out


def write_predictions_to_db(predictions: pd.DataFrame) -> None:
    output = predictions.copy()
    output["created_at"] = pd.Timestamp.utcnow()

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS features.match_predictions_mvp_v1"))

    output.to_sql(
        name="match_predictions_mvp_v1",
        con=engine,
        schema="features",
        if_exists="replace",
        index=False,
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_match_predictions_mvp_v1_match_id
                    ON features.match_predictions_mvp_v1 (historical_match_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_match_predictions_mvp_v1_match_date
                    ON features.match_predictions_mvp_v1 (match_date)
                """
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write-db",
        action="store_true",
        help="Write predictions to features.match_predictions_mvp_v1.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    train = load_training_data()
    pred = load_prediction_input()

    predictions = predict_fixtures(train=train, pred=pred)

    if args.write_db:
        write_predictions_to_db(predictions)

    print("World Cup fixture predictions MVP")
    print("Training split: match_date < 2018-01-01")
    print("Prediction rows:", len(predictions))
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


if __name__ == "__main__":
    main()
