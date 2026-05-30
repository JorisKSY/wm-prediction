-- ============================================================
-- KOMPLETTES MANUELLES ELO CODE MAPPING
-- Key   = elo_team_code aus Elo-Tabelle
-- Value = canonical_name aus staging.team_mapping
--
-- Dieses Skript:
-- 1. erstellt/füllt staging.elo_team_code_mapping neu
-- 2. setzt alle 243 Elo-Codes manuell
-- 3. ergänzt fehlende canonical_names in team_mapping
-- 4. schreibt elo_team_code zurück in staging.team_mapping
-- ============================================================


-- 1. Spalte in team_mapping sicherstellen
ALTER TABLE staging.team_mapping
ADD COLUMN IF NOT EXISTS elo_team_code TEXT;


-- 2. Elo-Mapping-Tabelle neu bauen
DROP TABLE IF EXISTS staging.elo_team_code_mapping;

CREATE TABLE staging.elo_team_code_mapping (
    elo_team_code TEXT PRIMARY KEY,
    canonical_name TEXT
);


-- 3. Alle Elo-Codes aus Raw-Elo-Tabelle übernehmen
INSERT INTO staging.elo_team_code_mapping (elo_team_code)
SELECT DISTINCT team_code
FROM raw.atheels_datasets_world_football_elo_clean
WHERE team_code IS NOT NULL;


-- 4. Manuelle Mapping-Liste
CREATE  TABLE manual_elo_mapping (
    elo_team_code TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL
) ;


INSERT INTO manual_elo_mapping (elo_team_code, canonical_name)
VALUES
        ('AB', 'Abkhazia'),
        ('AD', 'Andorra'),
        ('AE', 'United Arab Emirates'),
        ('AF', 'Afghanistan'),
        ('AG', 'Antigua and Barbuda'),
        ('AI', 'Anguilla'),
        ('AL', 'Albania'),
        ('AM', 'Armenia'),
        ('AO', 'Angola'),
        ('AR', 'Argentina'),
        ('AS', 'American Samoa'),
        ('AT', 'Austria'),
        ('AU', 'Australia'),
        ('AW', 'Aruba'),
        ('AZ', 'Azerbaijan'),
        ('BA', 'Bosnia and Herzegovina'),
        ('BB', 'Barbados'),
        ('BD', 'Bangladesh'),
        ('BE', 'Belgium'),
        ('BF', 'Burkina Faso'),
        ('BG', 'Bulgaria'),
        ('BH', 'Bahrain'),
        ('BI', 'Burundi'),
        ('BJ', 'Benin'),
        ('BL', 'Saint Barthélemy'),
        ('BM', 'Bermuda'),
        ('BN', 'Brunei Darussalam'),
        ('BO', 'Bolivia'),
        ('BQ', 'Bonaire'),
        ('BR', 'Brazil'),
        ('BS', 'Bahamas'),
        ('BT', 'Bhutan'),
        ('BW', 'Botswana'),
        ('BY', 'Belarus'),
        ('BZ', 'Belize'),
        ('CA', 'Canada'),
        ('CC', 'Cocos (Keeling) Islands'),
        ('CD', 'DR Congo'),
        ('CF', 'Central African Republic'),
        ('CG', 'Congo'),
        ('CH', 'Switzerland'),
        ('CI', 'Ivory Coast'),
        ('CK', 'Cook Islands'),
        ('CL', 'Chile'),
        ('CM', 'Cameroon'),
        ('CN', 'China'),
        ('CO', 'Colombia'),
        ('CR', 'Costa Rica'),
        ('CU', 'Cuba'),
        ('CV', 'Cape Verde'),
        ('CW', 'Curacao'),
        ('CX', 'Christmas Island'),
        ('CY', 'Cyprus'),
        ('CZ', 'Czech Republic'),
        ('DE', 'Germany'),
        ('DJ', 'Djibouti'),
        ('DK', 'Denmark'),
        ('DM', 'Dominica'),
        ('DO', 'Dominican Republic'),
        ('DZ', 'Algeria'),
        ('EC', 'Ecuador'),
        ('EE', 'Estonia'),
        ('EG', 'Egypt'),
        ('EH', 'Western Sahara'),
        ('EI', 'Ireland'),
        ('EN', 'England'),
        ('ER', 'Eritrea'),
        ('ES', 'Spain'),
        ('ET', 'Ethiopia'),
        ('EU', 'Basque Country'),
        ('FI', 'Finland'),
        ('FJ', 'Fiji'),
        ('FK', 'Falkland Islands'),
        ('FM', 'Micronesia'),
        ('FO', 'Faroe Islands'),
        ('FR', 'France'),
        ('GA', 'Gabon'),
        ('GD', 'Grenada'),
        ('GE', 'Georgia'),
        ('GF', 'French Guiana'),
        ('GH', 'Ghana'),
        ('GI', 'Gibraltar'),
        ('GL', 'Greenland'),
        ('GM', 'Gambia'),
        ('GN', 'Guinea'),
        ('GP', 'Guadeloupe'),
        ('GQ', 'Equatorial Guinea'),
        ('GR', 'Greece'),
        ('GT', 'Guatemala'),
        ('GU', 'Guam'),
        ('GW', 'Guinea-Bissau'),
        ('GY', 'Guyana'),
        ('HG', 'Hmong'),
        ('HK', 'Hong Kong'),
        ('HN', 'Honduras'),
        ('HR', 'Croatia'),
        ('HT', 'Haiti'),
        ('HU', 'Hungary'),
        ('ID', 'Indonesia'),
        ('IE', 'Republic of Ireland'),
        ('IL', 'Israel'),
        ('IN', 'India'),
        ('IQ', 'Iraq'),
        ('IR', 'Iran'),
        ('IS', 'Iceland'),
        ('IT', 'Italy'),
        ('JM', 'Jamaica'),
        ('JO', 'Jordan'),
        ('JP', 'Japan'),
        ('JS', 'Jersey'),
        ('KD', 'Kurdistan'),
        ('KE', 'Kenya'),
        ('KG', 'Kyrgyzstan'),
        ('KH', 'Cambodia'),
        ('KI', 'Kiribati'),
        ('KM', 'Comoros'),
        ('KN', 'Saint Kitts and Nevis'),
        ('KO', 'Kosovo'),
        ('KP', 'North Korea'),
        ('KR', 'South Korea'),
        ('KW', 'Kuwait'),
        ('KY', 'Cayman Islands'),
        ('KZ', 'Kazakhstan'),
        ('LA', 'Laos'),
        ('LB', 'Lebanon'),
        ('LC', 'Saint Lucia'),
        ('LI', 'Liechtenstein'),
        ('LK', 'Sri Lanka'),
        ('LR', 'Liberia'),
        ('LS', 'Lesotho'),
        ('LT', 'Lithuania'),
        ('LU', 'Luxembourg'),
        ('LV', 'Latvia'),
        ('LY', 'Libya'),
        ('MA', 'Morocco'),
        ('MC', 'Monaco'),
        ('MD', 'Moldova'),
        ('ME', 'Montenegro'),
        ('MF', 'Saint Martin'),
        ('MG', 'Madagascar'),
        ('MH', 'Marshall Islands'),
        ('ML', 'Mali'),
        ('MM', 'Myanmar'),
        ('MN', 'Mongolia'),
        ('MO', 'Macau'),
        ('MP', 'Northern Mariana Islands'),
        ('MQ', 'Martinique'),
        ('MR', 'Mauritania'),
        ('MS', 'Montserrat'),
        ('MT', 'Malta'),
        ('MU', 'Mauritius'),
        ('MV', 'Maldives'),
        ('MW', 'Malawi'),
        ('MX', 'Mexico'),
        ('MY', 'Malaysia'),
        ('MZ', 'Mozambique'),
        ('NC', 'New Caledonia'),
        ('NE', 'Niger'),
        ('NG', 'Nigeria'),
        ('NI', 'Northern Ireland'),
        ('NL', 'Netherlands'),
        ('NM', 'Namibia'),
        ('NO', 'Norway'),
        ('NP', 'Nepal'),
        ('NS', 'Northern Cyprus'),
        ('NU', 'Niue'),
        ('NZ', 'New Zealand'),
        ('OM', 'Oman'),
        ('PA', 'Panama'),
        ('PE', 'Peru'),
        ('PG', 'Papua New Guinea'),
        ('PH', 'Philippines'),
        ('PK', 'Pakistan'),
        ('PL', 'Poland'),
        ('PM', 'Saint Pierre and Miquelon'),
        ('PR', 'Puerto Rico'),
        ('PS', 'Palestine'),
        ('PT', 'Portugal'),
        ('PW', 'Palau'),
        ('PY', 'Paraguay'),
        ('QA', 'Qatar'),
        ('RE', 'Réunion'),
        ('RO', 'Romania'),
        ('RS', 'Serbia'),
        ('RU', 'Russia'),
        ('RW', 'Rwanda'),
        ('SA', 'Saudi Arabia'),
        ('SB', 'Solomon Islands'),
        ('SC', 'Scotland'),
        ('SD', 'Sudan'),
        ('SE', 'Sweden'),
        ('SG', 'Singapore'),
        ('SI', 'Slovenia'),
        ('SK', 'Slovakia'),
        ('SL', 'Sierra Leone'),
        ('SM', 'San Marino'),
        ('SN', 'Senegal'),
        ('SO', 'Somalia'),
        ('SQ', 'Sark'),
        ('SR', 'Suriname'),
        ('SS', 'South Sudan'),
        ('ST', 'São Tomé and Príncipe'),
        ('SV', 'El Salvador'),
        ('SW', 'Swaziland'),
        ('SX', 'Sint Maarten'),
        ('SY', 'Syria'),
        ('TC', 'Turks and Caicos Islands'),
        ('TD', 'Chad'),
        ('TE', 'Tamil Eelam'),
        ('TG', 'Togo'),
        ('TH', 'Thailand'),
        ('TI', 'Tibet'),
        ('TJ', 'Tajikistan'),
        ('TL', 'Timor-Leste'),
        ('TM', 'Turkmenistan'),
        ('TN', 'Tunisia'),
        ('TO', 'Tonga'),
        ('TR', 'Turkey'),
        ('TT', 'Trinidad and Tobago'),
        ('TV', 'Tuvalu'),
        ('TW', 'Taiwan'),
        ('TZ', 'Tanzania'),
        ('UA', 'Ukraine'),
        ('UG', 'Uganda'),
        ('US', 'United States'),
        ('UY', 'Uruguay'),
        ('UZ', 'Uzbekistan'),
        ('VA', 'Vatican City'),
        ('VC', 'Saint Vincent and the Grenadines'),
        ('VE', 'Venezuela'),
        ('VG', 'British Virgin Islands'),
        ('VI', 'United States Virgin Islands'),
        ('VN', 'Vietnam'),
        ('VU', 'Vanuatu'),
        ('WA', 'Wales'),
        ('WF', 'Wallis Islands and Futuna'),
        ('WS', 'Samoa'),
        ('YE', 'Yemen'),
        ('YT', 'Mayotte'),
        ('ZA', 'South Africa'),
        ('ZM', 'Zambia'),
        ('ZN', 'Zanzibar'),
        ('ZW', 'Zimbabwe');


-- 5. Mapping in elo_team_code_mapping setzen
UPDATE staging.elo_team_code_mapping em
SET canonical_name = mm.canonical_name
FROM manual_elo_mapping mm
WHERE em.elo_team_code = mm.elo_team_code;


-- 6. Falls ein Name aus dem Mapping noch nicht in team_mapping existiert,
-- wird er ergänzt.
-- Bei dir betrifft das wahrscheinlich vor allem:
-- Cocos (Keeling) Islands und Christmas Island.
INSERT INTO staging.team_mapping (canonical_name)
SELECT mm.canonical_name
FROM manual_elo_mapping mm
LEFT JOIN staging.team_mapping tm
    ON tm.canonical_name = mm.canonical_name
WHERE tm.team_id IS NULL
ON CONFLICT (canonical_name) DO NOTHING;


-- 7. Alte Elo-Codes in team_mapping zurücksetzen
UPDATE staging.team_mapping
SET elo_team_code = NULL
WHERE elo_team_code IS NOT NULL;


-- 8. Elo-Codes sauber in team_mapping schreiben
UPDATE staging.team_mapping tm
SET elo_team_code = em.elo_team_code
FROM staging.elo_team_code_mapping em
WHERE tm.canonical_name = em.canonical_name
  AND em.canonical_name IS NOT NULL;


-- ============================================================
-- CHECKS
-- ============================================================

-- Check 1: Sind wirklich alle Elo-Codes gemappt?
SELECT
    COUNT(*) AS total_elo_codes,
    COUNT(*) FILTER (WHERE canonical_name IS NOT NULL) AS mapped_elo_codes,
    COUNT(*) FILTER (WHERE canonical_name IS NULL) AS unmapped_elo_codes
FROM staging.elo_team_code_mapping;


-- Check 2: Welche Elo-Codes fehlen noch?
SELECT *
FROM staging.elo_team_code_mapping
WHERE canonical_name IS NULL
ORDER BY elo_team_code;


-- Check 3: Gibt es Mapping-Namen, die nicht in team_mapping stehen?
SELECT mm.*
FROM manual_elo_mapping mm
LEFT JOIN staging.team_mapping tm
    ON tm.canonical_name = mm.canonical_name
WHERE tm.team_id IS NULL
ORDER BY mm.elo_team_code;


-- Check 4: Gibt es doppelte elo_team_codes in team_mapping?
SELECT
    elo_team_code,
    COUNT(*) AS count_teams
FROM staging.team_mapping
WHERE elo_team_code IS NOT NULL
GROUP BY elo_team_code
HAVING COUNT(*) > 1
ORDER BY elo_team_code;


-- Check 5: Finale Übersicht
SELECT
    team_id,
    canonical_name,
    historical_fifa_code,
    fifa_country_code,
    kaggle_team_code,
    elo_team_code
FROM staging.team_mapping
WHERE elo_team_code IS NOT NULL
ORDER BY canonical_name;



DROP TABLE IF EXISTS staging.elo_ratings;

CREATE TABLE staging.elo_ratings AS
SELECT
    tm.team_id,
    tm.canonical_name,
    e.team_code AS elo_team_code,
    e.*
FROM raw.atheels_datasets_world_football_elo_clean e
JOIN staging.team_mapping tm
    ON e.team_code = tm.elo_team_code;