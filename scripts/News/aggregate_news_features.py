# aggregate_news_features.py

import ast
import pandas as pd


def parse_list(value):
    """
    Wandelt CSV-Strings wie '["Jamal Musiala"]' wieder in Python-Listen um.
    Wenn nichts drinsteht oder etwas kaputt ist, wird [] zurückgegeben.
    """
    if pd.isna(value):
        return []

    if isinstance(value, list):
        return value

    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            return parsed
        return []
    except (ValueError, SyntaxError):
        return []


def unique_names_from_lists(series):
    """
    Macht aus mehreren Listen eine eindeutige Liste.
    Beispiel:
    [["Jamal Musiala"], ["Jamal Musiala", "Florian Wirtz"]]
    -> ["Jamal Musiala", "Florian Wirtz"]
    """
    names = []

    for player_list in series:
        if isinstance(player_list, list):
            for name in player_list:
                if name and name not in names:
                    names.append(name)

    return names


def aggregate_team_news_features(input_file: str, output_file: str):
    df = pd.read_csv(input_file)

    # Nur erfolgreich analysierte Artikel aggregieren
    if "error" in df.columns:
        df = df[df["error"].isna()]

    # Falls nach dem Filtern nichts übrig bleibt
    if df.empty:
        print("Keine erfolgreich analysierten Artikel für die Aggregation gefunden.")
        return pd.DataFrame()

    # Listen-Spalten parsen
    df["injured_players"] = df["injured_players"].apply(parse_list)
    df["suspended_players"] = df["suspended_players"].apply(parse_list)

    # Anzahl pro Artikel
    df["injured_player_count"] = df["injured_players"].apply(len)
    df["suspended_player_count"] = df["suspended_players"].apply(len)

    # Boolean-Spalten in 0/1 umwandeln
    bool_columns = [
        "injury_news",
        "suspension_news",
        "morale_pressure_news",
        "coach_news",
        "coach_pressure",
    ]

    for col in bool_columns:
        if col in df.columns:
            df[col] = df[col].astype(bool).astype(int)

    # Numerische Aggregation
    team_features = df.groupby("team").agg(
        news_article_count=("team", "count"),

        avg_news_sentiment=("sentiment_score", "mean"),
        min_news_sentiment=("sentiment_score", "min"),
        max_news_sentiment=("sentiment_score", "max"),

        injury_news_count=("injury_news", "sum"),
        injured_player_mentions_count=("injured_player_count", "sum"),

        suspension_news_count=("suspension_news", "sum"),
        suspended_player_mentions_count=("suspended_player_count", "sum"),

        morale_pressure_news_count=("morale_pressure_news", "sum"),
        avg_morale_pressure_score=("morale_pressure_score", "mean"),

        coach_news_count=("coach_news", "sum"),
        coach_pressure_count=("coach_pressure", "sum"),
        avg_coach_sentiment_score=("coach_sentiment_score", "mean"),
    ).reset_index()

    # Verletzte Spieler als Namensliste pro Team
    injured_players = df.groupby("team")["injured_players"].apply(
        unique_names_from_lists
    ).reset_index()

    injured_players = injured_players.rename(
        columns={"injured_players": "injured_players_all"}
    )

    # Gesperrte Spieler auch als Namensliste pro Team
    suspended_players = df.groupby("team")["suspended_players"].apply(
        unique_names_from_lists
    ).reset_index()

    suspended_players = suspended_players.rename(
        columns={"suspended_players": "suspended_players_all"}
    )

    # Listen an Team-Features anhängen
    team_features = team_features.merge(injured_players, on="team", how="left")
    team_features = team_features.merge(suspended_players, on="team", how="left")

    team_features.to_csv(output_file, index=False, encoding="utf-8")

    print(f"Aggregierte Features gespeichert: {output_file}")

    return team_features


if __name__ == "__main__":
    aggregate_team_news_features(
        input_file="news_features_germany_national_team.csv",
        output_file="team_news_features.csv",
    )