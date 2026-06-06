-- 08_features_match_context.sql
-- Match-level context features.
--
-- One row per played historical match.
--
-- Leakage rule:
-- These features use only match metadata known before kickoff:
-- tournament, date, country/city, neutral flag.
--
-- Outputs:
-- - features.match_context

CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.match_context;

CREATE TABLE features.match_context AS
SELECT
    historical_match_id,
    match_date,
    tournament,
    city,
    country,
    COALESCE(neutral, false) AS is_neutral,

    EXTRACT(YEAR FROM match_date)::integer AS match_year,
    EXTRACT(MONTH FROM match_date)::integer AS match_month,

    (tournament = 'Friendly') AS is_friendly,

    (tournament = 'FIFA World Cup') AS is_world_cup,

    (tournament = 'FIFA World Cup qualification') AS is_world_cup_qualifier,

    (
        tournament IN (
            'UEFA Euro',
            'Copa América',
            'African Cup of Nations',
            'AFC Asian Cup',
            'Gold Cup',
            'Oceania Nations Cup',
            'CONCACAF Championship',
            'Confederations Cup'
        )
    ) AS is_major_continental_tournament,

    (
        tournament IN (
            'UEFA Euro qualification',
            'African Cup of Nations qualification',
            'AFC Asian Cup qualification',
            'Gold Cup qualification',
            'Oceania Nations Cup qualification',
            'CONCACAF Championship qualification'
        )
    ) AS is_continental_qualifier,

    (
        tournament IN (
            'UEFA Nations League',
            'CONCACAF Nations League',
            'CONCACAF Nations League qualification'
        )
    ) AS is_nations_league,

    CASE
        WHEN tournament = 'Friendly' THEN 'friendly'
        WHEN tournament = 'FIFA World Cup' THEN 'world_cup'
        WHEN tournament = 'FIFA World Cup qualification' THEN 'world_cup_qualifier'
        WHEN tournament IN (
            'UEFA Euro',
            'Copa América',
            'African Cup of Nations',
            'AFC Asian Cup',
            'Gold Cup',
            'Oceania Nations Cup',
            'CONCACAF Championship',
            'Confederations Cup'
        ) THEN 'major_continental_tournament'
        WHEN tournament IN (
            'UEFA Euro qualification',
            'African Cup of Nations qualification',
            'AFC Asian Cup qualification',
            'Gold Cup qualification',
            'Oceania Nations Cup qualification',
            'CONCACAF Championship qualification'
        ) THEN 'continental_qualifier'
        WHEN tournament IN (
            'UEFA Nations League',
            'CONCACAF Nations League',
            'CONCACAF Nations League qualification'
        ) THEN 'nations_league'
        ELSE 'other_tournament'
    END AS tournament_bucket,

    now() AS created_at
FROM staging.historical_matches
WHERE home_score IS NOT NULL
  AND away_score IS NOT NULL
  AND home_team_id IS NOT NULL
  AND away_team_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_match_context_match
    ON features.match_context (historical_match_id);

CREATE INDEX IF NOT EXISTS idx_match_context_date
    ON features.match_context (match_date);

CREATE INDEX IF NOT EXISTS idx_match_context_bucket
    ON features.match_context (tournament_bucket);
