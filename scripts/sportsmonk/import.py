
import requests
import json
from pathlib import Path

API_KEY = "8UC6gNaD4pDRpjaQJ4rWQSrIRN9IAv8BHlbO27xkv1YKSHYuTmkogBB8Bbjt"

fixture_id = 19439619

url = f"https://api.sportmonks.com/v3/football/fixtures/{fixture_id}"

params = {
    "api_token": API_KEY,
    "include": "participants;formations;lineups;events;statistics"
}

response = requests.get(url, params=params)

print("Status Code:", response.status_code)

data = response.json()



output_file = "fixture_demo_pretty.json"

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(data, file, ensure_ascii=False, indent=4)

print("Response wurde schön formatiert gespeichert unter:")
print(output_file)