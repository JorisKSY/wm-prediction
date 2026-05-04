## Overview

This document tracks all datasets considered for the project.

The goal is to understand the available data before defining database schemas, cleaning logic, feature engineering, or models.

---

## Dataset 0: <Dataset Beispiel>

### Source

- URL:
- Provider:
- Access date:
- License / usage notes:

### File information

- Local filename:
- Format:
- Approx. rows:
- Approx. columns:
- Time range:
- Level of data:
  - Match-level
  - Team-level
  - Tournament-level
  - Ranking-level
  - Other:

### Relevant columns

| Column | Meaning | Notes |
|---|---|---|
| date | Match date | |
| home_team | Home team | |
| away_team | Away team | |
| home_score | Goals home team | |
| away_score | Goals away team | |
| tournament | Competition name | |
| neutral | Neutral venue flag | |

### Initial quality notes

- Missing values:
- Duplicate rows:
- Team name issues:
- Date format:
- Score definition:
- Extra time included?
- Penalty shootouts included?
- Neutral venue available?
- Country/team identifiers available?

### Potential use in project

- Raw match history:
- World Cup-specific matches:
- Elo calculation:
- Model training:
- Simulation input:
- Not useful because:

### Open questions

- 

## Dataset 1: Open-Meteo Historical Weather API

### Source

- URL: https://archive-api.open-meteo.com/v1/archive
- Provider: Open-Meteo
- Access date: 2026-05-04
- License / usage notes:
  - API data is licensed under Creative Commons Attribution 4.0 International (CC BY 4.0).
  - Attribution is required when Open-Meteo data is used or displayed.
  - No API key is required for basic/non-commercial API access.
  - This source is accessed via API, not downloaded as one fixed static dataset.

### File information

- Local filename:
  - Planned local raw snapshots:
    - `data/raw/open_meteo/<location>_<start_date>_<end_date>_hourly.csv`
    - `data/raw/open_meteo/<location>_<start_date>_<end_date>_metadata.json`
- Format:
  - API response processed into local CSV snapshot
  - Metadata saved separately as JSON
- Approx. rows:
  - Depends on requested time range and frequency.
  - For hourly data: approximately one row per hour per location.
- Approx. columns:
  - Depends on requested weather variables.
- Time range:
  - Historical weather data available through Open-Meteo.
  - Exact project time range not decided yet.
- Level of data:
  - Match-level: No
  - Team-level: No
  - Tournament-level: No
  - Ranking-level: No
  - Other: Location-time-level weather data

### Relevant columns

| Column | Meaning | Notes |
|---|---|---|
| date | Timestamp of weather observation | UTC in current API example |
| temperature_2m | Air temperature at 2 meters | Potential weather feature |
| precipitation | Total precipitation | Potential weather feature |
| apparent_temperature | Perceived temperature | Potential weather feature |
| wind_speed_10m | Wind speed at 10 meters | Preferred over 100m for match context |
| wind_direction_10m | Wind direction at 10 meters | Optional |
| latitude | Requested latitude | Should be saved in metadata |
| longitude | Requested longitude | Should be saved in metadata |
| elevation | Location elevation returned by API | Should be saved in metadata |
| timezone / utc_offset | Timezone information returned by API | Important for matching kickoff times |

### Initial quality notes

- Missing values:
  - To be checked after first local snapshot.
- Duplicate rows:
  - To be checked after first local snapshot.
- Team name issues:
  - Not applicable.
- Date format:
  - API example returns timestamps converted with pandas.
  - Need to decide whether project stores UTC or local stadium time.
- Score definition:
  - Not applicable.
- Extra time included?
  - Not applicable.
- Penalty shootouts included?
  - Not applicable.
- Neutral venue available?
  - Not applicable.
- Country/team identifiers available?
  - Not applicable.
- Location issues:
  - Weather data requires coordinates.
  - Need mapping from match venue/city/stadium to latitude and longitude.
- Data leakage risk:
  - Historical actual weather is only available for past matches.
  - Future match prediction cannot use actual future weather unless using forecasts or assumptions.

### Potential use in project

- Raw match history:
  - No.
- World Cup-specific matches:
  - No, but can be joined later to matches by venue and kickoff time.
- Elo calculation:
  - No.
- Model training:
  - Possible auxiliary feature source for historical matches.
- Simulation input:
  - Maybe, but only if weather is modeled as forecast/scenario/assumption.
- Not useful because:
  - It does not contain football match results.
  - It requires reliable venue coordinates and kickoff times.
  - It may add complexity before the core match dataset is stable.

### Planned raw storage strategy

Open-Meteo data will not be committed directly to GitHub.

Local raw API snapshots should be stored under:

```text
data/raw/open_meteo/

Example local files:

data/raw/open_meteo/berlin_2026-04-18_2026-05-02_hourly.csv
data/raw/open_meteo/berlin_2026-04-18_2026-05-02_metadata.json

These files are treated as raw snapshots and should not be manually edited.

Open questions
Do we actually want weather as a model input?
Which match locations need weather data?
Do we use stadium coordinates or city coordinates?
Do we have reliable kickoff times for historical matches?
Should weather be matched by UTC time or local stadium time?
Do we need hourly weather or daily aggregates?
Which variables are justifiable for football prediction?
Should future simulations use weather forecasts, historical averages, or no weather feature?

## Dataset 2: SoccerData / FBref World Cup Schedule

### Source

- URL: https://pypi.org/project/soccerdata/
- Provider:
  - Python package: `soccerdata`
  - Underlying data source tested here: FBref
- Access date: 2026-05-04
- License / usage notes:
  - `soccerdata` package license: Apache-2.0.
  - The package uses web scraping and should be used responsibly.
  - Usage must comply with the terms of service of the underlying websites.
  - Scrapers may break when source websites change.

### File information

- Local filename:
  - `data/raw/soccerdata/fbref_world_cup/fbref_int_world_cup_2022_schedule_raw.csv`
  - `data/raw/soccerdata/fbref_world_cup/fbref_int_world_cup_2022_schedule_metadata.json`
- Format:
  - Data pulled via Python package and saved locally as CSV snapshot.
  - Metadata saved separately as JSON.
- Approx. rows:
  - To be filled after notebook exploration.
- Approx. columns:
  - To be filled after notebook exploration.
- Time range:
  - World Cup 2022 test query.
- Level of data:
  - Match-level

### Relevant columns

| Column | Meaning | Notes |
|---|---|---|
| date | Match date | To be checked |
| time | Kickoff time | To be checked |
| home_team | Home team / listed first team | May not mean true home advantage |
| away_team | Away team / listed second team | May not mean true away disadvantage |
| score | Match score | Needs later parsing |
| venue | Stadium / venue | Useful for possible weather joins |
| game_id | FBref match identifier | Useful as source-specific ID |
| match_report | Link/path to match report | Optional |

### Initial quality notes

- Missing values:
  - To be checked in notebook.
- Duplicate rows:
  - To be checked in notebook.
- Team name issues:
  - To be checked.
- Date format:
  - To be checked.
- Score definition:
  - Need to clarify whether score reflects final score, extra time, or penalties.
- Extra time included?
  - Open question.
- Penalty shootouts included?
  - Open question.
- Neutral venue available?
  - World Cup matches are generally neutral in modeling terms, but source may not provide a direct neutral flag.
- Country/team identifiers available?
  - To be checked.

### Potential use in project

- Raw match history:
  - Possible for World Cup-specific match schedule/results.
- World Cup-specific matches:
  - Yes, potentially useful.
- Elo calculation:
  - Not enough alone for broad Elo history.
- Model training:
  - Probably too small alone; useful as World Cup-specific validation/context.
- Simulation input:
  - Potentially useful for tournament structure or historical comparison.
- Not useful because:
  - Not broad enough alone for training a general goal model.
  - Depends on web scraping and source stability.

### Open questions

- Does this source contain enough international match history or only tournament-specific matches?
- Is `home_team` meaningful for neutral World Cup games?
- How exactly is `score` encoded?
- Are extra time and penalties represented clearly?
- Can this source be combined cleanly with our main match dataset?
- Should FBref be a core source or only a supplemental World Cup source?