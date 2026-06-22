-- 12_features_match_prediction_v2_technical_33.sql
-- Phase J.1 technical dry-run prediction input.
--
-- Purpose:
-- Build match-level prediction input for WM-2026 using the Phase-H XGBoost
-- candidate feature set WITHOUT rank momentum.
--
-- This is NOT the final production v2 input. The full 35-feature v2 is blocked
-- until a real 2025 FIFA ranking snapshot is available for rank_improve_1yr.
--
-- Feature set:
--   V2_TECHNICAL_33_NO_MOMENTUM_FEATURES
--   = v2_candidate_35_features minus:
--       - home_rank_improve_1yr
--       - away_rank_improve_1yr
--
-- Key fixes vs MVP-v1:
--   - FIFA rank_now for 2026 comes from staging.current_fifa_rankings
--     staged at 2026-06-04, not stale staging.fifa_rankings 2024-07-01.
--   - current_fifa names are normalized through staging.team_name_aliases.
--   - SOS mean-only features are recomputed for future matches using the same
--     leakage-safe logic as Phase E.
--
-- Known limitation:
--   SOS for previous matches in 2025/2026 still depends on
--   features.fifa_rank_percentile_snapshot, whose historical source currently
--   ends at 2024-07-01. This is acceptable for a technical dry run but must be
--   revisited when the ranking series is extended.

CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.match_prediction_v2_technical_33;

CREATE TABLE features.match_prediction_v2_technical_33 AS
WITH future_matches AS (
    SELECT
        historical_match_id,
        match_date,
        home_team_id,
        away_team_id,
        home_canonical_name AS home_team_name,
        away_canonical_name AS away_team_name,
        tournament,
        city,
        country,
        neutral AS is_neutral
    FROM staging.historical_matches
    WHERE match_date >= CURRENT_DATE
      AND home_score IS NULL
      AND away_score IS NULL
),
future_team_rows AS (
    SELECT
        historical_match_id,
        match_date,
        home_team_id AS team_id,
        home_team_name AS team_name,
        away_team_id AS opponent_team_id,
        away_team_name AS opponent_team_name,
        'home'::text AS team_side
    FROM future_matches

    UNION ALL

    SELECT
        historical_match_id,
        match_date,
        away_team_id AS team_id,
        away_team_name AS team_name,
        home_team_id AS opponent_team_id,
        home_team_name AS opponent_team_name,
        'away'::text AS team_side
    FROM future_matches
),
prev_matches AS (
    SELECT
        cur.historical_match_id,
        cur.team_id,
        cur.team_side,
        prev.match_date,
        prev.historical_match_id AS prev_historical_match_id,
        prev.goals_for,
        prev.goals_against,
        prev.goal_diff,
        prev.points,
        prev.opponent_team_name,
        ROW_NUMBER() OVER (
            PARTITION BY cur.historical_match_id, cur.team_id, cur.team_side
            ORDER BY prev.match_date DESC, prev.historical_match_id DESC
        ) AS rn_desc
    FROM future_team_rows cur
    JOIN features.team_match_rows prev
        ON prev.team_id = cur.team_id
       AND prev.match_date < cur.match_date
),
team_form AS (
    SELECT
        cur.historical_match_id,
        cur.team_id,
        cur.team_side,

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
            WHERE pm.match_date >= cur.match_date - INTERVAL '5 years'
              AND pm.match_date < cur.match_date
        ) AS prev5y_matches,
        SUM(pm.points) FILTER (
            WHERE pm.match_date >= cur.match_date - INTERVAL '5 years'
              AND pm.match_date < cur.match_date
        ) AS prev5y_points,
        SUM(pm.goals_for) FILTER (
            WHERE pm.match_date >= cur.match_date - INTERVAL '5 years'
              AND pm.match_date < cur.match_date
        ) AS prev5y_goals_for,
        SUM(pm.goals_against) FILTER (
            WHERE pm.match_date >= cur.match_date - INTERVAL '5 years'
              AND pm.match_date < cur.match_date
        ) AS prev5y_goals_against,
        SUM(pm.goal_diff) FILTER (
            WHERE pm.match_date >= cur.match_date - INTERVAL '5 years'
              AND pm.match_date < cur.match_date
        ) AS prev5y_goal_diff

    FROM future_team_rows cur
    LEFT JOIN prev_matches pm
        ON pm.historical_match_id = cur.historical_match_id
       AND pm.team_id = cur.team_id
       AND pm.team_side = cur.team_side
    GROUP BY
        cur.historical_match_id,
        cur.team_id,
        cur.team_side
),
team_form_rates AS (
    SELECT
        historical_match_id,
        team_id,
        team_side,

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
team_fifa AS (
    SELECT
        cur.historical_match_id,
        cur.team_id,
        cur.team_side,
        cf.fifa_ranking_date,
        cf.fifa_rank,
        (cur.match_date - cf.fifa_ranking_date) AS fifa_ranking_age_days,
        cf.fifa_total_points,
        cf.previous_fifa_rank,
        cf.previous_fifa_points
    FROM future_team_rows cur
    JOIN current_fifa_clean cf
        ON cf.feature_team_name = cur.team_name
       AND cf.rn = 1
       AND cf.fifa_ranking_date < cur.match_date
),
team_sos AS (
    SELECT
        cur.historical_match_id,
        cur.match_date,
        cur.team_id,
        cur.team_name,
        cur.team_side,

        prev5.opp_strength_mean AS prev5_opp_strength_mean,
        prev10.opp_strength_mean AS prev10_opp_strength_mean,
        prev365d.opp_strength_mean AS prev365d_opp_strength_mean,

        prev5.opp_strength_coverage AS prev5_opp_strength_coverage_audit,
        prev10.opp_strength_coverage AS prev10_opp_strength_coverage_audit,
        prev365d.opp_strength_coverage AS prev365d_opp_strength_coverage_audit
    FROM future_team_rows cur

    LEFT JOIN LATERAL (
        SELECT
            AVG(s.rank_pct) AS opp_strength_mean,
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
            AVG(s.rank_pct) AS opp_strength_mean,
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
            AVG(s.rank_pct) AS opp_strength_mean,
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
    ) prev365d ON TRUE
),
match_context AS (
    SELECT
        historical_match_id,
        match_date,
        tournament,
        city,
        country,
        is_neutral::integer AS is_neutral,
        EXTRACT(YEAR FROM match_date)::integer AS match_year,
        EXTRACT(MONTH FROM match_date)::integer AS match_month,
        CASE WHEN tournament = 'Friendly' THEN 1 ELSE 0 END AS is_friendly,
        CASE WHEN tournament = 'FIFA World Cup' THEN 1 ELSE 0 END AS is_world_cup,
        CASE WHEN tournament = 'FIFA World Cup qualification' THEN 1 ELSE 0 END AS is_world_cup_qualifier,
        CASE
            WHEN tournament IN (
                'AFC Asian Cup',
                'African Cup of Nations',
                'Copa América',
                'CONCACAF Championship',
                'CONCACAF Gold Cup',
                'Oceania Nations Cup',
                'UEFA Euro'
            ) THEN 1 ELSE 0
        END AS is_major_continental_tournament,
        CASE
            WHEN tournament ILIKE '%qualification%'
             AND tournament <> 'FIFA World Cup qualification'
            THEN 1 ELSE 0
        END AS is_continental_qualifier,
        CASE WHEN tournament ILIKE '%Nations League%' THEN 1 ELSE 0 END AS is_nations_league,
        CASE
            WHEN tournament = 'Friendly' THEN 'friendly'
            WHEN tournament = 'FIFA World Cup' THEN 'world_cup'
            WHEN tournament = 'FIFA World Cup qualification' THEN 'world_cup_qualifier'
            WHEN tournament IN (
                'AFC Asian Cup',
                'African Cup of Nations',
                'Copa América',
                'CONCACAF Championship',
                'CONCACAF Gold Cup',
                'Oceania Nations Cup',
                'UEFA Euro'
            ) THEN 'major_continental_tournament'
            WHEN tournament ILIKE '%qualification%'
             AND tournament <> 'FIFA World Cup qualification'
            THEN 'continental_qualifier'
            WHEN tournament ILIKE '%Nations League%' THEN 'nations_league'
            ELSE 'other_tournament'
        END AS tournament_bucket
    FROM future_matches
)
SELECT
    fm.historical_match_id,
    fm.match_date,
    fm.home_team_id,
    fm.away_team_id,
    fm.home_team_name,
    fm.away_team_name,

    mc.is_neutral,
    mc.is_friendly,
    mc.is_world_cup,
    mc.is_world_cup_qualifier,
    mc.is_major_continental_tournament,
    mc.is_continental_qualifier,
    mc.is_nations_league,
    mc.match_year,
    mc.match_month,
    mc.tournament_bucket,

    home_form.prev5_points_per_match AS home_prev5_points_per_match,
    home_form.prev5_goals_for_per_match AS home_prev5_goals_for_per_match,
    home_form.prev5_goals_against_per_match AS home_prev5_goals_against_per_match,
    home_form.prev5_goal_diff_per_match AS home_prev5_goal_diff_per_match,

    home_form.prev10_points_per_match AS home_prev10_points_per_match,
    home_form.prev10_goals_for_per_match AS home_prev10_goals_for_per_match,
    home_form.prev10_goals_against_per_match AS home_prev10_goals_against_per_match,
    home_form.prev10_goal_diff_per_match AS home_prev10_goal_diff_per_match,

    home_form.prev5y_points_per_match AS home_prev5y_points_per_match,
    home_form.prev5y_goals_for_per_match AS home_prev5y_goals_for_per_match,
    home_form.prev5y_goals_against_per_match AS home_prev5y_goals_against_per_match,
    home_form.prev5y_goal_diff_per_match AS home_prev5y_goal_diff_per_match,

    away_form.prev5_points_per_match AS away_prev5_points_per_match,
    away_form.prev5_goals_for_per_match AS away_prev5_goals_for_per_match,
    away_form.prev5_goals_against_per_match AS away_prev5_goals_against_per_match,
    away_form.prev5_goal_diff_per_match AS away_prev5_goal_diff_per_match,

    away_form.prev10_points_per_match AS away_prev10_points_per_match,
    away_form.prev10_goals_for_per_match AS away_prev10_goals_for_per_match,
    away_form.prev10_goals_against_per_match AS away_prev10_goals_against_per_match,
    away_form.prev10_goal_diff_per_match AS away_prev10_goal_diff_per_match,

    away_form.prev5y_points_per_match AS away_prev5y_points_per_match,
    away_form.prev5y_goals_for_per_match AS away_prev5y_goals_for_per_match,
    away_form.prev5y_goals_against_per_match AS away_prev5y_goals_against_per_match,
    away_form.prev5y_goal_diff_per_match AS away_prev5y_goal_diff_per_match,

    home_form.prev5_points_per_match - away_form.prev5_points_per_match AS prev5_points_per_match_diff,
    home_form.prev5_goal_diff_per_match - away_form.prev5_goal_diff_per_match AS prev5_goal_diff_per_match_diff,
    home_form.prev10_points_per_match - away_form.prev10_points_per_match AS prev10_points_per_match_diff,
    home_form.prev10_goal_diff_per_match - away_form.prev10_goal_diff_per_match AS prev10_goal_diff_per_match_diff,
    home_form.prev5y_points_per_match - away_form.prev5y_points_per_match AS prev5y_points_per_match_diff,
    home_form.prev5y_goal_diff_per_match - away_form.prev5y_goal_diff_per_match AS prev5y_goal_diff_per_match_diff,

    home_fifa.fifa_rank AS home_fifa_rank,
    away_fifa.fifa_rank AS away_fifa_rank,
    home_fifa.fifa_ranking_age_days AS home_fifa_ranking_age_days,
    away_fifa.fifa_ranking_age_days AS away_fifa_ranking_age_days,
    home_fifa.fifa_rank - away_fifa.fifa_rank AS fifa_rank_diff_home_minus_away,

    home_fifa.fifa_ranking_date AS home_fifa_ranking_date_audit,
    away_fifa.fifa_ranking_date AS away_fifa_ranking_date_audit,
    home_fifa.fifa_total_points AS home_fifa_total_points_audit,
    away_fifa.fifa_total_points AS away_fifa_total_points_audit,

    home_sos.prev5_opp_strength_mean AS home_prev5_opp_strength_mean,
    away_sos.prev5_opp_strength_mean AS away_prev5_opp_strength_mean,
    home_sos.prev10_opp_strength_mean AS home_prev10_opp_strength_mean,
    away_sos.prev10_opp_strength_mean AS away_prev10_opp_strength_mean,
    home_sos.prev365d_opp_strength_mean AS home_prev365d_opp_strength_mean,
    away_sos.prev365d_opp_strength_mean AS away_prev365d_opp_strength_mean,

    home_sos.prev5_opp_strength_coverage_audit AS home_prev5_opp_strength_coverage_audit,
    away_sos.prev5_opp_strength_coverage_audit AS away_prev5_opp_strength_coverage_audit,
    home_sos.prev10_opp_strength_coverage_audit AS home_prev10_opp_strength_coverage_audit,
    away_sos.prev10_opp_strength_coverage_audit AS away_prev10_opp_strength_coverage_audit,
    home_sos.prev365d_opp_strength_coverage_audit AS home_prev365d_opp_strength_coverage_audit,
    away_sos.prev365d_opp_strength_coverage_audit AS away_prev365d_opp_strength_coverage_audit,

    'v2_technical_33_no_momentum'::text AS feature_set_name,
    NOW() AS created_at

FROM future_matches fm
JOIN match_context mc
    ON mc.historical_match_id = fm.historical_match_id
JOIN team_form_rates home_form
    ON home_form.historical_match_id = fm.historical_match_id
   AND home_form.team_id = fm.home_team_id
   AND home_form.team_side = 'home'
JOIN team_form_rates away_form
    ON away_form.historical_match_id = fm.historical_match_id
   AND away_form.team_id = fm.away_team_id
   AND away_form.team_side = 'away'
JOIN team_fifa home_fifa
    ON home_fifa.historical_match_id = fm.historical_match_id
   AND home_fifa.team_id = fm.home_team_id
   AND home_fifa.team_side = 'home'
JOIN team_fifa away_fifa
    ON away_fifa.historical_match_id = fm.historical_match_id
   AND away_fifa.team_id = fm.away_team_id
   AND away_fifa.team_side = 'away'
JOIN team_sos home_sos
    ON home_sos.historical_match_id = fm.historical_match_id
   AND home_sos.team_id = fm.home_team_id
   AND home_sos.team_side = 'home'
JOIN team_sos away_sos
    ON away_sos.historical_match_id = fm.historical_match_id
   AND away_sos.team_id = fm.away_team_id
   AND away_sos.team_side = 'away';

CREATE INDEX IF NOT EXISTS idx_match_prediction_v2_technical_33_match_id
    ON features.match_prediction_v2_technical_33 (historical_match_id);

CREATE INDEX IF NOT EXISTS idx_match_prediction_v2_technical_33_match_date
    ON features.match_prediction_v2_technical_33 (match_date);
