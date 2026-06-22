-- 14_features_world_cup_groups_mvp_v1.sql
-- Builds features.world_cup_groups_mvp_v1: one row per (team, group).
--
-- BUGFIX 2026-06-07 (see docs/mvp_v1_notes.md "Knockout-Bracket nutzte
-- bedeutungslose Gruppenlabels"): The previous version reconstructed the
-- quartets correctly from fixtures but labelled groups by ROW_NUMBER() over the
-- alphabetically-sorted team list -> "internal A" = alphabetically-first group,
-- with NO relation to the official FIFA draw. official_group_label was NULL.
-- Since world_cup_round32_slots_mvp_v1 is wired to OFFICIAL letters, every
-- knockout pairing was mis-resolved. Fix: keep the fixture reconstruction as an
-- INDEPENDENT source of composition, set official_group_label from an explicit
-- 48-row VALUES list (official draw, names in DB spelling), and ASSERT that the
-- two sources agree (each team's three fixture opponents must carry the same
-- official letter) before the table is created.
--
-- Source of official draw: FIFA / Wikipedia "2026 FIFA World Cup", 2026-06-07.

CREATE SCHEMA IF NOT EXISTS features;

-- Step 1: official draw as the single source of truth (DB name spelling).
DROP TABLE IF EXISTS features.world_cup_official_draw_2026;
CREATE TABLE features.world_cup_official_draw_2026 (
    team_name            text PRIMARY KEY,
    official_group_label text NOT NULL
);
INSERT INTO features.world_cup_official_draw_2026 (team_name, official_group_label) VALUES
    ('Mexico', 'A'), ('South Africa', 'A'), ('South Korea', 'A'), ('Czech Republic', 'A'),
    ('Canada', 'B'), ('Bosnia and Herzegovina', 'B'), ('Qatar', 'B'), ('Switzerland', 'B'),
    ('Brazil', 'C'), ('Morocco', 'C'), ('Haiti', 'C'), ('Scotland', 'C'),
    ('United States', 'D'), ('Paraguay', 'D'), ('Australia', 'D'), ('Turkey', 'D'),
    ('Germany', 'E'), ('Curaçao', 'E'), ('Ivory Coast', 'E'), ('Ecuador', 'E'),
    ('Netherlands', 'F'), ('Japan', 'F'), ('Sweden', 'F'), ('Tunisia', 'F'),
    ('Belgium', 'G'), ('Egypt', 'G'), ('Iran', 'G'), ('New Zealand', 'G'),
    ('Spain', 'H'), ('Cape Verde', 'H'), ('Saudi Arabia', 'H'), ('Uruguay', 'H'),
    ('France', 'I'), ('Senegal', 'I'), ('Iraq', 'I'), ('Norway', 'I'),
    ('Argentina', 'J'), ('Algeria', 'J'), ('Austria', 'J'), ('Jordan', 'J'),
    ('Portugal', 'K'), ('DR Congo', 'K'), ('Uzbekistan', 'K'), ('Colombia', 'K'),
    ('England', 'L'), ('Croatia', 'L'), ('Ghana', 'L'), ('Panama', 'L');

-- Step 2: reconstruct quartets from fixtures (INDEPENDENT source of composition).
DROP TABLE IF EXISTS features.world_cup_groups_mvp_v1;
CREATE TABLE features.world_cup_groups_mvp_v1 AS
WITH team_matches AS (
    SELECT home_team_name AS team_name, away_team_name AS opponent_name
    FROM features.match_predictions_mvp_v1
    UNION ALL
    SELECT away_team_name AS team_name, home_team_name AS opponent_name
    FROM features.match_predictions_mvp_v1
),
team_groups AS (
    SELECT
        team_name,
        ARRAY(
            SELECT x
            FROM UNNEST(ARRAY_AGG(opponent_name ORDER BY opponent_name) || ARRAY[team_name]) AS x
            ORDER BY x
        ) AS group_teams
    FROM team_matches
    GROUP BY team_name
),
unique_groups AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY group_teams::text) AS internal_group_id,
        group_teams
    FROM (SELECT DISTINCT group_teams FROM team_groups) x
)
SELECT
    ug.internal_group_id,
    'Group ' || LPAD(ug.internal_group_id::text, 2, '0') AS internal_group_label,
    tg.team_name,
    od.official_group_label,
    NOW() AS created_at
FROM unique_groups ug
JOIN team_groups tg ON tg.group_teams = ug.group_teams
JOIN features.world_cup_official_draw_2026 od ON od.team_name = tg.team_name
ORDER BY ug.internal_group_id, tg.team_name;

CREATE INDEX IF NOT EXISTS idx_world_cup_groups_mvp_v1_team_name
    ON features.world_cup_groups_mvp_v1 (team_name);
CREATE INDEX IF NOT EXISTS idx_world_cup_groups_mvp_v1_internal_group_id
    ON features.world_cup_groups_mvp_v1 (internal_group_id);

-- Step 3: HARD ASSERTIONS. Any failure aborts the transaction (raises exception),
-- so a broken build never silently produces a mislabelled table.
DO $$
DECLARE
    v_rows           int;
    v_unmapped       int;
    v_groups         int;
    v_inconsistent   int;
BEGIN
    -- 3a: exactly 48 teams, none unmapped.
    SELECT COUNT(*) INTO v_rows FROM features.world_cup_groups_mvp_v1;
    IF v_rows <> 48 THEN
        RAISE EXCEPTION 'Expected 48 team rows, got %', v_rows;
    END IF;

    SELECT COUNT(*) INTO v_unmapped
    FROM features.world_cup_groups_mvp_v1
    WHERE official_group_label IS NULL;
    IF v_unmapped <> 0 THEN
        RAISE EXCEPTION '% teams without official_group_label', v_unmapped;
    END IF;

    -- 3b: exactly 12 official groups of 4.
    SELECT COUNT(*) INTO v_groups FROM (
        SELECT official_group_label
        FROM features.world_cup_groups_mvp_v1
        GROUP BY official_group_label
        HAVING COUNT(*) = 4
    ) g;
    IF v_groups <> 12 THEN
        RAISE EXCEPTION 'Expected 12 official groups of 4, got %', v_groups;
    END IF;

    -- 3c: CROSS-CHECK the two independent sources. For every team, each of its
    -- fixture-reconstructed group-mates must carry the SAME official letter.
    -- Counts teams whose internal group spans more than one official letter.
    SELECT COUNT(*) INTO v_inconsistent FROM (
        SELECT internal_group_id
        FROM features.world_cup_groups_mvp_v1
        GROUP BY internal_group_id
        HAVING COUNT(DISTINCT official_group_label) <> 1
    ) bad;
    IF v_inconsistent <> 0 THEN
        RAISE EXCEPTION
          'Fixture quartets disagree with official draw in % internal group(s)',
          v_inconsistent;
    END IF;
END $$;
