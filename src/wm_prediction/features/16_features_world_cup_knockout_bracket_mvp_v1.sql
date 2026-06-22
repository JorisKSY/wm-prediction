CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.world_cup_knockout_bracket_mvp_v1;

CREATE TABLE features.world_cup_knockout_bracket_mvp_v1 AS
WITH bracket(
    match_number,
    round_name,
    match_label,
    home_source_type,
    home_source_value,
    away_source_type,
    away_source_value
) AS (
    VALUES
        -- Round of 32 / Sechzehntelfinale
        (73,  'round_of_32', '2A vs 2B',     'slot', '2A',     'slot', '2B'),
        (74,  'round_of_32', '1E vs 3ABCDF', 'slot', '1E',     'slot', '3ABCDF'),
        (75,  'round_of_32', '1F vs 2C',     'slot', '1F',     'slot', '2C'),
        (76,  'round_of_32', '1C vs 2F',     'slot', '1C',     'slot', '2F'),
        (77,  'round_of_32', '1I vs 3CDFGH', 'slot', '1I',     'slot', '3CDFGH'),
        (78,  'round_of_32', '2E vs 2I',     'slot', '2E',     'slot', '2I'),
        (79,  'round_of_32', '1A vs 3CEFHI', 'slot', '1A',     'slot', '3CEFHI'),
        (80,  'round_of_32', '1L vs 3EHIJK', 'slot', '1L',     'slot', '3EHIJK'),
        (81,  'round_of_32', '1D vs 3BEFIJ', 'slot', '1D',     'slot', '3BEFIJ'),
        (82,  'round_of_32', '1G vs 3AEHIJ', 'slot', '1G',     'slot', '3AEHIJ'),
        (83,  'round_of_32', '2K vs 2L',     'slot', '2K',     'slot', '2L'),
        (84,  'round_of_32', '1H vs 2J',     'slot', '1H',     'slot', '2J'),
        (85,  'round_of_32', '1B vs 3EFGIJ', 'slot', '1B',     'slot', '3EFGIJ'),
        (86,  'round_of_32', '1J vs 2H',     'slot', '1J',     'slot', '2H'),
        (87,  'round_of_32', '1K vs 3DEIJL', 'slot', '1K',     'slot', '3DEIJL'),
        (88,  'round_of_32', '2D vs 2G',     'slot', '2D',     'slot', '2G'),

        -- Round of 16 / Achtelfinale
        (89,  'round_of_16', 'W74 vs W77',   'winner', '74',   'winner', '77'),
        (90,  'round_of_16', 'W73 vs W75',   'winner', '73',   'winner', '75'),
        (91,  'round_of_16', 'W76 vs W78',   'winner', '76',   'winner', '78'),
        (92,  'round_of_16', 'W79 vs W80',   'winner', '79',   'winner', '80'),
        (93,  'round_of_16', 'W83 vs W84',   'winner', '83',   'winner', '84'),
        (94,  'round_of_16', 'W81 vs W82',   'winner', '81',   'winner', '82'),
        (95,  'round_of_16', 'W86 vs W88',   'winner', '86',   'winner', '88'),
        (96,  'round_of_16', 'W85 vs W87',   'winner', '85',   'winner', '87'),

        -- Quarter-finals / Viertelfinale
        (97,  'quarter_final', 'W89 vs W90', 'winner', '89',   'winner', '90'),
        (98,  'quarter_final', 'W93 vs W94', 'winner', '93',   'winner', '94'),
        (99,  'quarter_final', 'W91 vs W92', 'winner', '91',   'winner', '92'),
        (100, 'quarter_final', 'W95 vs W96', 'winner', '95',   'winner', '96'),

        -- Semi-finals / Halbfinale
        (101, 'semi_final',    'W97 vs W98', 'winner', '97',   'winner', '98'),
        (102, 'semi_final',    'W99 vs W100','winner', '99',   'winner', '100'),

        -- Third-place match and final
        (103, 'third_place',   'L101 vs L102','loser', '101',  'loser', '102'),
        (104, 'final',         'W101 vs W102','winner', '101', 'winner', '102')
)
SELECT
    match_number,
    round_name,
    match_label,
    home_source_type,
    home_source_value,
    away_source_type,
    away_source_value,
    'fifa_schedule_text_manual'::text AS source,
    NOW() AS created_at
FROM bracket
ORDER BY match_number;

CREATE INDEX IF NOT EXISTS idx_world_cup_knockout_bracket_mvp_v1_match_number
    ON features.world_cup_knockout_bracket_mvp_v1 (match_number);
