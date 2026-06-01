-- ============================================================
-- 05_minimal_features.sql
--
-- Ziel:
-- Aus den gestagten Tabellen erste Feature-Tabellen bauen.
--
-- Voraussetzung:
-- staging.team_mapping
-- staging.current_fifa_rankings
-- staging.elo_ratings
-- staging.historical_matches
-- staging.national_team_profiles
--
-- Ergebnis:
-- features.team_strength_current
-- features.team_match_rows
-- features.team_form_current_last10
-- features.team_form_before_match
-- features.match_features_training_demo
-- features.baseline_evaluation_demo
-- ============================================================


CREATE SCHEMA IF NOT EXISTS features;


-- ============================================================
-- 0. Sicherheitscheck: existieren die benötigten Tabellen?
-- ============================================================

SELECT
    table_schema,
    table_name
FROM information_schema.tables
WHERE table_schema IN ('staging', 'features')
  AND table_name IN (
      'team_mapping',
      'current_fifa_rankings',
      'elo_ratings',
      'historical_matches',
      'national_team_profiles'
  )
ORDER BY table_schema, table_name;



-- ============================================================
-- 1. Teamstärke aktuell
-- ------------------------------------------------------------
-- Eine Zeile pro Team.
--
-- Hier kombinieren wir:
-- - Current FIFA Ranking
-- - Elo Rating
-- - Nationalteam-Profil / Marktwert / Kadergröße
--
-- Das ist noch kein Match-Feature.
-- Es beschreibt erstmal nur jedes Team.
-- ============================================================

DROP TABLE IF EXISTS features.team_strength_current;

CREATE TABLE features.team_strength_current AS
WITH fifa AS (
    SELECT DISTINCT ON (team_id)
        team_id,
        canonical_name,
        fifa_rank,
        fifa_total_points,
        previous_fifa_rank,
        previous_fifa_points,
        ranking_movement,
        rated_matches,
        confederation_name AS fifa_confederation
    FROM staging.current_fifa_rankings
    WHERE team_id IS NOT NULL
    ORDER BY team_id, fifa_rank NULLS LAST
),
elo AS (
    SELECT DISTINCT ON (team_id)
        team_id,
        canonical_name,

        CASE
            WHEN trim(rank) ~ '^[0-9]+(\.0+)?$'
            THEN trim(rank)::NUMERIC::INT
            ELSE NULL
        END AS elo_rank,

        CASE
            WHEN trim(elo_rating) ~ '^[0-9]+(\.[0-9]+)?$'
            THEN trim(elo_rating)::NUMERIC
            ELSE NULL
        END AS elo_rating,

        CASE
            WHEN trim(average_rating) ~ '^[0-9]+(\.[0-9]+)?$'
            THEN trim(average_rating)::NUMERIC
            ELSE NULL
        END AS elo_average_rating,

        CASE
            WHEN trim(matches_total) ~ '^[0-9]+(\.0+)?$'
            THEN trim(matches_total)::NUMERIC::INT
            ELSE NULL
        END AS elo_matches_total,

        CASE
            WHEN trim(wins) ~ '^[0-9]+(\.0+)?$'
            THEN trim(wins)::NUMERIC::INT
            ELSE NULL
        END AS elo_wins,

        CASE
            WHEN trim(draws) ~ '^[0-9]+(\.0+)?$'
            THEN trim(draws)::NUMERIC::INT
            ELSE NULL
        END AS elo_draws,

        CASE
            WHEN trim(losses) ~ '^[0-9]+(\.0+)?$'
            THEN trim(losses)::NUMERIC::INT
            ELSE NULL
        END AS elo_losses,

        CASE
            WHEN trim(goals_for) ~ '^[0-9]+(\.0+)?$'
            THEN trim(goals_for)::NUMERIC::INT
            ELSE NULL
        END AS elo_goals_for,

        CASE
            WHEN trim(goals_against) ~ '^[0-9]+(\.0+)?$'
            THEN trim(goals_against)::NUMERIC::INT
            ELSE NULL
        END AS elo_goals_against

    FROM staging.elo_ratings
    WHERE team_id IS NOT NULL
    ORDER BY team_id
),
ntp AS (
    SELECT DISTINCT ON (team_id)
        team_id,
        canonical_name,
        national_team_id,
        squad_size,
        average_age,
        foreigners_number,
        foreigners_percentage,
        total_market_value_eur,
        coach_name,
        confederation,
        kaggle_fifa_ranking
    FROM staging.national_team_profiles
    WHERE team_id IS NOT NULL
    ORDER BY team_id, last_season DESC NULLS LAST
)
SELECT
    tm.team_id,
    tm.canonical_name,

    -- FIFA
    fifa.fifa_rank,
    fifa.fifa_total_points,
    fifa.previous_fifa_rank,
    fifa.previous_fifa_points,
    fifa.ranking_movement,
    fifa.rated_matches,
    fifa.fifa_confederation,

    -- Elo
    elo.elo_rank,
    elo.elo_rating,
    elo.elo_average_rating,
    elo.elo_matches_total,
    elo.elo_wins,
    elo.elo_draws,
    elo.elo_losses,
    elo.elo_goals_for,
    elo.elo_goals_against,

    CASE
        WHEN elo.elo_matches_total IS NOT NULL
         AND elo.elo_matches_total > 0
        THEN ROUND(elo.elo_wins::NUMERIC / elo.elo_matches_total, 4)
        ELSE NULL
    END AS elo_win_rate,

    CASE
        WHEN elo.elo_matches_total IS NOT NULL
         AND elo.elo_matches_total > 0
        THEN ROUND(
            (elo.elo_goals_for - elo.elo_goals_against)::NUMERIC
            / elo.elo_matches_total,
            4
        )
        ELSE NULL
    END AS elo_goal_diff_per_match,

    -- Nationalteam Profil
    ntp.national_team_id,
    ntp.squad_size,
    ntp.average_age,
    ntp.foreigners_number,
    ntp.foreigners_percentage,
    ntp.total_market_value_eur,

    CASE
        WHEN ntp.total_market_value_eur IS NOT NULL
         AND ntp.total_market_value_eur > 0
        THEN ROUND(LN(ntp.total_market_value_eur + 1), 4)
        ELSE NULL
    END AS log_market_value,

    ntp.coach_name,
    ntp.confederation AS kaggle_confederation,
    ntp.kaggle_fifa_ranking,

    CURRENT_TIMESTAMP AS created_at

FROM staging.team_mapping tm
LEFT JOIN fifa
    ON fifa.team_id = tm.team_id
LEFT JOIN elo
    ON elo.team_id = tm.team_id
LEFT JOIN ntp
    ON ntp.team_id = tm.team_id
WHERE fifa.team_id IS NOT NULL
   OR elo.team_id IS NOT NULL
   OR ntp.team_id IS NOT NULL;



-- ============================================================
-- 2. Historische Spiele in Team-Perspektive umwandeln
-- ------------------------------------------------------------
-- Ein Spiel wird zu zwei Zeilen:
--
-- Deutschland vs Frankreich
-- wird:
-- Deutschland gegen Frankreich
-- Frankreich gegen Deutschland
--
-- Das brauchen wir für Form-Berechnungen.
-- ============================================================

DROP TABLE IF EXISTS features.team_match_rows;

CREATE TABLE features.team_match_rows AS
SELECT
    historical_match_id,
    match_date,

    home_team_id AS team_id,
    away_team_id AS opponent_team_id,

    home_canonical_name AS team_name,
    away_canonical_name AS opponent_name,

    TRUE AS is_home,
    neutral,

    home_score AS goals_for,
    away_score AS goals_against,

    CASE
        WHEN home_score > away_score THEN 'WIN'
        WHEN home_score < away_score THEN 'LOSS'
        WHEN home_score = away_score THEN 'DRAW'
        ELSE NULL
    END AS result_for_team,

    CASE
        WHEN home_score > away_score THEN 3
        WHEN home_score = away_score THEN 1
        WHEN home_score < away_score THEN 0
        ELSE NULL
    END AS points,

    tournament,
    city,
    country

FROM staging.historical_matches
WHERE home_team_id IS NOT NULL
  AND away_team_id IS NOT NULL
  AND home_score IS NOT NULL
  AND away_score IS NOT NULL
  AND match_date IS NOT NULL

UNION ALL

SELECT
    historical_match_id,
    match_date,

    away_team_id AS team_id,
    home_team_id AS opponent_team_id,

    away_canonical_name AS team_name,
    home_canonical_name AS opponent_name,

    FALSE AS is_home,
    neutral,

    away_score AS goals_for,
    home_score AS goals_against,

    CASE
        WHEN away_score > home_score THEN 'WIN'
        WHEN away_score < home_score THEN 'LOSS'
        WHEN away_score = home_score THEN 'DRAW'
        ELSE NULL
    END AS result_for_team,

    CASE
        WHEN away_score > home_score THEN 3
        WHEN away_score = home_score THEN 1
        WHEN away_score < home_score THEN 0
        ELSE NULL
    END AS points,

    tournament,
    city,
    country

FROM staging.historical_matches
WHERE home_team_id IS NOT NULL
  AND away_team_id IS NOT NULL
  AND home_score IS NOT NULL
  AND away_score IS NOT NULL
  AND match_date IS NOT NULL;



-- ============================================================
-- 3. Aktuelle Form: letzte 10 Spiele pro Team
-- ------------------------------------------------------------
-- Diese Tabelle ist gut zum Zeigen:
-- "Wie ist die aktuelle Form eines Teams?"
-- ============================================================

DROP TABLE IF EXISTS features.team_form_current_last10;

CREATE TABLE features.team_form_current_last10 AS
WITH numbered AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY team_id
            ORDER BY match_date DESC, historical_match_id DESC
        ) AS rn
    FROM features.team_match_rows
)
SELECT
    team_id,
    team_name,

    COUNT(*) AS last10_matches,

    COUNT(*) FILTER (WHERE result_for_team = 'WIN') AS last10_wins,
    COUNT(*) FILTER (WHERE result_for_team = 'DRAW') AS last10_draws,
    COUNT(*) FILTER (WHERE result_for_team = 'LOSS') AS last10_losses,

    SUM(points) AS last10_points,

    ROUND(AVG(points::NUMERIC), 4) AS last10_avg_points,
    ROUND(AVG(goals_for::NUMERIC), 4) AS last10_avg_goals_for,
    ROUND(AVG(goals_against::NUMERIC), 4) AS last10_avg_goals_against,
    ROUND(AVG((goals_for - goals_against)::NUMERIC), 4) AS last10_avg_goal_diff,

    ROUND(
        COUNT(*) FILTER (WHERE result_for_team = 'WIN')::NUMERIC
        / NULLIF(COUNT(*), 0),
        4
    ) AS last10_win_rate,

    MAX(match_date) AS latest_match_date,

    CURRENT_TIMESTAMP AS created_at

FROM numbered
WHERE rn <= 10
GROUP BY team_id, team_name;



-- ============================================================
-- 4. Rolling Form vor jedem Match
-- ------------------------------------------------------------
-- Wichtig für Modelltraining:
-- Bei einem historischen Spiel dürfen wir NICHT die Zukunft kennen.
--
-- Deshalb berechnen wir:
-- Form VOR dem jeweiligen Spiel.
--
-- Beispiel:
-- Spiel am 01.06.2022
-- dann werden nur Spiele davor benutzt.
-- ============================================================

DROP TABLE IF EXISTS features.team_form_before_match;

CREATE TABLE features.team_form_before_match AS
SELECT
    historical_match_id,
    match_date,
    team_id,
    team_name,
    opponent_team_id,
    opponent_name,
    is_home,

    COUNT(*) OVER (
        PARTITION BY team_id
        ORDER BY match_date, historical_match_id
        ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
    ) AS prev5_matches,

    ROUND(
        AVG(points::NUMERIC) OVER (
            PARTITION BY team_id
            ORDER BY match_date, historical_match_id
            ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
        ),
        4
    ) AS prev5_avg_points,

    ROUND(
        AVG(goals_for::NUMERIC) OVER (
            PARTITION BY team_id
            ORDER BY match_date, historical_match_id
            ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
        ),
        4
    ) AS prev5_avg_goals_for,

    ROUND(
        AVG(goals_against::NUMERIC) OVER (
            PARTITION BY team_id
            ORDER BY match_date, historical_match_id
            ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
        ),
        4
    ) AS prev5_avg_goals_against,

    ROUND(
        AVG((goals_for - goals_against)::NUMERIC) OVER (
            PARTITION BY team_id
            ORDER BY match_date, historical_match_id
            ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
        ),
        4
    ) AS prev5_avg_goal_diff

FROM features.team_match_rows;



-- ============================================================
-- 5. Match-Feature-Tabelle für Modell / Demo
-- ------------------------------------------------------------
-- Eine Zeile pro historischem Spiel.
--
-- Zielvariable:
-- result_label
--
-- Features:
-- - FIFA Rank Unterschied
-- - FIFA Punkte Unterschied
-- - Elo Rating Unterschied
-- - Marktwert Unterschied
-- - Form-Unterschied vor dem Spiel
-- - Heimvorteil / neutraler Ort
-- ============================================================

DROP TABLE IF EXISTS features.match_features_training_demo;

CREATE TABLE features.match_features_training_demo AS
SELECT
    hm.historical_match_id,
    hm.match_date,

    hm.home_team_id,
    hm.away_team_id,

    hm.home_canonical_name AS home_team,
    hm.away_canonical_name AS away_team,

    hm.home_score,
    hm.away_score,
    hm.result_label,

    hm.tournament,
    hm.city,
    hm.country,
    hm.neutral,

    -- Home Team Stärke
    home_strength.fifa_rank AS home_fifa_rank,
    home_strength.fifa_total_points AS home_fifa_total_points,
    home_strength.elo_rank AS home_elo_rank,
    home_strength.elo_rating AS home_elo_rating,
    home_strength.total_market_value_eur AS home_market_value_eur,
    home_strength.log_market_value AS home_log_market_value,
    home_strength.squad_size AS home_squad_size,
    home_strength.average_age AS home_average_age,

    -- Away Team Stärke
    away_strength.fifa_rank AS away_fifa_rank,
    away_strength.fifa_total_points AS away_fifa_total_points,
    away_strength.elo_rank AS away_elo_rank,
    away_strength.elo_rating AS away_elo_rating,
    away_strength.total_market_value_eur AS away_market_value_eur,
    away_strength.log_market_value AS away_log_market_value,
    away_strength.squad_size AS away_squad_size,
    away_strength.average_age AS away_average_age,

    -- Differenzen
    -- Bei FIFA Rank gilt: kleiner ist besser.
    -- Deshalb: away_rank - home_rank.
    -- Positiv bedeutet Vorteil Home.
    CASE
        WHEN home_strength.fifa_rank IS NOT NULL
         AND away_strength.fifa_rank IS NOT NULL
        THEN away_strength.fifa_rank - home_strength.fifa_rank
        ELSE NULL
    END AS fifa_rank_advantage_home,

    CASE
        WHEN home_strength.fifa_total_points IS NOT NULL
         AND away_strength.fifa_total_points IS NOT NULL
        THEN home_strength.fifa_total_points - away_strength.fifa_total_points
        ELSE NULL
    END AS fifa_points_advantage_home,

    CASE
        WHEN home_strength.elo_rating IS NOT NULL
         AND away_strength.elo_rating IS NOT NULL
        THEN home_strength.elo_rating - away_strength.elo_rating
        ELSE NULL
    END AS elo_rating_advantage_home,

    CASE
        WHEN home_strength.log_market_value IS NOT NULL
         AND away_strength.log_market_value IS NOT NULL
        THEN home_strength.log_market_value - away_strength.log_market_value
        ELSE NULL
    END AS log_market_value_advantage_home,

    CASE
        WHEN home_strength.average_age IS NOT NULL
         AND away_strength.average_age IS NOT NULL
        THEN home_strength.average_age - away_strength.average_age
        ELSE NULL
    END AS average_age_diff_home,

    CASE
        WHEN home_strength.squad_size IS NOT NULL
         AND away_strength.squad_size IS NOT NULL
        THEN home_strength.squad_size - away_strength.squad_size
        ELSE NULL
    END AS squad_size_diff_home,

    -- Form vor dem Spiel
    home_form.prev5_matches AS home_prev5_matches,
    home_form.prev5_avg_points AS home_prev5_avg_points,
    home_form.prev5_avg_goals_for AS home_prev5_avg_goals_for,
    home_form.prev5_avg_goals_against AS home_prev5_avg_goals_against,
    home_form.prev5_avg_goal_diff AS home_prev5_avg_goal_diff,

    away_form.prev5_matches AS away_prev5_matches,
    away_form.prev5_avg_points AS away_prev5_avg_points,
    away_form.prev5_avg_goals_for AS away_prev5_avg_goals_for,
    away_form.prev5_avg_goals_against AS away_prev5_avg_goals_against,
    away_form.prev5_avg_goal_diff AS away_prev5_avg_goal_diff,

    CASE
        WHEN home_form.prev5_avg_points IS NOT NULL
         AND away_form.prev5_avg_points IS NOT NULL
        THEN home_form.prev5_avg_points - away_form.prev5_avg_points
        ELSE NULL
    END AS form_points_advantage_home,

    CASE
        WHEN home_form.prev5_avg_goal_diff IS NOT NULL
         AND away_form.prev5_avg_goal_diff IS NOT NULL
        THEN home_form.prev5_avg_goal_diff - away_form.prev5_avg_goal_diff
        ELSE NULL
    END AS form_goal_diff_advantage_home,

    -- Einfache Home-Advantage-Variable
    CASE
        WHEN hm.neutral = TRUE THEN 0
        WHEN hm.neutral = FALSE THEN 1
        ELSE NULL
    END AS home_advantage_flag,

    CURRENT_TIMESTAMP AS created_at

FROM staging.historical_matches hm

LEFT JOIN features.team_strength_current home_strength
    ON home_strength.team_id = hm.home_team_id

LEFT JOIN features.team_strength_current away_strength
    ON away_strength.team_id = hm.away_team_id

LEFT JOIN features.team_form_before_match home_form
    ON home_form.historical_match_id = hm.historical_match_id
   AND home_form.team_id = hm.home_team_id

LEFT JOIN features.team_form_before_match away_form
    ON away_form.historical_match_id = hm.historical_match_id
   AND away_form.team_id = hm.away_team_id

WHERE hm.home_team_id IS NOT NULL
  AND hm.away_team_id IS NOT NULL
  AND hm.home_score IS NOT NULL
  AND hm.away_score IS NOT NULL
  AND hm.result_label IS NOT NULL;



-- ============================================================
-- 6. Sehr einfache Baseline Prediction
-- ------------------------------------------------------------
-- Das ist KEIN finales Modell.
-- Es ist nur eine nachvollziehbare Demo:
--
-- Elo + FIFA + Form + Heimvorteil → Ergebnis-Tendenz
-- ============================================================

DROP TABLE IF EXISTS features.baseline_predictions_demo;

CREATE TABLE features.baseline_predictions_demo AS
SELECT
    *,

    (
        COALESCE(elo_rating_advantage_home, 0)
        + COALESCE(fifa_rank_advantage_home, 0) * 3
        + COALESCE(form_points_advantage_home, 0) * 30
        + COALESCE(home_advantage_flag, 0) * 40
    ) AS simple_home_score,

    CASE
        WHEN (
            COALESCE(elo_rating_advantage_home, 0)
            + COALESCE(fifa_rank_advantage_home, 0) * 3
            + COALESCE(form_points_advantage_home, 0) * 30
            + COALESCE(home_advantage_flag, 0) * 40
        ) >= 75 THEN 'HOME_WIN'

        WHEN (
            COALESCE(elo_rating_advantage_home, 0)
            + COALESCE(fifa_rank_advantage_home, 0) * 3
            + COALESCE(form_points_advantage_home, 0) * 30
            + COALESCE(home_advantage_flag, 0) * 40
        ) <= -75 THEN 'AWAY_WIN'

        ELSE 'DRAW'
    END AS simple_predicted_result_label

FROM features.match_features_training_demo;



-- ============================================================
-- 7. Baseline Evaluation
-- ------------------------------------------------------------
-- Damit kannst du Montag eine Zahl zeigen:
-- Wie oft lag diese simple Baseline richtig?
-- ============================================================

DROP TABLE IF EXISTS features.baseline_evaluation_demo;

CREATE TABLE features.baseline_evaluation_demo AS
SELECT
    COUNT(*) AS matches_total,

    COUNT(*) FILTER (
        WHERE simple_predicted_result_label = result_label
    ) AS correct_predictions,

    ROUND(
        COUNT(*) FILTER (
            WHERE simple_predicted_result_label = result_label
        )::NUMERIC
        / NULLIF(COUNT(*), 0),
        4
    ) AS accuracy,

    COUNT(*) FILTER (WHERE result_label = 'HOME_WIN') AS real_home_wins,
    COUNT(*) FILTER (WHERE result_label = 'DRAW') AS real_draws,
    COUNT(*) FILTER (WHERE result_label = 'AWAY_WIN') AS real_away_wins,

    COUNT(*) FILTER (WHERE simple_predicted_result_label = 'HOME_WIN') AS predicted_home_wins,
    COUNT(*) FILTER (WHERE simple_predicted_result_label = 'DRAW') AS predicted_draws,
    COUNT(*) FILTER (WHERE simple_predicted_result_label = 'AWAY_WIN') AS predicted_away_wins,

    CURRENT_TIMESTAMP AS created_at

FROM features.baseline_predictions_demo;



-- ============================================================
-- 8. Checks / Ergebnisse anzeigen
-- ============================================================

SELECT
    'team_strength_current' AS table_name,
    COUNT(*) AS rows_total
FROM features.team_strength_current;

SELECT
    'team_match_rows' AS table_name,
    COUNT(*) AS rows_total
FROM features.team_match_rows;

SELECT
    'team_form_current_last10' AS table_name,
    COUNT(*) AS rows_total
FROM features.team_form_current_last10;

SELECT
    'match_features_training_demo' AS table_name,
    COUNT(*) AS rows_total
FROM features.match_features_training_demo;

SELECT *
FROM features.baseline_evaluation_demo;