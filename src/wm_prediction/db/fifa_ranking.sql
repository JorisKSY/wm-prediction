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
SELECT
    tm.team_id,
    tm.canonical_name,
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