import argparse

import numpy as np
import pandas as pd
from sqlalchemy import text

from wm_prediction.db.connection import get_engine
from wm_prediction.modeling.simulate_group_stage_mvp import (
    DEFAULT_RANDOM_SEED,
    DEFAULT_N_SIMULATIONS,
    build_group_table,
    load_groups,
    simulate_scores,
)


MODEL_NAME = "group_stage_monte_carlo_v2_technical_33_no_momentum"
PREDICTION_MODEL_NAME = "xgboost_v2_technical_33_no_momentum"
FEATURE_SET_NAME = "v2_technical_33_no_momentum"


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
        p_away_win,
        model_name,
        feature_set_name,
        is_technical_dry_run
    FROM features.match_predictions_v2_technical_33
    ORDER BY match_date, historical_match_id
    """

    engine = get_engine()
    with engine.connect() as conn:
        predictions = pd.read_sql_query(text(query), conn, parse_dates=["match_date"])

    if predictions.empty:
        raise ValueError("No rows found in features.match_predictions_v2_technical_33.")

    if not predictions["is_technical_dry_run"].all():
        raise ValueError("Expected all v2 technical prediction rows to be marked as dry run.")

    return predictions


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
    summary["model_name"] = MODEL_NAME
    summary["prediction_model_name"] = PREDICTION_MODEL_NAME
    summary["feature_set_name"] = FEATURE_SET_NAME
    summary["is_technical_dry_run"] = True
    summary["dry_run_reason"] = (
        "Missing real 2025 FIFA ranking snapshot for rank_improve_1yr; "
        "momentum features excluded."
    )
    summary["created_at"] = pd.Timestamp.utcnow()

    return summary


def write_summary_to_db(summary: pd.DataFrame) -> None:
    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS features.group_stage_simulation_summary_v2_technical_33"))

    summary.to_sql(
        name="group_stage_simulation_summary_v2_technical_33",
        con=engine,
        schema="features",
        if_exists="replace",
        index=False,
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_group_stage_sim_summary_v2_technical_33_team
                    ON features.group_stage_simulation_summary_v2_technical_33 (team)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_group_stage_sim_summary_v2_technical_33_group
                    ON features.group_stage_simulation_summary_v2_technical_33 ("group")
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
        help="Write summary to features.group_stage_simulation_summary_v2_technical_33.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.n_simulations < 1:
        raise ValueError("--n-simulations must be at least 1")

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

    print("World Cup group-stage Monte Carlo v2 technical 33 no momentum")
    print("Simulations:", args.n_simulations)
    print("Seed:", args.seed)
    print("Prediction model:", PREDICTION_MODEL_NAME)
    print("Feature set:", FEATURE_SET_NAME)
    print("Technical dry run:", True)
    print()

    display = summary.copy()
    probability_columns = [
        "p_rank_1",
        "p_rank_2",
        "p_rank_3",
        "p_top2",
        "p_best_third",
        "p_advance",
    ]
    numeric_columns = ["avg_points", "avg_goal_diff"] + probability_columns
    display[numeric_columns] = display[numeric_columns].round(4)

    print(display.to_string(index=False))

    print()
    print("Probability sum audit:")
    print("sum_p_advance:", round(float(summary["p_advance"].sum()), 10))
    print("sum_p_rank_1:", round(float(summary["p_rank_1"].sum()), 10))
    print("sum_p_rank_2:", round(float(summary["p_rank_2"].sum()), 10))


if __name__ == "__main__":
    main()
