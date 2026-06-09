-- 13_features_team_prediction_snapshot_v2_technical_33.sql
-- Phase J.1 technical dry-run team snapshot for dynamic knockout matchups.
--
-- Purpose:
-- Build team-level snapshot for WM-2026 teams using the same feature sources as
-- features.match_prediction_v2_technical_33, but one row per team.
--
-- Used by:
--   predict_knockout_matchup_v2_technical_33.py
--
-- This is NOT the final production v2 snapshot. Momentum is excluded because the
-- required 2025 FIFA ranking snapshot is currently missing.

CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.team_prediction_snapshot_v2_technical_33;

CREATE TABLE features.team_prediction_snapshot_v2_technical_33 AS
WITH wc_teams AS (
    SELECT home_team_id AS team_id, home_team_name AS team_name
    FROM features.match_prediction_v2_technical_33

    UNION

    SELECT away_team_id AS team_id, away_team_name AS team_name
    FROM features.match_prediction_v2_technical_33
),
snapshot_date AS (
    SELECT MIN(match_date)::date AS prediction_date
    FROM features.match_prediction_v2_technical_33
),
prev_matches AS (
    SELECT
        wt.team_id,
        wt.team_name,
        sd.prediction_date,
        prev.match_date,
        prev.historical_match_id,
        prev.goals_for,
        prev.goals_against,
        prev.goal_diff,
        prev.points,
        prev.opponent_team_name,
        ROW_NUMBER() OVER (
            PARTITION BY wt.team_id
            ORDER BY prev.match_date DESC, prev.historical_match_id DESC
        ) AS rn_desc
    FROM wc_teams wt
    CROSS JOIN snapshot_date sd
    JOIN features.team_match_rows prev
        ON prev.team_id = wt.team_id
       AND prev.match_date < sd.prediction_date
),
team_form AS (
    SELECT
        wt.team_id,
        wt.team_name,
        sd.prediction_date,

        COUNT(*) FILTER (WHERE pm.rn_desc <= 5) AS prev5_matches,
        SUM(pm.points) FILTER (WHERE pm.rn_desc <= 5) AS prev5_points,
        SUM(pm.goals_for) FILTER (WHERE pm.rn_desc <= 5) AS prev5_goals_for,
        SUM(pm.goals_against) FILTER (WHERE pm.rn_desc <= 5) AS prev5_goals_against,
        SUM(pm.goal_diff) FILTER (WHERE pm.rn_desc <= 5) AS prev5_goal_diff,

        COUNT(*) FILTER (WHERE pm.rn_desc <= 10) AS prev10_matches,
        SUM(pm.points) FILTER (WHERE pm.rn_desc <= 10) AS prev10_points,
        SUM(pm.goals_for) FILTER (WHERE pm.rn_desc <= 10) AS prev10_goals_for,
        SUM(pm.goals_against) FILTER (WHERE pm.rn_desc <= 10) AS prev10_goals_against,
        SUM(pm.goal_diff) FILTER (WHERE pm.rn_desc <= 10) AS prev10_goal_diff,

        COUNT(*) FILTER (
            WHERE pm.match_date >= sd.prediction_date - INTERVAL '5 years'
              AND pm.match_date < sd.prediction_date
        ) AS prev5y_matches,
        SUM(pm.points) FILTER (
            WHERE pm.match_date >= sd.prediction_date - INTERVAL '5 years'
              AND pm.match_date < sd.prediction_date
        ) AS prev5y_points,
        SUM(pm.goals_for) FILTER (
            WHERE pm.match_date >= sd.prediction_date - INTERVAL '5 years'
              AND pm.match_date < sd.prediction_date
        ) AS prev5y_goals_for,
        SUM(pm.goals_against) FILTER (
            WHERE pm.match_date >= sd.prediction_date - INTERVAL '5 years'
              AND pm.match_date < sd.prediction_date
        ) AS prev5y_goals_against,
        SUM(pm.goal_diff) FILTER (
            WHERE pm.match_date >= sd.prediction_date - INTERVAL '5 years'
              AND pm.match_date < sd.prediction_date
        ) AS prev5y_goal_diff

    FROM wc_teams wt
    CROSS JOIN snapshot_date sd
    LEFT JOIN prev_matches pm
        ON pm.team_id = wt.team_id
    GROUP BY
        wt.team_id,
        wt.team_name,
        sd.prediction_date
),
team_form_rates AS (
    SELECT
        team_id,
        team_name,
        prediction_date,

        prev5_matches,
        prev5_points::numeric / NULLIF(prev5_matches, 0) AS prev5_points_per_match,
        prev5_goals_for::numeric / NULLIF(prev5_matches, 0) AS prev5_goals_for_per_match,
        prev5_goals_against::numeric / NULLIF(prev5_matches, 0) AS prev5_goals_against_per_match,
        prev5_goal_diff::numeric / NULLIF(prev5_matches, 0) AS prev5_goal_diff_per_match,

        prev10_matches,
        prev10_points::numeric / NULLIF(prev10_matches, 0) AS prev10_points_per_match,
        prev10_goals_for::numeric / NULLIF(prev10_matches, 0) AS prev10_goals_for_per_match,
        prev10_goals_against::numeric / NULLIF(prev10_matches, 0) AS prev10_goals_against_per_match,
        prev10_goal_diff::numeric / NULLIF(prev10_matches, 0) AS prev10_goal_diff_per_match,

        prev5y_matches,
        prev5y_points::numeric / NULLIF(prev5y_matches, 0) AS prev5y_points_per_match,
        prev5y_goals_for::numeric / NULLIF(prev5y_matches, 0) AS prev5y_goals_for_per_match,
        prev5y_goals_against::numeric / NULLIF(prev5y_matches, 0) AS prev5y_goals_against_per_match,
        prev5y_goal_diff::numeric / NULLIF(prev5y_matches, 0) AS prev5y_goal_diff_per_match
    FROM team_form
),
current_fifa_clean AS (
    SELECT
        cf.*,
        COALESCE(a.canonical_name, cf.canonical_name) AS feature_team_name,
        cf.staged_at::date AS fifa_ranking_date,
        ROW_NUMBER() OVER (
            PARTITION BY COALESCE(a.canonical_name, cf.canonical_name)
            ORDER BY cf.staged_at DESC, cf.fifa_rank ASC
        ) AS rn
    FROM staging.current_fifa_rankings cf
    LEFT JOIN staging.team_name_aliases a
        ON a.source_name = cf.canonical_name
),
latest_fifa AS (
    SELECT
        wt.team_id,
        wt.team_name,
        sd.prediction_date,
        cf.fifa_ranking_date,
        cf.fifa_rank,
        (sd.prediction_date - cf.fifa_ranking_date) AS fifa_ranking_age_days,
        cf.fifa_total_points,
        cf.previous_fifa_rank,
        cf.previous_fifa_points
    FROM wc_teams wt
    CROSS JOIN snapshot_date sd
    JOIN current_fifa_clean cf
        ON cf.feature_team_name = wt.team_name
       AND cf.rn = 1
       AND cf.fifa_ranking_date < sd.prediction_date
),
team_sos AS (
    SELECT
        wt.team_id,
        wt.team_name,
        sd.prediction_date,

        prev5.opp_strength_mean AS prev5_opp_strength_mean,
        prev10.opp_strength_mean AS prev10_opp_strength_mean,
        prev365d.opp_strength_mean AS prev365d_opp_strength_mean,

        prev5.opp_strength_coverage AS prev5_opp_strength_coverage_audit,
        prev10.opp_strength_coverage AS prev10_opp_strength_coverage_audit,
        prev365d.opp_strength_coverage AS prev365d_opp_strength_coverage_audit
    FROM wc_teams wt
    CROSS JOIN snapshot_date sd

    LEFT JOIN LATERAL (
        SELECT
            AVG(s.rank_pct) AS opp_strength_mean,
            COUNT(s.rank_pct)::numeric / NULLIF(COUNT(*), 0) AS opp_strength_coverage
        FROM (
            SELECT prev.opponent_team_name, prev.match_date
            FROM features.team_match_rows prev
            WHERE prev.team_id = wt.team_id
              AND prev.match_date < sd.prediction_date
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
            AVG(s.rank_pct) AS opp_strength_mean,
            COUNT(s.rank_pct)::numeric / NULLIF(COUNT(*), 0) AS opp_strength_coverage
        FROM (
            SELECT prev.opponent_team_name, prev.match_date
            FROM features.team_match_rows prev
            WHERE prev.team_id = wt.team_id
              AND prev.match_date < sd.prediction_date
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
            AVG(s.rank_pct) AS opp_strength_mean,
            COUNT(s.rank_pct)::numeric / NULLIF(COUNT(*), 0) AS opp_strength_coverage
        FROM (
            SELECT prev.opponent_team_name, prev.match_date
            FROM features.team_match_rows prev
            WHERE prev.team_id = wt.team_id
              AND prev.match_date < sd.prediction_date
              AND prev.match_date >= sd.prediction_date - INTERVAL '365 days'
        ) w
        LEFT JOIN LATERAL (
            SELECT sp.rank_pct
            FROM features.fifa_rank_percentile_snapshot sp
            WHERE sp.feature_team_name = w.opponent_team_name
              AND sp.ranking_date < w.match_date
            ORDER BY sp.ranking_date DESC
            LIMIT 1
        ) s ON TRUE
    ) prev365d ON TRUE
)
SELECT
    tfr.team_id,
    tfr.team_name,
    tfr.prediction_date,

    tfr.prev5_matches,
    tfr.prev5_points_per_match,
    tfr.prev5_goals_for_per_match,
    tfr.prev5_goals_against_per_match,
    tfr.prev5_goal_diff_per_match,

    tfr.prev10_matches,
    tfr.prev10_points_per_match,
    tfr.prev10_goals_for_per_match,
    tfr.prev10_goals_against_per_match,
    tfr.prev10_goal_diff_per_match,

    tfr.prev5y_matches,
    tfr.prev5y_points_per_match,
    tfr.prev5y_goals_for_per_match,
    tfr.prev5y_goals_against_per_match,
    tfr.prev5y_goal_diff_per_match,

    lf.fifa_ranking_date,
    lf.fifa_rank,
    lf.fifa_ranking_age_days,
    lf.fifa_total_points AS fifa_total_points_audit,
    lf.previous_fifa_rank AS previous_fifa_rank_audit,
    lf.previous_fifa_points AS previous_fifa_points_audit,

    ts.prev5_opp_strength_mean,
    ts.prev10_opp_strength_mean,
    ts.prev365d_opp_strength_mean,

    ts.prev5_opp_strength_coverage_audit,
    ts.prev10_opp_strength_coverage_audit,
    ts.prev365d_opp_strength_coverage_audit,

    'v2_technical_33_no_momentum'::text AS feature_set_name,
    NOW() AS created_at

FROM team_form_rates tfr
JOIN latest_fifa lf
    ON lf.team_id = tfr.team_id
JOIN team_sos ts
    ON ts.team_id = tfr.team_id;
