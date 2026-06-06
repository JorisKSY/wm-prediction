-- 10_features_match_coverage.sql
-- Match-level feature coverage flags.
--
-- Purpose:
-- Track which matches have enough non-null features for different modeling scopes.
--
-- Outputs:
-- - features.match_feature_coverage

CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.match_feature_coverage;

CREATE TABLE features.match_feature_coverage AS
SELECT
    historical_match_id,
    match_date,
    home_team_id,
    away_team_id,
    home_team_name,
    away_team_name,
    tournament_bucket,

    (
        home_prev5_points_per_match IS NOT NULL
        AND away_prev5_points_per_match IS NOT NULL
        AND prev5_points_per_match_diff IS NOT NULL
        AND prev5_goal_diff_per_match_diff IS NOT NULL
    ) AS has_both_prev5,

    (
        home_prev10_points_per_match IS NOT NULL
        AND away_prev10_points_per_match IS NOT NULL
        AND prev10_points_per_match_diff IS NOT NULL
        AND prev10_goal_diff_per_match_diff IS NOT NULL
    ) AS has_both_prev10,

    (
        home_prev365d_points_per_match IS NOT NULL
        AND away_prev365d_points_per_match IS NOT NULL
        AND prev365d_points_per_match_diff IS NOT NULL
        AND prev365d_goal_diff_per_match_diff IS NOT NULL
    ) AS has_both_prev365d,

    (
        home_prev5y_points_per_match IS NOT NULL
        AND away_prev5y_points_per_match IS NOT NULL
        AND prev5y_points_per_match_diff IS NOT NULL
        AND prev5y_goal_diff_per_match_diff IS NOT NULL
    ) AS has_both_prev5y,

    (
        home_fifa_rank IS NOT NULL
        AND away_fifa_rank IS NOT NULL
        AND fifa_rank_diff_home_minus_away IS NOT NULL
        AND fifa_points_diff_home_minus_away IS NOT NULL
    ) AS has_both_fifa,

    -- Basic model candidate:
    -- modern FIFA era, enough short/medium/long team form, and both teams have FIFA ranking.
    (
        match_date >= DATE '1992-07-01'
        AND home_prev5_points_per_match IS NOT NULL
        AND away_prev5_points_per_match IS NOT NULL
        AND home_prev10_points_per_match IS NOT NULL
        AND away_prev10_points_per_match IS NOT NULL
        AND home_prev5y_points_per_match IS NOT NULL
        AND away_prev5y_points_per_match IS NOT NULL
        AND home_fifa_rank IS NOT NULL
        AND away_fifa_rank IS NOT NULL
    ) AS is_model_candidate_basic,

    now() AS created_at
FROM features.match_features_training;

CREATE UNIQUE INDEX IF NOT EXISTS ux_match_feature_coverage_match
    ON features.match_feature_coverage (historical_match_id);

CREATE INDEX IF NOT EXISTS idx_match_feature_coverage_date
    ON features.match_feature_coverage (match_date);

CREATE INDEX IF NOT EXISTS idx_match_feature_coverage_basic
    ON features.match_feature_coverage (is_model_candidate_basic);
