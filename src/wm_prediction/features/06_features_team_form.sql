-- 06_features_team_form.sql
-- Team-level time-dependent form features.
--
-- Leakage rule:
-- All feature values must only use matches that happened strictly before
-- the match_date of the row being predicted.
--
-- Outputs:
-- - features.team_match_rows
-- - features.team_form_before_match
--
-- This file intentionally does NOT use:
-- - current FIFA rankings
-- - current Elo snapshots
-- - current market value snapshots
-- - national_team_profiles snapshot fields

CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.team_match_rows;

CREATE TABLE features.team_match_rows AS
WITH played_matches AS (
    SELECT
        historical_match_id,
        match_date,
        home_team_id,
        away_team_id,
        home_canonical_name,
        away_canonical_name,
        home_score,
        away_score,
        tournament,
        city,
        country,
        neutral
    FROM staging.historical_matches
    WHERE home_score IS NOT NULL
      AND away_score IS NOT NULL
      AND home_team_id IS NOT NULL
      AND away_team_id IS NOT NULL
),
team_rows AS (
    SELECT
        historical_match_id,
        match_date,
        home_team_id AS team_id,
        away_team_id AS opponent_team_id,
        home_canonical_name AS team_name,
        away_canonical_name AS opponent_team_name,
        'home'::text AS team_side,
        home_score AS goals_for,
        away_score AS goals_against,
        CASE
            WHEN home_score > away_score THEN 'WIN'
            WHEN home_score = away_score THEN 'DRAW'
            ELSE 'LOSS'
        END AS team_result,
        tournament,
        city,
        country,
        neutral
    FROM played_matches

    UNION ALL

    SELECT
        historical_match_id,
        match_date,
        away_team_id AS team_id,
        home_team_id AS opponent_team_id,
        away_canonical_name AS team_name,
        home_canonical_name AS opponent_team_name,
        'away'::text AS team_side,
        away_score AS goals_for,
        home_score AS goals_against,
        CASE
            WHEN away_score > home_score THEN 'WIN'
            WHEN away_score = home_score THEN 'DRAW'
            ELSE 'LOSS'
        END AS team_result,
        tournament,
        city,
        country,
        neutral
    FROM played_matches
)
SELECT
    historical_match_id,
    match_date,
    team_id,
    opponent_team_id,
    team_name,
    opponent_team_name,
    team_side,
    goals_for,
    goals_against,
    goals_for - goals_against AS goal_diff,
    CASE team_result
        WHEN 'WIN' THEN 3
        WHEN 'DRAW' THEN 1
        ELSE 0
    END AS points,
    team_result,
    tournament,
    city,
    country,
    neutral,
    now() AS created_at
FROM team_rows;

CREATE INDEX IF NOT EXISTS idx_team_match_rows_team_date
    ON features.team_match_rows (team_id, match_date, historical_match_id);

CREATE INDEX IF NOT EXISTS idx_team_match_rows_match
    ON features.team_match_rows (historical_match_id);


DROP TABLE IF EXISTS features.team_form_before_match;

CREATE TABLE features.team_form_before_match AS
SELECT
    cur.historical_match_id,
    cur.match_date,
    cur.team_id,
    cur.opponent_team_id,
    cur.team_name,
    cur.opponent_team_name,
    cur.team_side,
    cur.tournament,
    cur.city,
    cur.country,
    cur.neutral,

    -- Current match outcome columns are kept for later training targets/audits.
    cur.goals_for,
    cur.goals_against,
    cur.goal_diff,
    cur.points,
    cur.team_result,

    -- Previous 5 matches before match_date.
    prev5.matches AS prev5_matches,
    prev5.points AS prev5_points,
    prev5.wins AS prev5_wins,
    prev5.draws AS prev5_draws,
    prev5.losses AS prev5_losses,
    prev5.goals_for AS prev5_goals_for,
    prev5.goals_against AS prev5_goals_against,
    prev5.goal_diff AS prev5_goal_diff,
    prev5.points::numeric / NULLIF(prev5.matches, 0) AS prev5_points_per_match,
    prev5.wins::numeric / NULLIF(prev5.matches, 0) AS prev5_win_rate,
    prev5.draws::numeric / NULLIF(prev5.matches, 0) AS prev5_draw_rate,
    prev5.losses::numeric / NULLIF(prev5.matches, 0) AS prev5_loss_rate,
    prev5.goals_for::numeric / NULLIF(prev5.matches, 0) AS prev5_goals_for_per_match,
    prev5.goals_against::numeric / NULLIF(prev5.matches, 0) AS prev5_goals_against_per_match,
    prev5.goal_diff::numeric / NULLIF(prev5.matches, 0) AS prev5_goal_diff_per_match,

    -- Previous 10 matches before match_date.
    prev10.matches AS prev10_matches,
    prev10.points AS prev10_points,
    prev10.wins AS prev10_wins,
    prev10.draws AS prev10_draws,
    prev10.losses AS prev10_losses,
    prev10.goals_for AS prev10_goals_for,
    prev10.goals_against AS prev10_goals_against,
    prev10.goal_diff AS prev10_goal_diff,
    prev10.points::numeric / NULLIF(prev10.matches, 0) AS prev10_points_per_match,
    prev10.wins::numeric / NULLIF(prev10.matches, 0) AS prev10_win_rate,
    prev10.draws::numeric / NULLIF(prev10.matches, 0) AS prev10_draw_rate,
    prev10.losses::numeric / NULLIF(prev10.matches, 0) AS prev10_loss_rate,
    prev10.goals_for::numeric / NULLIF(prev10.matches, 0) AS prev10_goals_for_per_match,
    prev10.goals_against::numeric / NULLIF(prev10.matches, 0) AS prev10_goals_against_per_match,
    prev10.goal_diff::numeric / NULLIF(prev10.matches, 0) AS prev10_goal_diff_per_match,

    -- Previous 365 days before match_date.
    prev365d.matches AS prev365d_matches,
    prev365d.points AS prev365d_points,
    prev365d.wins AS prev365d_wins,
    prev365d.draws AS prev365d_draws,
    prev365d.losses AS prev365d_losses,
    prev365d.goals_for AS prev365d_goals_for,
    prev365d.goals_against AS prev365d_goals_against,
    prev365d.goal_diff AS prev365d_goal_diff,
    prev365d.points::numeric / NULLIF(prev365d.matches, 0) AS prev365d_points_per_match,
    prev365d.wins::numeric / NULLIF(prev365d.matches, 0) AS prev365d_win_rate,
    prev365d.draws::numeric / NULLIF(prev365d.matches, 0) AS prev365d_draw_rate,
    prev365d.losses::numeric / NULLIF(prev365d.matches, 0) AS prev365d_loss_rate,
    prev365d.goals_for::numeric / NULLIF(prev365d.matches, 0) AS prev365d_goals_for_per_match,
    prev365d.goals_against::numeric / NULLIF(prev365d.matches, 0) AS prev365d_goals_against_per_match,
    prev365d.goal_diff::numeric / NULLIF(prev365d.matches, 0) AS prev365d_goal_diff_per_match,

    -- Previous 5 years before match_date.
    prev5y.matches AS prev5y_matches,
    prev5y.points AS prev5y_points,
    prev5y.wins AS prev5y_wins,
    prev5y.draws AS prev5y_draws,
    prev5y.losses AS prev5y_losses,
    prev5y.goals_for AS prev5y_goals_for,
    prev5y.goals_against AS prev5y_goals_against,
    prev5y.goal_diff AS prev5y_goal_diff,
    prev5y.points::numeric / NULLIF(prev5y.matches, 0) AS prev5y_points_per_match,
    prev5y.wins::numeric / NULLIF(prev5y.matches, 0) AS prev5y_win_rate,
    prev5y.draws::numeric / NULLIF(prev5y.matches, 0) AS prev5y_draw_rate,
    prev5y.losses::numeric / NULLIF(prev5y.matches, 0) AS prev5y_loss_rate,
    prev5y.goals_for::numeric / NULLIF(prev5y.matches, 0) AS prev5y_goals_for_per_match,
    prev5y.goals_against::numeric / NULLIF(prev5y.matches, 0) AS prev5y_goals_against_per_match,
    prev5y.goal_diff::numeric / NULLIF(prev5y.matches, 0) AS prev5y_goal_diff_per_match,

    now() AS created_at
FROM features.team_match_rows cur
LEFT JOIN LATERAL (
    SELECT
        COUNT(*)::integer AS matches,
        COALESCE(SUM(points), 0)::integer AS points,
        COALESCE(SUM((team_result = 'WIN')::integer), 0)::integer AS wins,
        COALESCE(SUM((team_result = 'DRAW')::integer), 0)::integer AS draws,
        COALESCE(SUM((team_result = 'LOSS')::integer), 0)::integer AS losses,
        COALESCE(SUM(goals_for), 0)::integer AS goals_for,
        COALESCE(SUM(goals_against), 0)::integer AS goals_against,
        COALESCE(SUM(goal_diff), 0)::integer AS goal_diff
    FROM (
        SELECT *
        FROM features.team_match_rows prev
        WHERE prev.team_id = cur.team_id
          AND prev.match_date < cur.match_date
        ORDER BY prev.match_date DESC, prev.historical_match_id DESC
        LIMIT 5
    ) x
) prev5 ON TRUE
LEFT JOIN LATERAL (
    SELECT
        COUNT(*)::integer AS matches,
        COALESCE(SUM(points), 0)::integer AS points,
        COALESCE(SUM((team_result = 'WIN')::integer), 0)::integer AS wins,
        COALESCE(SUM((team_result = 'DRAW')::integer), 0)::integer AS draws,
        COALESCE(SUM((team_result = 'LOSS')::integer), 0)::integer AS losses,
        COALESCE(SUM(goals_for), 0)::integer AS goals_for,
        COALESCE(SUM(goals_against), 0)::integer AS goals_against,
        COALESCE(SUM(goal_diff), 0)::integer AS goal_diff
    FROM (
        SELECT *
        FROM features.team_match_rows prev
        WHERE prev.team_id = cur.team_id
          AND prev.match_date < cur.match_date
        ORDER BY prev.match_date DESC, prev.historical_match_id DESC
        LIMIT 10
    ) x
) prev10 ON TRUE
LEFT JOIN LATERAL (
    SELECT
        COUNT(*)::integer AS matches,
        COALESCE(SUM(points), 0)::integer AS points,
        COALESCE(SUM((team_result = 'WIN')::integer), 0)::integer AS wins,
        COALESCE(SUM((team_result = 'DRAW')::integer), 0)::integer AS draws,
        COALESCE(SUM((team_result = 'LOSS')::integer), 0)::integer AS losses,
        COALESCE(SUM(goals_for), 0)::integer AS goals_for,
        COALESCE(SUM(goals_against), 0)::integer AS goals_against,
        COALESCE(SUM(goal_diff), 0)::integer AS goal_diff
    FROM features.team_match_rows prev
    WHERE prev.team_id = cur.team_id
      AND prev.match_date < cur.match_date
      AND prev.match_date >= cur.match_date - INTERVAL '365 days'
) prev365d ON TRUE
LEFT JOIN LATERAL (
    SELECT
        COUNT(*)::integer AS matches,
        COALESCE(SUM(points), 0)::integer AS points,
        COALESCE(SUM((team_result = 'WIN')::integer), 0)::integer AS wins,
        COALESCE(SUM((team_result = 'DRAW')::integer), 0)::integer AS draws,
        COALESCE(SUM((team_result = 'LOSS')::integer), 0)::integer AS losses,
        COALESCE(SUM(goals_for), 0)::integer AS goals_for,
        COALESCE(SUM(goals_against), 0)::integer AS goals_against,
        COALESCE(SUM(goal_diff), 0)::integer AS goal_diff
    FROM features.team_match_rows prev
    WHERE prev.team_id = cur.team_id
      AND prev.match_date < cur.match_date
      AND prev.match_date >= cur.match_date - INTERVAL '5 years'
) prev5y ON TRUE;

CREATE INDEX IF NOT EXISTS idx_team_form_before_match_team_date
    ON features.team_form_before_match (team_id, match_date, historical_match_id);

CREATE INDEX IF NOT EXISTS idx_team_form_before_match_match
    ON features.team_form_before_match (historical_match_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_team_match_rows_match_team
    ON features.team_match_rows (historical_match_id, team_id);

CREATE UNIQUE INDEX IF NOT EXISTS ux_team_form_before_match_match_team
    ON features.team_form_before_match (historical_match_id, team_id);
