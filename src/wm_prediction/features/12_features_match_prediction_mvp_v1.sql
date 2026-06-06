CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.match_prediction_mvp_v1;

CREATE TABLE features.match_prediction_mvp_v1 AS
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
        prev.goals_for,
        prev.goals_against,
        prev.goal_diff,
        prev.points,
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
fifa_normalized AS (
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
        rank_int
    FROM staging.fifa_rankings
),
team_fifa AS (
    SELECT
        cur.historical_match_id,
        cur.team_id,
        cur.team_side,
        fr.ranking_date,
        fr.rank_int AS fifa_rank,
        (cur.match_date - fr.ranking_date) AS fifa_ranking_age_days,
        ROW_NUMBER() OVER (
            PARTITION BY cur.historical_match_id, cur.team_id, cur.team_side
            ORDER BY fr.ranking_date DESC
        ) AS rn
    FROM future_team_rows cur
    JOIN fifa_normalized fr
        ON fr.feature_team_name = cur.team_name
       AND fr.ranking_date < cur.match_date
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
   AND home_fifa.rn = 1
JOIN team_fifa away_fifa
    ON away_fifa.historical_match_id = fm.historical_match_id
   AND away_fifa.team_id = fm.away_team_id
   AND away_fifa.team_side = 'away'
   AND away_fifa.rn = 1;

CREATE INDEX IF NOT EXISTS idx_match_prediction_mvp_v1_match_id
    ON features.match_prediction_mvp_v1 (historical_match_id);

CREATE INDEX IF NOT EXISTS idx_match_prediction_mvp_v1_match_date
    ON features.match_prediction_mvp_v1 (match_date);
