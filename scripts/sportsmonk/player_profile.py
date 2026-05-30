import requests
import json

API_TOKEN = "DEIN_TOKEN"
team_id = 18710  # Spain

url = f"https://api.sportmonks.com/v3/football/squads/teams/{team_id}/extended/"

params = {
    "api_token": "8UC6gNaD4pDRpjaQJ4rWQSrIRN9IAv8BHlbO27xkv1YKSHYuTmkogBB8Bbjt"
    #"include": "player;position;detailedPosition"
}

response = requests.get(url, params=params)

print("Status Code:", response.status_code)

data = response.json()

print(json.dumps(data, indent=4, ensure_ascii=False))




#?api_token=8UC6gNaD4pDRpjaQJ4rWQSrIRN9IAv8BHlbO27xkv1YKSHYuTmkogBB8Bbjt