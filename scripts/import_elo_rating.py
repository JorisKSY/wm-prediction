import pandas as pd

# Eingabedatei
input_file = "World (2).tsv"

# Ausgabedatei
output_file = "world_football_elo_clean.csv"

# TSV-Datei ohne Header einlesen
df = pd.read_csv(input_file, sep="\t", header=None)

# Prüfen, wie viele Spalten die Datei hat
print("Anzahl Spalten vorher:", df.shape[1])

# Zweite Spalte löschen, weil sie identisch mit der ersten ist
df = df.drop(columns=[1])

# Spaltennamen setzen
columns = [
    "rank",
    "team_code",
    "elo_rating",
    "highest_rank",
    "highest_rating",
    "average_rank",
    "average_rating",
    "lowest_rank",
    "lowest_rating",
    "change_rank_7d",
    "change_rating_7d",
    "change_rank_30d",
    "change_rating_30d",
    "change_rank_1y",
    "change_rating_1y",
    "change_rank_2y",
    "change_rating_2y",
    "change_rank_5y",
    "change_rating_5y",
    "change_rank_10y",
    "change_rating_10y",
    "matches_total",
    "matches_home",
    "matches_away",
    "matches_neutral",
    "wins",
    "losses",
    "draws",
    "goals_for",
    "goals_against"
]

# Sicherheitscheck
if df.shape[1] != len(columns):
    raise ValueError(
        f"Spaltenanzahl passt nicht: Datei hat {df.shape[1]} Spalten, "
        f"aber es wurden {len(columns)} Spaltennamen angegeben."
    )

df.columns = columns

# CSV speichern
df.to_csv(output_file, index=False, encoding="utf-8")

print("CSV wurde erfolgreich gespeichert als:", output_file)
print(df.head())