-- ============================================================
-- player_staging.sql
--
-- Ziel:
-- Spieler-Staging Schritt für Schritt aufbauen.
--
-- Dieser erste Stand baut nur:
-- 1. staging.players
--
-- Raw-Tabellen werden nicht verändert.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS staging;


-- ============================================================
-- 1. Spieler-Basistabelle
-- ------------------------------------------------------------
-- Quelle:
-- raw.kaggle_player_scores_players
--
-- Zweck:
-- Eine typisierte, stabile Spieler-Identität pro player_id.
--
-- Hinweise:
-- - current_national_team_id ist ein aktueller Snapshot.
--   Für finale historische Features kann das Leakage verursachen,
--   wenn man es ungeprüft rückwirkend verwendet.
-- - Marktwerte in dieser Tabelle sind ebenfalls aktuelle Snapshots.
--   Zeitabhängige Marktwerte kommen später aus
--   staging.player_valuations.
-- ============================================================

DROP TABLE IF EXISTS staging.players;

CREATE TABLE staging.players AS
WITH typed AS (
    SELECT
        CASE
            WHEN player_id ~ '^[0-9]+$' THEN player_id::INT
            ELSE NULL
        END AS player_id,

        NULLIF(trim(first_name), '') AS first_name,
        NULLIF(trim(last_name), '') AS last_name,
        NULLIF(trim(name), '') AS player_name,
        NULLIF(trim(player_code), '') AS player_code,

        CASE
            WHEN last_season ~ '^[0-9]+$' THEN last_season::INT
            ELSE NULL
        END AS last_season,

        CASE
            WHEN current_club_id ~ '^[0-9]+$' THEN current_club_id::INT
            ELSE NULL
        END AS current_club_id,

        NULLIF(trim(current_club_name), '') AS current_club_name,
        NULLIF(trim(current_club_domestic_competition_id), '') AS current_club_domestic_competition_id,

        NULLIF(trim(country_of_birth), '') AS country_of_birth,
        NULLIF(trim(city_of_birth), '') AS city_of_birth,
        NULLIF(trim(country_of_citizenship), '') AS country_of_citizenship,

        CASE
            WHEN left(trim(date_of_birth), 10) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            THEN left(trim(date_of_birth), 10)::DATE
            ELSE NULL
        END AS date_of_birth,

        NULLIF(trim(position), '') AS position,
        NULLIF(trim(sub_position), '') AS sub_position,
        NULLIF(trim(foot), '') AS foot,

        CASE
            WHEN height_in_cm ~ '^[0-9]+$' THEN height_in_cm::INT
            ELSE NULL
        END AS height_cm,

        CASE
            WHEN left(trim(contract_expiration_date), 10) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
            THEN left(trim(contract_expiration_date), 10)::DATE
            ELSE NULL
        END AS contract_expiration_date,

        NULLIF(trim(agent_name), '') AS agent_name,
        NULLIF(trim(image_url), '') AS image_url,
        NULLIF(trim(url), '') AS url,

        CASE
            WHEN international_caps ~ '^[0-9]+$' THEN international_caps::INT
            ELSE NULL
        END AS international_caps,

        CASE
            WHEN international_goals ~ '^[0-9]+$' THEN international_goals::INT
            ELSE NULL
        END AS international_goals,

        CASE
            WHEN current_national_team_id ~ '^[0-9]+$' THEN current_national_team_id
            ELSE NULL
        END AS current_national_team_id,

        CASE
            WHEN market_value_in_eur ~ '^[0-9]+$' THEN market_value_in_eur::NUMERIC
            ELSE NULL
        END AS current_market_value_eur,

        CASE
            WHEN highest_market_value_in_eur ~ '^[0-9]+$' THEN highest_market_value_in_eur::NUMERIC
            ELSE NULL
        END AS highest_market_value_eur

    FROM raw.kaggle_player_scores_players
)
SELECT
    t.*,

    ntp.team_id AS current_national_team_team_id,
    ntp.canonical_name AS current_national_team_name,

    CURRENT_TIMESTAMP AS staged_at

FROM typed t
LEFT JOIN staging.national_team_profiles ntp
    ON ntp.national_team_id = t.current_national_team_id
WHERE t.player_id IS NOT NULL;


-- ============================================================
-- Checks
-- ============================================================

SELECT
    'players' AS table_name,
    count(*) AS rows_total,
    count(DISTINCT player_id) AS distinct_player_ids,
    count(*) FILTER (WHERE player_name IS NOT NULL) AS with_player_name,
    count(*) FILTER (WHERE date_of_birth IS NOT NULL) AS with_date_of_birth,
    count(*) FILTER (WHERE position IS NOT NULL) AS with_position,
    count(*) FILTER (WHERE current_national_team_id IS NOT NULL) AS with_current_national_team_id,
    count(*) FILTER (WHERE current_national_team_team_id IS NOT NULL) AS with_mapped_current_national_team,
    count(*) FILTER (WHERE current_market_value_eur IS NOT NULL) AS with_current_market_value
FROM staging.players;

SELECT
    current_national_team_id,
    player_name
FROM staging.players
WHERE current_national_team_id IS NOT NULL
  AND current_national_team_team_id IS NULL
ORDER BY current_national_team_id, player_name
LIMIT 30;


-- ============================================================
-- 2. Spieler-Marktwerte historisch
-- ------------------------------------------------------------
-- Quelle:
-- raw.kaggle_player_scores_player_valuations
--
-- Zweck:
-- Zeitabhängige Marktwerte pro Spieler.
--
-- Wichtig:
-- Diese Tabelle ist später die saubere Quelle für Marktwert-Features
-- "vor einem Match". Nicht die Snapshot-Spalte aus staging.players.
-- ============================================================

DROP TABLE IF EXISTS staging.player_valuations;

CREATE TABLE staging.player_valuations AS
SELECT
    v.player_id::INT AS player_id,

    left(trim(v.date), 10)::DATE AS valuation_date,

    v.market_value_in_eur::NUMERIC AS market_value_eur,

    CASE
        WHEN v.current_club_id ~ '^[0-9]+$' THEN v.current_club_id::INT
        ELSE NULL
    END AS current_club_id,

    NULLIF(trim(v.current_club_name), '') AS current_club_name,
    NULLIF(trim(v.player_club_domestic_competition_id), '') AS player_club_domestic_competition_id,

    CASE
        WHEN p.player_id IS NOT NULL THEN TRUE
        ELSE FALSE
    END AS has_player_profile,

    CURRENT_TIMESTAMP AS staged_at

FROM raw.kaggle_player_scores_player_valuations v
LEFT JOIN staging.players p
    ON p.player_id = v.player_id::INT
WHERE v.player_id ~ '^[0-9]+$'
  AND left(trim(v.date), 10) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
  AND v.market_value_in_eur ~ '^[0-9]+$';


-- Checks: player_valuations
SELECT
    'player_valuations' AS table_name,
    count(*) AS rows_total,
    count(DISTINCT player_id) AS distinct_player_ids,
    min(valuation_date) AS min_valuation_date,
    max(valuation_date) AS max_valuation_date,
    count(*) FILTER (WHERE has_player_profile) AS rows_with_player_profile,
    count(*) FILTER (WHERE NOT has_player_profile) AS rows_without_player_profile
FROM staging.player_valuations;

SELECT
    player_id,
    valuation_date,
    market_value_eur,
    current_club_name
FROM staging.player_valuations
WHERE NOT has_player_profile
ORDER BY player_id, valuation_date
LIMIT 20;


-- ============================================================
-- 3. Wettbewerbe
-- ------------------------------------------------------------
-- Quelle:
-- raw.kaggle_player_scores_competitions
--
-- Zweck:
-- Typisierte Wettbewerbsdimension für games/appearances.
-- ============================================================

DROP TABLE IF EXISTS staging.competitions;

CREATE TABLE staging.competitions AS
SELECT
    NULLIF(trim(competition_id), '') AS competition_id,
    NULLIF(trim(competition_code), '') AS competition_code,
    NULLIF(trim(name), '') AS competition_name,
    NULLIF(trim(sub_type), '') AS sub_type,
    NULLIF(trim(type), '') AS competition_type,
    NULLIF(trim(country_id), '') AS country_id,
    NULLIF(trim(country_name), '') AS country_name,
    NULLIF(trim(domestic_league_code), '') AS domestic_league_code,
    NULLIF(trim(confederation), '') AS confederation,

    CASE
        WHEN total_clubs ~ '^[0-9]+$' THEN total_clubs::INT
        ELSE NULL
    END AS total_clubs,

    NULLIF(trim(url), '') AS url,

    CURRENT_TIMESTAMP AS staged_at

FROM raw.kaggle_player_scores_competitions
WHERE NULLIF(trim(competition_id), '') IS NOT NULL;


-- Checks: competitions
SELECT
    'competitions' AS table_name,
    count(*) AS rows_total,
    count(DISTINCT competition_id) AS distinct_competition_ids,
    count(*) FILTER (WHERE competition_type IS NOT NULL) AS with_competition_type
FROM staging.competitions;


-- ============================================================
-- 4. Spiele
-- ------------------------------------------------------------
-- Quelle:
-- raw.kaggle_player_scores_games
--
-- Zweck:
-- Typisierte Spiele aus Kaggle/Transfermarkt.
--
-- Wichtig:
-- Diese Games sind überwiegend Clubspiele.
-- Nationalteam-Kontext kann über competition_type =
-- 'national_team_competition' gefiltert werden.
-- ============================================================

DROP TABLE IF EXISTS staging.games;

CREATE TABLE staging.games AS
SELECT
    g.game_id::INT AS game_id,

    NULLIF(trim(g.competition_id), '') AS competition_id,
    c.competition_name,
    c.competition_type AS competition_type_from_competitions,
    c.sub_type AS competition_sub_type,

    CASE
        WHEN g.season ~ '^[0-9]+$' THEN g.season::INT
        ELSE NULL
    END AS season,

    NULLIF(trim(g.round), '') AS round,

    left(trim(g.date), 10)::DATE AS game_date,

    g.home_club_id::INT AS home_club_id,
    g.away_club_id::INT AS away_club_id,

    NULLIF(trim(g.home_club_name), '') AS home_club_name,
    NULLIF(trim(g.away_club_name), '') AS away_club_name,

    g.home_club_goals::INT AS home_club_goals,
    g.away_club_goals::INT AS away_club_goals,

    CASE
        WHEN g.home_club_position ~ '^-?[0-9]+$' THEN g.home_club_position::INT
        ELSE NULL
    END AS home_club_position,

    CASE
        WHEN g.away_club_position ~ '^-?[0-9]+$' THEN g.away_club_position::INT
        ELSE NULL
    END AS away_club_position,

    NULLIF(trim(g.home_club_manager_name), '') AS home_club_manager_name,
    NULLIF(trim(g.away_club_manager_name), '') AS away_club_manager_name,

    NULLIF(trim(g.stadium), '') AS stadium,

    CASE
        WHEN g.attendance ~ '^[0-9]+$' THEN g.attendance::INT
        ELSE NULL
    END AS attendance,

    NULLIF(trim(g.referee), '') AS referee,
    NULLIF(trim(g.url), '') AS url,

    NULLIF(trim(g.home_club_formation), '') AS home_club_formation,
    NULLIF(trim(g.away_club_formation), '') AS away_club_formation,

    NULLIF(trim(g.aggregate), '') AS aggregate,
    NULLIF(trim(g.competition_type), '') AS competition_type_raw,

    CASE
        WHEN NULLIF(trim(g.competition_type), '') = 'national_team_competition'
          OR c.competition_type = 'national_team_competition'
        THEN TRUE
        ELSE FALSE
    END AS is_national_team_competition,

    CURRENT_TIMESTAMP AS staged_at

FROM raw.kaggle_player_scores_games g
LEFT JOIN staging.competitions c
    ON c.competition_id = g.competition_id
WHERE g.game_id ~ '^[0-9]+$'
  AND left(trim(g.date), 10) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
  AND g.home_club_id ~ '^[0-9]+$'
  AND g.away_club_id ~ '^[0-9]+$'
  AND g.home_club_goals ~ '^-?[0-9]+$'
  AND g.away_club_goals ~ '^-?[0-9]+$';


-- Checks: games
SELECT
    'games' AS table_name,
    count(*) AS rows_total,
    count(DISTINCT game_id) AS distinct_game_ids,
    min(game_date) AS min_game_date,
    max(game_date) AS max_game_date,
    count(*) FILTER (WHERE competition_id IS NOT NULL) AS with_competition_id,
    count(*) FILTER (WHERE competition_type_from_competitions IS NOT NULL) AS with_competition_type,
    count(*) FILTER (WHERE is_national_team_competition) AS national_team_games
FROM staging.games;

SELECT
    competition_type_raw,
    competition_type_from_competitions,
    competition_sub_type,
    count(*) AS games
FROM staging.games
GROUP BY competition_type_raw, competition_type_from_competitions, competition_sub_type
ORDER BY games DESC, competition_type_raw, competition_sub_type;


-- ============================================================
-- 5. Spieler-Einsätze / Match Stats
-- ------------------------------------------------------------
-- Quelle:
-- raw.kaggle_player_scores_appearances
--
-- Zweck:
-- Typisierte Spielerleistungen pro Spiel:
-- Minuten, Tore, Assists, Karten.
--
-- Wichtig:
-- Diese Daten sind überwiegend Club-Kontext.
-- Nationalteam-Appearances sind im aktuellen Datenstand nur
-- sehr begrenzt vorhanden.
-- ============================================================

DROP TABLE IF EXISTS staging.player_appearances;

CREATE TABLE staging.player_appearances AS
SELECT
    NULLIF(trim(a.appearance_id), '') AS appearance_id,

    a.game_id::INT AS game_id,
    g.game_date,
    g.competition_id,
    g.competition_type_from_competitions AS competition_type,
    g.competition_sub_type,
    g.is_national_team_competition,

    a.player_id::INT AS player_id,
    NULLIF(trim(a.player_name), '') AS player_name,

    CASE
        WHEN p.player_id IS NOT NULL THEN TRUE
        ELSE FALSE
    END AS has_player_profile,

    CASE
        WHEN a.player_club_id ~ '^[0-9]+$' THEN a.player_club_id::INT
        ELSE NULL
    END AS player_club_id,

    CASE
        WHEN a.player_current_club_id ~ '^[0-9]+$' THEN a.player_current_club_id::INT
        ELSE NULL
    END AS player_current_club_id,

    NULLIF(trim(a.competition_id), '') AS raw_competition_id,

    a.yellow_cards::INT AS yellow_cards,
    a.red_cards::INT AS red_cards,
    a.goals::INT AS goals,
    a.assists::INT AS assists,
    a.minutes_played::INT AS minutes_played,

    CURRENT_TIMESTAMP AS staged_at

FROM raw.kaggle_player_scores_appearances a
LEFT JOIN staging.players p
    ON p.player_id = a.player_id::INT
LEFT JOIN staging.games g
    ON g.game_id = a.game_id::INT
WHERE NULLIF(trim(a.appearance_id), '') IS NOT NULL
  AND a.game_id ~ '^[0-9]+$'
  AND a.player_id ~ '^[0-9]+$'
  AND a.yellow_cards ~ '^-?[0-9]+$'
  AND a.red_cards ~ '^-?[0-9]+$'
  AND a.goals ~ '^-?[0-9]+$'
  AND a.assists ~ '^-?[0-9]+$'
  AND a.minutes_played ~ '^-?[0-9]+$';


-- Checks: player_appearances
SELECT
    'player_appearances' AS table_name,
    count(*) AS rows_total,
    count(DISTINCT appearance_id) AS distinct_appearance_ids,
    count(DISTINCT player_id) AS distinct_player_ids,
    count(DISTINCT game_id) AS distinct_game_ids,
    count(*) FILTER (WHERE has_player_profile) AS rows_with_player_profile,
    count(*) FILTER (WHERE NOT has_player_profile) AS rows_without_player_profile,
    count(*) FILTER (WHERE game_date IS NOT NULL) AS rows_with_game_date,
    count(*) FILTER (WHERE is_national_team_competition) AS national_team_appearances,
    sum(goals) AS total_goals,
    sum(assists) AS total_assists,
    sum(minutes_played) AS total_minutes
FROM staging.player_appearances;

SELECT
    competition_sub_type,
    count(*) AS national_team_appearances
FROM staging.player_appearances
WHERE is_national_team_competition
GROUP BY competition_sub_type
ORDER BY national_team_appearances DESC;


-- ============================================================
-- 6. Spieler-Lineups
-- ------------------------------------------------------------
-- Quelle:
-- raw.kaggle_player_scores_game_lineups
--
-- Zweck:
-- Typisierte Startelf-/Bank-Informationen pro Spiel:
-- - starting_lineup vs substitutes
-- - Position im Spiel
-- - Club/Home/Away-Zuordnung
-- - Captain
--
-- Wichtig:
-- Diese Daten sind für spätere Features wie Formation,
-- Spieler-vs-Spieler-Matchups, Startelfstärke und Kaderstruktur
-- relevanter als appearances, enthalten aber viele player_id,
-- die nicht in staging.players joinen.
-- ============================================================

DROP TABLE IF EXISTS staging.player_lineups;

CREATE TABLE staging.player_lineups AS
SELECT
    NULLIF(trim(l.game_lineups_id), '') AS game_lineups_id,

    l.game_id::INT AS game_id,
    g.game_date,
    g.competition_id,
    g.competition_type_from_competitions AS competition_type,
    g.competition_sub_type,
    g.is_national_team_competition,

    l.player_id::INT AS player_id,
    NULLIF(trim(l.player_name), '') AS player_name,

    CASE
        WHEN p.player_id IS NOT NULL THEN TRUE
        ELSE FALSE
    END AS has_player_profile,

    l.club_id::INT AS club_id,

    CASE
        WHEN l.club_id::INT = g.home_club_id THEN 'HOME'
        WHEN l.club_id::INT = g.away_club_id THEN 'AWAY'
        ELSE 'UNKNOWN'
    END AS home_away_side,

    CASE
        WHEN l.club_id::INT = g.home_club_id THEN g.home_club_name
        WHEN l.club_id::INT = g.away_club_id THEN g.away_club_name
        ELSE NULL
    END AS club_name_from_game,

    NULLIF(trim(l.type), '') AS lineup_type,
    NULLIF(trim(l.position), '') AS lineup_position,

    CASE
        WHEN l.number ~ '^[0-9]+$' THEN l.number::INT
        ELSE NULL
    END AS shirt_number,

    CASE
        WHEN l.team_captain = '1' THEN TRUE
        WHEN l.team_captain = '0' THEN FALSE
        ELSE NULL
    END AS is_team_captain,

    CURRENT_TIMESTAMP AS staged_at

FROM raw.kaggle_player_scores_game_lineups l
LEFT JOIN staging.players p
    ON p.player_id = l.player_id::INT
LEFT JOIN staging.games g
    ON g.game_id = l.game_id::INT
WHERE NULLIF(trim(l.game_lineups_id), '') IS NOT NULL
  AND l.game_id ~ '^[0-9]+$'
  AND l.player_id ~ '^[0-9]+$'
  AND l.club_id ~ '^[0-9]+$'
  AND left(trim(l.date), 10) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$';


-- Checks: player_lineups
SELECT
    'player_lineups' AS table_name,
    count(*) AS rows_total,
    count(DISTINCT game_lineups_id) AS distinct_lineup_ids,
    count(DISTINCT player_id) AS distinct_player_ids,
    count(DISTINCT game_id) AS distinct_game_ids,
    count(*) FILTER (WHERE has_player_profile) AS rows_with_player_profile,
    count(*) FILTER (WHERE NOT has_player_profile) AS rows_without_player_profile,
    count(*) FILTER (WHERE home_away_side = 'HOME') AS rows_home,
    count(*) FILTER (WHERE home_away_side = 'AWAY') AS rows_away,
    count(*) FILTER (WHERE home_away_side = 'UNKNOWN') AS rows_unknown_side,
    count(*) FILTER (WHERE lineup_type = 'starting_lineup') AS starting_lineup_rows,
    count(*) FILTER (WHERE lineup_type = 'substitutes') AS substitutes_rows,
    count(*) FILTER (WHERE is_team_captain) AS captain_rows,
    count(*) FILTER (WHERE is_national_team_competition) AS national_team_lineups
FROM staging.player_lineups;

SELECT
    competition_sub_type,
    lineup_type,
    count(*) AS national_team_lineups
FROM staging.player_lineups
WHERE is_national_team_competition
GROUP BY competition_sub_type, lineup_type
ORDER BY competition_sub_type, lineup_type;


-- ============================================================
-- 7. Spieler-Spielereignisse
-- ------------------------------------------------------------
-- Quelle:
-- raw.kaggle_player_scores_game_events
--
-- Zweck:
-- Typisierte Events pro Spiel:
-- - Goals
-- - Cards
-- - Substitutions
-- - Shootout
--
-- Wichtig:
-- Diese Tabelle enthält wertvollen Nationalteam-Kontext,
-- inklusive World Cup und UEFA Euro.
-- ============================================================

DROP TABLE IF EXISTS staging.player_game_events;

CREATE TABLE staging.player_game_events AS
SELECT
    NULLIF(trim(e.game_event_id), '') AS game_event_id,

    e.game_id::INT AS game_id,
    g.game_date,
    g.competition_id,
    g.competition_type_from_competitions AS competition_type,
    g.competition_sub_type,
    g.is_national_team_competition,

    e.minute::INT AS event_minute,

    NULLIF(trim(e.type), '') AS event_type,

    e.club_id::INT AS club_id,
    NULLIF(trim(e.club_name), '') AS club_name,

    CASE
        WHEN e.club_id::INT = g.home_club_id THEN 'HOME'
        WHEN e.club_id::INT = g.away_club_id THEN 'AWAY'
        ELSE 'UNKNOWN'
    END AS home_away_side,

    e.player_id::INT AS player_id,
    NULLIF(trim(e.description), '') AS description,

    CASE
        WHEN p.player_id IS NOT NULL THEN TRUE
        ELSE FALSE
    END AS has_player_profile,

    CASE
        WHEN e.player_in_id ~ '^[0-9]+$' THEN e.player_in_id::INT
        ELSE NULL
    END AS player_in_id,

    CASE
        WHEN pin.player_id IS NOT NULL THEN TRUE
        ELSE FALSE
    END AS has_player_in_profile,

    CASE
        WHEN e.player_assist_id ~ '^[0-9]+$' THEN e.player_assist_id::INT
        ELSE NULL
    END AS player_assist_id,

    CASE
        WHEN pa.player_id IS NOT NULL THEN TRUE
        ELSE FALSE
    END AS has_player_assist_profile,

    CURRENT_TIMESTAMP AS staged_at

FROM raw.kaggle_player_scores_game_events e
LEFT JOIN staging.games g
    ON g.game_id = e.game_id::INT
LEFT JOIN staging.players p
    ON p.player_id = e.player_id::INT
LEFT JOIN staging.players pin
    ON pin.player_id = e.player_in_id::INT
LEFT JOIN staging.players pa
    ON pa.player_id = e.player_assist_id::INT
WHERE NULLIF(trim(e.game_event_id), '') IS NOT NULL
  AND e.game_id ~ '^[0-9]+$'
  AND e.player_id ~ '^[0-9]+$'
  AND e.club_id ~ '^[0-9]+$'
  AND e.minute ~ '^-?[0-9]+$'
  AND left(trim(e.date), 10) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$';


-- Checks: player_game_events
SELECT
    'player_game_events' AS table_name,
    count(*) AS rows_total,
    count(DISTINCT game_event_id) AS distinct_event_ids,
    count(DISTINCT player_id) AS distinct_player_ids,
    count(DISTINCT game_id) AS distinct_game_ids,
    count(*) FILTER (WHERE has_player_profile) AS rows_with_player_profile,
    count(*) FILTER (WHERE NOT has_player_profile) AS rows_without_player_profile,
    count(*) FILTER (WHERE home_away_side = 'HOME') AS rows_home,
    count(*) FILTER (WHERE home_away_side = 'AWAY') AS rows_away,
    count(*) FILTER (WHERE home_away_side = 'UNKNOWN') AS rows_unknown_side,
    count(*) FILTER (WHERE is_national_team_competition) AS national_team_events
FROM staging.player_game_events;

SELECT
    event_type,
    count(*) AS rows
FROM staging.player_game_events
GROUP BY event_type
ORDER BY rows DESC;

SELECT
    competition_sub_type,
    event_type,
    count(*) AS national_team_events
FROM staging.player_game_events
WHERE is_national_team_competition
GROUP BY competition_sub_type, event_type
ORDER BY competition_sub_type, national_team_events DESC;


-- ============================================================
-- 8. Club-/Team-Perspektive pro Spiel
-- ------------------------------------------------------------
-- Quelle:
-- raw.kaggle_player_scores_club_games
--
-- Zweck:
-- Eine Zeile pro Game und Club/Team:
-- - Home/Away
-- - eigene Tore / Gegentore
-- - Manager
-- - Tabellenposition
-- - Win-Flag
--
-- Wichtig:
-- Diese Tabelle ist hauptsächlich Club-Kontext, enthält aber auch
-- Zeilen für national_team_competition-Games aus staging.games.
-- ============================================================

DROP TABLE IF EXISTS staging.club_games;

CREATE TABLE staging.club_games AS
SELECT
    cg.game_id::INT AS game_id,
    g.game_date,
    g.competition_id,
    g.competition_type_from_competitions AS competition_type,
    g.competition_sub_type,
    g.is_national_team_competition,

    cg.club_id::INT AS club_id,
    cg.opponent_id::INT AS opponent_id,

    CASE
        WHEN cg.hosting = 'Home' THEN 'HOME'
        WHEN cg.hosting = 'Away' THEN 'AWAY'
        ELSE NULL
    END AS home_away_side,

    cg.own_goals::INT AS own_goals,
    cg.opponent_goals::INT AS opponent_goals,

    CASE
        WHEN cg.own_position ~ '^-?[0-9]+$' THEN cg.own_position::INT
        ELSE NULL
    END AS own_position,

    CASE
        WHEN cg.opponent_position ~ '^-?[0-9]+$' THEN cg.opponent_position::INT
        ELSE NULL
    END AS opponent_position,

    NULLIF(trim(cg.own_manager_name), '') AS own_manager_name,
    NULLIF(trim(cg.opponent_manager_name), '') AS opponent_manager_name,

    CASE
        WHEN cg.is_win = '1' THEN TRUE
        WHEN cg.is_win = '0' THEN FALSE
        ELSE NULL
    END AS is_win,

    CURRENT_TIMESTAMP AS staged_at

FROM raw.kaggle_player_scores_club_games cg
LEFT JOIN staging.games g
    ON g.game_id = cg.game_id::INT
WHERE cg.game_id ~ '^[0-9]+$'
  AND cg.club_id ~ '^[0-9]+$'
  AND cg.opponent_id ~ '^[0-9]+$'
  AND cg.own_goals ~ '^-?[0-9]+$'
  AND cg.opponent_goals ~ '^-?[0-9]+$';


-- Checks: club_games
SELECT
    'club_games' AS table_name,
    count(*) AS rows_total,
    count(DISTINCT game_id) AS distinct_game_ids,
    count(DISTINCT club_id) AS distinct_club_ids,
    count(*) FILTER (WHERE home_away_side = 'HOME') AS home_rows,
    count(*) FILTER (WHERE home_away_side = 'AWAY') AS away_rows,
    count(*) FILTER (WHERE home_away_side IS NULL) AS unknown_side_rows,
    count(*) FILTER (WHERE is_win) AS win_rows,
    count(*) FILTER (WHERE is_national_team_competition) AS national_team_rows
FROM staging.club_games;

SELECT
    rows_per_game,
    count(*) AS games
FROM (
    SELECT
        game_id,
        count(*) AS rows_per_game
    FROM staging.club_games
    GROUP BY game_id
) x
GROUP BY rows_per_game
ORDER BY rows_per_game;
