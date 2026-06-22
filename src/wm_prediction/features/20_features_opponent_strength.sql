-- 20_features_opponent_strength.sql
-- Phase E: opponent-adjusted form (strength-of-schedule).
--
-- Idea:
-- The existing prevN_goals_for/against form features are UNADJUSTED: a 3-0 win
-- counts the same whether against a top side or a minnow. This file adds the
-- average opponent strength faced over recent matches, so later models can
-- contextualize raw form by who it was achieved against.
--
-- Opponent strength = FIFA rank percentile WITHIN the contemporaneous semester
-- snapshot (scale-robust across the 2018 methodology change and changing number
-- of ranked teams). 1.0 = strongest team in that snapshot, 0.0 = weakest.
--
-- Leakage rules (BOTH enforced):
--   1) Only past matches contribute:        prev.match_date < cur.match_date
--   2) Opponent rank is as-of that match:    snap.ranking_date < prev.match_date
-- Comparator '<' matches 07_features_fifa_ranking.sql exactly.
--
-- NULL policy (agreed): if NONE of the window's matches has an opponent rank,
-- the *_mean is NULL (consistent with how 06 leaves prevN_* NULL on thin history).
-- Coverage counts matches WITH a rank divided by matches IN the window (not /N),
-- so a young team with few games is not falsely shown as low coverage.
--
-- Reads the shared name-normalization via features.fifa_rank_percentile_snapshot,
-- which is built here from features.fifa_rankings_normalized (created in 07).
-- Do NOT duplicate the canonical_name -> feature_team_name CASE block.
--
-- Outputs:
--   - features.fifa_rank_percentile_snapshot
--   - features.team_opponent_strength_before_match

CREATE SCHEMA IF NOT EXISTS features;

-- Per-snapshot rank percentile. Built from the normalized names so that
-- North Macedonia / Taiwan / Cape Verde / Curacao / Sao Tome resolve correctly.
DROP TABLE IF EXISTS features.fifa_rank_percentile_snapshot;

CREATE TABLE features.fifa_rank_percentile_snapshot AS
SELECT
    feature_team_name,
    ranking_date,
    ranking_year,
    ranking_semester,
    rank_int,
    1.0 - (rank_int - 1)::numeric
          / NULLIF(MAX(rank_int) OVER (PARTITION BY ranking_date) - 1, 0)
        AS rank_pct
FROM features.fifa_rankings_normalized;

CREATE INDEX IF NOT EXISTS idx_fifa_rank_pct_name_date
    ON features.fifa_rank_percentile_snapshot (feature_team_name, ranking_date DESC);


DROP TABLE IF EXISTS features.team_opponent_strength_before_match;

CREATE TABLE features.team_opponent_strength_before_match AS
SELECT
    cur.historical_match_id,
    cur.match_date,
    cur.team_id,
    cur.team_name,
    cur.team_side,

    prev5.opp_strength_mean      AS prev5_opp_strength_mean,
    prev5.opp_strength_coverage  AS prev5_opp_strength_coverage,

    prev10.opp_strength_mean     AS prev10_opp_strength_mean,
    prev10.opp_strength_coverage AS prev10_opp_strength_coverage,

    prev365d.opp_strength_mean     AS prev365d_opp_strength_mean,
    prev365d.opp_strength_coverage AS prev365d_opp_strength_coverage,

    now() AS created_at
FROM features.team_match_rows cur

LEFT JOIN LATERAL (
    SELECT
        AVG(s.rank_pct)                                  AS opp_strength_mean,
        COUNT(s.rank_pct)::numeric / NULLIF(COUNT(*), 0) AS opp_strength_coverage
    FROM (
        SELECT prev.opponent_team_name, prev.match_date
        FROM features.team_match_rows prev
        WHERE prev.team_id = cur.team_id
          AND prev.match_date < cur.match_date
        ORDER BY prev.match_date DESC, prev.historical_match_id DESC
        LIMIT 5
    ) w
    LEFT JOIN LATERAL (
        SELECT sp.rank_pct
        FROM features.fifa_rank_percentile_snapshot sp
        WHERE sp.feature_team_name = w.opponent_team_name
          AND sp.ranking_date < w.match_date
        ORDER BY sp.ranking_date DESC
        LIMIT 1
    ) s ON TRUE
) prev5 ON TRUE

LEFT JOIN LATERAL (
    SELECT
        AVG(s.rank_pct)                                  AS opp_strength_mean,
        COUNT(s.rank_pct)::numeric / NULLIF(COUNT(*), 0) AS opp_strength_coverage
    FROM (
        SELECT prev.opponent_team_name, prev.match_date
        FROM features.team_match_rows prev
        WHERE prev.team_id = cur.team_id
          AND prev.match_date < cur.match_date
        ORDER BY prev.match_date DESC, prev.historical_match_id DESC
        LIMIT 10
    ) w
    LEFT JOIN LATERAL (
        SELECT sp.rank_pct
        FROM features.fifa_rank_percentile_snapshot sp
        WHERE sp.feature_team_name = w.opponent_team_name
          AND sp.ranking_date < w.match_date
        ORDER BY sp.ranking_date DESC
        LIMIT 1
    ) s ON TRUE
) prev10 ON TRUE

LEFT JOIN LATERAL (
    SELECT
        AVG(s.rank_pct)                                  AS opp_strength_mean,
        COUNT(s.rank_pct)::numeric / NULLIF(COUNT(*), 0) AS opp_strength_coverage
    FROM (
        SELECT prev.opponent_team_name, prev.match_date
        FROM features.team_match_rows prev
        WHERE prev.team_id = cur.team_id
          AND prev.match_date < cur.match_date
          AND prev.match_date >= cur.match_date - INTERVAL '365 days'
    ) w
    LEFT JOIN LATERAL (
        SELECT sp.rank_pct
        FROM features.fifa_rank_percentile_snapshot sp
        WHERE sp.feature_team_name = w.opponent_team_name
          AND sp.ranking_date < w.match_date
        ORDER BY sp.ranking_date DESC
        LIMIT 1
    ) s ON TRUE
) prev365d ON TRUE;

CREATE INDEX IF NOT EXISTS idx_team_opp_strength_team_date
    ON features.team_opponent_strength_before_match (team_id, match_date, historical_match_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_team_opp_strength_match_team
    ON features.team_opponent_strength_before_match (historical_match_id, team_id);
