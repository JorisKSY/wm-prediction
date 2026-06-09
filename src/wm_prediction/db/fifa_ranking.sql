-- ============================================================
-- FIFA STAGING SAUBER NEU BAUEN
-- Raw-Spalten bleiben komplett so wie sie sind.
-- Wir fügen nur team_id und canonical_name dazu.
-- Elo wird nicht angefasst.
-- ============================================================

DROP TABLE IF EXISTS staging.fifa_team_aliases;

CREATE TABLE staging.fifa_team_aliases (
    fifa_team_name TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL
);

INSERT INTO staging.fifa_team_aliases (fifa_team_name, canonical_name)
VALUES
    ('USA', 'United States'),
    ('IR Iran', 'Iran'),
    ('Korea Republic', 'South Korea'),
    ('Türkiye', 'Turkey'),
    ('Turkiye', 'Turkey'),
    ('Czechia', 'Czech Republic'),
    ('Congo DR', 'DR Congo'),
    ('Côte d''Ivoire', 'Ivory Coast'),
    ('Aotearoa New Zealand', 'New Zealand'),
    ('China PR', 'China'),
    ('Hong Kong, China', 'Hong Kong'),
    ('Korea DPR', 'North Korea'),
    ('Kyrgyz Republic', 'Kyrgyzstan'),
    ('St Kitts and Nevis', 'Saint Kitts and Nevis'),
    ('St. Kitts and Nevis', 'Saint Kitts and Nevis'),
    ('St Lucia', 'Saint Lucia'),
    ('St. Lucia', 'Saint Lucia'),
    ('St Vincent and the Grenadines', 'Saint Vincent and the Grenadines'),
    ('St. Vincent and the Grenadines', 'Saint Vincent and the Grenadines'),
    ('US Virgin Islands', 'United States Virgin Islands')
ON CONFLICT (fifa_team_name) DO UPDATE SET
    canonical_name = EXCLUDED.canonical_name;


DROP TABLE IF EXISTS staging.fifa_rankings;

CREATE TABLE staging.fifa_rankings AS
SELECT DISTINCT
    tm.team_id,
    tm.canonical_name,

    CASE
        WHEN trim(f.date) ~ '^[0-9]{4}$'
        THEN trim(f.date)::INT
        ELSE NULL
    END AS ranking_year,

    CASE
        WHEN trim(f.semester) ~ '^[0-9]+$'
        THEN trim(f.semester)::INT
        ELSE NULL
    END AS ranking_semester,

    CASE
        WHEN trim(f.date) ~ '^[0-9]{4}$'
         AND trim(f.semester) = '1'
        THEN make_date(trim(f.date)::INT, 1, 1)

        WHEN trim(f.date) ~ '^[0-9]{4}$'
         AND trim(f.semester) = '2'
        THEN make_date(trim(f.date)::INT, 7, 1)

        WHEN trim(f.date) ~ '^[0-9]{4}$'
        THEN make_date(trim(f.date)::INT, 1, 1)

        ELSE NULL
    END AS ranking_date,

    CASE
        WHEN trim(f.rank) ~ '^[0-9]+(\.0+)?$'
        THEN trim(f.rank)::NUMERIC::INT
        ELSE NULL
    END AS rank_int,

    CASE
        WHEN trim(f.total_points) ~ '^-?[0-9]+(\.[0-9]+)?$'
        THEN trim(f.total_points)::NUMERIC
        ELSE NULL
    END AS total_points_numeric,

    CASE
        WHEN trim(f.previous_points) ~ '^-?[0-9]+(\.[0-9]+)?$'
        THEN trim(f.previous_points)::NUMERIC
        ELSE NULL
    END AS previous_points_numeric,

    CASE
        WHEN trim(f.diff_points) ~ '^-?[0-9]+(\.[0-9]+)?$'
        THEN trim(f.diff_points)::NUMERIC
        ELSE NULL
    END AS diff_points_numeric,

    f.*
FROM raw.atheels_datasets_historical_fifa_mens_rank f
LEFT JOIN staging.fifa_team_aliases a
    ON f.team = a.fifa_team_name
JOIN staging.team_mapping tm
    ON tm.canonical_name = COALESCE(a.canonical_name, f.team);

-- Welche FIFA-Teamnamen konnten nicht gemappt werden?
SELECT DISTINCT
    f.team,
    f.acronym
FROM raw.atheels_datasets_historical_fifa_mens_rank f
LEFT JOIN staging.fifa_team_aliases a
    ON f.team = a.fifa_team_name
LEFT JOIN staging.team_mapping tm
    ON tm.canonical_name = COALESCE(a.canonical_name, f.team)
WHERE tm.team_id IS NULL
ORDER BY f.team;
-- ============================================================
-- NEUE FIFA-RANKINGS 2024-07 bis 2026-06 (Phase J)
-- Quelle: raw.atheels_datasets_fifa_mens_rankings
--   (gescrapte offizielle FIFA-Men's-Releases, echte ranking_date)
-- Anhang an die historische staging.fifa_rankings.
-- Designentscheidungen:
--   - ranking_date: echtes Release-Datum 1:1 (genauer als histor. Semester-Rundung)
--   - ranking_year: aus ranking_date abgeleitet
--   - ranking_semester: grobes Etikett (1=Jan-Jun, 2=Jul-Dez).
--     ACHTUNG: bei mehreren Releases pro Halbjahr NICHT eindeutig.
--     Der wahre Snapshot-Identifikator ist ranking_date. Alle as-of-Joins
--     (07, 20, 21) joinen ueber ranking_date, daher unkritisch.
--   - Giftzeilen (gescrapter Werbecode) ueber country_code-Filter entfernt.
--   - Namensnormalisierung ausschliesslich ueber staging.fifa_team_aliases
--     + staging.team_mapping (eine Quelle der Wahrheit, nicht dupliziert).
-- Idempotent: vorhandene neue Snapshots werden vorher entfernt.
-- ============================================================
DELETE FROM staging.fifa_rankings
WHERE ranking_date >= DATE '2024-07-18';

INSERT INTO staging.fifa_rankings (
    team_id, canonical_name, ranking_year, ranking_semester, ranking_date,
    rank_int, total_points_numeric, previous_points_numeric, diff_points_numeric,
    date, semester, rank, team, acronym, total_points, previous_points, diff_points
)
SELECT
    tm.team_id,
    tm.canonical_name,
    EXTRACT(YEAR FROM r.ranking_date::date)::int,
    CASE WHEN EXTRACT(MONTH FROM r.ranking_date::date) <= 6 THEN 1 ELSE 2 END,
    r.ranking_date::date,
    r.rank_int::int,
    r.total_points::numeric,
    NULLIF(r.previous_points,'')::numeric,
    NULL::numeric,
    r.ranking_date,
    NULL::text,
    r.rank_int,
    r.team_name,
    r.country_code,
    r.total_points,
    r.previous_points,
    NULL::text
FROM raw.atheels_datasets_fifa_mens_rankings r
LEFT JOIN staging.fifa_team_aliases a
    ON r.team_name = a.fifa_team_name
JOIN staging.team_mapping tm
    ON tm.canonical_name = COALESCE(a.canonical_name, r.team_name)
WHERE r.country_code ~ '^[A-Z]{3}$';
