CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS features;


CREATE SCHEMA IF NOT EXISTS staging;

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



INSERT INTO staging.team_mapping (
    canonical_name,
    historical_fifa_name,
    historical_fifa_code
)
SELECT DISTINCT
    team AS canonical_name,
    team AS historical_fifa_name,
    acronym AS historical_fifa_code
FROM raw.atheels_datasets_historical_fifa_mens_rank
WHERE team IS NOT NULL
ON CONFLICT (canonical_name) DO NOTHING;


INSERT INTO staging.team_mapping (canonical_name)
SELECT DISTINCT home_team
FROM raw.atheels_datasets_results
WHERE home_team IS NOT NULL
ON CONFLICT (canonical_name) DO NOTHING;

INSERT INTO staging.team_mapping (canonical_name)
SELECT DISTINCT away_team
FROM raw.atheels_datasets_results
WHERE away_team IS NOT NULL
ON CONFLICT (canonical_name) DO NOTHING;



INSERT INTO staging.team_mapping (
    canonical_name,
    kaggle_national_team_id,
    kaggle_name,
    kaggle_team_code,
    kaggle_country_name
)
SELECT DISTINCT
    name AS canonical_name,
    national_team_id,
    name,
    team_code,
    country_name
FROM raw.kaggle_player_scores_national_teams
WHERE name IS NOT NULL
ON CONFLICT (canonical_name) DO UPDATE SET
    kaggle_national_team_id = EXCLUDED.kaggle_national_team_id,
    kaggle_name = EXCLUDED.kaggle_name,
    kaggle_team_code = EXCLUDED.kaggle_team_code,
    kaggle_country_name = EXCLUDED.kaggle_country_name;


INSERT INTO staging.team_mapping (
    canonical_name,
    fifa_team_id,
    fifa_country_code,
    fifa_name
)
SELECT DISTINCT
    regexp_replace(team_name, '^.*Description'': ''([^'']+)''.*$', '\1') AS canonical_name,
    id_team,
    id_country,
    regexp_replace(team_name, '^.*Description'': ''([^'']+)''.*$', '\1') AS fifa_name
FROM raw.atheels_datasets_fifa_ranking
WHERE team_name IS NOT NULL
ON CONFLICT (canonical_name) DO UPDATE SET
    fifa_team_id = EXCLUDED.fifa_team_id,
    fifa_country_code = EXCLUDED.fifa_country_code,
    fifa_name = EXCLUDED.fifa_name;