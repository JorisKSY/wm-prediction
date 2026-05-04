# WM Prediction via Two-Stage Modeling

Data Science project for probabilistic football match prediction.

## Tech Stack

- Python
- PostgreSQL via Docker
- Streamlit
- VS Code
- GitHub

## Project Goal

Build a two-stage model:

1. Predict expected goals for both teams.
2. Convert expected goals into match probabilities and tournament simulations.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d
streamlit run app/Home.py