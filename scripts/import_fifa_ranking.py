import requests
import pandas as pd

url = "https://api.fifa.com/api/v3/fifarankings/rankings/rankingsbyschedule?rankingScheduleId=FRS_Male_Football_20260119&language=en"

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(url, headers=headers)
response.raise_for_status()

data = response.json()

df = pd.DataFrame(data["Results"])

print(df.head())
print(df.columns)

df.to_csv("fifa_ranking.csv", index=False, encoding="utf-8")