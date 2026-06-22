import argparse

import numpy as np
import pandas as pd
from sqlalchemy import text

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.predict_knockout_matchup_v2_full_35 import KnockoutMatchupPredictorV2Full35
from wm_prediction.modeling.simulate_group_stage_mvp import (
    DEFAULT_RANDOM_SEED,
    build_group_table,
    load_groups,
    simulate_scores,
)
from wm_prediction.modeling.simulate_group_stage_v2_full_35 import load_match_predictions


def load_knockout_bracket() -> pd.DataFrame:
    query = """
    SELECT
        match_number,
        round_name,
        match_label,
        home_source_type,
        home_source_value,
        away_source_type,
        away_source_value
    FROM features.world_cup_knockout_bracket_mvp_v1
    ORDER BY match_number
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn)


def group_letter(group_label: str) -> str:
    return group_label.replace("Group ", "")


def add_qualification_flags(table: pd.DataFrame) -> pd.DataFrame:
    third_placed = (
        table[table["rank"] == 3]
        .sort_values(
            ["points", "goal_diff", "goals_for", "team"],
            ascending=[False, False, False, True],
        )
        .copy()
    )
    third_placed["third_place_rank"] = np.arange(1, len(third_placed) + 1)

    out = table.merge(
        third_placed[["team", "third_place_rank"]],
        on="team",
        how="left",
    )

    out["group_letter"] = out["group"].map(group_letter)
    out["qualified_as"] = np.select(
        [
            out["rank"] == 1,
            out["rank"] == 2,
            out["third_place_rank"].between(1, 8),
        ],
        [
            "group_winner",
            "group_runner_up",
            "best_third",
        ],
        default="eliminated",
    )
    out["qualified"] = out["qualified_as"] != "eliminated"

    return out


def simulate_group_stage(
    rng: np.random.Generator,
    matches: pd.DataFrame | None = None,
    groups: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    # matches/groups can be passed in to avoid re-reading the DB on every
    # simulation (Monte Carlo loop). Defaults preserve standalone behaviour.
    if matches is None:
        matches = load_match_predictions()
    if groups is None:
        groups = load_groups()
    simulated = simulate_scores(matches, rng)

    tables = [
        build_group_table(group_name, teams, simulated)
        for group_name, teams in groups.items()
    ]

    group_table = pd.concat(tables, ignore_index=True)
    return add_qualification_flags(group_table)


def resolve_fixed_slot(group_table: pd.DataFrame, rank: int, group_candidates: str) -> str:
    if len(group_candidates) != 1:
        raise ValueError(f"Fixed slot expected one group, got {group_candidates}")

    match = group_table[
        (group_table["group_letter"] == group_candidates)
        & (group_table["rank"] == rank)
    ]

    if len(match) != 1:
        raise ValueError(f"Expected exactly one team for {rank}{group_candidates}, got {len(match)}")

    return str(match.iloc[0]["team"])


def resolve_random_third_slot(
    group_table: pd.DataFrame,
    group_candidates: str,
    used_third_teams: set[str],
    rng: np.random.Generator,
) -> str:
    candidates = group_table[
        (group_table["rank"] == 3)
        & (group_table["qualified"])
        & (group_table["group_letter"].isin(list(group_candidates)))
        & (~group_table["team"].isin(used_third_teams))
    ].copy()

    if candidates.empty:
        raise ValueError(f"No available third-place team for candidate groups {group_candidates}")

    chosen_index = int(rng.integers(0, len(candidates)))
    team = str(candidates.iloc[chosen_index]["team"])
    used_third_teams.add(team)

    return team


def build_third_place_slot_assignment(
    bracket: pd.DataFrame,
    group_table: pd.DataFrame,
    rng: np.random.Generator,
) -> dict[tuple[int, str], str]:
    """Assign all third-place Round-of-32 slots together.

    Greedy random assignment can create dead ends. This keeps the MVP rule
    random, but uses backtracking so every qualified third-place team is used
    at most once and every 3... slot gets a valid team.
    """
    third_slots: list[tuple[int, str, str]] = []

    for row in bracket.itertuples(index=False):
        match_number = int(row.match_number)

        for side in ("home", "away"):
            source_type = getattr(row, f"{side}_source_type")
            source_value = str(getattr(row, f"{side}_source_value"))

            if source_type == "slot" and source_value.startswith("3"):
                third_slots.append((match_number, side, source_value[1:]))

    qualified_thirds = group_table[
        (group_table["rank"] == 3) & (group_table["qualified"])
    ].copy()

    if len(qualified_thirds) != len(third_slots):
        raise ValueError(
            "Expected one qualified third-place team per third-place slot, "
            f"got {len(qualified_thirds)} teams and {len(third_slots)} slots"
        )

    group_to_team = dict(
        zip(
            qualified_thirds["group_letter"],
            qualified_thirds["team"],
            strict=False,
        )
    )

    slot_options: list[tuple[int, str, str, list[str]]] = []

    for match_number, side, group_candidates in third_slots:
        teams = [
            str(group_to_team[group])
            for group in list(group_candidates)
            if group in group_to_team
        ]
        teams = rng.permutation(teams).tolist()

        if not teams:
            raise ValueError(
                f"No qualified third-place team for slot 3{group_candidates} "
                f"in match {match_number}"
            )

        slot_options.append((match_number, side, group_candidates, teams))

    slot_options.sort(key=lambda item: len(item[3]))

    assignment: dict[tuple[int, str], str] = {}
    used_teams: set[str] = set()

    def backtrack(position: int) -> bool:
        if position == len(slot_options):
            return True

        match_number, side, _group_candidates, teams = slot_options[position]
        key = (match_number, side)

        for team in teams:
            if team in used_teams:
                continue

            assignment[key] = team
            used_teams.add(team)

            if backtrack(position + 1):
                return True

            used_teams.remove(team)
            assignment.pop(key, None)

        return False

    if not backtrack(0):
        qualified_groups = "".join(sorted(group_to_team))
        slot_descriptions = ", ".join(
            f"{match_number}:{side}=3{group_candidates}"
            for match_number, side, group_candidates, _teams in slot_options
        )
        raise ValueError(
            "Could not assign third-place teams to Round-of-32 slots. "
            f"Qualified third groups: {qualified_groups}. "
            f"Slots: {slot_descriptions}"
        )

    return assignment


def resolve_slot(
    slot_value: str,
    group_table: pd.DataFrame,
    used_third_teams: set[str],
    rng: np.random.Generator,
) -> str:
    rank = int(slot_value[0])
    group_candidates = slot_value[1:]

    if rank in (1, 2):
        return resolve_fixed_slot(group_table, rank, group_candidates)

    if rank == 3:
        return resolve_random_third_slot(
            group_table=group_table,
            group_candidates=group_candidates,
            used_third_teams=used_third_teams,
            rng=rng,
        )

    raise ValueError(f"Unsupported slot: {slot_value}")


def resolve_source(
    source_type: str,
    source_value: str,
    group_table: pd.DataFrame,
    match_results: dict[int, dict[str, str]],
    used_third_teams: set[str],
    rng: np.random.Generator,
    third_slot_assignment: dict[tuple[int, str], str] | None = None,
    match_number: int | None = None,
    side: str | None = None,
) -> str:
    if source_type == "slot":
        if source_value.startswith("3") and third_slot_assignment is not None:
            if match_number is None or side is None:
                raise ValueError("Third-place slot assignment needs match_number and side")
            return third_slot_assignment[(match_number, side)]

        return resolve_slot(source_value, group_table, used_third_teams, rng)

    source_match = int(source_value)

    if source_type == "winner":
        return match_results[source_match]["winner"]

    if source_type == "loser":
        return match_results[source_match]["loser"]

    raise ValueError(f"Unsupported source_type: {source_type}")


def simulate_knockout_match(
    match_number: int,
    round_name: str,
    home_team: str,
    away_team: str,
    rng: np.random.Generator,
    predictor: KnockoutMatchupPredictorV2Full35,
) -> dict[str, object]:
    pred = predictor.predict(home_team, away_team)

    home_advances = rng.random() < pred["p_home_advance"]
    winner = home_team if home_advances else away_team
    loser = away_team if home_advances else home_team

    return {
        "match_number": match_number,
        "round_name": round_name,
        "home_team": home_team,
        "away_team": away_team,
        "p_home_advance": pred["p_home_advance"],
        "p_away_advance": pred["p_away_advance"],
        "winner": winner,
        "loser": loser,
    }


def simulate_tournament(
    seed: int,
    predictor: KnockoutMatchupPredictorV2Full35 | None = None,
    matches: pd.DataFrame | None = None,
    groups: dict[str, list[str]] | None = None,
    bracket: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)

    group_table = simulate_group_stage(rng, matches=matches, groups=groups)
    if bracket is None:
        bracket = load_knockout_bracket()

    used_third_teams: set[str] = set()
    third_slot_assignment = build_third_place_slot_assignment(bracket, group_table, rng)

    if predictor is None:
        predictor = KnockoutMatchupPredictorV2Full35(sorted(group_table["team"].unique()))

    match_results: dict[int, dict[str, str]] = {}
    knockout_rows = []

    for row in bracket.itertuples(index=False):
        home_team = resolve_source(
            source_type=row.home_source_type,
            source_value=str(row.home_source_value),
            group_table=group_table,
            match_results=match_results,
            used_third_teams=used_third_teams,
            rng=rng,
            third_slot_assignment=third_slot_assignment,
            match_number=int(row.match_number),
            side="home",
        )
        away_team = resolve_source(
            source_type=row.away_source_type,
            source_value=str(row.away_source_value),
            group_table=group_table,
            match_results=match_results,
            used_third_teams=used_third_teams,
            rng=rng,
            third_slot_assignment=third_slot_assignment,
            match_number=int(row.match_number),
            side="away",
        )

        result = simulate_knockout_match(
            match_number=int(row.match_number),
            round_name=str(row.round_name),
            home_team=home_team,
            away_team=away_team,
            rng=rng,
            predictor=predictor,
        )

        match_results[int(row.match_number)] = {
            "winner": str(result["winner"]),
            "loser": str(result["loser"]),
        }
        knockout_rows.append(result)

    knockout = pd.DataFrame(knockout_rows)

    qualified = (
        group_table[group_table["qualified"]]
        .sort_values(["group", "rank", "third_place_rank", "team"])
        [
            [
                "group",
                "rank",
                "team",
                "points",
                "goal_diff",
                "goals_for",
                "qualified_as",
                "third_place_rank",
            ]
        ]
    )

    return group_table, qualified, knockout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument(
        "--n-simulations",
        type=int,
        default=1,
        help="Number of full tournament simulations to run.",
    )
    parser.add_argument(
        "--write-db",
        action="store_true",
        help="Write multi-simulation team probability summary to the database.",
    )
    parser.add_argument(
        "--simulation-run-id",
        default=None,
        help="Optional run id for database output. Defaults to model/seed/n metadata.",
    )
    return parser.parse_args()


def print_single_simulation(
    seed: int,
    qualified: pd.DataFrame,
    knockout: pd.DataFrame,
) -> None:
    champion = knockout.loc[knockout["match_number"] == 104, "winner"].iloc[0]
    third_place = knockout.loc[knockout["match_number"] == 103, "winner"].iloc[0]

    print("World Cup full tournament simulation v2 full 35")
    print("Seed:", seed)
    print("Qualified teams:", len(qualified))
    print("Knockout matches:", len(knockout))
    print("Champion:", champion)
    print("Third place:", third_place)
    print()

    print("Qualified teams:")
    print(qualified.to_string(index=False))
    print()

    display = knockout.copy()
    display["p_home_advance"] = (display["p_home_advance"] * 100).round(1)
    display["p_away_advance"] = (display["p_away_advance"] * 100).round(1)

    print("Knockout results:")
    print(display.to_string(index=False))


def make_team_probability_summary(
    summary: pd.DataFrame,
    column: str,
    count_name: str,
    probability_name: str,
) -> pd.DataFrame:
    n_simulations = len(summary)

    if summary[column].apply(lambda value: isinstance(value, list)).all():
        teams = summary[column].explode()
    else:
        teams = summary[column]

    out = (
        teams
        .value_counts()
        .rename_axis("team")
        .reset_index(name=count_name)
    )
    out[probability_name] = out[count_name] / n_simulations

    return out


def make_combined_team_probability_summary(
    summary: pd.DataFrame,
    team_names: list[str],
) -> pd.DataFrame:
    rows = []

    for team in team_names:
        rows.append(
            {
                "team": team,
                "p_advance_group": summary["qualified_teams"].apply(lambda teams: team in teams).mean(),
                "p_reach_round_of_16": summary["round_of_16_teams"].apply(lambda teams: team in teams).mean(),
                "p_reach_quarter_final": summary["quarter_final_teams"].apply(lambda teams: team in teams).mean(),
                "p_reach_semi_final": summary["semi_final_teams"].apply(lambda teams: team in teams).mean(),
                "p_final": summary["final_teams"].apply(lambda teams: team in teams).mean(),
                "p_title": (summary["champion"] == team).mean(),
                "p_third_place": (summary["third_place"] == team).mean(),
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values(
            [
                "p_title",
                "p_final",
                "p_reach_semi_final",
                "p_reach_quarter_final",
                "p_reach_round_of_16",
                "p_advance_group",
            ],
            ascending=False,
        )
        .reset_index(drop=True)
    )


def write_tournament_summary_to_db(
    results: list[dict[str, object]],
    team_names: list[str],
    seed_start: int,
    n_simulations: int,
    simulation_run_id: str | None = None,
) -> str:
    model_name = "xgboost_v2_full_35"
    seed_end = seed_start + n_simulations - 1

    if simulation_run_id is None:
        simulation_run_id = (
            f"{model_name}_seed_{seed_start}_to_{seed_end}_n_{n_simulations}"
        )

    summary = pd.DataFrame(results)
    combined_summary = make_combined_team_probability_summary(summary, team_names)

    out = combined_summary.copy()
    out.insert(0, "seed_end", seed_end)
    out.insert(0, "seed_start", seed_start)
    out.insert(0, "n_simulations", n_simulations)
    out.insert(0, "feature_set_name", "v2_full_35")
    out.insert(0, "is_technical_dry_run", False)
    out.insert(0, "model_name", model_name)
    out.insert(0, "simulation_run_id", simulation_run_id)

    columns = [
        "simulation_run_id",
        "model_name",
        "is_technical_dry_run",
        "feature_set_name",
        "n_simulations",
        "seed_start",
        "seed_end",
        "team",
        "p_advance_group",
        "p_reach_round_of_16",
        "p_reach_quarter_final",
        "p_reach_semi_final",
        "p_final",
        "p_title",
        "p_third_place",
    ]
    out = out[columns]

    engine = get_engine()

    table_name = "tournament_simulation_summary_v2_full_35"

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS features"))

        exists = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'features'
                      AND table_name = :table_name
                )
                """
            ),
            {"table_name": table_name},
        ).scalar_one()

        if exists:
            conn.execute(
                text(
                    """
                    DELETE FROM features.tournament_simulation_summary_v2_full_35
                    WHERE simulation_run_id = :simulation_run_id
                    """
                ),
                {"simulation_run_id": simulation_run_id},
            )

        out.to_sql(
            name=table_name,
            con=conn,
            schema="features",
            if_exists="append",
            index=False,
            method="multi",
        )

        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_tournament_sim_summary_v2_full_35_run
                    ON features.tournament_simulation_summary_v2_full_35 (simulation_run_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_tournament_sim_summary_v2_full_35_team
                    ON features.tournament_simulation_summary_v2_full_35 (team)
                """
            )
        )

    return simulation_run_id


def print_multi_simulation_summary(
    results: list[dict[str, object]],
    team_names: list[str],
) -> None:
    summary = pd.DataFrame(results)
    n_simulations = len(summary)

    combined_summary = make_combined_team_probability_summary(summary, team_names)

    advance_summary = make_team_probability_summary(
        summary,
        column="qualified_teams",
        count_name="advance_group",
        probability_name="p_advance_group",
    )
    round_of_16_summary = make_team_probability_summary(
        summary,
        column="round_of_16_teams",
        count_name="round_of_16",
        probability_name="p_reach_round_of_16",
    )
    quarter_final_summary = make_team_probability_summary(
        summary,
        column="quarter_final_teams",
        count_name="quarter_finals",
        probability_name="p_reach_quarter_final",
    )
    semi_final_summary = make_team_probability_summary(
        summary,
        column="semi_final_teams",
        count_name="semi_finals",
        probability_name="p_reach_semi_final",
    )
    finalist_summary = make_team_probability_summary(
        summary,
        column="final_teams",
        count_name="finals",
        probability_name="p_final",
    )
    champion_summary = make_team_probability_summary(
        summary,
        column="champion",
        count_name="titles",
        probability_name="p_title",
    )
    third_place_summary = make_team_probability_summary(
        summary,
        column="third_place",
        count_name="third_places",
        probability_name="p_third_place",
    )

    print("World Cup full tournament Monte Carlo v2 full 35")
    print("Simulations:", n_simulations)
    print("Seed start:", int(summary["seed"].min()))
    print("Seed end:", int(summary["seed"].max()))
    print()

    print("Combined team probability summary:")
    print(combined_summary.head(20).to_string(index=False))
    print()

    print("Probability sum audit:")
    print("sum_p_advance_group:", round(float(combined_summary["p_advance_group"].sum()), 10))
    print("sum_p_reach_round_of_16:", round(float(combined_summary["p_reach_round_of_16"].sum()), 10))
    print("sum_p_reach_quarter_final:", round(float(combined_summary["p_reach_quarter_final"].sum()), 10))
    print("sum_p_reach_semi_final:", round(float(combined_summary["p_reach_semi_final"].sum()), 10))
    print("sum_p_final:", round(float(combined_summary["p_final"].sum()), 10))
    print("sum_p_title:", round(float(combined_summary["p_title"].sum()), 10))
    print("sum_p_third_place:", round(float(combined_summary["p_third_place"].sum()), 10))
    print()

    print("Top Round-of-32 probabilities (advanced from group):")
    print(advance_summary.head(20).to_string(index=False))
    print()

    print("Top Round-of-16 probabilities (won Round of 32):")
    print(round_of_16_summary.head(20).to_string(index=False))
    print()

    print("Top quarter-final probabilities:")
    print(quarter_final_summary.head(20).to_string(index=False))
    print()

    print("Top semi-final probabilities:")
    print(semi_final_summary.head(20).to_string(index=False))
    print()

    print("Top final probabilities:")
    print(finalist_summary.head(20).to_string(index=False))
    print()

    print("Top title probabilities:")
    print(champion_summary.head(20).to_string(index=False))
    print()

    print("Top third-place probabilities:")
    print(third_place_summary.head(20).to_string(index=False))


def main() -> None:
    args = parse_args()

    if args.n_simulations < 1:
        raise ValueError("--n-simulations must be at least 1")

    if args.n_simulations == 1:
        if args.write_db:
            raise ValueError("--write-db currently requires --n-simulations > 1")

        _group_table, qualified, knockout = simulate_tournament(seed=args.seed)
        print_single_simulation(
            seed=args.seed,
            qualified=qualified,
            knockout=knockout,
        )
        return

    groups = load_groups()
    team_names = sorted(
        team
        for teams in groups.values()
        for team in teams
    )
    predictor = KnockoutMatchupPredictorV2Full35(team_names)

    # Load invariant data ONCE before the Monte Carlo loop (was re-read per sim).
    matches = load_match_predictions()
    bracket = load_knockout_bracket()

    results: list[dict[str, object]] = []

    for offset in range(args.n_simulations):
        seed = args.seed + offset
        _group_table, _qualified, knockout = simulate_tournament(
            seed=seed,
            predictor=predictor,
            matches=matches,
            groups=groups,
            bracket=bracket,
        )

        final = knockout.loc[knockout["match_number"] == 104].iloc[0]
        third_place_match = knockout.loc[knockout["match_number"] == 103].iloc[0]

        results.append(
            {
                "seed": seed,
                "qualified_teams": sorted(_qualified["team"].tolist()),
                "round_of_16_teams": sorted(
                    knockout.loc[
                        knockout["round_name"] == "round_of_32",
                        "winner",
                    ].tolist()
                ),
                "quarter_final_teams": sorted(
                    knockout.loc[
                        knockout["round_name"] == "round_of_16",
                        "winner",
                    ].tolist()
                ),
                "semi_final_teams": sorted(
                    knockout.loc[
                        knockout["round_name"] == "quarter_final",
                        "winner",
                    ].tolist()
                ),
                "final_teams": sorted([final["home_team"], final["away_team"]]),
                "champion": final["winner"],
                "runner_up": final["loser"],
                "third_place": third_place_match["winner"],
                "fourth_place": third_place_match["loser"],
            }
        )

    if args.write_db:
        simulation_run_id = write_tournament_summary_to_db(
            results=results,
            team_names=team_names,
            seed_start=args.seed,
            n_simulations=args.n_simulations,
            simulation_run_id=args.simulation_run_id,
        )
        print("Wrote tournament simulation summary to DB")
        print("simulation_run_id:", simulation_run_id)
        print()

    print_multi_simulation_summary(results, team_names=team_names)


if __name__ == "__main__":
    main()
