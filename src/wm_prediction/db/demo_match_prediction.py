import os
import math

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text


# ============================================================
# DB-Verbindung
# ============================================================

def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return database_url

    return "postgresql+psycopg2://wm_user:wm_password@localhost:5432/wm_prediction"

@st.cache_resource
def get_engine():
    return create_engine(get_database_url())


# ============================================================
# Daten laden
# ============================================================

@st.cache_data(ttl=300)
def load_team_snapshot() -> pd.DataFrame:
    """
    Lädt alle Teamdaten, die wir für die Demo brauchen.

    Voraussetzung:
    Diese Tabellen existieren schon:
    - features.team_strength_current
    - features.team_form_current_last10
    """

    engine = get_engine()

    query = """
            SELECT s.team_id, \
                   s.canonical_name, \

                   s.fifa_rank, \
                   s.fifa_total_points, \

                   s.elo_rating, \
                   s.elo_rank, \

                   s.total_market_value_eur, \
                   s.log_market_value, \

                   s.squad_size, \
                   s.average_age, \

                   f.last10_matches, \
                   f.last10_wins, \
                   f.last10_draws, \
                   f.last10_losses, \
                   f.last10_avg_points, \
                   f.last10_avg_goals_for, \
                   f.last10_avg_goals_against, \
                   f.last10_avg_goal_diff, \
                   f.last10_win_rate, \
                   f.latest_match_date

            FROM features.team_strength_current s
                     LEFT JOIN features.team_form_current_last10 f
                               ON f.team_id = s.team_id

            WHERE s.canonical_name IS NOT NULL
            ORDER BY s.canonical_name; \
            """

    return pd.read_sql_query(text(query), engine)


# ============================================================
# Prediction-Logik
# ============================================================

def safe_number(value, default=0.0) -> float:
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def logistic(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def predict_match(team_a: pd.Series, team_b: pd.Series) -> dict:
    """
    Demo-Heuristik.
    Noch kein echtes ML-Modell.

    Idee:
    - Elo besser -> Vorteil
    - FIFA Rank kleiner -> Vorteil
    - FIFA Punkte höher -> Vorteil
    - Form letzte 10 Spiele besser -> Vorteil
    - Marktwert höher -> kleiner Vorteil
    """

    elo_diff = safe_number(team_a["elo_rating"]) - safe_number(team_b["elo_rating"])

    # Bei FIFA Rank ist kleiner besser.
    # Wenn Team A Rank 2 und Team B Rank 10 hat:
    # 10 - 2 = +8 Vorteil Team A.
    fifa_rank_diff = safe_number(team_b["fifa_rank"]) - safe_number(team_a["fifa_rank"])

    fifa_points_diff = (
            safe_number(team_a["fifa_total_points"])
            - safe_number(team_b["fifa_total_points"])
    )

    form_points_diff = (
            safe_number(team_a["last10_avg_points"])
            - safe_number(team_b["last10_avg_points"])
    )

    form_goal_diff = (
            safe_number(team_a["last10_avg_goal_diff"])
            - safe_number(team_b["last10_avg_goal_diff"])
    )

    market_value_diff = (
            safe_number(team_a["log_market_value"])
            - safe_number(team_b["log_market_value"])
    )

    strength_score = (
            (elo_diff / 200.0)
            + (fifa_rank_diff / 30.0)
            + (fifa_points_diff / 300.0)
            + (form_points_diff / 3.0)
            + (form_goal_diff / 3.0)
            + (market_value_diff / 5.0)
    )

    # Draw ist wahrscheinlicher, wenn beide Teams nah beieinander sind.
    draw_probability = 0.28 - abs(strength_score) * 0.06
    draw_probability = max(0.16, min(0.35, draw_probability))

    team_a_non_draw_share = logistic(strength_score)

    team_a_win_probability = (1 - draw_probability) * team_a_non_draw_share
    team_b_win_probability = (1 - draw_probability) * (1 - team_a_non_draw_share)

    # Erwartete Tore grob aus:
    # Angriff Team A + Defensive Team B
    expected_goals_a = (
            (
                    safe_number(team_a["last10_avg_goals_for"], 1.3)
                    + safe_number(team_b["last10_avg_goals_against"], 1.3)
            )
            / 2.0
            + strength_score * 0.20
    )

    expected_goals_b = (
            (
                    safe_number(team_b["last10_avg_goals_for"], 1.3)
                    + safe_number(team_a["last10_avg_goals_against"], 1.3)
            )
            / 2.0
            - strength_score * 0.20
    )

    expected_goals_a = max(0.2, min(4.5, expected_goals_a))
    expected_goals_b = max(0.2, min(4.5, expected_goals_b))

    probabilities = {
        f"{team_a['canonical_name']} gewinnt": team_a_win_probability,
        "Unentschieden": draw_probability,
        f"{team_b['canonical_name']} gewinnt": team_b_win_probability,
    }

    predicted_result = max(probabilities, key=probabilities.get)

    return {
        "team_a": team_a["canonical_name"],
        "team_b": team_b["canonical_name"],

        "team_a_win_probability": round(team_a_win_probability * 100, 1),
        "draw_probability": round(draw_probability * 100, 1),
        "team_b_win_probability": round(team_b_win_probability * 100, 1),

        "predicted_result": predicted_result,

        "expected_goals_team_a": round(expected_goals_a, 2),
        "expected_goals_team_b": round(expected_goals_b, 2),
        "expected_total_goals": round(expected_goals_a + expected_goals_b, 2),

        "strength_score": round(strength_score, 3),

        "elo_diff": round(elo_diff, 1),
        "fifa_rank_diff": round(fifa_rank_diff, 1),
        "fifa_points_diff": round(fifa_points_diff, 1),
        "form_points_diff": round(form_points_diff, 2),
        "form_goal_diff": round(form_goal_diff, 2),
    }


# ============================================================
# Streamlit UI
# ============================================================

st.set_page_config(
    page_title="WM 2026 Match Prediction Demo",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ WM 2026 Match Prediction Demo")

st.write(
    "Wähle zwei Nationalteams aus. "
    "Die Demo berechnet eine einfache Prognose aus FIFA Ranking, Elo Rating, Marktwert und aktueller Form."
)

df = load_team_snapshot()

if df.empty:
    st.error("Keine Teamdaten gefunden. Prüfe, ob die Feature-Tabellen existieren.")
    st.stop()

teams = df["canonical_name"].dropna().sort_values().tolist()

col1, col2 = st.columns(2)

with col1:
    team_a_name = st.selectbox("Team A", teams, index=teams.index("Germany") if "Germany" in teams else 0)

with col2:
    default_b_index = teams.index("France") if "France" in teams else min(1, len(teams) - 1)
    team_b_name = st.selectbox("Team B", teams, index=default_b_index)

if team_a_name == team_b_name:
    st.warning("Bitte zwei unterschiedliche Teams auswählen.")
    st.stop()

team_a = df[df["canonical_name"] == team_a_name].iloc[0]
team_b = df[df["canonical_name"] == team_b_name].iloc[0]

result = predict_match(team_a, team_b)

st.subheader("Prediction")

m1, m2, m3 = st.columns(3)

with m1:
    st.metric(
        label=f"{result['team_a']} gewinnt",
        value=f"{result['team_a_win_probability']} %",
    )

with m2:
    st.metric(
        label="Unentschieden",
        value=f"{result['draw_probability']} %",
    )

with m3:
    st.metric(
        label=f"{result['team_b']} gewinnt",
        value=f"{result['team_b_win_probability']} %",
    )

st.success(f"Vorhergesagtes Ergebnis: **{result['predicted_result']}**")

st.subheader("Erwartete Tore")

g1, g2, g3 = st.columns(3)

with g1:
    st.metric(
        label=f"Expected Goals {result['team_a']}",
        value=result["expected_goals_team_a"],
    )

with g2:
    st.metric(
        label=f"Expected Goals {result['team_b']}",
        value=result["expected_goals_team_b"],
    )

with g3:
    st.metric(
        label="Expected Total Goals",
        value=result["expected_total_goals"],
    )

st.subheader("Feature-Vergleich")

comparison = pd.DataFrame(
    [
        {
            "Feature": "FIFA Rank",
            result["team_a"]: team_a["fifa_rank"],
            result["team_b"]: team_b["fifa_rank"],
        },
        {
            "Feature": "FIFA Points",
            result["team_a"]: team_a["fifa_total_points"],
            result["team_b"]: team_b["fifa_total_points"],
        },
        {
            "Feature": "Elo Rating",
            result["team_a"]: team_a["elo_rating"],
            result["team_b"]: team_b["elo_rating"],
        },
        {
            "Feature": "Last 10 Avg Points",
            result["team_a"]: team_a["last10_avg_points"],
            result["team_b"]: team_b["last10_avg_points"],
        },
        {
            "Feature": "Last 10 Avg Goals For",
            result["team_a"]: team_a["last10_avg_goals_for"],
            result["team_b"]: team_b["last10_avg_goals_for"],
        },
        {
            "Feature": "Last 10 Avg Goals Against",
            result["team_a"]: team_a["last10_avg_goals_against"],
            result["team_b"]: team_b["last10_avg_goals_against"],
        },
        {
            "Feature": "Market Value",
            result["team_a"]: team_a["total_market_value_eur"],
            result["team_b"]: team_b["total_market_value_eur"],
        },
    ]
)

st.dataframe(comparison, use_container_width=True)

with st.expander("Technische Erklärung"):
    st.write(
        """
        Diese Demo ist noch kein finales trainiertes ML-Modell.
        Sie ist eine regelbasierte Baseline.

        Verwendete Daten:
        - FIFA Ranking
        - Elo Rating
        - Marktwert / Kaderdaten
        - Form der letzten 10 historischen Spiele

        Noch nicht enthalten:
        - Verletzungen
        - Sperren
        - NLP-News
        - Spielerform
        - wahrscheinliche Startelf
        """
    )

    st.json(result)