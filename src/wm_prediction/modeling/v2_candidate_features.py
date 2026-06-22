import pandas as pd
from sqlalchemy import text

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.experiment_attack_defense_form_v2 import (
    BASE_CONTEXT_FEATURES,
    FIFA_FEATURES,
    POINTS_FORM_FEATURES,
    ATTACK_DEFENSE_FORM_FEATURES,
)


SOS_MEAN_ONLY = [
    "home_prev5_opp_strength_mean",
    "away_prev5_opp_strength_mean",
    "home_prev10_opp_strength_mean",
    "away_prev10_opp_strength_mean",
    "home_prev365d_opp_strength_mean",
    "away_prev365d_opp_strength_mean",
]


RANK_MOMENTUM_FEATURES = [
    "home_rank_improve_1yr",
    "away_rank_improve_1yr",
]


V2_CANDIDATE_FEATURES = (
    BASE_CONTEXT_FEATURES
    + FIFA_FEATURES
    + POINTS_FORM_FEATURES
    + ATTACK_DEFENSE_FORM_FEATURES
    + SOS_MEAN_ONLY
    + RANK_MOMENTUM_FEATURES
)


V2_REQUIRED_JOINED_FEATURES = SOS_MEAN_ONLY + RANK_MOMENTUM_FEATURES


def load_v2_candidate_model_input() -> pd.DataFrame:
    joined_feature_columns = set(V2_REQUIRED_JOINED_FEATURES)
    base_feature_columns = sorted(
        c for c in V2_CANDIDATE_FEATURES
        if c not in joined_feature_columns
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

# Technical Phase-J dry-run feature set:
# Same as the 35-feature v2 candidate, but WITHOUT rank momentum because the
# required 2025 FIFA ranking snapshot is currently missing for WM-2026 prediction.
#
# This is NOT the final production v2 feature set. Once the missing 2025 rankings
# are available, use V2_CANDIDATE_FEATURES with all 35 features again.
V2_TECHNICAL_33_NO_MOMENTUM_FEATURES = (
    BASE_CONTEXT_FEATURES
    + FIFA_FEATURES
    + POINTS_FORM_FEATURES
    + ATTACK_DEFENSE_FORM_FEATURES
    + SOS_MEAN_ONLY
)

V2_TECHNICAL_33_REQUIRED_JOINED_FEATURES = SOS_MEAN_ONLY
