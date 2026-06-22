from dotenv import load_dotenv

load_dotenv()

import pandas as pd
import streamlit as st
from sqlalchemy import text

from wm_prediction.db.connection import check_database_connection, get_engine
from wm_prediction.modeling.scenario_tournament_v2_full_35 import run_scenario_simulation


st.set_page_config(
    page_title="WM 2026 Forecast Dashboard",
    page_icon="⚽",
    layout="wide",
)


MODELS = {
    "MVP v1 (Poisson)": {
        "match_predictions": "match_predictions_mvp_v1",
        "group_stage_summary": "group_stage_simulation_summary_mvp_v1",
        "tournament_summary": "tournament_simulation_summary_mvp_v1",
        "is_dry_run": False,
    },
    "v2 Technical 33 (Dry Run, XGBoost)": {
        "match_predictions": "match_predictions_v2_technical_33",
        "group_stage_summary": "group_stage_simulation_summary_v2_technical_33",
        "tournament_summary": "tournament_simulation_summary_v2_technical_33",
        "is_dry_run": True,
    },
    "v2 Full 35 (XGBoost)": {
        "match_predictions": "match_predictions_v2_full_35",
        "group_stage_summary": "group_stage_simulation_summary_v2_full_35",
        "tournament_summary": "tournament_simulation_summary_v2_full_35",
        "is_dry_run": False,
    },
}


CSS = """
<style>
    .stApp {
        background: #f4f6f8;
        color: #172033;
    }

    h1, h2, h3 {
        color: #14213d;
        letter-spacing: -0.02em;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1280px;
    }

    section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #e6e9ef;
    }

    .hero {
        background: linear-gradient(135deg, #ffffff 0%, #edf2f7 100%);
        border: 1px solid #e5e8ef;
        border-radius: 22px;
        padding: 28px 32px;
        margin-bottom: 24px;
        box-shadow: 0 12px 30px rgba(20, 33, 61, 0.06);
    }

    .hero-title {
        font-size: 2.6rem;
        font-weight: 760;
        color: #14213d;
        margin-bottom: 0.35rem;
    }

    .hero-subtitle {
        font-size: 1.08rem;
        color: #526070;
        max-width: 850px;
        line-height: 1.55;
    }

    .kpi-card {
        background: #ffffff;
        border: 1px solid #e5e8ef;
        border-radius: 18px;
        padding: 22px 22px 18px 22px;
        box-shadow: 0 10px 24px rgba(20, 33, 61, 0.055);
        min-height: 145px;
    }

    .kpi-label {
        color: #697586;
        font-size: 0.86rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 700;
        margin-bottom: 10px;
    }

    .kpi-main {
        color: #14213d;
        font-size: 1.35rem;
        font-weight: 760;
        line-height: 1.2;
        margin-bottom: 8px;
    }

    .kpi-value {
        color: #1f7a4d;
        font-size: 1.65rem;
        font-weight: 800;
        line-height: 1.15;
    }

    .kpi-value.gold {
        color: #b88900;
    }

    .section-card {
        background: #ffffff;
        border: 1px solid #e5e8ef;
        border-radius: 18px;
        padding: 20px 22px;
        box-shadow: 0 10px 24px rgba(20, 33, 61, 0.04);
        margin-top: 16px;
    }

    .match-card {
        background: #ffffff;
        border: 1px solid #e5e8ef;
        border-radius: 22px;
        padding: 26px 30px;
        box-shadow: 0 12px 30px rgba(20, 33, 61, 0.055);
        margin-top: 16px;
        margin-bottom: 18px;
    }

    .match-title {
        color: #14213d;
        font-size: 2.1rem;
        font-weight: 780;
        text-align: center;
        margin-bottom: 6px;
    }

    .match-subtitle {
        color: #697586;
        font-size: 0.95rem;
        text-align: center;
        margin-bottom: 18px;
    }

    .prob-card {
        background: #f8fafc;
        border: 1px solid #e6e9ef;
        border-radius: 16px;
        padding: 18px 20px;
        text-align: center;
    }

    .prob-label {
        color: #697586;
        font-size: 0.84rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .prob-value {
        color: #14213d;
        font-size: 1.8rem;
        font-weight: 800;
    }

    .small-muted {
        color: #697586;
        font-size: 0.92rem;
        line-height: 1.45;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 14px;
        overflow: hidden;
    }
</style>
"""


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


@st.cache_data(ttl=60)
def load_tournament_runs(table: str) -> pd.DataFrame:
    query = f"""
    SELECT
        simulation_run_id,
        model_name,
        n_simulations,
        seed_start,
        seed_end,
        COUNT(*) AS teams
    FROM features.{table}
    GROUP BY
        simulation_run_id,
        model_name,
        n_simulations,
        seed_start,
        seed_end
    ORDER BY n_simulations DESC, simulation_run_id DESC
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn)


@st.cache_data(ttl=60)
def load_tournament_summary(table: str, simulation_run_id: str) -> pd.DataFrame:
    query = f"""
    SELECT
        team,
        p_advance_group,
        p_reach_round_of_16,
        p_reach_quarter_final,
        p_reach_semi_final,
        p_final,
        p_title,
        p_third_place
    FROM features.{table}
    WHERE simulation_run_id = :simulation_run_id
    ORDER BY p_title DESC, p_final DESC, team
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(
            text(query),
            conn,
            params={"simulation_run_id": simulation_run_id},
        )


@st.cache_data(ttl=60)
def load_group_stage_summary(table: str) -> pd.DataFrame:
    query = f"""
    SELECT
        "group",
        team,
        avg_points,
        avg_goal_diff,
        p_rank_1,
        p_top2,
        p_best_third,
        p_advance
    FROM features.{table}
    ORDER BY "group", p_advance DESC, avg_points DESC
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn)


@st.cache_data(ttl=60)
def load_match_predictions(table: str) -> pd.DataFrame:
    query = f"""
    SELECT
        match_date,
        home_team_name,
        away_team_name,
        lambda_home,
        lambda_away,
        p_home_win,
        p_draw,
        p_away_win
    FROM features.{table}
    ORDER BY match_date, home_team_name, away_team_name
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn)


@st.cache_data(ttl=60)
def load_table_counts(match_table: str, group_table: str, tournament_table: str) -> pd.DataFrame:
    query = f"""
    SELECT '{match_table}' AS table_name, COUNT(*) AS rows
    FROM features.{match_table}

    UNION ALL

    SELECT '{group_table}' AS table_name, COUNT(*) AS rows
    FROM features.{group_table}

    UNION ALL

    SELECT '{tournament_table}' AS table_name, COUNT(*) AS rows
    FROM features.{tournament_table}
    """

    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn)


def pick_dark_horse(tournament_summary: pd.DataFrame) -> pd.Series:
    candidates = tournament_summary[
        (tournament_summary["p_title"] >= 0.015)
        & (tournament_summary["p_title"] <= 0.065)
    ].copy()

    if candidates.empty:
        candidates = tournament_summary.iloc[6:16].copy()

    return candidates.sort_values(
        ["p_title", "p_final", "p_reach_semi_final"],
        ascending=False,
    ).iloc[0]


def pick_open_group(group_summary: pd.DataFrame) -> tuple[str, float]:
    group_strength = (
        group_summary.groupby("group")
        .agg(
            top_advance=("p_advance", "max"),
            bottom_advance=("p_advance", "min"),
        )
        .reset_index()
    )
    group_strength["spread"] = (
        group_strength["top_advance"] - group_strength["bottom_advance"]
    )

    row = group_strength.sort_values("spread", ascending=True).iloc[0]
    return str(row["group"]), float(row["spread"])


def make_comparison_table() -> pd.DataFrame:
    rows = []

    for model_label, model in MODELS.items():
        runs = load_tournament_runs(model["tournament_summary"])

        if runs.empty:
            continue

        selected_run = runs.iloc[0]["simulation_run_id"]
        summary = load_tournament_summary(model["tournament_summary"], selected_run)
        top = summary.sort_values("p_title", ascending=False).iloc[0]

        rows.append(
            {
                "Model": model_label,
                "Run": selected_run,
                "Simulations": int(runs.iloc[0]["n_simulations"]),
                "Top Team": top["team"],
                "Title Chance": top["p_title"],
                "Final Chance": top["p_final"],
                "Dry Run": bool(model["is_dry_run"]),
            }
        )

    return pd.DataFrame(rows)


def make_match_interpretation(row: pd.Series) -> str:
    outcomes = {
        row["home_team_name"]: float(row["p_home_win"]),
        "Draw": float(row["p_draw"]),
        row["away_team_name"]: float(row["p_away_win"]),
    }
    sorted_outcomes = sorted(outcomes.items(), key=lambda item: item[1], reverse=True)
    favorite, favorite_prob = sorted_outcomes[0]
    runner_up_prob = sorted_outcomes[1][1]
    margin = favorite_prob - runner_up_prob

    if favorite == "Draw":
        return "The model sees this as a very balanced match, with a draw as the single most likely outcome."

    if margin < 0.08:
        return f"The model expects a close match, with a slight edge for {favorite}."
    if margin < 0.20:
        return f"The model gives {favorite} a clear but not overwhelming advantage."
    return f"The model sees {favorite} as a strong favorite in this fixture."


st.markdown(CSS, unsafe_allow_html=True)


try:
    db_ok = check_database_connection()
except Exception as error:
    st.error("Postgres connection failed.")
    st.code(str(error))
    st.stop()

if not db_ok:
    st.error("Postgres connection failed.")
    st.stop()


with st.sidebar:
    st.markdown("## Controls")
    selected_model_name = st.selectbox(
        "Model",
        options=list(MODELS.keys()),
        index=2,
    )

    model = MODELS[selected_model_name]
    tournament_runs = load_tournament_runs(model["tournament_summary"])

    if tournament_runs.empty:
        st.error("No tournament simulation runs found for this model.")
        st.stop()

    selected_run = st.selectbox(
        "Simulation run",
        options=tournament_runs["simulation_run_id"].tolist(),
        index=0,
    )

    selected_run_meta = tournament_runs[
        tournament_runs["simulation_run_id"] == selected_run
    ].iloc[0]

    st.caption(
        f"{int(selected_run_meta['n_simulations']):,} simulations · "
        f"seeds {int(selected_run_meta['seed_start'])}–{int(selected_run_meta['seed_end'])}"
    )

    st.divider()

    st.caption(
        "The main views use the selected model and simulation run. "
        "The Overview also keeps a compact model comparison."
    )


if model["is_dry_run"]:
    st.warning(
        "Technical dry run: this model is useful for comparison, but it is not the final WM-2026 forecast.",
        icon="⚠️",
    )


tournament_summary = load_tournament_summary(
    model["tournament_summary"],
    selected_run,
)
group_summary = load_group_stage_summary(model["group_stage_summary"])
match_predictions = load_match_predictions(model["match_predictions"])


overview_tab, match_tab, groups_tab, scenario_tab, team_path_tab, full_results_tab, method_tab = st.tabs(
    [
        "Overview",
        "Match Explorer",
        "Groups",
        "Scenario Mode",
        "Team Path",
        "Full Results",
        "Method / Data",
    ]
)


with overview_tab:
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">WM 2026 Forecast Dashboard</div>
            <div class="hero-subtitle">
                Match predictions, group-stage outcomes and full-tournament probabilities
                from probabilistic two-stage modeling and Monte Carlo simulation.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    title_favorite = tournament_summary.sort_values("p_title", ascending=False).iloc[0]
    final_favorite = tournament_summary.sort_values("p_final", ascending=False).iloc[0]
    dark_horse = pick_dark_horse(tournament_summary)
    open_group, open_group_spread = pick_open_group(group_summary)

    kpi_cols = st.columns(4)

    with kpi_cols[0]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Title favorite</div>
                <div class="kpi-main">{title_favorite['team']}</div>
                <div class="kpi-value gold">{pct(title_favorite['p_title'])}</div>
                <div class="small-muted">Highest simulated title probability</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with kpi_cols[1]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Highest final chance</div>
                <div class="kpi-main">{final_favorite['team']}</div>
                <div class="kpi-value">{pct(final_favorite['p_final'])}</div>
                <div class="small-muted">Most likely team to reach the final</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with kpi_cols[2]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Dark horse</div>
                <div class="kpi-main">{dark_horse['team']}</div>
                <div class="kpi-value gold">{pct(dark_horse['p_title'])}</div>
                <div class="small-muted">Strong title chance outside the top tier</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with kpi_cols[3]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Most open group</div>
                <div class="kpi-main">Group {open_group}</div>
                <div class="kpi-value">{open_group_spread * 100:.1f} pp</div>
                <div class="small-muted">Smallest spread in advance probabilities</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    chart_cols = st.columns(2)

    with chart_cols[0]:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Top 10 title chances")
        chart_data = (
            tournament_summary.sort_values("p_title", ascending=False)
            .head(10)
            .set_index("team")[["p_title"]]
            .sort_values("p_title")
        )
        st.bar_chart(chart_data, horizontal=True, height=360)
        st.markdown("</div>", unsafe_allow_html=True)

    with chart_cols[1]:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Top 10 final chances")
        chart_data = (
            tournament_summary.sort_values("p_final", ascending=False)
            .head(10)
            .set_index("team")[["p_final"]]
            .sort_values("p_final")
        )
        st.bar_chart(chart_data, horizontal=True, height=360)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Model comparison")

    comparison = make_comparison_table()

    if comparison.empty:
        st.info("No model comparison available yet.")
    else:
        display_comparison = comparison.copy()
        for column in ["Title Chance", "Final Chance"]:
            display_comparison[column] = display_comparison[column].map(lambda value: pct(value))

        st.dataframe(
            display_comparison,
            width="stretch",
            hide_index=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


with match_tab:
    st.header("Match Explorer")
    st.caption("Explore one precomputed group-stage fixture from the selected model.")

    all_teams = sorted(
        set(match_predictions["home_team_name"]).union(match_predictions["away_team_name"])
    )
    selected_team = st.selectbox("Team", options=all_teams)

    team_matches = match_predictions[
        (match_predictions["home_team_name"] == selected_team)
        | (match_predictions["away_team_name"] == selected_team)
    ].copy()

    team_matches["opponent"] = team_matches.apply(
        lambda row: row["away_team_name"]
        if row["home_team_name"] == selected_team
        else row["home_team_name"],
        axis=1,
    )

    selected_opponent = st.selectbox(
        "Opponent",
        options=team_matches.sort_values("opponent")["opponent"].tolist(),
    )

    match_row = team_matches[team_matches["opponent"] == selected_opponent].iloc[0]

    st.markdown(
        f"""
        <div class="match-card">
            <div class="match-title">{match_row['home_team_name']} vs {match_row['away_team_name']}</div>
            <div class="match-subtitle">Fixture date: {match_row['match_date']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    lambda_cols = st.columns(2)
    lambda_cols[0].metric(
        f"Expected goals · {match_row['home_team_name']}",
        f"{match_row['lambda_home']:.2f}",
    )
    lambda_cols[1].metric(
        f"Expected goals · {match_row['away_team_name']}",
        f"{match_row['lambda_away']:.2f}",
    )

    prob_cols = st.columns(3)

    with prob_cols[0]:
        st.markdown(
            f"""
            <div class="prob-card">
                <div class="prob-label">{match_row['home_team_name']} win</div>
                <div class="prob-value">{pct(match_row['p_home_win'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with prob_cols[1]:
        st.markdown(
            f"""
            <div class="prob-card">
                <div class="prob-label">Draw</div>
                <div class="prob-value">{pct(match_row['p_draw'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with prob_cols[2]:
        st.markdown(
            f"""
            <div class="prob-card">
                <div class="prob-label">{match_row['away_team_name']} win</div>
                <div class="prob-value">{pct(match_row['p_away_win'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Outcome probabilities")
    outcome_chart = pd.DataFrame(
        {
            "Outcome": [
                f"{match_row['home_team_name']} win",
                "Draw",
                f"{match_row['away_team_name']} win",
            ],
            "Probability": [
                float(match_row["p_home_win"]),
                float(match_row["p_draw"]),
                float(match_row["p_away_win"]),
            ],
        }
    ).set_index("Outcome")
    st.bar_chart(outcome_chart, horizontal=True, height=260)
    st.write(make_match_interpretation(match_row))
    st.markdown("</div>", unsafe_allow_html=True)


with groups_tab:
    st.header("Groups")
    st.caption("Explore one group at a time for the selected model.")

    group_options = sorted(group_summary["group"].unique())
    selected_group = st.selectbox("Group", options=group_options)

    group_view = (
        group_summary[group_summary["group"] == selected_group]
        .sort_values(["p_advance", "p_rank_1", "avg_points"], ascending=False)
        .copy()
    )

    likely_winner = group_view.sort_values("p_rank_1", ascending=False).iloc[0]
    highest_advance = group_view.sort_values("p_advance", ascending=False).iloc[0]
    lowest_advance = group_view.sort_values("p_advance", ascending=True).iloc[0]

    rank2_sorted = group_view.sort_values("p_top2", ascending=False).reset_index(drop=True)
    if len(rank2_sorted) >= 3:
        second_place_gap = float(rank2_sorted.loc[1, "p_top2"] - rank2_sorted.loc[2, "p_top2"])
        second_place_label = (
            f"{rank2_sorted.loc[1, 'team']} vs {rank2_sorted.loc[2, 'team']}"
        )
    else:
        second_place_gap = 0.0
        second_place_label = "Not available"

    st.subheader(f"Group {selected_group}")

    group_kpis = st.columns(4)

    with group_kpis[0]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Likely group winner</div>
                <div class="kpi-main">{likely_winner['team']}</div>
                <div class="kpi-value">{pct(likely_winner['p_rank_1'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with group_kpis[1]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Tightest race for top 2</div>
                <div class="kpi-main">{second_place_label}</div>
                <div class="kpi-value">{second_place_gap * 100:.1f} pp</div>
                <div class="small-muted">Gap between 2nd and 3rd top-2 probability</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with group_kpis[2]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Highest advance chance</div>
                <div class="kpi-main">{highest_advance['team']}</div>
                <div class="kpi-value">{pct(highest_advance['p_advance'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with group_kpis[3]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Lowest advance chance</div>
                <div class="kpi-main">{lowest_advance['team']}</div>
                <div class="kpi-value">{pct(lowest_advance['p_advance'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    display_group = group_view[
        [
            "team",
            "p_rank_1",
            "p_top2",
            "p_best_third",
            "p_advance",
            "avg_points",
            "avg_goal_diff",
        ]
    ].rename(
        columns={
            "team": "Team",
            "p_rank_1": "Place 1",
            "p_top2": "Top 2",
            "p_best_third": "Best third",
            "p_advance": "Advance",
            "avg_points": "Avg points",
            "avg_goal_diff": "Avg goal diff",
        }
    )

    for column in ["Place 1", "Top 2", "Best third", "Advance"]:
        display_group[column] = display_group[column].map(lambda value: pct(value))

    for column in ["Avg points", "Avg goal diff"]:
        display_group[column] = display_group[column].round(2)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Group probabilities")
    st.dataframe(display_group, width="stretch", hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Advance probability")
    advance_chart = (
        group_view.set_index("team")[["p_advance"]]
        .sort_values("p_advance")
        .rename(columns={"p_advance": "Advance probability"})
    )
    st.bar_chart(advance_chart, horizontal=True, height=280)
    st.markdown("</div>", unsafe_allow_html=True)


with scenario_tab:
    st.header("Scenario Mode")
    st.caption(
        "Create a custom group-stage ranking scenario and simulate the knockout stage from there."
    )

    if selected_model_name != "v2 Full 35 (XGBoost)":
        st.info(
            "Scenario Mode is currently available for v2 Full 35 only. "
            "The rest of the dashboard still supports all three models."
        )
    else:
        st.markdown(
            """
            <div class="section-card">
                <h3>Custom Group Rankings</h3>
                <p class="small-muted">
                    Set the final ranking in each group. The scenario changes the knockout path,
                    not the underlying team-strength features. Because no exact group scores are entered,
                    best third-place teams are ordered using the selected model's baseline advance strength.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        scenario_controls = st.columns([1, 1, 2])
        scenario_n = scenario_controls[0].selectbox(
            "Scenario simulations",
            options=[100, 200, 300, 500, 1000, 10000],
            index=2,
            help=(
                "Higher values reduce Monte Carlo noise but take longer. "
                "100-500 is good for live exploration; 1000+ is better for a more stable scenario."
            ),
        )
        scenario_seed = scenario_controls[1].number_input(
            "Seed start",
            min_value=1,
            max_value=100000,
            value=42,
            step=1,
            help=(
                "Seed for reproducible random simulations. "
                "The app uses consecutive seeds from this value onward."
            ),
        )

        if scenario_n >= 10000:
            st.warning(
                "10k scenario simulations can take noticeably longer. "
                "Use it for a more stable result, not for fast live clicking.",
                icon="⏱️",
            )

        default_rankings = {}
        group_rankings = {}

        group_names = sorted(group_summary["group"].unique())
        group_columns = st.columns(3)

        for group_index, group_name in enumerate(group_names):
            group_data = (
                group_summary[group_summary["group"] == group_name]
                .sort_values(
                    ["p_rank_1", "p_top2", "p_advance"],
                    ascending=False,
                )
                .copy()
            )
            teams = group_data["team"].tolist()
            default_rankings[group_name] = teams

            with group_columns[group_index % 3]:
                st.markdown(f"#### Group {group_name}")

                chosen = []
                for rank in range(1, 5):
                    remaining_options = teams
                    default_team = teams[rank - 1]

                    value = st.selectbox(
                        f"Group {group_name} · Rank {rank}",
                        options=remaining_options,
                        index=remaining_options.index(default_team),
                        key=f"scenario_{group_name}_{rank}",
                    )
                    chosen.append(value)

                if len(set(chosen)) != 4:
                    st.error(f"Group {group_name} contains duplicate teams.")

                group_rankings[group_name] = chosen

        duplicates_exist = any(len(set(teams)) != 4 for teams in group_rankings.values())

        run_scenario = st.button(
            "Run scenario",
            type="primary",
            disabled=duplicates_exist,
        )

        if run_scenario:
            third_place_strength = dict(
                zip(
                    group_summary["team"],
                    group_summary["p_advance"],
                    strict=False,
                )
            )

            with st.spinner("Simulating scenario knockout stage..."):
                scenario_probabilities, scenario_knockout, scenario_qualified = run_scenario_simulation(
                    group_rankings=group_rankings,
                    third_place_strength=third_place_strength,
                    seed_start=int(scenario_seed),
                    n_simulations=int(scenario_n),
                )

            st.success(
                f"Scenario completed: {int(scenario_n)} knockout simulations from custom group rankings."
            )

            scenario_sums = scenario_probabilities[
                [
                    "p_advance_group",
                    "p_reach_round_of_16",
                    "p_reach_quarter_final",
                    "p_reach_semi_final",
                    "p_final",
                    "p_title",
                    "p_third_place",
                ]
            ].sum()

            expected_sums = {
                "p_advance_group": 32.0,
                "p_reach_round_of_16": 16.0,
                "p_reach_quarter_final": 8.0,
                "p_reach_semi_final": 4.0,
                "p_final": 2.0,
                "p_title": 1.0,
                "p_third_place": 1.0,
            }

            sums_ok = all(
                abs(float(scenario_sums[column]) - expected) < 1e-9
                for column, expected in expected_sums.items()
            )

            if sums_ok:
                st.caption("Internal check passed: scenario round probability sums are consistent.")
            else:
                st.warning("Internal check failed: scenario round sums are not consistent.")

            scenario_top = scenario_probabilities.sort_values(
                ["p_title", "p_final", "p_reach_semi_final"],
                ascending=False,
            ).copy()

            champion = scenario_top.iloc[0]

            kpi_cols = st.columns(4)
            kpi_cols[0].metric("Scenario favorite", champion["team"], pct(champion["p_title"]))
            kpi_cols[1].metric("Final chance", pct(champion["p_final"]))
            kpi_cols[2].metric("Qualified teams", len(scenario_qualified))
            kpi_cols[3].metric("Knockout matches", len(scenario_knockout))

            chart_cols = st.columns(2)

            with chart_cols[0]:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.subheader("Scenario title chances")
                scenario_chart = (
                    scenario_top.head(10)
                    .set_index("team")[["p_title"]]
                    .sort_values("p_title")
                    .rename(columns={"p_title": "Title probability"})
                )
                st.bar_chart(scenario_chart, horizontal=True, height=340)
                st.markdown("</div>", unsafe_allow_html=True)

            with chart_cols[1]:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.subheader("Representative bracket run")
                bracket_view = scenario_knockout[
                    [
                        "match_number",
                        "round_name",
                        "home_team",
                        "away_team",
                        "winner",
                    ]
                ].copy()
                bracket_view = bracket_view.rename(
                    columns={
                        "match_number": "Match",
                        "round_name": "Round",
                        "home_team": "Team A",
                        "away_team": "Team B",
                        "winner": "Winner",
                    }
                )
                st.dataframe(bracket_view, width="stretch", hide_index=True)
                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("Scenario probabilities")
            display_scenario = scenario_top[
                [
                    "team",
                    "p_advance_group",
                    "p_reach_round_of_16",
                    "p_reach_quarter_final",
                    "p_reach_semi_final",
                    "p_final",
                    "p_title",
                    "p_third_place",
                ]
            ].rename(
                columns={
                    "team": "Team",
                    "p_advance_group": "Advance group",
                    "p_reach_round_of_16": "Round of 16",
                    "p_reach_quarter_final": "Quarter-final",
                    "p_reach_semi_final": "Semi-final",
                    "p_final": "Final",
                    "p_title": "Title",
                    "p_third_place": "Third place",
                }
            )

            for column in [
                "Advance group",
                "Round of 16",
                "Quarter-final",
                "Semi-final",
                "Final",
                "Title",
                "Third place",
            ]:
                display_scenario[column] = display_scenario[column].map(lambda value: pct(value))

            st.dataframe(display_scenario, width="stretch", hide_index=True)
            st.markdown("</div>", unsafe_allow_html=True)


with team_path_tab:
    st.header("Team Path")
    st.caption("Follow one team's simulated path through the tournament.")

    team_options = tournament_summary.sort_values("team")["team"].tolist()
    default_team_index = team_options.index("Germany") if "Germany" in team_options else 0

    selected_team_path = st.selectbox(
        "Team",
        options=team_options,
        index=default_team_index,
        key="team_path_team",
    )

    team_row = tournament_summary[
        tournament_summary["team"] == selected_team_path
    ].iloc[0]

    path_steps = pd.DataFrame(
        {
            "Stage": [
                "Advance from group",
                "Reach round of 16",
                "Reach quarter-final",
                "Reach semi-final",
                "Reach final",
                "Win title",
                "Win third-place match",
            ],
            "Probability": [
                float(team_row["p_advance_group"]),
                float(team_row["p_reach_round_of_16"]),
                float(team_row["p_reach_quarter_final"]),
                float(team_row["p_reach_semi_final"]),
                float(team_row["p_final"]),
                float(team_row["p_title"]),
                float(team_row["p_third_place"]),
            ],
        }
    )

    st.markdown(
        f"""
        <div class="match-card">
            <div class="match-title">{selected_team_path}</div>
            <div class="match-subtitle">Tournament path based on selected simulation run</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    path_cols = st.columns(5)
    path_cols[0].metric("Group", pct(team_row["p_advance_group"]))
    path_cols[1].metric("Quarter-final", pct(team_row["p_reach_quarter_final"]))
    path_cols[2].metric("Semi-final", pct(team_row["p_reach_semi_final"]))
    path_cols[3].metric("Final", pct(team_row["p_final"]))
    path_cols[4].metric("Title", pct(team_row["p_title"]))

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Path probabilities")

    path_chart = (
        path_steps.set_index("Stage")[["Probability"]]
        .sort_values("Probability")
    )
    st.bar_chart(path_chart, horizontal=True, height=360)

    display_path = path_steps.copy()
    display_path["Probability"] = display_path["Probability"].map(lambda value: pct(value))
    st.dataframe(display_path, width="stretch", hide_index=True)

    st.markdown("</div>", unsafe_allow_html=True)


with full_results_tab:
    st.header("Full Results")
    st.caption("Complete tournament probabilities for the selected model and simulation run.")

    search_term = st.text_input(
        "Filter teams",
        value="",
        placeholder="Search team...",
    ).strip().lower()

    results = tournament_summary.sort_values(
        ["p_title", "p_final", "p_reach_semi_final"],
        ascending=False,
    ).copy()

    results.insert(
        0,
        "Rank",
        range(1, len(results) + 1),
    )

    results["Team"] = results.apply(
        lambda row: (
            f"🥇 {row['team']}" if row["Rank"] == 1
            else f"🥈 {row['team']}" if row["Rank"] == 2
            else f"🥉 {row['team']}" if row["Rank"] == 3
            else row["team"]
        ),
        axis=1,
    )

    display_results = results[
        [
            "Rank",
            "Team",
            "p_advance_group",
            "p_reach_round_of_16",
            "p_reach_quarter_final",
            "p_reach_semi_final",
            "p_final",
            "p_title",
            "p_third_place",
        ]
    ].rename(
        columns={
            "p_advance_group": "Advance group",
            "p_reach_round_of_16": "Round of 16",
            "p_reach_quarter_final": "Quarter-final",
            "p_reach_semi_final": "Semi-final",
            "p_final": "Final",
            "p_title": "Title",
            "p_third_place": "Third place",
        }
    )

    if search_term:
        display_results = display_results[
            display_results["Team"].str.lower().str.contains(search_term, regex=False)
        ]

    for column in [
        "Advance group",
        "Round of 16",
        "Quarter-final",
        "Semi-final",
        "Final",
        "Title",
        "Third place",
    ]:
        display_results[column] = display_results[column].map(lambda value: pct(value))

    st.markdown('<div class="section-card">', unsafe_allow_html=True)

    top_team = results.iloc[0]
    st.write(
        f"Showing **{len(display_results)}** teams. "
        f"Current top title probability: **{top_team['team']} ({pct(top_team['p_title'])})**."
    )

    st.dataframe(
        display_results,
        width="stretch",
        hide_index=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)


with method_tab:
    st.header("Method / Data")
    st.caption("A compact overview of the forecasting pipeline and the selected data run.")

    st.markdown(
        """
        <div class="section-card">
            <h3>Forecasting pipeline</h3>
            <p class="small-muted">
                Historical international matches → time-aware feature engineering →
                expected-goals model → Poisson match probabilities →
                Monte Carlo tournament simulation → team outcome probabilities.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    method_cols = st.columns(5)
    method_cols[0].metric("Match predictions", f"{len(match_predictions):,}")
    method_cols[1].metric("Group rows", f"{len(group_summary):,}")
    method_cols[2].metric("Teams", f"{tournament_summary['team'].nunique():,}")
    method_cols[3].metric("Simulations", f"{int(selected_run_meta['n_simulations']):,}")
    method_cols[4].metric("Title sum", f"{tournament_summary['p_title'].sum():.1f}")

    st.markdown(
        """
        <div class="section-card">
            <h3>Interpretation note</h3>
            <p class="small-muted">
                The probabilities are model outputs, not certainties. They depend on the selected
                model, available pre-match features, official fixtures, bracket assumptions and the
                simulation run shown in the sidebar.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Technical checks", expanded=False):
        counts = load_table_counts(
            model["match_predictions"],
            model["group_stage_summary"],
            model["tournament_summary"],
        )

        st.subheader("Database status")
        st.success("Postgres connection: OK")

        st.subheader("Available tables for selected model")
        st.dataframe(counts, width="stretch", hide_index=True)

        st.subheader("Selected run")
        st.write(
            {
                "selected_model": selected_model_name,
                "selected_run": selected_run,
                "n_simulations": int(selected_run_meta["n_simulations"]),
                "seed_start": int(selected_run_meta["seed_start"]),
                "seed_end": int(selected_run_meta["seed_end"]),
                "match_predictions_rows": int(len(match_predictions)),
                "group_summary_rows": int(len(group_summary)),
                "tournament_summary_rows": int(len(tournament_summary)),
                "title_probability_sum": round(float(tournament_summary["p_title"].sum()), 6),
                "group_advance_sum": round(float(tournament_summary["p_advance_group"].sum()), 6),
                "round_of_16_sum": round(float(tournament_summary["p_reach_round_of_16"].sum()), 6),
                "quarter_final_sum": round(float(tournament_summary["p_reach_quarter_final"].sum()), 6),
                "semi_final_sum": round(float(tournament_summary["p_reach_semi_final"].sum()), 6),
                "final_sum": round(float(tournament_summary["p_final"].sum()), 6),
                "third_place_sum": round(float(tournament_summary["p_third_place"].sum()), 6),
            }
        )

        st.subheader("Model comparison run policy")
        st.write(
            "The comparison table uses the largest available simulation run for each model. "
            "The main dashboard views use the exact model and run selected in the sidebar."
        )
