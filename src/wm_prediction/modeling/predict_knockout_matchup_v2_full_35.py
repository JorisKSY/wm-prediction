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


def load_training_data() -> pd.DataFrame:
    df = load_v2_candidate_model_input()
    df = add_temporal_split(df)
    df = df.dropna(subset=V2_REQUIRED_JOINED_FEATURES).copy()
    df = df[df["split"] == "train_pre_2018"].copy()

    missing_features = int(df[V2_CANDIDATE_FEATURES].isna().sum().sum())
    if missing_features:
        raise ValueError(f"Training input contains {missing_features} missing feature values.")

    return df


def load_team_snapshot(team_names: list[str]) -> pd.DataFrame:
    query = """
    SELECT *
    FROM features.team_prediction_snapshot_v2_full_35
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
        # v2_full_35 knockout assumption: neutral World Cup match.
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
        "prev10_points_per_match_diff": home["prev10_points_per_match"] - away["prev10_points_per_match"],
        "prev5y_points_per_match_diff": home["prev5y_points_per_match"] - away["prev5y_points_per_match"],

        "home_prev5_goals_for_per_match": home["prev5_goals_for_per_match"],
        "home_prev5_goals_against_per_match": home["prev5_goals_against_per_match"],
        "away_prev5_goals_for_per_match": away["prev5_goals_for_per_match"],
        "away_prev5_goals_against_per_match": away["prev5_goals_against_per_match"],

        "home_prev10_goals_for_per_match": home["prev10_goals_for_per_match"],
        "home_prev10_goals_against_per_match": home["prev10_goals_against_per_match"],
        "away_prev10_goals_for_per_match": away["prev10_goals_for_per_match"],
        "away_prev10_goals_against_per_match": away["prev10_goals_against_per_match"],

        "home_prev5y_goals_for_per_match": home["prev5y_goals_for_per_match"],
        "home_prev5y_goals_against_per_match": home["prev5y_goals_against_per_match"],
        "away_prev5y_goals_for_per_match": away["prev5y_goals_for_per_match"],
        "away_prev5y_goals_against_per_match": away["prev5y_goals_against_per_match"],

        "home_prev5_opp_strength_mean": home["prev5_opp_strength_mean"],
        "away_prev5_opp_strength_mean": away["prev5_opp_strength_mean"],
        "home_prev10_opp_strength_mean": home["prev10_opp_strength_mean"],
        "away_prev10_opp_strength_mean": away["prev10_opp_strength_mean"],
        "home_prev365d_opp_strength_mean": home["prev365d_opp_strength_mean"],
        "away_prev365d_opp_strength_mean": away["prev365d_opp_strength_mean"],

        "home_rank_improve_1yr": home["rank_improve_1yr"],
        "away_rank_improve_1yr": away["rank_improve_1yr"],
    }

    return pd.DataFrame([row], columns=V2_CANDIDATE_FEATURES)


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


class KnockoutMatchupPredictorV2Full35:
    """Reusable knockout predictor for the real v2_full_35 model."""

    def __init__(self, team_names: list[str]) -> None:
        self.train = load_training_data()
        self.snapshot = load_team_snapshot(team_names)

        found_teams = set(self.snapshot["team_name"])
        missing_teams = sorted(set(team_names) - found_teams)
        if missing_teams:
            raise ValueError(f"Missing teams in v2_full_35 prediction snapshot: {missing_teams}")

        self.home_model = make_xgb_best()
        self.away_model = make_xgb_best()

        self.home_model.fit(
            self.train[V2_CANDIDATE_FEATURES],
            self.train["home_goals"],
        )
        self.away_model.fit(
            self.train[V2_CANDIDATE_FEATURES],
            self.train["away_goals"],
        )

        # Perf: O(1) team lookup instead of a full DataFrame scan per predict().
        self._row_by_team = {
            r["team_name"]: r for _, r in self.snapshot.iterrows()
        }
        # Perf: cache lambda pair per ORDERED (home, away) matchup.
        # NOT symmetric: (A,B) != (B,A). Lives across the whole Monte Carlo run
        # when the predictor is constructed once and reused.
        self._lambda_cache: dict[tuple[str, str], tuple[float, float]] = {}

    def predict(self, home_team: str, away_team: str) -> dict:
        if home_team == away_team:
            raise ValueError("home_team and away_team must be different.")

        found_teams = set(self.snapshot["team_name"])
        missing_teams = sorted({home_team, away_team} - found_teams)
        if missing_teams:
            raise ValueError(f"Missing teams in v2_full_35 prediction snapshot: {missing_teams}")

        key = (home_team, away_team)
        cached = self._lambda_cache.get(key)
        if cached is not None:
            lambda_home, lambda_away = cached
        else:
            home = self._row_by_team[home_team]
            away = self._row_by_team[away_team]

            x = make_matchup_features(home, away)

            missing_features = int(x[V2_CANDIDATE_FEATURES].isna().sum().sum())
            if missing_features:
                raise ValueError(f"Matchup features contain {missing_features} missing values.")

            lambda_home = float(
                np.clip(
                    self.home_model.predict(x[V2_CANDIDATE_FEATURES])[0],
                    0.01,
                    20.0,
                )
            )
            lambda_away = float(
                np.clip(
                    self.away_model.predict(x[V2_CANDIDATE_FEATURES])[0],
                    0.01,
                    20.0,
                )
            )
            self._lambda_cache[key] = (lambda_home, lambda_away)

        p_home_win, p_draw, p_away_win = poisson_result_probs(lambda_home, lambda_away)

        # Same knockout assumption as MVP:
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
            "model_name": "xgboost_v2_full_35",
            "feature_set_name": "v2_full_35",
            "is_technical_dry_run": False,
        }


def predict_knockout_matchup(home_team: str, away_team: str) -> dict:
    predictor = KnockoutMatchupPredictorV2Full35([home_team, away_team])
    return predictor.predict(home_team, away_team)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prediction = predict_knockout_matchup(args.home, args.away)

    print("Knockout matchup prediction v2 full 35")
    print("Assumption: draw after 90 minutes split 50/50 for advancement")
    print("Technical dry run: False")
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
