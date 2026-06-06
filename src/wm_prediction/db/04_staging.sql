-- ============================================================
-- 04_minimal_staging.sql
--
-- Ziel:
-- Nur das minimale Staging für Montag bauen.
--
-- Wird neu gebaut:
-- 1. staging.team_name_aliases
-- 2. staging.current_fifa_rankings
-- 3. staging.historical_matches
-- 4. staging.national_team_profiles
-- 5. staging.world_cup_2026_matches_raw_ids
--
-- Wird NICHT neu gebaut:
-- - staging.elo_ratings
-- - staging.fifa_rankings
-- - staging.team_mapping
-- ============================================================


CREATE SCHEMA IF NOT EXISTS staging;


-- ============================================================
-- 1. Zentrale Alias-Tabelle
-- ------------------------------------------------------------
-- Die Alias-Tabelle wird zentral in staging.sql aufgebaut.
-- Dieses Script nutzt staging.team_name_aliases nur noch read-only.
-- ============================================================


-- ============================================================
-- 2. Current FIFA Ranking stagen
-- ============================================================

DROP TABLE IF EXISTS staging.current_fifa_rankings;

CREATE TABLE staging.current_fifa_rankings AS
WITH parsed AS (
    SELECT
        f.*,

        btrim(
            COALESCE(
                substring(f.team_name FROM $$'Description': '([^']+)'$$),
                f.team_name
            )
        ) AS fifa_team_name
    FROM raw.atheels_datasets_fifa_ranking f
),
mapped AS (
    SELECT
        p.*,
        COALESCE(a.canonical_name, p.fifa_team_name) AS mapped_canonical_name
    FROM parsed p
    LEFT JOIN staging.team_name_aliases a
        ON p.fifa_team_name = a.source_name
)
SELECT
    tm.team_id,
    m.mapped_canonical_name AS canonical_name,

    m.id_team AS fifa_team_id,
    m.fifa_team_name,
    m.id_country AS fifa_country_code,

    NULLIF(m.gender, '')::NUMERIC::INT AS gender,
    m.id_confederation,
    m.confederation_name,

    NULLIF(m.rank, '')::NUMERIC::INT AS fifa_rank,
    NULLIF(m.prev_rank, '')::NUMERIC::INT AS previous_fifa_rank,

    NULLIF(m.total_points, '')::NUMERIC AS fifa_total_points,
    NULLIF(m.prev_points, '')::NUMERIC AS previous_fifa_points,

    NULLIF(m.ranking_movement, '')::NUMERIC AS ranking_movement,
    NULLIF(m.rated_matches, '')::NUMERIC::INT AS rated_matches,

    m.ranking_status,
    m.properties,
    m.is_updateable,

    CURRENT_TIMESTAMP AS staged_at
FROM mapped m
LEFT JOIN staging.team_mapping tm
    ON tm.canonical_name = m.mapped_canonical_name;


-- ============================================================
-- 2b. Current FIFA Infos zurück in team_mapping schreiben
-- ------------------------------------------------------------
-- Das verändert nicht die IDs deiner team_mapping-Tabelle.
-- Es ergänzt nur fifa_team_id, fifa_country_code, fifa_name.
-- ============================================================

UPDATE staging.team_mapping tm
SET
    fifa_team_id = c.fifa_team_id,
    fifa_country_code = c.fifa_country_code,
    fifa_name = c.fifa_team_name
FROM staging.current_fifa_rankings c
WHERE tm.team_id = c.team_id
  AND c.team_id IS NOT NULL;



-- ============================================================
-- 3. Historische Spiele stagen
-- ------------------------------------------------------------
-- Quelle:
-- raw.atheels_datasets_results
--
-- Problem:
-- Manche Scores sind "NA".
-- Deshalb casten wir nur echte Zahlen zu INT.
-- ============================================================

DROP TABLE IF EXISTS staging.historical_matches;

CREATE TABLE staging.historical_matches AS
WITH parsed AS (
    SELECT
        r.*,

        COALESCE(ha.canonical_name, r.home_team) AS mapped_home_team,
        COALESCE(aa.canonical_name, r.away_team) AS mapped_away_team
    FROM raw.atheels_datasets_results r
    LEFT JOIN staging.team_name_aliases ha
        ON r.home_team = ha.source_name
    LEFT JOIN staging.team_name_aliases aa
        ON r.away_team = aa.source_name
),
typed AS (
    SELECT
        p.*,

        CASE
            WHEN trim(p.date) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            THEN trim(p.date)::DATE
            ELSE NULL
        END AS match_date_clean,

        CASE
            WHEN trim(p.home_score) ~ '^[0-9]+(\.0+)?$'
            THEN trim(p.home_score)::NUMERIC::INT
            ELSE NULL
        END AS home_score_clean,

        CASE
            WHEN trim(p.away_score) ~ '^[0-9]+(\.0+)?$'
            THEN trim(p.away_score)::NUMERIC::INT
            ELSE NULL
        END AS away_score_clean,

        CASE
            WHEN LOWER(trim(COALESCE(p.neutral, ''))) IN ('true', 't', '1', 'yes') THEN TRUE
            WHEN LOWER(trim(COALESCE(p.neutral, ''))) IN ('false', 'f', '0', 'no') THEN FALSE
            ELSE NULL
        END AS neutral_clean

    FROM parsed p
)
SELECT
    ROW_NUMBER() OVER (
        ORDER BY t.match_date_clean, t.home_team, t.away_team
    ) AS historical_match_id,

    t.match_date_clean AS match_date,

    home_tm.team_id AS home_team_id,
    away_tm.team_id AS away_team_id,

    t.mapped_home_team AS home_canonical_name,
    t.mapped_away_team AS away_canonical_name,

    t.home_team AS raw_home_team,
    t.away_team AS raw_away_team,

    t.home_score_clean AS home_score,
    t.away_score_clean AS away_score,

    t.tournament,
    t.city,
    t.country,

    t.neutral_clean AS neutral,

    CASE
        WHEN t.home_score_clean IS NULL OR t.away_score_clean IS NULL THEN NULL
        WHEN t.home_score_clean > t.away_score_clean THEN 'HOME_WIN'
        WHEN t.home_score_clean < t.away_score_clean THEN 'AWAY_WIN'
        WHEN t.home_score_clean = t.away_score_clean THEN 'DRAW'
        ELSE NULL
    END AS result_label,

    CURRENT_TIMESTAMP AS staged_at

FROM typed t
LEFT JOIN staging.team_mapping home_tm
    ON home_tm.canonical_name = t.mapped_home_team
LEFT JOIN staging.team_mapping away_tm
    ON away_tm.canonical_name = t.mapped_away_team;


-- ============================================================
-- 4. Nationalteam-Profile stagen
-- ------------------------------------------------------------
-- Quelle:
-- raw.kaggle_player_scores_national_teams
--
-- Das ist noch kein Feature.
-- Es ist nur sauber typisiertes Staging:
-- Marktwert, Durchschnittsalter, Kadergröße, Coach usw.
--
-- Ergebnis:
-- staging.national_team_profiles
-- ============================================================

DROP TABLE IF EXISTS staging.national_team_profiles;

CREATE TABLE staging.national_team_profiles AS
WITH parsed AS (
    SELECT
        n.*,
        COALESCE(a.canonical_name, n.name) AS mapped_canonical_name
    FROM raw.kaggle_player_scores_national_teams n
    LEFT JOIN staging.team_name_aliases a
        ON n.name = a.source_name
)
SELECT
    COALESCE(tm_by_id.team_id, tm_by_name.team_id) AS team_id,
    COALESCE(tm_by_id.canonical_name, tm_by_name.canonical_name, p.mapped_canonical_name) AS canonical_name,

    p.national_team_id,
    p.name AS raw_team_name,
    p.team_code,
    p.country_id,
    p.country_name,
    p.country_code,
    p.confederation,

    CASE
        WHEN p.squad_size ~ '^[0-9]+$' THEN p.squad_size::INT
        ELSE NULL
    END AS squad_size,

    CASE
        WHEN p.average_age ~ '^[0-9]+(\.[0-9]+)?$' THEN p.average_age::NUMERIC
        ELSE NULL
    END AS average_age,

    CASE
        WHEN p.foreigners_number ~ '^[0-9]+$' THEN p.foreigners_number::INT
        ELSE NULL
    END AS foreigners_number,

    CASE
        WHEN p.foreigners_percentage ~ '^[0-9]+(\.[0-9]+)?$' THEN p.foreigners_percentage::NUMERIC
        ELSE NULL
    END AS foreigners_percentage,

    CASE
        WHEN p.total_market_value ~ '^[0-9]+$' THEN p.total_market_value::NUMERIC
        ELSE NULL
    END AS total_market_value_eur,

    p.coach_name,

    CASE
        WHEN p.fifa_ranking ~ '^[0-9]+$' THEN p.fifa_ranking::INT
        ELSE NULL
    END AS kaggle_fifa_ranking,

    CASE
        WHEN p.last_season ~ '^[0-9]+$' THEN p.last_season::INT
        ELSE NULL
    END AS last_season,

    p.url,
    p.team_image_url,

    CURRENT_TIMESTAMP AS staged_at
FROM parsed p
LEFT JOIN staging.team_mapping tm_by_id
    ON tm_by_id.kaggle_national_team_id = p.national_team_id
LEFT JOIN staging.team_mapping tm_by_name
    ON tm_by_name.canonical_name = p.mapped_canonical_name;






-- ============================================================
-- 6. Kleine Checks
-- ------------------------------------------------------------
-- Diese SELECTs zeigen dir direkt, ob das Staging funktioniert hat.
-- ============================================================

SELECT
    'current_fifa_rankings' AS table_name,
    COUNT(*) AS rows_total,
    COUNT(*) FILTER (WHERE team_id IS NOT NULL) AS mapped_rows,
    COUNT(*) FILTER (WHERE team_id IS NULL) AS unmapped_rows
FROM staging.current_fifa_rankings;

SELECT
    'historical_matches' AS table_name,
    COUNT(*) AS rows_total,
    COUNT(*) FILTER (
        WHERE home_team_id IS NOT NULL
          AND away_team_id IS NOT NULL
    ) AS fully_mapped_rows,
    COUNT(*) FILTER (
        WHERE home_team_id IS NULL
           OR away_team_id IS NULL
    ) AS rows_with_missing_team_mapping
FROM staging.historical_matches;

SELECT
    'national_team_profiles' AS table_name,
    COUNT(*) AS rows_total,
    COUNT(*) FILTER (WHERE team_id IS NOT NULL) AS mapped_rows,
    COUNT(*) FILTER (WHERE team_id IS NULL) AS unmapped_rows
FROM staging.national_team_profiles;




-- ============================================================
-- 7. Falls etwas nicht gemappt wurde: anzeigen
-- ============================================================

SELECT
    fifa_team_name,
    canonical_name,
    fifa_rank
FROM staging.current_fifa_rankings
WHERE team_id IS NULL
ORDER BY fifa_team_name;

SELECT DISTINCT
    raw_home_team,
    home_canonical_name
FROM staging.historical_matches
WHERE home_team_id IS NULL
ORDER BY raw_home_team;

SELECT DISTINCT
    raw_away_team,
    away_canonical_name
FROM staging.historical_matches
WHERE away_team_id IS NULL
ORDER BY raw_away_team;

SELECT
    raw_team_name,
    canonical_name,
    national_team_id
FROM staging.national_team_profiles
WHERE team_id IS NULL
ORDER BY raw_team_name;