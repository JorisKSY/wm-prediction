-- 21_features_rank_momentum.sql
-- Phase F: FIFA rank momentum (2-semester / 1-year delta), as-of dated and freshness-gated.
--
-- Idea:
-- Momentum is a DIFFERENCE, not a level:
--   rank_improve_1yr = rank_1yr_ago - rank_now
-- positive = climbed/improved.
--
-- Definition:
--   rank_now      = rank from the latest fresh snapshot strictly BEFORE match_date
--   rank_1yr_ago  = rank from the latest fresh snapshot strictly BEFORE match_date - 1 year
--
-- Freshness gate:
--   A snapshot is accepted only if it is at most 240 days older than its as-of date.
--   This prevents stale "last known ranking" artifacts, e.g. teams whose 2019
--   1-year-ago rank would otherwise fall back to a 2006 snapshot.
--
-- Leakage rules:
--   raw now snapshot condition: ranking_date < match_date
--   raw ago snapshot condition: ranking_date < match_date - 1 year
--   Then freshness gate is applied AFTER the as-of lookup.
--   Comparator '<' matches 07 / 20 exactly.
--
-- Join rule:
--   Reads features.fifa_rank_percentile_snapshot and joins own team via
--   team_match_rows.team_name = feature_team_name.
--   Do NOT join through staging.fifa_rankings.team_id; that id domain is not
--   compatible with team_match_rows.team_id.
--   Do NOT duplicate name-normalization logic here.
--
-- NULL policy:
--   rank_improve_1yr is NULL if either gated rank is NULL.
--   A delta from one rank only, or from a stale snapshot, is undefined.
--
-- Regime note:
--   Semester-to-semester rank volatility dropped after the 2018 FIFA methodology
--   change. Momentum only qualifies if it improves the post-2019 validation window,
--   not just older rolling windows.
--
-- Output:
--   - features.team_rank_momentum_before_match
--     team-level, key historical_match_id + team_id

CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.team_rank_momentum_before_match;
CREATE TABLE features.team_rank_momentum_before_match AS
WITH raw_momentum AS (
    SELECT
        cur.historical_match_id,
        cur.match_date,
        cur.team_id,
        cur.team_name,
        cur.team_side,

        now_s.rank_int AS raw_rank_now,
        ago_s.rank_int AS raw_rank_1yr_ago,
        now_s.ranking_date AS rank_now_snapshot_date,
        ago_s.ranking_date AS rank_1yr_ago_snapshot_date,

        (cur.match_date - now_s.ranking_date) AS rank_now_age_days,
        ((cur.match_date - INTERVAL '1 year')::date - ago_s.ranking_date) AS rank_1yr_ago_age_days
    FROM features.team_match_rows cur
    LEFT JOIN LATERAL (
        SELECT sp.rank_int, sp.ranking_date
        FROM features.fifa_rank_percentile_snapshot sp
        WHERE sp.feature_team_name = cur.team_name
          AND sp.ranking_date < cur.match_date
        ORDER BY sp.ranking_date DESC
        LIMIT 1
    ) now_s ON TRUE
    LEFT JOIN LATERAL (
        SELECT sp.rank_int, sp.ranking_date
        FROM features.fifa_rank_percentile_snapshot sp
        WHERE sp.feature_team_name = cur.team_name
          AND sp.ranking_date < cur.match_date - INTERVAL '1 year'
        ORDER BY sp.ranking_date DESC
        LIMIT 1
    ) ago_s ON TRUE
)
SELECT
    historical_match_id,
    match_date,
    team_id,
    team_name,
    team_side,

    CASE
        WHEN raw_rank_now IS NOT NULL
         AND rank_now_age_days <= 240
        THEN raw_rank_now
        ELSE NULL
    END AS rank_now,

    CASE
        WHEN raw_rank_1yr_ago IS NOT NULL
         AND rank_1yr_ago_age_days <= 240
        THEN raw_rank_1yr_ago
        ELSE NULL
    END AS rank_1yr_ago,

    CASE
        WHEN raw_rank_now IS NOT NULL
         AND raw_rank_1yr_ago IS NOT NULL
         AND rank_now_age_days <= 240
         AND rank_1yr_ago_age_days <= 240
        THEN raw_rank_1yr_ago - raw_rank_now
        ELSE NULL
    END AS rank_improve_1yr,

    rank_now_snapshot_date,
    rank_1yr_ago_snapshot_date,
    rank_now_age_days,
    rank_1yr_ago_age_days,
    240 AS rank_snapshot_max_age_days,
    now() AS created_at
FROM raw_momentum;

CREATE INDEX IF NOT EXISTS idx_team_rank_momentum_match_team
    ON features.team_rank_momentum_before_match (historical_match_id, team_id);
