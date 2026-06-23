import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv


# .env aus demselben Ordner wie diese Python-Datei laden
CURRENT_DIR = Path(__file__).resolve().parent
ENV_PATH = CURRENT_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

SPORTMONKS_API_KEY = os.getenv("SPORTMONKS_API_KEY")

if not SPORTMONKS_API_KEY:
    raise ValueError(f"SPORTMONKS_API_KEY wurde nicht gefunden. Geprüfter Pfad: {ENV_PATH}")


fixture_id = 19439619

url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}"

params = {
    "api_token": SPORTMONKS_API_KEY,
    "include": "participants;formations;lineups;events;statistics"
}

response = requests.get(url, params=params)

print("Status Code:", response.status_code)

response.raise_for_status()

data = response.json()

output_file = CURRENT_DIR / "fixture_demo_pretty.json"

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(data, file, ensure_ascii=False, indent=4)

print("Response wurde schön formatiert gespeichert unter:")
print(output_file)