import argparse

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sqlalchemy import text

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.poisson_regressor_mvp import FEATURE_COLUMNS, make_model


MAX_GOALS = 20


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


def load_team_snapshot(team_names: list[str]) -> pd.DataFrame:
    query = """
    SELECT *
    FROM features.team_prediction_snapshot_mvp_v1
    WHERE team_name = ANY(:team_names)
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(
            text(query),
            conn,
            params={"team_names": team_names},
        )


def make_matchup_features(home: pd.Series, away: pd.Series) -> pd.DataFrame:
    row = {
        # MVP assumption for knockout: neutral World Cup match.
        "is_neutral": 1,
        "is_friendly": 0,
        "is_world_cup": 1,
        "is_world_cup_qualifier": 0,
        "is_major_continental_tournament": 0,
        "is_continental_qualifier": 0,
        "is_nations_league": 0,
        "home_fifa_rank": home["fifa_rank"],
        "away_fifa_rank": away["fifa_rank"],
        "home_fifa_ranking_age_days": home["fifa_ranking_age_days"],
        "away_fifa_ranking_age_days": away["fifa_ranking_age_days"],
        "fifa_rank_diff_home_minus_away": home["fifa_rank"] - away["fifa_rank"],
        "prev5_points_per_match_diff": home["prev5_points_per_match"] - away["prev5_points_per_match"],
        "prev5_goal_diff_per_match_diff": home["prev5_goal_diff_per_match"] - away["prev5_goal_diff_per_match"],
        "prev10_points_per_match_diff": home["prev10_points_per_match"] - away["prev10_points_per_match"],
        "prev10_goal_diff_per_match_diff": home["prev10_goal_diff_per_match"] - away["prev10_goal_diff_per_match"],
        "prev5y_points_per_match_diff": home["prev5y_points_per_match"] - away["prev5y_points_per_match"],
        "prev5y_goal_diff_per_match_diff": home["prev5y_goal_diff_per_match"] - away["prev5y_goal_diff_per_match"],
    }

    return pd.DataFrame([row], columns=FEATURE_COLUMNS)


def poisson_result_probs(lambda_home: float, lambda_away: float) -> tuple[float, float, float]:
    goals = np.arange(MAX_GOALS + 1)
    score_matrix = np.outer(
        poisson.pmf(goals, lambda_home),
        poisson.pmf(goals, lambda_away),
    )

    p_home = np.tril(score_matrix, k=-1).sum()
    p_draw = np.trace(score_matrix)
    p_away = np.triu(score_matrix, k=1).sum()

    probs = np.array([p_home, p_draw, p_away], dtype=float)
    probs = probs / probs.sum()

    return tuple(float(x) for x in probs)


class KnockoutMatchupPredictor:
    """Reusable knockout predictor.

    This loads data and fits the two Poisson models once, then can score many
    knockout matchups without repeated DB reads and repeated model fitting.
    """

    def __init__(self, team_names: list[str]) -> None:
        self.train = load_training_data()
        self.snapshot = load_team_snapshot(team_names)

        found_teams = set(self.snapshot["team_name"])
        missing_teams = sorted(set(team_names) - found_teams)
        if missing_teams:
            raise ValueError(f"Missing teams in prediction snapshot: {missing_teams}")

        self.home_model = make_model()
        self.away_model = make_model()

        self.home_model.fit(self.train[FEATURE_COLUMNS], self.train["home_goals"])
        self.away_model.fit(self.train[FEATURE_COLUMNS], self.train["away_goals"])

    def predict(self, home_team: str, away_team: str) -> dict:
        if home_team == away_team:
            raise ValueError("home_team and away_team must be different.")

        found_teams = set(self.snapshot["team_name"])
        missing_teams = sorted({home_team, away_team} - found_teams)
        if missing_teams:
            raise ValueError(f"Missing teams in prediction snapshot: {missing_teams}")

        home = self.snapshot[self.snapshot["team_name"] == home_team].iloc[0]
        away = self.snapshot[self.snapshot["team_name"] == away_team].iloc[0]

        x = make_matchup_features(home, away)

        missing_features = int(x[FEATURE_COLUMNS].isna().sum().sum())
        if missing_features:
            raise ValueError(f"Matchup features contain {missing_features} missing values.")

        lambda_home = float(np.clip(self.home_model.predict(x)[0], 0.01, 20.0))
        lambda_away = float(np.clip(self.away_model.predict(x)[0], 0.01, 20.0))

        p_home_win, p_draw, p_away_win = poisson_result_probs(lambda_home, lambda_away)

        # MVP knockout assumption:
        # Draw after 90 minutes is split 50/50 across extra time + penalties.
        p_home_advance = p_home_win + 0.5 * p_draw
        p_away_advance = p_away_win + 0.5 * p_draw

        return {
            "home_team": home_team,
            "away_team": away_team,
            "lambda_home": lambda_home,
            "lambda_away": lambda_away,
            "p_home_win_90": p_home_win,
            "p_draw_90": p_draw,
            "p_away_win_90": p_away_win,
            "p_home_advance": p_home_advance,
            "p_away_advance": p_away_advance,
        }


def predict_knockout_matchup(home_team: str, away_team: str) -> dict:
    predictor = KnockoutMatchupPredictor([home_team, away_team])
    return predictor.predict(home_team, away_team)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prediction = predict_knockout_matchup(args.home, args.away)

    print("Knockout matchup prediction MVP")
    print("Assumption: draw after 90 minutes split 50/50 for advancement")
    print()

    for key, value in prediction.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")

    print()
    print(
        "advance_prob_sum:",
        f"{prediction['p_home_advance'] + prediction['p_away_advance']:.8f}",
    )


if __name__ == "__main__":
    main()
