-- 07_features_fifa_ranking.sql
-- Team-level historical FIFA ranking features before each match.
--
-- Leakage rule:
-- FIFA ranking values are selected using only rankings with:
-- ranking_date < match_date
--
-- Important:
-- staging.fifa_rankings.team_id is not compatible with staging.team_mapping.team_id,
-- so this feature joins FIFA rankings by normalized canonical team name.
--
-- Outputs:
-- - features.team_fifa_ranking_before_match
--
-- This file intentionally does NOT use:
-- - current_fifa_rankings snapshot
-- - current Elo snapshots
-- - current market value snapshots
-- - national_team_profiles snapshot fields

CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.team_fifa_ranking_before_match;

CREATE TABLE features.team_fifa_ranking_before_match AS
WITH fifa_rankings_normalized AS (
    SELECT
        CASE
            WHEN canonical_name IN ('Cabo Verde', 'Cape Verde Islands') THEN 'Cape Verde'
            WHEN canonical_name = 'Chinese Taipei' THEN 'Taiwan'
            WHEN canonical_name = 'Curacao' THEN 'Curaçao'
            WHEN canonical_name = 'FYR Macedonia' THEN 'North Macedonia'
            WHEN canonical_name = 'Sao Tome e Principe' THEN 'São Tomé and Príncipe'
            ELSE canonical_name
        END AS feature_team_name,
        ranking_date,
        rank_int,
        total_points_numeric,
        previous_points_numeric,
        diff_points_numeric
    FROM staging.fifa_rankings
)
SELECT
    cur.historical_match_id,
    cur.match_date,
    cur.team_id,
    cur.opponent_team_id,
    cur.team_name,
    cur.opponent_team_name,
    cur.team_side,
    cur.tournament,
    cur.neutral,

    fr.ranking_date AS fifa_ranking_date,
    fr.rank_int AS fifa_rank,
    fr.total_points_numeric AS fifa_total_points,
    fr.previous_points_numeric AS fifa_previous_points,
    fr.diff_points_numeric AS fifa_diff_points,
    (cur.match_date - fr.ranking_date) AS fifa_ranking_age_days,
    (fr.ranking_date IS NOT NULL) AS has_fifa_ranking_before_match,

    now() AS created_at
FROM features.team_match_rows cur
LEFT JOIN LATERAL (
    SELECT
        ranking_date,
        rank_int,
        total_points_numeric,
        previous_points_numeric,
        diff_points_numeric
    FROM fifa_rankings_normalized fr
    WHERE fr.feature_team_name = cur.team_name
      AND fr.ranking_date < cur.match_date
    ORDER BY fr.ranking_date DESC
    LIMIT 1
) fr ON TRUE;

CREATE INDEX IF NOT EXISTS idx_team_fifa_ranking_before_match_team_date
    ON features.team_fifa_ranking_before_match (team_id, match_date, historical_match_id);

CREATE INDEX IF NOT EXISTS idx_team_fifa_ranking_before_match_match
    ON features.team_fifa_ranking_before_match (historical_match_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_team_fifa_ranking_before_match_match_team
    ON features.team_fifa_ranking_before_match (historical_match_id, team_id);
