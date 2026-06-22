import argparse

import numpy as np
import pandas as pd
from sqlalchemy import text

from wm_prediction.db.connection import get_engine


DEFAULT_RANDOM_SEED = 42
DEFAULT_N_SIMULATIONS = 1000


def load_match_predictions() -> pd.DataFrame:
    query = """
    SELECT
        historical_match_id,
        match_date,
        home_team_name,
        away_team_name,
        lambda_home,
        lambda_away,
        p_home_win,
        p_draw,
        p_away_win
    FROM features.match_predictions_mvp_v1
    ORDER BY match_date, historical_match_id
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn, parse_dates=["match_date"])


def load_groups() -> dict[str, list[str]]:
    # Keyed by OFFICIAL group label (A..L), the source of truth for knockout
    # slot resolution. The group-stage computation itself is label-agnostic
    # (build_group_table works on team sets), so the key content does not affect
    # standings; it only matters when official slots like "1A" are resolved.
    query = """
    SELECT
        official_group_label,
        team_name
    FROM features.world_cup_groups_mvp_v1
    ORDER BY official_group_label, team_name
    """
    engine = get_engine()
    with engine.connect() as conn:
        groups_df = pd.read_sql_query(text(query), conn)
    return {
        group_label: group_df["team_name"].tolist()
        for group_label, group_df in groups_df.groupby("official_group_label", sort=False)
    }

def simulate_scores(matches: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    simulated = matches.copy()

    simulated["sim_home_goals"] = rng.poisson(simulated["lambda_home"].to_numpy())
    simulated["sim_away_goals"] = rng.poisson(simulated["lambda_away"].to_numpy())

    return simulated


def build_group_table(
    group_name: str,
    teams: list[str],
    simulated_matches: pd.DataFrame,
) -> pd.DataFrame:
    rows = {
        team: {
            "group": group_name,
            "team": team,
            "played": 0,
            "points": 0,
            "goals_for": 0,
            "goals_against": 0,
            "goal_diff": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
        }
        for team in teams
    }

    group_matches = simulated_matches[
        simulated_matches["home_team_name"].isin(teams)
        & simulated_matches["away_team_name"].isin(teams)
    ]

    for row in group_matches.itertuples(index=False):
        home = row.home_team_name
        away = row.away_team_name
        hg = int(row.sim_home_goals)
        ag = int(row.sim_away_goals)

        rows[home]["played"] += 1
        rows[away]["played"] += 1

        rows[home]["goals_for"] += hg
        rows[home]["goals_against"] += ag
        rows[away]["goals_for"] += ag
        rows[away]["goals_against"] += hg

        if hg > ag:
            rows[home]["points"] += 3
            rows[home]["wins"] += 1
            rows[away]["losses"] += 1
        elif hg < ag:
            rows[away]["points"] += 3
            rows[away]["wins"] += 1
            rows[home]["losses"] += 1
        else:
            rows[home]["points"] += 1
            rows[away]["points"] += 1
            rows[home]["draws"] += 1
            rows[away]["draws"] += 1

    table = pd.DataFrame(rows.values())
    table["goal_diff"] = table["goals_for"] - table["goals_against"]

    table = table.sort_values(
        ["points", "goal_diff", "goals_for", "team"],
        ascending=[False, False, False, True],
    ).copy()

    table["rank"] = np.arange(1, len(table) + 1)

    return table[
        [
            "group",
            "rank",
            "team",
            "played",
            "points",
            "goal_diff",
            "goals_for",
            "goals_against",
            "wins",
            "draws",
            "losses",
        ]
    ]


def simulate_group_stage_once(
    matches: pd.DataFrame,
    groups: dict[str, list[str]],
    rng: np.random.Generator,
) -> pd.DataFrame:
    simulated = simulate_scores(matches, rng)

    tables = [
        build_group_table(group_name, teams, simulated)
        for group_name, teams in groups.items()
    ]

    table = pd.concat(tables, ignore_index=True)

    third_placed = (
        table[table["rank"] == 3]
        .sort_values(
            ["points", "goal_diff", "goals_for", "team"],
            ascending=[False, False, False, True],
        )
        .copy()
    )
    third_placed["third_place_rank"] = np.arange(1, len(third_placed) + 1)

    table = table.merge(
        third_placed[["team", "third_place_rank"]],
        on="team",
        how="left",
    )

    table["is_group_winner"] = table["rank"] == 1
    table["is_group_runner_up"] = table["rank"] == 2
    table["is_third_place"] = table["rank"] == 3
    table["is_best_third_place"] = table["third_place_rank"].between(1, 8)
    table["is_top2"] = table["rank"] <= 2
    table["advances"] = table["is_top2"] | table["is_best_third_place"].fillna(False)

    return table


def run_monte_carlo(
    matches: pd.DataFrame,
    groups: dict[str, list[str]],
    n_simulations: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    all_rows = []

    for simulation_id in range(1, n_simulations + 1):
        table = simulate_group_stage_once(matches, groups, rng)
        table["simulation_id"] = simulation_id
        all_rows.append(table)

    sims = pd.concat(all_rows, ignore_index=True)

    summary = (
        sims.groupby(["group", "team"], as_index=False)
        .agg(
            avg_points=("points", "mean"),
            avg_goal_diff=("goal_diff", "mean"),
            p_rank_1=("rank", lambda s: float((s == 1).mean())),
            p_rank_2=("rank", lambda s: float((s == 2).mean())),
            p_rank_3=("rank", lambda s: float((s == 3).mean())),
            p_top2=("is_top2", "mean"),
            p_best_third=("is_best_third_place", "mean"),
            p_advance=("advances", "mean"),
        )
        .sort_values(["group", "p_advance", "avg_points"], ascending=[True, False, False])
    )

    summary["n_simulations"] = n_simulations
    summary["seed"] = seed
    summary["model_name"] = "group_stage_monte_carlo_mvp_v1"
    summary["created_at"] = pd.Timestamp.utcnow()

    return summary


def write_summary_to_db(summary: pd.DataFrame) -> None:
    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS features.group_stage_simulation_summary_mvp_v1"))

    summary.to_sql(
        name="group_stage_simulation_summary_mvp_v1",
        con=engine,
        schema="features",
        if_exists="replace",
        index=False,
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_group_stage_sim_summary_mvp_v1_team
                    ON features.group_stage_simulation_summary_mvp_v1 (team)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_group_stage_sim_summary_mvp_v1_group
                    ON features.group_stage_simulation_summary_mvp_v1 ("group")
                """
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-simulations", type=int, default=DEFAULT_N_SIMULATIONS)
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument(
        "--write-db",
        action="store_true",
        help="Write summary to features.group_stage_simulation_summary_mvp_v1.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    matches = load_match_predictions()
    groups = load_groups()

    summary = run_monte_carlo(
        matches=matches,
        groups=groups,
        n_simulations=args.n_simulations,
        seed=args.seed,
    )

    if args.write_db:
        write_summary_to_db(summary)

    print("World Cup group-stage Monte Carlo MVP")
    print("Simulations:", args.n_simulations)
    print("Seed:", args.seed)
    print("Matches:", len(matches))
    print("Groups:", len(groups))
    print()

    display = summary.copy()
    numeric_columns = [
        "avg_points",
        "avg_goal_diff",
        "p_rank_1",
        "p_rank_2",
        "p_rank_3",
        "p_top2",
        "p_best_third",
        "p_advance",
    ]
    display[numeric_columns] = display[numeric_columns].round(4)

    print(display.to_string(index=False))


if __name__ == "__main__":
    main()
