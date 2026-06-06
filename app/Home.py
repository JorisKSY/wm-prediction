from dotenv import load_dotenv

load_dotenv()

import pandas as pd
import streamlit as st
from sqlalchemy import text

from wm_prediction.db.connection import check_database_connection, get_engine


st.set_page_config(
    page_title="WM Prediction",
    page_icon="⚽",
    layout="wide",
)


@st.cache_data(ttl=60)
def load_table_counts() -> pd.DataFrame:
    query = """
    SELECT 'match_predictions_mvp_v1' AS table_name, COUNT(*) AS rows
    FROM features.match_predictions_mvp_v1

    UNION ALL

    SELECT 'group_stage_simulation_summary_mvp_v1' AS table_name, COUNT(*) AS rows
    FROM features.group_stage_simulation_summary_mvp_v1

    UNION ALL

    SELECT 'tournament_simulation_summary_mvp_v1' AS table_name, COUNT(*) AS rows
    FROM features.tournament_simulation_summary_mvp_v1
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn)


@st.cache_data(ttl=60)
def load_group_stage_summary() -> pd.DataFrame:
    query = """
    SELECT
        "group",
        team,
        avg_points,
        avg_goal_diff,
        p_rank_1,
        p_top2,
        p_best_third,
        p_advance
    FROM features.group_stage_simulation_summary_mvp_v1
    ORDER BY "group", p_advance DESC, avg_points DESC
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn)


@st.cache_data(ttl=60)
def load_tournament_runs() -> pd.DataFrame:
    query = """
    SELECT
        simulation_run_id,
        model_name,
        n_simulations,
        seed_start,
        seed_end,
        MAX(created_at) AS created_at,
        COUNT(*) AS teams
    FROM features.tournament_simulation_summary_mvp_v1
    GROUP BY
        simulation_run_id,
        model_name,
        n_simulations,
        seed_start,
        seed_end
    ORDER BY created_at DESC, simulation_run_id DESC
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn)


@st.cache_data(ttl=60)
def load_tournament_summary(simulation_run_id: str) -> pd.DataFrame:
    query = """
    SELECT
        team,
        p_advance_group,
        p_reach_round_of_16,
        p_reach_quarter_final,
        p_reach_semi_final,
        p_final,
        p_title,
        p_third_place
    FROM features.tournament_simulation_summary_mvp_v1
    WHERE simulation_run_id = :simulation_run_id
    ORDER BY p_title DESC, p_final DESC, p_reach_semi_final DESC, team
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(
            text(query),
            conn,
            params={"simulation_run_id": simulation_run_id},
        )


@st.cache_data(ttl=60)
def load_match_predictions() -> pd.DataFrame:
    query = """
    SELECT
        match_date,
        home_team_name,
        away_team_name,
        lambda_home,
        lambda_away,
        p_home_win,
        p_draw,
        p_away_win
    FROM features.match_predictions_mvp_v1
    ORDER BY match_date, home_team_name, away_team_name
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn)


st.title("⚽ WM Prediction")
st.write("MVP: Two-Stage Poisson-Modell, Fixture Predictions und Gruppenphase-Simulation.")

st.subheader("System Status")

try:
    db_ok = check_database_connection()

    if db_ok:
        st.success("Postgres connection: OK")
    else:
        st.error("Postgres connection: failed")

except Exception as error:
    st.error("Postgres connection: failed")
    st.code(str(error))
    st.stop()


st.subheader("Datenstatus")

try:
    counts = load_table_counts()
    st.dataframe(counts, width="stretch", hide_index=True)

except Exception as error:
    st.warning("MVP prediction/simulation tables not available yet.")
    st.code(str(error))
    st.stop()


st.subheader("Gruppenphase Simulation")

summary = load_group_stage_summary()

metric_cols = st.columns(4)
metric_cols[0].metric("Teams", summary["team"].nunique())
metric_cols[1].metric("Gruppen", summary["group"].nunique())
metric_cols[2].metric("Ø Advance Sum", f"{summary['p_advance'].sum():.1f}")
metric_cols[3].metric("Top Advance", f"{summary['p_advance'].max():.1%}")

selected_group = st.selectbox(
    "Gruppe auswählen",
    options=sorted(summary["group"].unique()),
)

group_view = summary[summary["group"] == selected_group].copy()
percent_columns = ["p_rank_1", "p_top2", "p_best_third", "p_advance"]

for column in ["avg_points", "avg_goal_diff"]:
    group_view[column] = group_view[column].round(2)

for column in percent_columns:
    group_view[column] = (group_view[column] * 100).round(1)

st.dataframe(group_view, width="stretch", hide_index=True)

st.subheader("Top Weiterkommen-Wahrscheinlichkeiten")

top_advance = summary.sort_values("p_advance", ascending=False).head(12).copy()

for column in ["avg_points", "avg_goal_diff"]:
    top_advance[column] = top_advance[column].round(2)

for column in percent_columns:
    top_advance[column] = (top_advance[column] * 100).round(1)

st.dataframe(top_advance, width="stretch", hide_index=True)


st.subheader("Full-Tournament Simulation")

try:
    tournament_runs = load_tournament_runs()

    if tournament_runs.empty:
        st.info("No full-tournament simulation runs available yet.")
    else:
        selected_run = st.selectbox(
            "Simulation Run auswählen",
            options=tournament_runs["simulation_run_id"].tolist(),
            index=0,
        )

        selected_run_meta = tournament_runs[
            tournament_runs["simulation_run_id"] == selected_run
        ].iloc[0]

        tournament_summary = load_tournament_summary(selected_run).copy()

        tournament_metric_cols = st.columns(5)
        tournament_metric_cols[0].metric("Teams", tournament_summary["team"].nunique())
        tournament_metric_cols[1].metric("Simulationen", int(selected_run_meta["n_simulations"]))
        tournament_metric_cols[2].metric("Seed Start", int(selected_run_meta["seed_start"]))
        tournament_metric_cols[3].metric("Seed End", int(selected_run_meta["seed_end"]))
        tournament_metric_cols[4].metric("Title Sum", f"{tournament_summary['p_title'].sum():.1f}")

        probability_columns = [
            "p_advance_group",
            "p_reach_round_of_16",
            "p_reach_quarter_final",
            "p_reach_semi_final",
            "p_final",
            "p_title",
            "p_third_place",
        ]

        display_summary = tournament_summary.copy()

        for column in probability_columns:
            display_summary[column] = (display_summary[column] * 100).round(1)

        st.dataframe(display_summary, width="stretch", hide_index=True)

except Exception as error:
    st.warning("Full-tournament simulation summary not available yet.")
    st.code(str(error))


st.subheader("Match Predictions")

predictions = load_match_predictions().copy()

for column in ["lambda_home", "lambda_away"]:
    predictions[column] = predictions[column].round(2)

for column in ["p_home_win", "p_draw", "p_away_win"]:
    predictions[column] = (predictions[column] * 100).round(1)

st.dataframe(predictions, width="stretch", hide_index=True)
