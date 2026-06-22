import numpy as np
import pandas as pd

from wm_prediction.modeling.predict_knockout_matchup_v2_full_35 import (
    KnockoutMatchupPredictorV2Full35,
)
from wm_prediction.modeling.simulate_group_stage_mvp import load_groups
from wm_prediction.modeling.simulate_tournament_v2_full_35 import (
    build_third_place_slot_assignment,
    load_knockout_bracket,
    make_combined_team_probability_summary,
    resolve_source,
    simulate_knockout_match,
)


ROUND_TEAM_COLUMNS = {
    "round_of_32": "round_of_16_teams",
    "round_of_16": "quarter_final_teams",
    "quarter_final": "semi_final_teams",
    "semi_final": "final_teams",
}


def build_manual_group_table(
    group_rankings: dict[str, list[str]],
    third_place_strength: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Build a qualified-team table from manually chosen group rankings.

    The user controls ranks 1-4 per group. Because no exact group-stage scores
    are entered, best-third ordering uses a model-strength proxy passed in via
    third_place_strength. This changes the knockout path, not team strength.
    """
    third_place_strength = third_place_strength or {}

    rows = []
    for group, teams in group_rankings.items():
        if len(teams) != 4:
            raise ValueError(f"Group {group} must contain exactly 4 teams")

        if len(set(teams)) != 4:
            raise ValueError(f"Group {group} contains duplicate teams")

        for index, team in enumerate(teams, start=1):
            rows.append(
                {
                    "group": group,
                    "group_letter": group,
                    "rank": index,
                    "team": team,
                    "points": 5 - index,
                    "goal_diff": 4 - index,
                    "goals_for": 4 - index,
                    "third_place_strength": float(third_place_strength.get(team, 0.0)),
                }
            )

    table = pd.DataFrame(rows)

    third_placed = (
        table[table["rank"] == 3]
        .sort_values(
            ["third_place_strength", "group", "team"],
            ascending=[False, True, True],
        )
        .copy()
    )
    third_placed["third_place_rank"] = np.arange(1, len(third_placed) + 1)

    table = table.merge(
        third_placed[["team", "third_place_rank"]],
        on="team",
        how="left",
    )

    table["qualified_as"] = np.select(
        [
            table["rank"] == 1,
            table["rank"] == 2,
            table["third_place_rank"].between(1, 8),
        ],
        [
            "group_winner",
            "group_runner_up",
            "best_third",
        ],
        default="eliminated",
    )
    table["qualified"] = table["qualified_as"] != "eliminated"

    return table


def simulate_knockout_from_group_table(
    group_table: pd.DataFrame,
    seed: int,
    predictor: KnockoutMatchupPredictorV2Full35,
    bracket: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    if bracket is None:
        bracket = load_knockout_bracket()

    used_third_teams: set[str] = set()
    third_slot_assignment = build_third_place_slot_assignment(
        bracket=bracket,
        group_table=group_table,
        rng=rng,
    )

    match_results: dict[int, dict[str, str]] = {}
    knockout_rows = []

    for row in bracket.itertuples(index=False):
        match_number = int(row.match_number)

        home_team = resolve_source(
            source_type=row.home_source_type,
            source_value=str(row.home_source_value),
            group_table=group_table,
            match_results=match_results,
            used_third_teams=used_third_teams,
            rng=rng,
            third_slot_assignment=third_slot_assignment,
            match_number=match_number,
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
            match_number=match_number,
            side="away",
        )

        result = simulate_knockout_match(
            match_number=match_number,
            round_name=str(row.round_name),
            home_team=home_team,
            away_team=away_team,
            rng=rng,
            predictor=predictor,
        )

        match_results[match_number] = {
            "winner": str(result["winner"]),
            "loser": str(result["loser"]),
        }
        knockout_rows.append(result)

    return pd.DataFrame(knockout_rows)


def summarize_knockout_run(
    group_table: pd.DataFrame,
    knockout: pd.DataFrame,
) -> dict[str, object]:
    qualified_teams = group_table[group_table["qualified"]]["team"].tolist()

    out: dict[str, object] = {
        "qualified_teams": qualified_teams,
        "round_of_16_teams": [],
        "quarter_final_teams": [],
        "semi_final_teams": [],
        "final_teams": [],
        "champion": knockout.loc[knockout["match_number"] == 104, "winner"].iloc[0],
        "third_place": knockout.loc[knockout["match_number"] == 103, "winner"].iloc[0],
    }

    for round_name, column in ROUND_TEAM_COLUMNS.items():
        round_matches = knockout[knockout["round_name"] == round_name]
        out[column] = round_matches["winner"].tolist()

    return out


def run_scenario_simulation(
    group_rankings: dict[str, list[str]],
    third_place_strength: dict[str, float] | None = None,
    seed_start: int = 42,
    n_simulations: int = 300,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    group_table = build_manual_group_table(
        group_rankings=group_rankings,
        third_place_strength=third_place_strength,
    )

    team_names = sorted(group_table["team"].unique())
    bracket = load_knockout_bracket()
    predictor = KnockoutMatchupPredictorV2Full35(team_names)

    results = []
    representative_knockout = None

    for offset in range(n_simulations):
        knockout = simulate_knockout_from_group_table(
            group_table=group_table,
            seed=seed_start + offset,
            predictor=predictor,
            bracket=bracket,
        )

        if representative_knockout is None:
            representative_knockout = knockout.copy()

        results.append(
            summarize_knockout_run(
                group_table=group_table,
                knockout=knockout,
            )
        )

    summary = pd.DataFrame(results)
    probabilities = make_combined_team_probability_summary(
        summary=summary,
        team_names=team_names,
    )

    if representative_knockout is None:
        representative_knockout = pd.DataFrame()

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
        .copy()
    )

    return probabilities, representative_knockout, qualified


def default_group_rankings() -> dict[str, list[str]]:
    return load_groups()


if __name__ == "__main__":
    rankings = default_group_rankings()
    probabilities, knockout, qualified = run_scenario_simulation(
        group_rankings=rankings,
        seed_start=42,
        n_simulations=20,
    )

    print("qualified", len(qualified))
    print("knockout_matches", len(knockout))
    print(
        probabilities[
            [
                "p_advance_group",
                "p_reach_round_of_16",
                "p_reach_quarter_final",
                "p_reach_semi_final",
                "p_final",
                "p_title",
                "p_third_place",
            ]
        ].sum().round(6).to_string()
    )
    print(probabilities.head(10).to_string(index=False))
