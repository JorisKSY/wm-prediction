# DB Dump Restore

Diese Anleitung ist fuer den schnellen Projektstart mit einem vorberechneten
Postgres-Dump gedacht. Sie ersetzt den kompletten Rebuild aus Raw-Daten, wenn
nur der aktuelle Forecast-/Frontend-Stand genutzt werden soll.

## Dump-Inhalt

Der empfohlene Slim-Dump enthaelt nur:

- Schema `features`
- Schema `experiments`

Nicht enthalten:

- Schema `raw`
- Schema `staging`
- grosse Player-/Lineup-/Event-Tabellen
- lokale Raw-Daten
- lokale `.env`-Dateien

Damit reicht der Dump fuer:

- Streamlit-Frontend
- Match Predictions
- Group-Stage-Summaries
- Full-Tournament-Summaries
- v2_full_35 Scenario Mode
- Modellvergleich im Dashboard

## Erwarteter Dump-Name

Beispiel:

    db_dumps/wm_prediction_features_experiments_2026_06_09.dump

Der Ordner `db_dumps/` ist bewusst in `.gitignore` und wird nicht committed.
Die Datei muss separat geteilt werden, z.B. per Cloud/USB.

## Restore in lokale Docker-Postgres-DB

Voraussetzung:

    docker compose up -d postgres

Dann aus dem Projektroot:

    docker compose exec -T postgres sh -lc 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" --if-exists'
    docker compose exec -T postgres sh -lc 'createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'

    docker compose exec -T postgres sh -lc 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' \
      < db_dumps/wm_prediction_features_experiments_2026_06_09.dump

## Plausibilitaetscheck nach Restore

    docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' <<'SQL'
    SELECT schemaname, COUNT(*) AS table_count
    FROM pg_tables
    WHERE schemaname IN ('features', 'experiments')
    GROUP BY schemaname
    ORDER BY schemaname;

    SELECT
        simulation_run_id,
        COUNT(*) AS rows,
        MIN(n_simulations) AS n_simulations,
        ROUND(SUM(p_advance_group)::numeric, 10) AS sum_group,
        ROUND(SUM(p_reach_round_of_16)::numeric, 10) AS sum_r16,
        ROUND(SUM(p_reach_quarter_final)::numeric, 10) AS sum_qf,
        ROUND(SUM(p_reach_semi_final)::numeric, 10) AS sum_sf,
        ROUND(SUM(p_final)::numeric, 10) AS sum_final,
        ROUND(SUM(p_title)::numeric, 10) AS sum_title,
        ROUND(SUM(p_third_place)::numeric, 10) AS sum_third
    FROM features.tournament_simulation_summary_v2_full_35
    WHERE simulation_run_id = 'xgboost_v2_full_35_seed_42_to_10041_n_10000'
    GROUP BY simulation_run_id;
    SQL

Erwartung fuer den finalen v2_full_35-Run:

- rows = 48
- n_simulations = 10000
- Summen = 32 / 16 / 8 / 4 / 2 / 1 / 1

## Frontend starten

    streamlit run app/Home.py

## Hinweis

Dieser Dump ist ein Snapshot des aktuellen berechneten DB-Stands. Er ist fuer
Demo, Frontend und Reproduzierbarkeit des aktuellen Forecasts gedacht. Fuer
vollstaendige Entwicklung aus Rohdaten weiterhin `docs/rebuild_order.md` nutzen.
