CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS features;


-- ============================================================
-- Zentrale Alias-Tabelle
-- ------------------------------------------------------------
-- Wichtig:
-- Diese Tabelle muss VOR staging.team_mapping existieren,
-- damit semantisch gleiche Teams nicht als Dubletten entstehen.
-- Beispiele: USA -> United States, China PR -> China,
-- Korea Republic -> South Korea.
-- ============================================================

DROP TABLE IF EXISTS staging.team_name_aliases;

CREATE TABLE staging.team_name_aliases (
    source_name TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL
);

INSERT INTO staging.team_name_aliases (source_name, canonical_name)
VALUES
    ('USA', 'United States'),
    ('United States of America', 'United States'),

    ('Bosnia-Herzegovina', 'Bosnia and Herzegovina'),
    ('Bosnia & Herzegovina', 'Bosnia and Herzegovina'),

    ('IR Iran', 'Iran'),

    ('Korea Republic', 'South Korea'),
    ('Korea DPR', 'North Korea'),

    ('Türkiye', 'Turkey'),
    ('Turkiye', 'Turkey'),

    ('FYR Macedonia', 'North Macedonia'),

    ('Czechia', 'Czech Republic'),

    ('Congo DR', 'DR Congo'),
    ('Côte d''Ivoire', 'Ivory Coast'),
    ('Cote d''Ivoire', 'Ivory Coast'),

    ('Aotearoa New Zealand', 'New Zealand'),

    ('China PR', 'China'),
    ('Hong Kong, China', 'Hong Kong'),

    ('Kyrgyz Republic', 'Kyrgyzstan'),

    ('St Kitts and Nevis', 'Saint Kitts and Nevis'),
    ('St. Kitts and Nevis', 'Saint Kitts and Nevis'),

    ('St Lucia', 'Saint Lucia'),
    ('St. Lucia', 'Saint Lucia'),

    ('St Vincent and the Grenadines', 'Saint Vincent and the Grenadines'),
    ('St. Vincent and the Grenadines', 'Saint Vincent and the Grenadines'),

    ('US Virgin Islands', 'United States Virgin Islands')
ON CONFLICT (source_name) DO UPDATE SET
    canonical_name = EXCLUDED.canonical_name;


-- ============================================================
-- Team Mapping
-- ------------------------------------------------------------
-- Wird aus mehreren Quellen aufgebaut, aber alle Namen werden
-- zuerst über staging.team_name_aliases normalisiert.
-- ============================================================

DROP TABLE IF EXISTS staging.team_mapping;

CREATE TABLE staging.team_mapping (
    team_id SERIAL PRIMARY KEY,

    canonical_name TEXT NOT NULL UNIQUE,

    fifa_team_id TEXT,
    fifa_country_code TEXT,
    fifa_name TEXT,

    historical_fifa_name TEXT,
    historical_fifa_code TEXT,

    kaggle_national_team_id TEXT,
    kaggle_name TEXT,
    kaggle_team_code TEXT,
    kaggle_country_name TEXT,

    elo_team_code TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Historische FIFA Rankings
-- Nach Alias-Normalisierung können mehrere Raw-Namen auf denselben
-- canonical_name fallen. Deshalb wählen wir pro canonical_name genau
-- eine stabile Repräsentation für team_mapping.
INSERT INTO staging.team_mapping (
    canonical_name,
    historical_fifa_name,
    historical_fifa_code
)
WITH mapped AS (
    SELECT DISTINCT
        COALESCE(a.canonical_name, r.team) AS canonical_name,
        r.team AS historical_fifa_name,
        r.acronym AS historical_fifa_code
    FROM raw.atheels_datasets_historical_fifa_mens_rank r
    LEFT JOIN staging.team_name_aliases a
        ON r.team = a.source_name
    WHERE r.team IS NOT NULL
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY canonical_name
            ORDER BY
                CASE WHEN historical_fifa_name = canonical_name THEN 0 ELSE 1 END,
                historical_fifa_name,
                historical_fifa_code
        ) AS rn
    FROM mapped
)
SELECT
    canonical_name,
    historical_fifa_name,
    historical_fifa_code
FROM ranked
WHERE rn = 1
ORDER BY canonical_name
ON CONFLICT (canonical_name) DO UPDATE SET
    historical_fifa_name = COALESCE(staging.team_mapping.historical_fifa_name, EXCLUDED.historical_fifa_name),
    historical_fifa_code = COALESCE(staging.team_mapping.historical_fifa_code, EXCLUDED.historical_fifa_code);


-- Historische Matches: Home Teams
INSERT INTO staging.team_mapping (canonical_name)
SELECT DISTINCT
    COALESCE(a.canonical_name, r.home_team) AS canonical_name
FROM raw.atheels_datasets_results r
LEFT JOIN staging.team_name_aliases a
    ON r.home_team = a.source_name
WHERE r.home_team IS NOT NULL
ORDER BY canonical_name
ON CONFLICT (canonical_name) DO NOTHING;


-- Historische Matches: Away Teams
INSERT INTO staging.team_mapping (canonical_name)
SELECT DISTINCT
    COALESCE(a.canonical_name, r.away_team) AS canonical_name
FROM raw.atheels_datasets_results r
LEFT JOIN staging.team_name_aliases a
    ON r.away_team = a.source_name
WHERE r.away_team IS NOT NULL
ORDER BY canonical_name
ON CONFLICT (canonical_name) DO NOTHING;


-- Kaggle Nationalteam-Profile
INSERT INTO staging.team_mapping (
    canonical_name,
    kaggle_national_team_id,
    kaggle_name,
    kaggle_team_code,
    kaggle_country_name
)
SELECT DISTINCT
    COALESCE(a.canonical_name, n.name) AS canonical_name,
    n.national_team_id,
    n.name,
    n.team_code,
    n.country_name
FROM raw.kaggle_player_scores_national_teams n
LEFT JOIN staging.team_name_aliases a
    ON n.name = a.source_name
WHERE n.name IS NOT NULL
ORDER BY canonical_name
ON CONFLICT (canonical_name) DO UPDATE SET
    kaggle_national_team_id = EXCLUDED.kaggle_national_team_id,
    kaggle_name = EXCLUDED.kaggle_name,
    kaggle_team_code = EXCLUDED.kaggle_team_code,
    kaggle_country_name = EXCLUDED.kaggle_country_name;


-- Current FIFA Ranking
INSERT INTO staging.team_mapping (
    canonical_name,
    fifa_team_id,
    fifa_country_code,
    fifa_name
)
WITH parsed AS (
    SELECT
        regexp_replace(team_name, '^.*Description'': ''([^'']+)''.*$', '\1') AS fifa_team_name,
        id_team,
        id_country
    FROM raw.atheels_datasets_fifa_ranking
    WHERE team_name IS NOT NULL
)
SELECT DISTINCT
    COALESCE(a.canonical_name, p.fifa_team_name) AS canonical_name,
    p.id_team,
    p.id_country,
    p.fifa_team_name AS fifa_name
FROM parsed p
LEFT JOIN staging.team_name_aliases a
    ON p.fifa_team_name = a.source_name
ORDER BY canonical_name
ON CONFLICT (canonical_name) DO UPDATE SET
    fifa_team_id = EXCLUDED.fifa_team_id,
    fifa_country_code = EXCLUDED.fifa_country_code,
    fifa_name = EXCLUDED.fifa_name;
