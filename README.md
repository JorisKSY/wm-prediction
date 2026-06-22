# FIFA World Cup 2026 Prediction System

A full-stack Data Science project for forecasting FIFA World Cup 2026 match outcomes, group standings, knockout paths and tournament winner probabilities.

This project combines historical football data, team-strength indicators, FIFA rankings, Elo-style performance signals, player market-value information, feature engineering, expected-goals modeling, probabilistic match simulation and an interactive Streamlit dashboard.

The goal is not to predict a single deterministic winner, but to build a transparent probabilistic forecasting system that answers questions such as:

- How likely is a team to win a specific match?
- Which teams are most likely to advance from the group stage?
- How does the knockout bracket influence title chances?
- Which teams are strong favorites, dark horses or high-risk teams?
- How do different model versions compare against each other?
- What happens if the group rankings change in a custom scenario?

---

## Project Overview

The project predicts World Cup 2026 results using a two-stage forecasting approach:

1. **Expected Goals Modeling**  
   The model estimates the expected number of goals for both teams in a match.

2. **Probabilistic Match & Tournament Simulation**  
   The expected goals are transformed into win/draw/loss probabilities using a Poisson-based simulation logic. These match probabilities are then used in Monte Carlo simulations to estimate group-stage outcomes, knockout progression and title probabilities.

```text
Raw Data
   ↓
PostgreSQL Database
   ↓
Staging Layer
   ↓
Feature Engineering
   ↓
Model Training & Validation
   ↓
Match Probability Prediction
   ↓
Group Stage Simulation
   ↓
Knockout & Full Tournament Simulation
   ↓
Streamlit Forecast Dashboard
```

---

## Why This Project Is Interesting

Football prediction is a difficult real-world Data Science problem because match results are noisy, low-scoring and influenced by many interacting factors.

A single match can be decided by a red card, one injury, one penalty, weather, travel fatigue, tactical mismatch or random finishing variance. Because of that, the project does not simply output “Team A will win”. Instead, it models uncertainty explicitly.

The system produces probability distributions:

```text
Argentina vs Morocco

Argentina win: 52.4%
Draw:          25.1%
Morocco win:   22.5%
Expected goals: Argentina 1.62 — Morocco 0.94
```

For a tournament, this is extended into thousands of possible tournament paths:

```text
Team        Group Advance   Quarter Final   Semi Final   Final   Title
Brazil          91.2%           55.8%          34.1%     21.4%   12.8%
France          89.7%           53.5%          31.9%     19.8%   11.6%
Argentina       88.9%           51.2%          30.5%     18.6%   10.9%
```

This makes the project more realistic than a simple classification model.

---

## Core Features

### Match Prediction

The system predicts individual World Cup fixtures with:

- expected goals for both teams
- home win probability
- draw probability
- away win probability
- goal-based outcome probabilities
- model version selection
- comparison between different modeling approaches

---

### Full Tournament Simulation

The project simulates the FIFA World Cup 2026 tournament structure end-to-end:

- group stage
- group ranking probabilities
- best third-place qualification logic
- Round of 32
- Round of 16
- quarter-finals
- semi-finals
- third-place match
- final
- title probability

The simulation uses repeated Monte Carlo runs to estimate how often each team reaches each tournament stage.

---

### Interactive Streamlit Dashboard

The final project includes a presentation-ready Streamlit dashboard with multiple views:

- **Overview**  
  Summary of the main tournament forecast, favorites, dark horses and model comparison.

- **Match Explorer**  
  Select a World Cup fixture and inspect expected goals and win/draw/loss probabilities.

- **Groups**  
  Explore qualification probabilities for every group.

- **Scenario Mode**  
  Manually change group rankings and simulate how the knockout path changes.

- **Team Path**  
  Analyze the predicted tournament path of a selected team.

- **Full Results**  
  View all team probabilities across tournament stages.

- **Method / Data**  
  Compact explanation of the forecasting pipeline and model logic.

---

## Tech Stack

### Programming & Data Science

- Python 3.11+
- pandas
- NumPy
- scikit-learn
- XGBoost
- SciPy
- SQLAlchemy

### Database & Infrastructure

- PostgreSQL
- Docker
- Docker Compose
- Python virtual environment
- `.env` configuration

### Web App

- Streamlit
- interactive dashboard components
- custom CSS styling
- model selection
- scenario simulation

### Data & Modeling

- FIFA rankings
- Elo-style team strength data
- historical international matches
- World Cup 2026 fixture data
- player market value data
- team-form features
- ranking momentum features
- opponent-strength features
- Monte Carlo simulation

### NLP / News Research Track

The project also includes an NLP-oriented research component for extracting football-relevant signals from news data, such as:

- injury mentions
- suspensions
- negative or positive team sentiment
- coach pressure
- team conflicts
- squad-related uncertainty
- media pressure before matches

This extends the project beyond pure tabular modeling and connects classic Data Science with NLP-based feature enrichment.

---

## Data Sources

The project is based on multiple football-related data sources:

### Team Strength Data

- FIFA ranking snapshots
- Elo-style team rating data
- historical team performance
- team-level form indicators

### Match Data

- historical international matches
- home/away team information
- match dates
- scores
- neutral-ground information
- tournament context

### World Cup 2026 Data

- official-style World Cup 2026 fixture structure
- group-stage matches
- tournament bracket assumptions
- group-to-knockout qualification logic

### Player & Squad Data

- Transfermarkt-style player information
- market values
- player profiles
- national team links
- squad-level value aggregation ideas

### NLP / News Data

- NewsAPI-based article collection
- team-related news search
- LLM-assisted article analysis
- aggregation of extracted news signals into team-level features

---

## Modeling Approach

The project follows a two-stage modeling design.

### Stage 1: Expected Goals Model

Instead of directly predicting match result classes, the system first predicts expected goals:

```text
Input features → Model → λ_home, λ_away
```

Where:

- `λ_home` = expected goals for the home team
- `λ_away` = expected goals for the away team

This is useful because football is a low-scoring sport and goals provide a more flexible intermediate representation than a simple win/loss label.

---

### Stage 2: Poisson Match Probability Layer

The predicted expected goals are converted into scoreline probabilities.

Example:

```text
P(0-0), P(1-0), P(1-1), P(2-1), ...
```

From these scoreline probabilities, the system derives:

```text
P(home win)
P(draw)
P(away win)
```

This allows the model to output realistic probability distributions instead of only one predicted class.

---

## Model Versions

The project contains multiple model versions and experiments.

### MVP v1 — Poisson Regression

The first working model version is based on a Poisson regression approach.

It provides:

- interpretable baseline modeling
- expected-goals prediction
- match probability generation
- group-stage simulation
- full tournament simulation

This version is useful as a transparent baseline.

---

### v2 Technical 33 — XGBoost Dry Run

The second model generation introduces a stronger machine learning approach using XGBoost.

It uses a broader technical feature set and was used as a dry run for testing:

- feature compatibility
- model pipeline stability
- simulation integration
- frontend model switching
- tournament simulation performance

This version is kept in the project as a documented experiment.

---

### v2 Full 35 — Final XGBoost Forecast Model

The strongest model candidate in the current project is `v2 Full 35`.

It uses 35 engineered features and an XGBoost-based expected-goals model.

This version includes:

- real FIFA ranking snapshots
- rank momentum features
- opponent-strength features
- team form features
- match-context features
- full World Cup fixture prediction
- group simulation
- knockout simulation
- final 10,000-run Monte Carlo tournament simulation
- dashboard integration without dry-run warning

This is the main model version used for the final dashboard.

---

## Feature Engineering

The feature layer is one of the most important parts of the project.

Features are built in SQL and Python from staged, cleaned and normalized data.

### Team Form Features

Examples:

- recent match results
- goals scored before a match
- goals conceded before a match
- rolling team performance
- attacking form
- defensive form

### FIFA Ranking Features

Examples:

- FIFA rank before match date
- normalized FIFA ranking
- ranking percentile
- rank difference between teams
- rank momentum over time

### Opponent Strength Features

The project does not only count whether a team won or lost. It also considers the strength of opponents.

Winning against a weak team is not the same signal as winning against a top-ranked team.

Opponent-adjusted features help distinguish:

```text
Team A wins many games against weak opponents
vs.
Team B performs well against strong opponents
```

### Match Context Features

Examples:

- home/away information
- neutral venue flag
- tournament context
- group-stage vs knockout assumptions
- match-level identifiers

### Player & Market Value Features

The project also explores player-level and squad-level data:

- player market values
- squad market value
- top-player value concentration
- squad depth proxies
- player profile information

These features are especially useful because national team strength is often strongly influenced by squad quality and depth.

### NLP-Based News Features

The NLP part is designed to extract soft information that is not directly visible in structured match data.

Examples:

- “key player injured”
- “coach under pressure”
- “internal conflict”
- “positive team atmosphere”
- “important player suspended”
- “media pressure before tournament”

These signals can be aggregated into team-level features and used as an additional model input layer.

---

## Database Design

The project uses PostgreSQL as a central analytical database.

The data pipeline is organized into several layers:

```text
raw
  ↓
staging
  ↓
features
  ↓
experiments
  ↓
dashboard
```

### Raw Layer

The raw layer keeps imported source data as close as possible to the original format.

This makes the pipeline more reproducible and protects the original data from accidental changes.

### Staging Layer

The staging layer cleans and normalizes the raw data.

Typical staging tasks:

- team-name normalization
- country-code mapping
- date parsing
- type conversion
- duplicate handling
- filtering invalid rows
- preparing joinable team identifiers

### Feature Layer

The feature layer contains model-ready tables.

Examples:

- team form before match
- FIFA ranking before match
- model input tables
- World Cup match prediction tables
- tournament simulation summary tables

### Experiments Layer

The experiments layer stores model evaluation results.

This allows different model versions to be compared in a structured way.

---

## Project Structure

```text
wm-prediction/
├── app/
│   └── Home.py
│
├── data/
│   ├── raw/
│   └── processed/
│
├── docs/
│   ├── data_sources.md
│   ├── feature_feasibility_matrix.md
│   ├── mvp_v1_notes.md
│   ├── rebuild_order.md
│   └── db_dump_restore.md
│
├── scripts/
│   ├── News/
│   │   ├── import_news_api.py
│   │   ├── news_analysis.py
│   │   ├── aggregate_news_features.py
│   │   └── run_news_pipeline.py
│   │
│   └── sportsmonk/
│
├── src/
│   └── wm_prediction/
│       ├── config.py
│       │
│       ├── db/
│       │   ├── connection.py
│       │   ├── import_raw.py
│       │   ├── staging.sql
│       │   ├── elo_staging.sql
│       │   ├── fifa_ranking.sql
│       │   └── player_staging.sql
│       │
│       ├── features/
│       │   ├── 06_features_team_form.sql
│       │   ├── 07_features_fifa_ranking.sql
│       │   ├── 08_features_match_context.sql
│       │   ├── 09_features_match_training.sql
│       │   ├── 10_features_match_coverage.sql
│       │   ├── 11_features_model_input_mvp_v1.sql
│       │   ├── 12_features_match_prediction_mvp_v1.sql
│       │   ├── 12_features_match_prediction_v2_full_35.sql
│       │   ├── 13_features_team_prediction_snapshot_v2_full_35.sql
│       │   ├── 20_features_opponent_strength.sql
│       │   └── 21_features_rank_momentum.sql
│       │
│       └── modeling/
│           ├── baseline_poisson.py
│           ├── poisson_regressor_mvp.py
│           ├── predict_world_cup_fixtures_mvp.py
│           ├── predict_world_cup_fixtures_v2_full_35.py
│           ├── simulate_group_stage_mvp.py
│           ├── simulate_group_stage_v2_full_35.py
│           ├── simulate_tournament_mvp.py
│           ├── simulate_tournament_v2_full_35.py
│           ├── scenario_tournament_v2_full_35.py
│           └── model comparison / validation scripts
│
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Dashboard Preview

The Streamlit dashboard is designed as a compact forecasting interface.

Main capabilities:

- select model version
- select simulation run
- inspect title probabilities
- compare tournament favorites
- explore group probabilities
- analyze individual matches
- simulate custom knockout scenarios
- inspect full team result tables
- view technical checks and probability sums

The dashboard is built for both technical analysis and presentation use.

---

## Scenario Mode

One of the most interesting features of the project is the Scenario Mode.

Instead of only accepting the baseline group-stage simulation, the user can manually define group rankings.

Example:

```text
Group A:
1. Germany
2. Morocco
3. Japan
4. Canada
```

The app then simulates the knockout stage based on that custom group outcome.

This allows interactive “what-if” analysis:

- What if a favorite only finishes second?
- What if a dark horse wins the group?
- What if two strong teams meet earlier than expected?
- How does the bracket path change title probabilities?

Scenario Mode is useful because tournament probabilities are not only about team strength. They are also heavily influenced by the path through the bracket.

---

## Model Evaluation

The project includes several evaluation and experiment scripts.

Evaluation metrics include:

- goal prediction error
- Poisson deviance
- win/draw/loss log loss
- Brier score
- rolling validation results
- model comparison across time windows

The project compares:

- simple Poisson baseline
- tuned Poisson regression
- HistGradientBoosting
- XGBoost
- different feature sets
- ranking momentum variants
- opponent-strength variants

The final model decision is based on both validation performance and end-to-end tournament simulation usability.

---

## Monte Carlo Simulation

The tournament simulation uses repeated random tournament runs.

For each simulation:

1. group-stage matches are sampled from match probabilities
2. group tables are generated
3. top teams qualify
4. best third-place teams are selected
5. knockout matchups are resolved
6. a champion is produced

After many simulations, the system aggregates the results:

```text
p_advance_group
p_reach_round_of_16
p_reach_quarter_final
p_reach_semi_final
p_final
p_title
p_third_place
```

The final XGBoost model uses a 10,000-run simulation for more stable tournament probabilities.

---

## Example Output

Example of a full tournament probability table:

```text
Team          Advance Group   Round of 16   Quarter Final   Semi Final   Final   Title
Brazil            0.91           0.74           0.55          0.34       0.21    0.13
France            0.90           0.72           0.53          0.32       0.20    0.12
Argentina         0.89           0.70           0.51          0.31       0.19    0.11
Spain             0.88           0.69           0.49          0.29       0.17    0.10
England           0.86           0.67           0.47          0.27       0.16    0.09
```

The exact values depend on the selected model and simulation run.

---

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd wm-prediction
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate
```

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### 4. Create environment file

```bash
cp .env.example .env
```

Example `.env`:

```env
DATABASE_URL=postgresql+psycopg://wm_user:wm_password@localhost:5432/wm_prediction
APP_ENV=development
```

### 5. Start PostgreSQL

```bash
docker compose up -d
```

### 6. Start the dashboard

```bash
streamlit run app/Home.py
```

---

## Rebuild Workflow

The full rebuild process is documented in `docs/rebuild_order.md`.

At a high level:

```text
1. Start PostgreSQL
2. Import raw data
3. Run staging SQL
4. Build feature tables
5. Train / evaluate models
6. Predict World Cup fixtures
7. Simulate group stage
8. Simulate full tournament
9. Launch Streamlit dashboard
```

---

## Key Technical Highlights

- End-to-end Data Science pipeline from raw data to dashboard
- PostgreSQL-based analytical data warehouse structure
- SQL-heavy feature engineering
- time-aware feature creation to reduce data leakage
- Poisson-based expected-goals modeling
- XGBoost model candidate with 35 engineered features
- model comparison and rolling validation
- Monte Carlo simulation for tournament probabilities
- official-style World Cup 2026 tournament logic
- group-stage and knockout simulation
- scenario-based interactive analysis
- Streamlit dashboard with multiple analysis views
- NLP-based research track for news-derived football signals

---

## Lessons Learned

This project was especially valuable because the hardest part was not simply training a model.

The biggest learning areas were:

- understanding how messy football data is in practice
- dealing with inconsistent team names across sources
- avoiding data leakage in time-dependent features
- separating raw, staging and feature layers
- designing a reproducible database workflow
- comparing baseline and advanced models fairly
- building simulation logic that matches tournament rules
- turning model outputs into an understandable dashboard
- connecting classical tabular modeling with NLP-based feature ideas

The project shows that real Data Science work is not only about algorithms. It is mostly about data quality, feature design, validation, interpretation and communication.

---

## Future Improvements

Possible next steps:

- integrate live injury and suspension data more deeply
- improve player-level squad aggregation
- add betting market comparison
- include weather and venue conditions
- add travel distance and timezone features
- improve NLP sentiment classification
- add team chemistry proxies
- train additional ensemble models
- deploy the dashboard online
- automate data refresh workflows
- add CI checks for database rebuild consistency

---

## Disclaimer

This project is a Data Science and forecasting project. The generated probabilities are model-based estimates and should not be interpreted as guaranteed outcomes.

Football is highly uncertain, and even the best model can only estimate probabilities based on available data.

---

## Author

Built as part of a Data Science / NLP project focused on predicting FIFA World Cup 2026 results using structured football data, feature engineering, probabilistic modeling and interactive dashboarding.
