CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.team_prediction_snapshot_mvp_v1;

CREATE TABLE features.team_prediction_snapshot_mvp_v1 AS
WITH wc_teams AS (
    SELECT home_team_id AS team_id, home_team_name AS team_name
    FROM features.match_prediction_mvp_v1

    UNION

    SELECT away_team_id AS team_id, away_team_name AS team_name
    FROM features.match_prediction_mvp_v1
),
snapshot_date AS (
    SELECT MIN(match_date)::date AS prediction_date
    FROM features.match_prediction_mvp_v1
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
latest_fifa AS (
    SELECT
        wt.team_id,
        wt.team_name,
        sd.prediction_date,
        fr.ranking_date,
        fr.rank_int AS fifa_rank,
        (sd.prediction_date - fr.ranking_date) AS fifa_ranking_age_days,
        ROW_NUMBER() OVER (
            PARTITION BY wt.team_id
            ORDER BY fr.ranking_date DESC
        ) AS rn
    FROM wc_teams wt
    CROSS JOIN snapshot_date sd
    JOIN fifa_normalized fr
        ON fr.feature_team_name = wt.team_name
       AND fr.ranking_date < sd.prediction_date
)
SELECT
    tf.team_id,
    tf.team_name,
    tf.prediction_date,

    tf.prev5_matches,
    tf.prev5_points::numeric / NULLIF(tf.prev5_matches, 0) AS prev5_points_per_match,
    tf.prev5_goals_for::numeric / NULLIF(tf.prev5_matches, 0) AS prev5_goals_for_per_match,
    tf.prev5_goals_against::numeric / NULLIF(tf.prev5_matches, 0) AS prev5_goals_against_per_match,
    tf.prev5_goal_diff::numeric / NULLIF(tf.prev5_matches, 0) AS prev5_goal_diff_per_match,

    tf.prev10_matches,
    tf.prev10_points::numeric / NULLIF(tf.prev10_matches, 0) AS prev10_points_per_match,
    tf.prev10_goals_for::numeric / NULLIF(tf.prev10_matches, 0) AS prev10_goals_for_per_match,
    tf.prev10_goals_against::numeric / NULLIF(tf.prev10_matches, 0) AS prev10_goals_against_per_match,
    tf.prev10_goal_diff::numeric / NULLIF(tf.prev10_matches, 0) AS prev10_goal_diff_per_match,

    tf.prev5y_matches,
    tf.prev5y_points::numeric / NULLIF(tf.prev5y_matches, 0) AS prev5y_points_per_match,
    tf.prev5y_goals_for::numeric / NULLIF(tf.prev5y_matches, 0) AS prev5y_goals_for_per_match,
    tf.prev5y_goals_against::numeric / NULLIF(tf.prev5y_matches, 0) AS prev5y_goals_against_per_match,
    tf.prev5y_goal_diff::numeric / NULLIF(tf.prev5y_matches, 0) AS prev5y_goal_diff_per_match,

    lf.ranking_date AS fifa_ranking_date,
    lf.fifa_rank,
    lf.fifa_ranking_age_days,

    NOW() AS created_at
FROM team_form tf
JOIN latest_fifa lf
    ON lf.team_id = tf.team_id
   AND lf.rn = 1;

CREATE INDEX IF NOT EXISTS idx_team_prediction_snapshot_mvp_v1_team_id
    ON features.team_prediction_snapshot_mvp_v1 (team_id);

CREATE INDEX IF NOT EXISTS idx_team_prediction_snapshot_mvp_v1_team_name
    ON features.team_prediction_snapshot_mvp_v1 (team_name);
