CREATE SCHEMA IF NOT EXISTS features;

DROP TABLE IF EXISTS features.world_cup_groups_mvp_v1;

CREATE TABLE features.world_cup_groups_mvp_v1 AS
WITH team_matches AS (
    SELECT
        home_team_name AS team_name,
        away_team_name AS opponent_name
    FROM features.match_predictions_mvp_v1

    UNION ALL

    SELECT
        away_team_name AS team_name,
        home_team_name AS opponent_name
    FROM features.match_predictions_mvp_v1
),
team_groups AS (
    SELECT
        team_name,
        ARRAY(
            SELECT x
            FROM UNNEST(
                ARRAY_AGG(opponent_name ORDER BY opponent_name) || ARRAY[team_name]
            ) AS x
            ORDER BY x
        ) AS group_teams
    FROM team_matches
    GROUP BY team_name
),
unique_groups AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY group_teams::text) AS internal_group_id,
        group_teams
    FROM (
        SELECT DISTINCT group_teams
        FROM team_groups
    ) x
)
SELECT
    ug.internal_group_id,
    'Group ' || LPAD(ug.internal_group_id::text, 2, '0') AS internal_group_label,
    tg.team_name,
    NULL::text AS official_group_label,
    NOW() AS created_at
FROM unique_groups ug
JOIN team_groups tg
    ON tg.group_teams = ug.group_teams
ORDER BY
    ug.internal_group_id,
    tg.team_name;

CREATE INDEX IF NOT EXISTS idx_world_cup_groups_mvp_v1_team_name
    ON features.world_cup_groups_mvp_v1 (team_name);

CREATE INDEX IF NOT EXISTS idx_world_cup_groups_mvp_v1_internal_group_id
    ON features.world_cup_groups_mvp_v1 (internal_group_id);
