-- 11_features_model_input_mvp_v1.sql
-- Model-ready MVP v1 input table.
--
-- Purpose:
-- Provide a deliberately small, leakage-safe, null-free training input for
-- the first two-stage model.
--
-- Scope:
-- - played matches only
-- - FIFA era only via match_feature_coverage.is_model_candidate_basic
-- - team form before match
-- - historical FIFA rank before match
-- - basic match context
--
-- Note:
-- FIFA total_points are intentionally excluded from MVP v1 because the points
-- scale changes substantially across historical FIFA ranking systems.
--
-- Outputs:
-- - features.model_input_mvp_v1

CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.model_input_mvp_v1;

CREATE TABLE features.model_input_mvp_v1 AS
SELECT
    m.historical_match_id,
    m.match_date,

    m.home_team_id,
    m.away_team_id,
    m.home_team_name,
    m.away_team_name,

    -- Targets for Stage 1.
    m.home_goals,
    m.away_goals,

    -- Result label for Stage 2 evaluation.
    m.result_label,

    -- Context features.
    m.is_neutral::integer AS is_neutral,
    m.is_friendly::integer AS is_friendly,
    m.is_world_cup::integer AS is_world_cup,
    m.is_world_cup_qualifier::integer AS is_world_cup_qualifier,
    m.is_major_continental_tournament::integer AS is_major_continental_tournament,
    m.is_continental_qualifier::integer AS is_continental_qualifier,
    m.is_nations_league::integer AS is_nations_league,
    m.match_year,
    m.match_month,
    m.tournament_bucket,

    -- Home form features.
    m.home_prev5_points_per_match,
    m.home_prev5_win_rate,
    m.home_prev5_goals_for_per_match,
    m.home_prev5_goals_against_per_match,
    m.home_prev5_goal_diff_per_match,

    m.home_prev10_points_per_match,
    m.home_prev10_win_rate,
    m.home_prev10_goals_for_per_match,
    m.home_prev10_goals_against_per_match,
    m.home_prev10_goal_diff_per_match,

    m.home_prev5y_points_per_match,
    m.home_prev5y_win_rate,
    m.home_prev5y_goals_for_per_match,
    m.home_prev5y_goals_against_per_match,
    m.home_prev5y_goal_diff_per_match,

    -- Away form features.
    m.away_prev5_points_per_match,
    m.away_prev5_win_rate,
    m.away_prev5_goals_for_per_match,
    m.away_prev5_goals_against_per_match,
    m.away_prev5_goal_diff_per_match,

    m.away_prev10_points_per_match,
    m.away_prev10_win_rate,
    m.away_prev10_goals_for_per_match,
    m.away_prev10_goals_against_per_match,
    m.away_prev10_goal_diff_per_match,

    m.away_prev5y_points_per_match,
    m.away_prev5y_win_rate,
    m.away_prev5y_goals_for_per_match,
    m.away_prev5y_goals_against_per_match,
    m.away_prev5y_goal_diff_per_match,

    -- Relative form features.
    m.prev5_points_per_match_diff,
    m.prev5_goal_diff_per_match_diff,
    m.prev10_points_per_match_diff,
    m.prev10_goal_diff_per_match_diff,
    m.prev5y_points_per_match_diff,
    m.prev5y_goal_diff_per_match_diff,

    -- FIFA features.
    m.home_fifa_rank,
    m.away_fifa_rank,
    m.home_fifa_ranking_age_days,
    m.away_fifa_ranking_age_days,

    -- Relative FIFA features. Lower rank is better.
    m.fifa_rank_diff_home_minus_away,

    now() AS created_at
FROM features.match_features_training m
JOIN features.match_feature_coverage c
    ON c.historical_match_id = m.historical_match_id
WHERE c.is_model_candidate_basic;

CREATE UNIQUE INDEX IF NOT EXISTS ux_model_input_mvp_v1_match
    ON features.model_input_mvp_v1 (historical_match_id);

CREATE INDEX IF NOT EXISTS idx_model_input_mvp_v1_date
    ON features.model_input_mvp_v1 (match_date);

CREATE INDEX IF NOT EXISTS idx_model_input_mvp_v1_teams
    ON features.model_input_mvp_v1 (home_team_id, away_team_id);
