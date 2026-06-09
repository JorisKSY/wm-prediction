# Rebuild-Reihenfolge

## Zweck

Diese Datei dokumentiert, wie ein Kollege denselben Projektstand des WM-Prediction-Projekts
reproduzieren kann – entweder schnell per DB-Dump/Restore oder vollständig aus den Raw-Daten.

---

## Empfohlener Weg: DB-Dump/Restore

**Warum nicht einfach nur Git pullen?**
Der Git-Code enthält keine Raw-Daten und keinen DB-State. Tabellen wie Staging, Features,
Experiment-Ergebnisse und Simulationsergebnisse existieren nur in der laufenden PostgreSQL-Instanz.
Ohne Dump fehlt der gesamte Datenbestand.

**Für schnelles Onboarding ist ein PostgreSQL-Dump des aktuellen DB-Stands am besten.**

### Schritte

**1. Branch pullen**

```bash
git pull
git checkout neuestagingtabellen
```

**2. `.env` prüfen / anlegen**

Die Datei `.env` muss existieren und folgende Variablen enthalten (Werte ggf. anpassen):

```
POSTGRES_USER=wm_user
POSTGRES_DB=wm_prediction
POSTGRES_PASSWORD=<passwort>
```

**3. Docker-Postgres starten**

```bash
docker compose up -d postgres
```

Warten bis der Container hochgefahren ist:

```bash
docker compose ps
```

**4. DB-Dump einspielen**

> ⚠️ Der Dateiname des Dumps ist projektabhängig – bitte den konkreten Dump-Pfad mit dem
> Kollegen absprechen, der den Dump erstellt hat.

Dump erstellen (auf der Quellmaschine, falls noch nicht vorhanden):

```bash
# Dump erstellen – Dateiname und Pfad ggf. anpassen
docker compose exec -T postgres sh -lc \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl -Fc' \
  > wm_prediction_dump_$(date +%Y%m%d).dump
```

Dump einspielen (auf der Zielmaschine):

```bash
# Dump einspielen – Dateiname anpassen
docker compose exec -T postgres sh -lc \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl -Fc' \
  < wm_prediction_dump_YYYYMMDD.dump
```

**5. Projekt installieren**

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

**6. Streamlit starten**

```bash
streamlit run app/Home.py
```

---

## Vollständiger Rebuild aus Raw-Daten

Dieser Weg ist nur nötig, wenn kein DB-Dump verfügbar ist oder der DB-State vollständig
von Grund auf neu aufgebaut werden soll.

**Voraussetzungen:**
- Docker läuft, `docker compose up -d postgres` wurde ausgeführt.
- Das Projekt ist installiert: `pip install -e .`
- Die Raw-Daten liegen lokal vor (nicht in Git – siehe Hinweise am Ende).

Die psql-Befehle unten nutzen den psql im Postgres-Container, da psql lokal nicht zwingend
installiert ist:

```bash
# Abkürzung für psql im Container – in dieser Datei als PSQL verwendet
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off'
```

---

### 1. Raw-Daten importieren

Der Raw-Layer muss **vollständig** existieren, bevor Staging-SQL läuft.
Raw-Tabellen werden **nicht verändert** – sie sind reine Eingabedaten.

Raw-Import-Skripte und CSV-Pfade sind projektabhängig und müssen vor dem Rebuild
vorliegen. Typischerweise werden die CSVs per `COPY`-Befehl oder per Python-Importskript
in die Raw-Schemata geladen.

**Checkliste der benötigten Raw-Tabellen:**

- [ ] `raw.atheels_datasets_results`
- [ ] `raw.atheels_datasets_goalscorers`
- [ ] `raw.atheels_datasets_fifa_ranking`
- [ ] `raw.atheels_datasets_historical_fifa_mens_rank`
- [ ] `raw.atheels_datasets_fifa_mens_rankings`
- [ ] `raw.atheels_datasets_world_football_elo_clean`
- [ ] `raw.atheels_datasets_matches`
- [ ] `raw.kaggle_player_scores_players`
- [ ] `raw.kaggle_player_scores_appearances`
- [ ] `raw.kaggle_player_scores_game_lineups`
- [ ] `raw.kaggle_player_scores_game_events`
- [ ] `raw.kaggle_player_scores_games`
- [ ] `raw.kaggle_player_scores_club_games`
- [ ] `raw.kaggle_player_scores_player_valuations`
- [ ] `raw.kaggle_player_scores_competitions`
- [ ] `raw.kaggle_player_scores_national_teams`
- [ ] `raw.soccerdata_fbref_world_cup_2018_schedule`
- [ ] `raw.soccerdata_fbref_world_cup_2022_schedule`

Vor dem nächsten Schritt sicherstellen, dass alle Tabellen befüllt sind.

---

### 2. Staging-SQL ausführen

> **Wichtig:** `staging.sql` muss als Erstes laufen. Dort werden zentrale Team-Aliases
> und das Team-Mapping-Grundgerüst aufgebaut, auf dem alle späteren Staging-Skripte aufbauen.

Reihenfolge:

```bash
# 1. Zentrale Staging-Basis (Team-Aliases, Team-Mapping)
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' \
  < src/wm_prediction/db/staging.sql

# 2. Elo-Staging
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' \
  < src/wm_prediction/db/elo_staging.sql

# 3. Erweitertes Staging (04)
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' \
  < src/wm_prediction/db/04_staging.sql

# 4. FIFA-Ranking-Staging
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' \
  < src/wm_prediction/db/fifa_ranking.sql

# 5. Player-Staging
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' \
  < src/wm_prediction/db/player_staging.sql
```

---

### 3. Feature-SQL ausführen

Die Feature-SQL-Dateien liegen unter `src/wm_prediction/features/` und müssen in
numerischer Reihenfolge ausgeführt werden, da spätere Skripte auf Tabellen der früheren
aufbauen.

```bash
for f in \
  src/wm_prediction/features/06_features_team_form.sql \
  src/wm_prediction/features/07_features_fifa_ranking.sql \
  src/wm_prediction/features/08_features_match_context.sql \
  src/wm_prediction/features/09_features_match_training.sql \
  src/wm_prediction/features/10_features_match_coverage.sql \
  src/wm_prediction/features/11_features_model_input_mvp_v1.sql \
  src/wm_prediction/features/12_features_match_prediction_mvp_v1.sql \
  src/wm_prediction/features/13_features_team_prediction_snapshot_mvp_v1.sql \
  src/wm_prediction/features/14_features_world_cup_groups_mvp_v1.sql \
  src/wm_prediction/features/15_features_world_cup_round32_slots_mvp_v1.sql \
  src/wm_prediction/features/16_features_world_cup_knockout_bracket_mvp_v1.sql \
  src/wm_prediction/features/17_features_tournament_simulation_summary_mvp_v1.sql
do
  echo "==> $f"
  docker compose exec -T postgres sh -lc \
    'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' \
    < "$f"
done
```

---

### 4. Experiment-SQL ausführen

Diese Tabellen und Views speichern Modellvergleichsmetriken. Sie gehören logisch zum
Experimenttracking und sind kein Teil des Feature-Layers.

```bash
# Tabellen für Modellvergleichsmetriken
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' \
  < src/wm_prediction/db/18_experiments_model_evaluation_results.sql

# Views für Modellvergleich
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' \
  < src/wm_prediction/db/19_experiments_model_evaluation_views.sql
```

---

### 5. Modeling-, Prediction- und Simulation-Skripte ausführen

Diese Skripte müssen nach dem Feature-Aufbau in dieser Reihenfolge ausgeführt werden.
Vor dem Ausführen: venv aktivieren und Projekt installiert haben (`pip install -e .`).

```bash
# 1. Modell evaluieren (schreibt keine WM-Predictions, nur Evaluation)
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.poisson_regressor_mvp

# 2. WM-Fixture-Predictions in DB schreiben → features.match_predictions_mvp_v1
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.predict_world_cup_fixtures_mvp --write-db

# 3. Gruppenphase simulieren → Gruppenphasen-Summary in DB
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.simulate_group_stage_mvp \
  --n-simulations 1000 \
  --seed 42 \
  --write-db

# 4. Gesamtturnier simulieren → Full-Tournament-Summary in DB
#    Achtung: Bei gleicher simulation_run_id wird die Tournament-Summary
#    vorher gelöscht und neu geschrieben.
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.simulate_tournament_mvp \
  --seed 42 \
  --n-simulations 1000 \
  --write-db \
  --simulation-run-id mvp_v1_seed_42_n_1000

# 5. Modellvergleichsmetriken in experiments.model_evaluation_results schreiben
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.write_poisson_experiment_results
```

**Was welches Skript schreibt:**

| Skript | Schreibt in DB |
|---|---|
| `poisson_regressor_mvp` | Nein (nur Evaluation/Logs) |
| `predict_world_cup_fixtures_mvp --write-db` | `features.match_predictions_mvp_v1` |
| `simulate_group_stage_mvp --write-db` | Gruppenphasen-Summary |
| `simulate_tournament_mvp --write-db` | `features.tournament_simulation_summary_mvp_v1` |
| `write_poisson_experiment_results` | `experiments.model_evaluation_results` |

---

### 6. Optionale Diagnose-Skripte

Diese Skripte sind für Analyse und Diagnose nützlich, aber **nicht zwingend nötig**,
um den DB-Endstand für die App zu erzeugen.

```bash
# Baseline-Modell (Vergleichsreferenz)
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.baseline_poisson

# Feature-Ablation-Studien
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.feature_ablation_poisson_mvp
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.feature_ablation_extreme_scores_mvp
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.feature_ablation_fifa_transform_mvp
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.feature_ablation_context_flags_mvp

# Einzelnes Knockout-Matchup vorhersagen
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.predict_knockout_matchup_mvp
```

---

> **Achtung:** Die folgenden Diagnose-Skripte sind ebenfalls nicht zwingend noetig fuer den App-DB-Endstand, schreiben aber in experiments.model_evaluation_results (anders als die print-only Ablationen oben). Sie setzen voraus, dass die Experiment-SQL aus Abschnitt 4 bereits ausgefuehrt wurde. Zusammen mit write_poisson_experiment_results (Abschnitt 5, Phase A) reproduzieren sie alle vier Experiment-Runs.

- Phase B Alpha-Tuning: python -m wm_prediction.modeling.tune_poisson_alpha_mvp
- Phase C Attack/Defense: python -m wm_prediction.modeling.experiment_attack_defense_form_v2
- Phase D Rolling Validation: python -m wm_prediction.modeling.rolling_validation_poisson_v2

---

## Validierungschecks

Nach dem Rebuild prüfen, ob die wichtigsten Tabellen befüllt sind.
Alle Befehle über psql im Container ausführen:

```bash
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off -c "
    SELECT
      (SELECT COUNT(*) FROM features.model_input_mvp_v1)
        AS model_input,
      (SELECT COUNT(*) FROM features.match_predictions_mvp_v1)
        AS match_predictions,
      (SELECT COUNT(*) FROM features.group_stage_simulation_summary_mvp_v1)
        AS group_stage_sim,
      (SELECT COUNT(*) FROM features.tournament_simulation_summary_mvp_v1)
        AS tournament_sim,
      (SELECT COUNT(*) FROM experiments.model_evaluation_results)
        AS eval_results;
  "'
```

Prüfen, dass die Tournament-Summary für `mvp_v1_seed_42_n_1000` genau 48 Teams enthält:

```bash
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off -c "
    SELECT COUNT(DISTINCT team)
    FROM features.tournament_simulation_summary_mvp_v1
    WHERE simulation_run_id = '"'"'mvp_v1_seed_42_n_1000'"'"';
  "'
# Erwartet: 48
```

---

## Streamlit starten

```bash
streamlit run app/Home.py
```

Die App ist danach unter `http://localhost:8501` erreichbar.

---

## Hinweise / Fallstricke

- **Raw-Daten sind nicht in Git.** `data/external/` ist in `.gitignore` eingetragen.
  Wer einen Rebuild startet, muss die Raw-Daten separat besorgen.
- **FIFA-Regel-PDF** liegt ggf. lokal, darf aber nicht committed werden.
- **Feature-Ordner heißt `features`**, nicht `feature`.
- **`staging.national_team_profiles`** sowie aktuelle FIFA-, Elo- und Marktwert-Snapshots
  dürfen **nicht blind für historisches Training** genutzt werden – sie spiegeln den
  aktuellen Stand wider, nicht den historischen zum Spielzeitpunkt.
- **`is_nations_league`** hat im aktuellen `train_pre_2018`-Split **keine positiven
  Trainingsbeispiele**. Das ist bekannt und kein Fehler.
- **Nicht jedes Modeling-Skript schreibt DB-Tabellen.** Nur Skripte mit `--write-db`
  oder explizitem DB-Write-Aufruf verändern den DB-State.
- **Simulationen können je nach `--n-simulations` länger dauern.** Bei 1000 Simulationen
  sind einige Minuten einzuplanen.
- **Bei gleicher `simulation_run_id`** wird die Tournament-Summary vorher gelöscht und
  komplett neu geschrieben – das ist Absicht, kein Datenverlust.
---

## Phase-E-Ergänzungen (opponent-adjusted Form / SOS)

> Diese Schritte kamen nach dem ursprünglichen MVP-v1-Rebuild dazu. Sie sind
> additiv und fassen den produktiven MVP-Pfad (11 und nachgelagert) NICHT an.

**Geänderte Datei:** `07_features_fifa_ranking.sql` baut jetzt zusätzlich die
geteilte Tabelle `features.fifa_rankings_normalized` (Namensnormalisierung, vorher
inline-CTE). Verhalten von `team_fifa_ranking_before_match` ist unverändert. Die
Rebuild-Reihenfolge in Abschnitt 3 bleibt gültig (Tabelle entsteht innerhalb 07).

**Neue Feature-Datei (nach 17 ausführen):**

```bash
docker compose exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' \
  < src/wm_prediction/features/20_features_opponent_strength.sql
```

Erzeugt `features.fifa_rank_percentile_snapshot` und
`features.team_opponent_strength_before_match`. Setzt voraus, dass 07 (wegen
`features.fifa_rankings_normalized`) und 06 (wegen `features.team_match_rows`)
vorher gelaufen sind.

**Neue Experiment-Scripte (schreiben in experiments.model_evaluation_results,
setzen Abschnitt 4 voraus):**

```bash
# Phase E fester Split (SOS)
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.experiment_opponent_strength_v2_phase_e_2026_06_07

# Phase E Rolling Validation (SOS, Hürde 2)
PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.rolling_validation_opponent_strength_phase_e_2026_06_07
```

Beide sind idempotent über ihre experiment_run_id. Zusammen mit den Phase-A/B/C/D-Runs
ergeben sich damit sechs reproduzierbare Experiment-Runs.

## Phase F Ergänzung: FIFA-Rang-Momentum

Nach Phase E kann zusätzlich das Rang-Momentum gebaut werden.

Build:

    docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' < src/wm_prediction/features/21_features_rank_momentum.sql

Die Datei baut:

- features.team_rank_momentum_before_match

Wichtig:

- basiert auf features.fifa_rank_percentile_snapshot
- Join über normalisierte Teamnamen, nicht über staging.fifa_rankings.team_id
- rank_now: letzter frischer Snapshot strikt vor match_date
- rank_1yr_ago: letzter frischer Snapshot strikt vor match_date - 1 year
- rank_improve_1yr = rank_1yr_ago - rank_now
- positiv = Ranking-Verbesserung
- Snapshots werden nur akzeptiert, wenn sie höchstens 240 Tage alt sind
- andernfalls bleibt das Momentum NULL

Danach können die Phase-F-Experimente reproduziert werden:

    python -m wm_prediction.modeling.experiment_rank_momentum_phase_f_2026_06_07
    python -m wm_prediction.modeling.rolling_validation_rank_momentum_phase_f_2026_06_07

Experiment-Runs:

- poisson_rank_momentum_phase_f_2026_06_07
- rolling_validation_rank_momentum_phase_f_2026_06_07

Entscheidung:

- home_rank_improve_1yr
- away_rank_improve_1yr

qualifizieren sich als weiterer v2-Kandidat-Block.

Nicht aufnehmen:

- rank_improve_1yr_diff, weil es im linearen PoissonRegressor redundant zu Home- und Away-Momentum ist.

Hinweis: Der 2022+-Holdout ist für Momentum aktuell nur eingeschränkt interpretierbar, weil staging.fifa_rankings derzeit nur bis 2024-07-01 reicht. Für WM-2026-End-to-End muss die Rankingquelle in Phase J aktualisiert werden.

## Phase H Ergänzung: Modellklassenvergleich und XGBoost-Kandidat

Nach Phase F wird das v2-Kandidaten-Feature-Set zentral geladen über:

- src/wm_prediction/modeling/v2_candidate_features.py

Dieses Feature-Set enthält 35 Features:

- MVP-Kontextfeatures
- FIFA-Rangfeatures
- Points-Form-Diffs
- Attack/Defense-Formfeatures
- SOS mean-only
- FIFA-Rang-Momentum

Abhängigkeit:
XGBoost ist in pyproject.toml als Dependency ergänzt:

- xgboost>=2.1,<4

Phase-H-Scripts in Reproduktionsreihenfolge:

    python -m wm_prediction.modeling.model_class_comparison_phase_h_2026_06_07
    python -m wm_prediction.modeling.rolling_validation_model_class_phase_h_2026_06_07
    python -m wm_prediction.modeling.tune_boosting_phase_h_2026_06_07
    python -m wm_prediction.modeling.final_model_candidates_phase_h_2026_06_07

Experiment-Runs:

- model_class_comparison_phase_h_2026_06_07
- rolling_validation_model_class_phase_h_2026_06_07
- tune_boosting_phase_h_2026_06_07
- final_model_candidates_phase_h_2026_06_07

Phase-H-Entscheidung:

Aktueller v2-Modellkandidat ist XGBoost mit Poisson-Ziel:

- objective=count:poisson
- eval_metric=poisson-nloglik
- n_estimators=800
- learning_rate=0.02
- max_depth=3
- min_child_weight=5
- subsample=0.90
- colsample_bytree=0.90
- reg_lambda=2.0
- reg_alpha=0.0
- tree_method=hist
- random_state=42
- n_jobs=4

Kurzbegründung:
XGBoost gewinnt im Rolling-Tuning die mittlere Goal-Deviance und verschlechtert
die WDL-Guardrails nicht gegenüber dem Poisson-Referenzmodell. HistGB ist knapp,
aber bei Goal-Deviance etwas schwächer. Da die Turniersimulation direkt aus den
Lambdas Tore zieht, hat Goal-Deviance Vorrang.

Hinweis:
Dies ist noch nicht die produktive v2-End-to-End-Pipeline. Für Phase J muss die
Prediction-/Simulation-Pipeline auf das v2-Feature-Set und XGBoost umgebaut werden.
Außerdem muss vor WM-2026-End-to-End geklärt werden, wie die FIFA-Rankings nach
2024-07-01 aktualisiert oder Momentum-Features für 2026 sauber behandelt werden.

## Phase J.1 Ergänzung: v2 Technical Dry Run ohne Momentum

Produktives v2 mit allen 35 Features ist aktuell blockiert, weil für `rank_improve_1yr`
ein echter FIFA-Ranking-Snapshot rund um 2025-06 fehlt.

Bis dieser Snapshot verfügbar ist, gibt es einen technischen Dry Run:

- Feature-Set: `v2_technical_33_no_momentum`
- Modell: `xgboost_v2_technical_33_no_momentum`
- nicht als finale WM-2026-Prognose interpretieren

Vorbedingung:
`staging.current_fifa_rankings` muss vorhanden sein und einen aktuellen Snapshot vom
2026-06-04 enthalten.

Zentraler Alias-Fix in `src/wm_prediction/db/staging.sql`:

- `Cabo Verde` -> `Cape Verde`
- fehlerhafter JSON-Text mit `Côte d'Ivoire` -> `Ivory Coast`

Falls die laufende DB nicht neu gestaged wurde, Aliases direkt upserten:

    docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' <<'SQL'
    INSERT INTO staging.team_name_aliases (source_name, canonical_name)
    VALUES
        ('Cabo Verde', 'Cape Verde'),
        ('[{''Locale'': ''en-GB'', ''Description'': "Côte d''Ivoire"}]', 'Ivory Coast')
    ON CONFLICT (source_name) DO UPDATE SET
        canonical_name = EXCLUDED.canonical_name;
    SQL

Feature-Konstanten:

- Datei: `src/wm_prediction/modeling/v2_candidate_features.py`
- `V2_TECHNICAL_33_NO_MOMENTUM_FEATURES`
- `V2_TECHNICAL_33_REQUIRED_JOINED_FEATURES`

Build-Reihenfolge Phase J.1:

    docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' < src/wm_prediction/features/12_features_match_prediction_v2_technical_33.sql

    docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' < src/wm_prediction/features/13_features_team_prediction_snapshot_v2_technical_33.sql

    python -m wm_prediction.modeling.predict_world_cup_fixtures_v2_technical_33 --write-db

    python -m wm_prediction.modeling.simulate_group_stage_v2_technical_33 \
      --n-simulations 1000 \
      --seed 42 \
      --write-db

    python -m wm_prediction.modeling.simulate_tournament_v2_technical_33 \
      --n-simulations 100 \
      --seed 42 \
      --write-db \
      --simulation-run-id xgboost_v2_technical_33_no_momentum_seed_42_to_141_n_100

Erzeugte Tabellen:

- `features.match_prediction_v2_technical_33`
- `features.team_prediction_snapshot_v2_technical_33`
- `features.match_predictions_v2_technical_33`
- `features.group_stage_simulation_summary_v2_technical_33`
- `features.tournament_simulation_summary_v2_technical_33`

Known limitation:
Die Full-Tournament-Simulation sollte vor größeren Läufen performanter gemacht werden.
Der 10er-Lauf war schnell, 100 lief erfolgreich durch, aber 1000 war zuvor zu langsam.
Vermutlich werden innerhalb der Simulation noch Daten wiederholt geladen oder unnötige Arbeit pro Simulation gemacht.

Nächster Schritt:
Full-Tournament-Tabelle auditieren, dann Performance optimieren, dann 1000/10000 Simulationslauf starten.

Sobald der echte 2025er FIFA-Ranking-Snapshot verfügbar ist:

- historische Rankingreihe bis 2026 ergänzen
- `rank_improve_1yr` für 2026 korrekt bauen
- `v2_full_35` aktivieren
- finale v2-End-to-End-Prognose bauen

## WICHTIG: Reihenfolge-Abhaengigkeit 14_features_world_cup_groups (2026-06-07)

14_features_world_cup_groups_mvp_v1.sql liest aus features.match_predictions_mvp_v1
(PLURAL, die Fixture-Predictions) -- diese Tabelle wird ERST vom Modeling-Schritt
"predict_world_cup_fixtures_mvp --write-db" erzeugt, NICHT im Feature-SQL-Block.
ACHTUNG: 12_features_match_prediction_mvp_v1.sql erzeugt match_prediction_mvp_v1
(SINGULAR) -- das ist NICHT dieselbe Tabelle.

Folge bei Rebuild von Null: 14 (und damit 15/16/17, die auf den Gruppen aufbauen)
MUSS NACH dem Schritt "predict_world_cup_fixtures_mvp --write-db" laufen, sonst
scheitert 14 mit "relation features.match_predictions_mvp_v1 does not exist".
Reihenfolge im Feature-Block oben entsprechend interpretieren: 06-13 zuerst, dann
Modeling-Schritt 2 (Fixture-Predictions), DANN 14-17, dann restliche Modeling-Schritte.
(Diese Luecke bestand schon vor dem Bracket-Label-Bugfix; faellt nur bei einem
echten Rebuild von der gruenen Wiese auf.)

## Bracket-Label-Bugfix + Re-Runs (2026-06-07)
14_features_world_cup_groups_mvp_v1.sql wurde umgebaut (siehe mvp_v1_notes.md):
official_group_label kommt jetzt aus expliziter VALUES-Liste (offizielle Auslosung),
nicht mehr aus alphabetischer ROW_NUMBER(). Beide Full-Tournament-Pipelines danach
neu simuliert:
- MVP: simulate_tournament_mvp --seed 42 --n-simulations 1000 --simulation-run-id mvp_v1_seed_42_n_1000 --write-db
- v2:  simulate_tournament_v2_technical_33 --seed 42 --n-simulations 1000 --write-db
       (run_id xgboost_v2_technical_33_no_momentum_seed_42_to_1041_n_1000;
        ERSETZT den frueheren 100er-Run aus diesem Doc weiter unten.)

## Performance (2026-06-07)
simulate_tournament_v2_technical_33: invariante DB-Reads (matches/groups/bracket)
einmal vor der Monte-Carlo-Schleife geladen; KnockoutMatchupPredictor mit
O(1)-Team-Lookup + Lambda-Cache pro geordnetem Matchup. n=1000: ~196s -> ~47s.
Verhaltensneutral (Seed-42-100er bitgenau identisch verifiziert).

## Frontend Modellauswahl (2026-06-07)
app/Home.py: Modell-Dropdown (MVP v1 vs. v2 Technical 33 Dry Run) ueber MODELS-Dict
(eine Quelle der Wahrheit fuer Tabellennamen). Default MVP v1. v2 zeigt Dry-Run-
Warnung. load_tournament_runs ohne created_at (v2-Tabelle hat die Spalte nicht),
sortiert nach simulation_run_id DESC. Start: streamlit run app/Home.py

## Phase J.2 Ergänzung: v2_full_35 mit echten 2025/2026-FIFA-Rankings

Diese Ergänzung ersetzt nicht den MVP-v1-Rebuild oben, sondern beschreibt die
zusätzlichen Schritte für den echten v2-End-to-End-Stand mit 35 Features.

Neue Raw-Voraussetzung:

- `raw.atheels_datasets_fifa_mens_rankings`
- Quelle: `data/raw/atheels_datasets/fifa_mens_rankings_2024_07_to_2026_06.csv`
- Raw bleibt originalgetreu, inkl. 11 gescrapter Werbe-/JS-Muellzeilen
- Staging filtert ungueltige Zeilen ueber `country_code !~ '^[A-Z]{3}$'`

Wichtige fachliche Regeln:

- `ranking_date` ist der echte Snapshot-Schluessel.
- `ranking_year` und `ranking_semester` sind nur grobe Etiketten.
- Nie ueber `staging.fifa_rankings.team_id` an Match-Teams joinen.
- FIFA-Ranking-Joins immer ueber normalisierte/canonical Namen und as-of-Logik.
- `current_fifa_rankings` nicht fuer historisches Training verwenden.
- `v2_full_35` nutzt die erweiterte `fifa_rankings_normalized`-Kette, nicht den alten 2026-06-04-current-Snapshot.

Relevante Code-/SQL-Aenderungen fuer Rebuild:

- `src/wm_prediction/db/fifa_ranking.sql`
  - idempotenter Append-Block fuer `ranking_date >= '2024-07-18'`
  - schreibt 2311 gueltige neue Ranking-Zeilen nach `staging.fifa_rankings`
- `src/wm_prediction/features/07_features_fifa_ranking.sql`
  - Normalisierung: `Cabo Verde`/`Cape Verde Islands` -> `Cape Verde`
  - Normalisierung: `The Gambia` -> `Gambia`
  - Normalisierung: `Brunei Darussalam` -> `Brunei`
- `src/wm_prediction/features/20_features_opponent_strength.sql`
  - Perzentil-Snapshot partitioniert nach `ranking_date`, nicht mehr nach `(ranking_year, ranking_semester)`
- `src/wm_prediction/features/21_features_rank_momentum.sql`
  - Momentum basiert jetzt auf dichterer echter Ranking-Historie
- `src/wm_prediction/features/12_features_match_prediction_v2_full_35.sql`
- `src/wm_prediction/features/13_features_team_prediction_snapshot_v2_full_35.sql`
- `src/wm_prediction/modeling/predict_world_cup_fixtures_v2_full_35.py`

Zusätzliche Build-Reihenfolge nach dem normalen Staging und nach den gemeinsamen
Feature-Skripten 06 bis 11 sowie 20 und 21:

    docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' < src/wm_prediction/features/12_features_match_prediction_v2_full_35.sql

    docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' < src/wm_prediction/features/13_features_team_prediction_snapshot_v2_full_35.sql

    PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.predict_world_cup_fixtures_v2_full_35 --write-db

Erzeugte v2_full_35-Basistabellen:

- `features.match_prediction_v2_full_35`
- `features.team_prediction_snapshot_v2_full_35`
- `features.match_predictions_v2_full_35`

Plausibilitaetschecks nach diesem Schritt:

- `features.match_prediction_v2_full_35`: 72 Fixtures
- `features.team_prediction_snapshot_v2_full_35`: 48 Teams
- `features.match_predictions_v2_full_35`: 72 Predictions
- keine NULLs in Rang-, Momentum- und SOS-Features fuer WM-2026-Teams
- Spanien: Rang 2, Momentum +1
- Argentinien: Rang 1, Momentum 0
- Cape Verde: Rang 67 vorhanden
- Match-Wahrscheinlichkeiten summieren pro Fixture auf 1.0

Modellstatus:

- `v2_full_35` ist kein Dry Run.
- Modellname: `xgboost_v2_full_35`
- Feature-Set: `V2_CANDIDATE_FEATURES` mit 35 Features
- XGBoost-Setup: `make_xgb_best()`
- Fester Split und Rolling Validation sind bestanden.
- `v2_technical_33` bleibt nur als technischer Dry Run dokumentiert.

Noch offene Rebuild-Schritte nach aktuellem Stand:

- `simulate_group_stage_v2_full_35.py` bauen und verifizieren
- `predict_knockout_matchup_v2_full_35.py` bauen und verifizieren
- `simulate_tournament_v2_full_35.py` bauen und verifizieren
- 10k Full-Tournament-Simulation schreiben
- `app/Home.py` um dritten Kandidaten `v2_full_35` erweitern, ohne Dry-Run-Warnung

Pflichtcheck fuer jede Full-Tournament-Simulation:

- Summe `p_advance_group` = 32
- Summe `p_reach_round_of_16` = 16
- Summe `p_reach_quarter_final` = 8
- Summe `p_reach_semi_final` = 4
- Summe `p_final` = 2
- Summe `p_title` = 1
- Summe `p_third_place` = 1

## Phase J.3 Ergänzung: v2_full_35 Simulation + Frontend

Diese Ergänzung betrifft gezielt den echten `v2_full_35`-Kandidaten. Sie ersetzt
nicht die MVP-v1- oder v2-technical-33-Dokumentation.

Nach erfolgreichem Aufbau von:

- `features.match_prediction_v2_full_35`
- `features.team_prediction_snapshot_v2_full_35`
- `features.match_predictions_v2_full_35`

kommen fuer v2_full_35 diese Modeling-Schritte hinzu:

    PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.simulate_group_stage_v2_full_35 \
      --n-simulations 1000 \
      --seed 42 \
      --write-db

    PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.simulate_tournament_v2_full_35 \
      --seed 42 \
      --n-simulations 10000 \
      --write-db \
      --simulation-run-id xgboost_v2_full_35_seed_42_to_10041_n_10000

Erzeugte bzw. befuellte Tabellen:

- `features.group_stage_simulation_summary_v2_full_35`
- `features.tournament_simulation_summary_v2_full_35`

Neu angelegte Skripte:

- `src/wm_prediction/modeling/simulate_group_stage_v2_full_35.py`
- `src/wm_prediction/modeling/predict_knockout_matchup_v2_full_35.py`
- `src/wm_prediction/modeling/simulate_tournament_v2_full_35.py`

Performance-/Bracket-Hinweis:

`simulate_tournament_v2_full_35.py` wurde aus dem optimierten
`simulate_tournament_v2_technical_33.py` abgeleitet. Dadurch bleiben erhalten:

- invariante DB-Reads fuer matches/groups/bracket ausserhalb der Monte-Carlo-Schleife
- einmaliger Knockout-Predictor pro Run
- O(1)-Team-Lookup im Knockout-Predictor
- Lambda-Cache pro geordnetem `(home, away)`-Matchup
- offizieller Bracket-Label-Fix ueber `load_groups()`
- Backtracking-Aufloesung der Drittplatzierten-Slots

Pflichtcheck nach v2_full_35 Full-Tournament-Simulation:

    docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' <<'SQL'
    SELECT
        simulation_run_id,
        model_name,
        feature_set_name,
        is_technical_dry_run,
        COUNT(*) AS rows,
        MIN(n_simulations) AS n_simulations,
        MIN(seed_start) AS seed_start,
        MAX(seed_end) AS seed_end,
        ROUND(SUM(p_advance_group)::numeric, 10) AS sum_group,
        ROUND(SUM(p_reach_round_of_16)::numeric, 10) AS sum_r16,
        ROUND(SUM(p_reach_quarter_final)::numeric, 10) AS sum_qf,
        ROUND(SUM(p_reach_semi_final)::numeric, 10) AS sum_sf,
        ROUND(SUM(p_final)::numeric, 10) AS sum_final,
        ROUND(SUM(p_title)::numeric, 10) AS sum_title,
        ROUND(SUM(p_third_place)::numeric, 10) AS sum_third
    FROM features.tournament_simulation_summary_v2_full_35
    WHERE simulation_run_id = 'xgboost_v2_full_35_seed_42_to_10041_n_10000'
    GROUP BY simulation_run_id, model_name, feature_set_name, is_technical_dry_run;
    SQL

Erwartung fuer den finalen 10k-Run:

- rows = 48
- model_name = `xgboost_v2_full_35`
- feature_set_name = `v2_full_35`
- is_technical_dry_run = false
- n_simulations = 10000
- seed_start = 42
- seed_end = 10041
- Summen exakt: 32 / 16 / 8 / 4 / 2 / 1 / 1

Frontend:

`app/Home.py` enthaelt jetzt einen dritten Modellkandidaten:

- Label: `v2 Full 35 (XGBoost)`
- Match Predictions: `features.match_predictions_v2_full_35`
- Gruppenphase: `features.group_stage_simulation_summary_v2_full_35`
- Full Tournament: `features.tournament_simulation_summary_v2_full_35`
- `is_dry_run = False`

Die Dry-Run-Warnung bleibt nur fuer `v2 Technical 33 (Dry Run, XGBoost)` aktiv.

## Phase J.4 Ergänzung: Praesentations-Frontend + Scenario Mode

Nach erfolgreichem Aufbau der v2_full_35-Pipeline und der Simulationstabellen
wurde das Streamlit-Frontend praesentationsfaehig ueberarbeitet.

Betroffene Dateien:

- `app/Home.py`
- `src/wm_prediction/modeling/scenario_tournament_v2_full_35.py`
- `pyproject.toml`
- `.gitignore`

Neue Frontend-Struktur:

- Overview
- Match Explorer
- Groups
- Scenario Mode
- Team Path
- Full Results
- Method / Data

Die Modell-/Tabellenzuordnung bleibt weiterhin whitelist-basiert im `MODELS`-
Dictionary in `app/Home.py`. Es werden keine Tabellennamen aus User-Input gebaut.

Weiterhin unterstuetzte Frontend-Modelle:

- `MVP v1 (Poisson)`
- `v2 Technical 33 (Dry Run, XGBoost)`
- `v2 Full 35 (XGBoost)`

Dry-Run-Regel:

- `v2 Technical 33 (Dry Run, XGBoost)` zeigt weiterhin eine Warnung.
- `v2 Full 35 (XGBoost)` zeigt keine Dry-Run-Warnung.

Scenario Mode:

- ist aktuell nur fuer `v2 Full 35 (XGBoost)` aktiv
- schreibt keine Datenbanktabellen
- nutzt manuelle Gruppenplatzierungen als Input
- nutzt die bestehende offizielle Bracket- und Drittplatzierten-Slot-Logik
- nutzt `KnockoutMatchupPredictorV2Full35` fuer K.o.-Matchups
- simuliert nur den K.o.-Pfad ab manueller Gruppenphase

Wichtige methodische Grenze:

Scenario Mode aktualisiert keine zeitabhaengigen Modellfeatures aus den
hypothetischen Gruppenspielen. Er veraendert nur den Turnierpfad. Teamstaerken
bleiben auf Basis des v2_full_35-Snapshots. Dadurch bleibt der Modus ein
interaktives Path-Szenario und kein ungeprueftes neues Modell.

Neue Python-Datei:

- `src/wm_prediction/modeling/scenario_tournament_v2_full_35.py`

Technischer Smoke fuer Scenario Mode:

    PYTHONDONTWRITEBYTECODE=1 python -m wm_prediction.modeling.scenario_tournament_v2_full_35

Erwartung:

- qualified = 32
- knockout_matches = 32
- p_advance_group = 32
- p_reach_round_of_16 = 16
- p_reach_quarter_final = 8
- p_reach_semi_final = 4
- p_final = 2
- p_title = 1
- p_third_place = 1

Frontend-Smoke:

    streamlit run app/Home.py

Manuell pruefen:

- sechs bzw. sieben Tabs sichtbar inklusive Scenario Mode
- Modellwechsel funktioniert fuer alle drei Modelle
- v2 Technical 33 zeigt Dry-Run-Warnung
- v2 Full 35 zeigt keine Dry-Run-Warnung
- Match Explorer zeigt alle Gruppengegner auch bei Away-Fixtures
- Groups zeigt nur eine ausgewaehlte Gruppe
- Team Path zeigt plausible absteigende Pfadwahrscheinlichkeiten
- Full Results ist nach Titelchance sortiert
- Scenario Mode laeuft fuer v2 Full 35 mit Default-Rankings und 300 Simulationen
- Scenario Mode bleibt fuer andere Modelle deaktiviert bzw. erklaerend gesperrt

Dependency-Hinweis:

`pyproject.toml` enthaelt jetzt `xgboost>=2.1,<4`, weil v2_full_35 und der
Scenario Mode den XGBoost-basierten Kandidaten verwenden.

Git-/Daten-Hinweis:

- lokale Raw-/Exportdaten werden nicht committed
- `player_valuations.csv` im Projektroot ist explizit in `.gitignore` aufgenommen
- generierte `src/wm_prediction.egg-info`-Aenderungen werden nicht committed
