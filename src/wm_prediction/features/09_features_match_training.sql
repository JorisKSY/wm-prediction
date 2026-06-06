-- 09_features_match_training.sql
-- Match-level training table for two-stage modeling.
--
-- One row per played historical match.
--
-- Leakage rule:
-- All feature inputs come from feature tables that only use information
-- available strictly before match_date, plus match metadata known before kickoff.
--
-- Outputs:
-- - features.match_features_training

CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.match_features_training;

CREATE TABLE features.match_features_training AS
SELECT
    home.historical_match_id,
    home.match_date,

    ctx.match_year,
    ctx.match_month,
    ctx.tournament,
    ctx.tournament_bucket,
    ctx.city,
    ctx.country,
    ctx.is_neutral,
    ctx.is_friendly,
    ctx.is_world_cup,
    ctx.is_world_cup_qualifier,
    ctx.is_major_continental_tournament,
    ctx.is_continental_qualifier,
    ctx.is_nations_league,

    home.team_id AS home_team_id,
    away.team_id AS away_team_id,
    home.team_name AS home_team_name,
    away.team_name AS away_team_name,

    -- Stage 1 targets.
    home.goals_for AS home_goals,
    away.goals_for AS away_goals,

    -- Result target/audit fields.
    home.goals_for - away.goals_for AS home_goal_diff,
    CASE
        WHEN home.goals_for > away.goals_for THEN 'HOME_WIN'
        WHEN home.goals_for = away.goals_for THEN 'DRAW'
        ELSE 'AWAY_WIN'
    END AS result_label,

    -- Home form features.
    home.prev5_matches AS home_prev5_matches,
    home.prev5_points_per_match AS home_prev5_points_per_match,
    home.prev5_win_rate AS home_prev5_win_rate,
    home.prev5_draw_rate AS home_prev5_draw_rate,
    home.prev5_loss_rate AS home_prev5_loss_rate,
    home.prev5_goals_for_per_match AS home_prev5_goals_for_per_match,
    home.prev5_goals_against_per_match AS home_prev5_goals_against_per_match,
    home.prev5_goal_diff_per_match AS home_prev5_goal_diff_per_match,

    home.prev10_matches AS home_prev10_matches,
    home.prev10_points_per_match AS home_prev10_points_per_match,
    home.prev10_win_rate AS home_prev10_win_rate,
    home.prev10_draw_rate AS home_prev10_draw_rate,
    home.prev10_loss_rate AS home_prev10_loss_rate,
    home.prev10_goals_for_per_match AS home_prev10_goals_for_per_match,
    home.prev10_goals_against_per_match AS home_prev10_goals_against_per_match,
    home.prev10_goal_diff_per_match AS home_prev10_goal_diff_per_match,

    home.prev365d_matches AS home_prev365d_matches,
    home.prev365d_points_per_match AS home_prev365d_points_per_match,
    home.prev365d_win_rate AS home_prev365d_win_rate,
    home.prev365d_draw_rate AS home_prev365d_draw_rate,
    home.prev365d_loss_rate AS home_prev365d_loss_rate,
    home.prev365d_goals_for_per_match AS home_prev365d_goals_for_per_match,
    home.prev365d_goals_against_per_match AS home_prev365d_goals_against_per_match,
    home.prev365d_goal_diff_per_match AS home_prev365d_goal_diff_per_match,

    home.prev5y_matches AS home_prev5y_matches,
    home.prev5y_points_per_match AS home_prev5y_points_per_match,
    home.prev5y_win_rate AS home_prev5y_win_rate,
    home.prev5y_draw_rate AS home_prev5y_draw_rate,
    home.prev5y_loss_rate AS home_prev5y_loss_rate,
    home.prev5y_goals_for_per_match AS home_prev5y_goals_for_per_match,
    home.prev5y_goals_against_per_match AS home_prev5y_goals_against_per_match,
    home.prev5y_goal_diff_per_match AS home_prev5y_goal_diff_per_match,

    -- Away form features.
    away.prev5_matches AS away_prev5_matches,
    away.prev5_points_per_match AS away_prev5_points_per_match,
    away.prev5_win_rate AS away_prev5_win_rate,
    away.prev5_draw_rate AS away_prev5_draw_rate,
    away.prev5_loss_rate AS away_prev5_loss_rate,
    away.prev5_goals_for_per_match AS away_prev5_goals_for_per_match,
    away.prev5_goals_against_per_match AS away_prev5_goals_against_per_match,
    away.prev5_goal_diff_per_match AS away_prev5_goal_diff_per_match,

    away.prev10_matches AS away_prev10_matches,
    away.prev10_points_per_match AS away_prev10_points_per_match,
    away.prev10_win_rate AS away_prev10_win_rate,
    away.prev10_draw_rate AS away_prev10_draw_rate,
    away.prev10_loss_rate AS away_prev10_loss_rate,
    away.prev10_goals_for_per_match AS away_prev10_goals_for_per_match,
    away.prev10_goals_against_per_match AS away_prev10_goals_against_per_match,
    away.prev10_goal_diff_per_match AS away_prev10_goal_diff_per_match,

    away.prev365d_matches AS away_prev365d_matches,
    away.prev365d_points_per_match AS away_prev365d_points_per_match,
    away.prev365d_win_rate AS away_prev365d_win_rate,
    away.prev365d_draw_rate AS away_prev365d_draw_rate,
    away.prev365d_loss_rate AS away_prev365d_loss_rate,
    away.prev365d_goals_for_per_match AS away_prev365d_goals_for_per_match,
    away.prev365d_goals_against_per_match AS away_prev365d_goals_against_per_match,
    away.prev365d_goal_diff_per_match AS away_prev365d_goal_diff_per_match,

    away.prev5y_matches AS away_prev5y_matches,
    away.prev5y_points_per_match AS away_prev5y_points_per_match,
    away.prev5y_win_rate AS away_prev5y_win_rate,
    away.prev5y_draw_rate AS away_prev5y_draw_rate,
    away.prev5y_loss_rate AS away_prev5y_loss_rate,
    away.prev5y_goals_for_per_match AS away_prev5y_goals_for_per_match,
    away.prev5y_goals_against_per_match AS away_prev5y_goals_against_per_match,
    away.prev5y_goal_diff_per_match AS away_prev5y_goal_diff_per_match,

    -- Relative form features: home minus away.
    home.prev5_points_per_match - away.prev5_points_per_match AS prev5_points_per_match_diff,
    home.prev5_goal_diff_per_match - away.prev5_goal_diff_per_match AS prev5_goal_diff_per_match_diff,
    home.prev10_points_per_match - away.prev10_points_per_match AS prev10_points_per_match_diff,
    home.prev10_goal_diff_per_match - away.prev10_goal_diff_per_match AS prev10_goal_diff_per_match_diff,
    home.prev365d_points_per_match - away.prev365d_points_per_match AS prev365d_points_per_match_diff,
    home.prev365d_goal_diff_per_match - away.prev365d_goal_diff_per_match AS prev365d_goal_diff_per_match_diff,
    home.prev5y_points_per_match - away.prev5y_points_per_match AS prev5y_points_per_match_diff,
    home.prev5y_goal_diff_per_match - away.prev5y_goal_diff_per_match AS prev5y_goal_diff_per_match_diff,

    -- Historical FIFA ranking features.
    home_fifa.fifa_ranking_date AS home_fifa_ranking_date,
    home_fifa.fifa_rank AS home_fifa_rank,
    home_fifa.fifa_total_points AS home_fifa_total_points,
    home_fifa.fifa_diff_points AS home_fifa_diff_points,
    home_fifa.fifa_ranking_age_days AS home_fifa_ranking_age_days,
    home_fifa.has_fifa_ranking_before_match AS home_has_fifa_ranking_before_match,

    away_fifa.fifa_ranking_date AS away_fifa_ranking_date,
    away_fifa.fifa_rank AS away_fifa_rank,
    away_fifa.fifa_total_points AS away_fifa_total_points,
    away_fifa.fifa_diff_points AS away_fifa_diff_points,
    away_fifa.fifa_ranking_age_days AS away_fifa_ranking_age_days,
    away_fifa.has_fifa_ranking_before_match AS away_has_fifa_ranking_before_match,

    -- Relative FIFA features. Lower rank is better.
    home_fifa.fifa_rank - away_fifa.fifa_rank AS fifa_rank_diff_home_minus_away,
    home_fifa.fifa_total_points - away_fifa.fifa_total_points AS fifa_points_diff_home_minus_away,

    now() AS created_at
FROM features.team_form_before_match home
JOIN features.team_form_before_match away
    ON away.historical_match_id = home.historical_match_id
   AND away.team_side = 'away'
JOIN features.match_context ctx
    ON ctx.historical_match_id = home.historical_match_id
JOIN features.team_fifa_ranking_before_match home_fifa
    ON home_fifa.historical_match_id = home.historical_match_id
   AND home_fifa.team_id = home.team_id
JOIN features.team_fifa_ranking_before_match away_fifa
    ON away_fifa.historical_match_id = away.historical_match_id
   AND away_fifa.team_id = away.team_id
WHERE home.team_side = 'home';

CREATE UNIQUE INDEX IF NOT EXISTS ux_match_features_training_match
    ON features.match_features_training (historical_match_id);

CREATE INDEX IF NOT EXISTS idx_match_features_training_date
    ON features.match_features_training (match_date);

CREATE INDEX IF NOT EXISTS idx_match_features_training_teams
    ON features.match_features_training (home_team_id, away_team_id);

CREATE INDEX IF NOT EXISTS idx_match_features_training_bucket
    ON features.match_features_training (tournament_bucket);
