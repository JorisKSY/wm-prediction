CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.world_cup_round32_slots_mvp_v1;

CREATE TABLE features.world_cup_round32_slots_mvp_v1 AS
WITH official_round32(match_number, match_label) AS (
    VALUES
        (73, '2A vs 2B'),
        (74, '1E vs 3ABCDF'),
        (75, '1F vs 2C'),
        (76, '1C vs 2F'),
        (77, '1I vs 3CDFGH'),
        (78, '2E vs 2I'),
        (79, '1A vs 3CEFHI'),
        (80, '1L vs 3EHIJK'),
        (81, '1D vs 3BEFIJ'),
        (82, '1G vs 3AEHIJ'),
        (83, '2K vs 2L'),
        (84, '1H vs 2J'),
        (85, '1B vs 3EFGIJ'),
        (86, '1J vs 2H'),
        (87, '1K vs 3DEIJL'),
        (88, '2D vs 2G')
),
parsed AS (
    SELECT
        match_number,
        match_label,
        TRIM(SPLIT_PART(match_label, ' vs ', 1)) AS slot_home,
        TRIM(SPLIT_PART(match_label, ' vs ', 2)) AS slot_away
    FROM official_round32
)
SELECT
    match_number,
    match_label,

    slot_home,
    SUBSTRING(slot_home FROM '^([123])')::integer AS home_group_rank,
    SUBSTRING(slot_home FROM '^[123](.*)$') AS home_group_candidates,
    LENGTH(SUBSTRING(slot_home FROM '^[123](.*)$')) AS home_group_candidate_count,

    slot_away,
    SUBSTRING(slot_away FROM '^([123])')::integer AS away_group_rank,
    SUBSTRING(slot_away FROM '^[123](.*)$') AS away_group_candidates,
    LENGTH(SUBSTRING(slot_away FROM '^[123](.*)$')) AS away_group_candidate_count,

    'fifa_schedule_text_manual'::text AS source,
    NOW() AS created_at
FROM parsed
ORDER BY match_number;

CREATE INDEX IF NOT EXISTS idx_world_cup_round32_slots_mvp_v1_match_number
    ON features.world_cup_round32_slots_mvp_v1 (match_number);
