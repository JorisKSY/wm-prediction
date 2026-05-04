# WM Prediction via Two-Stage Modeling

Data Science project for probabilistic football match prediction.

This project predicts football match outcomes using a two-stage approach:

1. Predict expected goals for both teams.
2. Convert expected goals into match probabilities and tournament simulations.

The long-term goal is to simulate a World Cup tournament using Monte Carlo simulation.

---

## Project Idea

We want to build a probabilistic football prediction system.

The planned pipeline is:

```text
Data → PostgreSQL → Cleaning → Features → Goal Model → Poisson Probabilities → Tournament Simulation → Streamlit App
```

The project is built step by step.  
At the current stage, the focus is **project setup**, not model training yet.

---

## Tech Stack

We use:

- Python
- PostgreSQL
- Docker
- Streamlit
- VS Code
- GitHub
- SQLAlchemy
- python-dotenv

---

## Current Project Status

Already implemented:

- Basic Python project structure
- Virtual environment setup
- Docker-based PostgreSQL database
- Database connection from Python
- Streamlit app with database status check
- GitHub repository setup

Not implemented yet:

- Real datasets
- Database tables
- Data import pipeline
- Feature engineering
- Machine learning models
- Tournament simulation

---

## Project Structure

```text
wm-prediction/
├── app/
│   └── Home.py
├── data/
│   ├── raw/
│   └── processed/
├── docker/
├── notebooks/
├── src/
│   └── wm_prediction/
│       ├── __init__.py
│       ├── config.py
│       ├── data/
│       ├── db/
│       │   ├── __init__.py
│       │   └── connection.py
│       ├── features/
│       ├── models/
│       └── simulation/
├── tests/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── pyproject.toml
├── README.md
└── requirements.txt
```

---

## Setup Guide for Team Members

Follow these steps carefully.

This guide assumes you are on macOS.

---

## 1. Install Required Tools

Before starting, make sure these tools are installed:

### Python

Check:

```bash
python3 --version
```

### Git

Check:

```bash
git --version
```

### Docker Desktop

Check:

```bash
docker --version
docker compose version
```

Docker Desktop must be running before starting the database.

### VS Code

Check:

```bash
code --version
```

---

## 2. Clone the Repository

Choose a folder where you want to store the project.

Example:

```bash
cd ~/Documents
git clone <REPOSITORY_URL>
cd wm-prediction
```

Replace `<REPOSITORY_URL>` with the GitHub repository URL.

---

## 3. Open the Project in VS Code

```bash
code .
```

---

## 4. Create a Python Virtual Environment

Inside the project folder:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

You should now see `(.venv)` in your terminal.

Example:

```text
(.venv) username@MacBook wm-prediction %
```

---

## 5. Install Python Dependencies

With the virtual environment activated:

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

The command `pip install -e .` makes the local project package importable in Python.

---

## 6. Create Your Local `.env` File

The project uses environment variables for configuration.

Create a local `.env` file from the example file:

```bash
cp .env.example .env
```

Your `.env` should contain:

```env
DATABASE_URL=postgresql+psycopg://wm_user:wm_password@localhost:5432/wm_prediction
APP_ENV=development
```

Important:

```text
Never commit the .env file to GitHub.
```

Only `.env.example` should be committed.

---

## 7. Start the PostgreSQL Database

Make sure Docker Desktop is running.

Then start the database:

```bash
docker compose up -d
```

Check if the database container is running:

```bash
docker ps
```

You should see a container named:

```text
wm_prediction_postgres
```

---

## 8. Test the Database Connection

Run:

```bash
python -c "from wm_prediction.db.connection import check_database_connection; print(check_database_connection())"
```

Expected output:

```text
True
```

If you see `True`, Python can connect to PostgreSQL successfully.

---

## 9. Start the Streamlit App

Run:

```bash
streamlit run app/Home.py
```

The app should open in your browser.

You should see:

```text
Postgres connection: OK
```

---

## Common Daily Workflow

When you start working on the project:

```bash
cd path/to/wm-prediction
source .venv/bin/activate
docker compose up -d
streamlit run app/Home.py
```

When you are done working:

```bash
docker compose down
```

---

## Git Workflow for Team Members

Before starting work, always get the newest version:

```bash
git pull
```

Check what changed locally:

```bash
git status
```

After making changes:

```bash
git add .
git commit -m "Describe your change here"
git push
```

Example:

```bash
git add .
git commit -m "Update README setup instructions"
git push
```

---

## Branch Workflow

For larger changes, create a new branch:

```bash
git checkout -b your-branch-name
```

Example:

```bash
git checkout -b add-data-import
```

After making changes:

```bash
git add .
git commit -m "Add initial data import script"
git push origin add-data-import
```

Then open a Pull Request on GitHub.

---

## Useful Commands

### Activate virtual environment

```bash
source .venv/bin/activate
```

### Start database

```bash
docker compose up -d
```

### Stop database

```bash
docker compose down
```

### Check running Docker containers

```bash
docker ps
```

### Open PostgreSQL shell

```bash
docker compose exec postgres psql -U wm_user -d wm_prediction
```

### List database tables

Inside `psql`:

```sql
\dt
```

At the moment, it is normal if there are no tables yet.

### Exit PostgreSQL shell

```sql
\q
```

### Start Streamlit

```bash
streamlit run app/Home.py
```

---

## Troubleshooting

### Problem: Docker is not running

Error example:

```text
Cannot connect to the Docker daemon
```

Solution:

Open Docker Desktop and wait until it is fully started.

Then run:

```bash
docker ps
```

---

### Problem: Database container is not running

Run:

```bash
docker compose up -d
```

Then check:

```bash
docker ps
```

---

### Problem: Python cannot import `wm_prediction`

Run:

```bash
pip install -e .
```

Then try again.

---

### Problem: `.env` is missing

Run:

```bash
cp .env.example .env
```

---

### Problem: psycopg / libpq error

If you see an error like:

```text
ImportError: no pq wrapper available
```

Run:

```bash
pip install "psycopg[binary]"
pip freeze > requirements.txt
```

Then test again:

```bash
python -c "from wm_prediction.db.connection import check_database_connection; print(check_database_connection())"
```

---

### Problem: Streamlit cannot connect to the database

Check these things:

1. Is Docker Desktop running?
2. Is the database container running?

```bash
docker ps
```

3. Does `.env` exist?

```bash
ls -a
```

4. Does the database connection test work?

```bash
python -c "from wm_prediction.db.connection import check_database_connection; print(check_database_connection())"
```

---

## Important Rules

Please follow these rules:

1. Do not commit `.env`.
2. Do not commit large raw datasets.
3. Do not change `docker-compose.yml` without discussing it with the team.
4. Always run `git pull` before starting work.
5. Always use the virtual environment.
6. Keep commits small and understandable.
7. Do not add modeling code before the data and database structure are agreed on.

---

## Planned Next Steps

Next technical steps:

1. Define the initial database structure.
2. Decide how raw match data will be stored.
3. Add first database tables.
4. Add a simple data import workflow.
5. Add a Streamlit page for viewing database contents.
6. Later: add feature engineering.
7. Later: add goal prediction model.
8. Later: add Poisson match probabilities.
9. Later: add Monte Carlo tournament simulation.

---

## Project Goal in One Sentence

Build a Streamlit-based data science app that predicts football match outcomes and simulates World Cup tournaments using expected goals, Poisson probabilities and Monte Carlo simulation.