from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from wm_prediction.config import PROJECT_ROOT
from wm_prediction.db.connection import get_engine
from wm_prediction.db.import_raw import (
    RAW_DATA_DIR,
    RAW_SCHEMA,
    build_plan_for_csv,
    discover_csv_files,
    quote_identifier,
)


DATE_COLUMN_PATTERN = re.compile(r"(^date$|_date$|date_of_|expiration_date|transfer_date)", re.IGNORECASE)


@dataclass(frozen=True)
class TableAudit:
    table_name: str
    csv_path: Path
    csv_rows: int
    db_rows: int
    row_count_matches: bool
    empty_columns: list[str]
    primary_key_candidates: list[str]
    broken_date_columns: dict[str, int]


def fetch_scalar(sql: str, params: dict | None = None):
    engine = get_engine()

    with engine.connect() as connection:
        return connection.execute(text(sql), params or {}).scalar()


def fetch_all(sql: str, params: dict | None = None):
    engine = get_engine()

    with engine.connect() as connection:
        return connection.execute(text(sql), params or {}).fetchall()


def list_raw_tables() -> list[str]:
    rows = fetch_all(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = :schema
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """,
        {"schema": RAW_SCHEMA},
    )
    return [row[0] for row in rows]


def table_columns(table_name: str) -> list[str]:
    rows = fetch_all(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :schema
          AND table_name = :table_name
        ORDER BY ordinal_position
        """,
        {"schema": RAW_SCHEMA, "table_name": table_name},
    )
    return [row[0] for row in rows]


def count_rows(table_name: str) -> int:
    schema_sql = quote_identifier(RAW_SCHEMA)
    table_sql = quote_identifier(table_name)

    return int(fetch_scalar(f"SELECT COUNT(*) FROM {schema_sql}.{table_sql}"))


def find_empty_columns(table_name: str, columns: list[str]) -> list[str]:
    schema_sql = quote_identifier(RAW_SCHEMA)
    table_sql = quote_identifier(table_name)

    empty_columns: list[str] = []

    for column in columns:
        column_sql = quote_identifier(column)
        non_empty_count = fetch_scalar(
            f"""
            SELECT COUNT(*)
            FROM {schema_sql}.{table_sql}
            WHERE {column_sql} IS NOT NULL
              AND btrim({column_sql}) <> ''
            """
        )

        if int(non_empty_count) == 0:
            empty_columns.append(column)

    return empty_columns


def find_primary_key_candidates(table_name: str, columns: list[str], db_rows: int) -> list[str]:
    if db_rows == 0:
        return []

    schema_sql = quote_identifier(RAW_SCHEMA)
    table_sql = quote_identifier(table_name)

    candidates: list[str] = []

    for column in columns:
        column_sql = quote_identifier(column)

        stats = fetch_all(
            f"""
            SELECT
                COUNT(*) AS total_rows,
                COUNT({column_sql}) AS non_null_rows,
                COUNT(DISTINCT {column_sql}) AS distinct_values
            FROM {schema_sql}.{table_sql}
            """
        )[0]

        total_rows, non_null_rows, distinct_values = map(int, stats)

        if total_rows == non_null_rows == distinct_values:
            candidates.append(column)

    return candidates


def find_broken_date_columns(table_name: str, columns: list[str]) -> dict[str, int]:
    schema_sql = quote_identifier(RAW_SCHEMA)
    table_sql = quote_identifier(table_name)

    broken: dict[str, int] = {}

    for column in columns:
        if not DATE_COLUMN_PATTERN.search(column):
            continue

        column_sql = quote_identifier(column)

        # Accept:
        # - year only: YYYY
        # - date: YYYY-MM-DD
        # - timestamp-like: YYYY-MM-DDTHH:MM, YYYY-MM-DD HH:MM, optionally with seconds
        broken_count = fetch_scalar(
            f"""
            SELECT COUNT(*)
            FROM {schema_sql}.{table_sql}
            WHERE {column_sql} IS NOT NULL
              AND btrim({column_sql}) <> ''
              AND {column_sql} !~ '^\\d{{4}}(-\\d{{2}}-\\d{{2}}([ T]\\d{{2}}:\\d{{2}}(:\\d{{2}})?)?)?$'
            """
        )

        if int(broken_count) > 0:
            broken[column] = int(broken_count)

    return broken


def audit_table(table_name: str, csv_path: Path, csv_rows: int) -> TableAudit:
    columns = table_columns(table_name)
    db_rows = count_rows(table_name)

    return TableAudit(
        table_name=table_name,
        csv_path=csv_path,
        csv_rows=csv_rows,
        db_rows=db_rows,
        row_count_matches=csv_rows == db_rows,
        empty_columns=find_empty_columns(table_name, columns),
        primary_key_candidates=find_primary_key_candidates(table_name, columns, db_rows),
        broken_date_columns=find_broken_date_columns(table_name, columns),
    )


def print_audit(audits: list[TableAudit]) -> None:
    print(f"Schema audited: {RAW_SCHEMA}")
    print(f"Tables audited: {len(audits)}")

    print("\nTables:")
    for audit in audits:
        status = "OK" if audit.row_count_matches else "MISMATCH"
        print(
            f"- {RAW_SCHEMA}.{audit.table_name}: "
            f"csv_rows={audit.csv_rows}, db_rows={audit.db_rows}, row_count={status}"
        )

    print("\nPrimary-key candidates:")
    for audit in audits:
        candidates = ", ".join(audit.primary_key_candidates) if audit.primary_key_candidates else "-"
        print(f"- {RAW_SCHEMA}.{audit.table_name}: {candidates}")

    print("\nCompletely empty columns:")
    any_empty = False
    for audit in audits:
        if audit.empty_columns:
            any_empty = True
            print(f"- {RAW_SCHEMA}.{audit.table_name}: {', '.join(audit.empty_columns)}")
    if not any_empty:
        print("- none")

    print("\nBroken date-like fields:")
    any_broken_dates = False
    for audit in audits:
        if audit.broken_date_columns:
            any_broken_dates = True
            details = ", ".join(
                f"{column}={count}" for column, count in audit.broken_date_columns.items()
            )
            print(f"- {RAW_SCHEMA}.{audit.table_name}: {details}")
    if not any_broken_dates:
        print("- none")

    row_count_mismatches = [audit for audit in audits if not audit.row_count_matches]
    if row_count_mismatches:
        raise SystemExit("\nAudit failed: at least one table has a row-count mismatch.")

    print("\nAudit completed. No row-count mismatches found.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit raw PostgreSQL tables against local CSV files.")
    parser.parse_args()

    plans = [build_plan_for_csv(path) for path in discover_csv_files()]
    tables = set(list_raw_tables())

    missing_tables = [
        f"{RAW_SCHEMA}.{plan.table_name}" for plan in plans if plan.table_name not in tables
    ]

    if missing_tables:
        raise SystemExit("Missing raw tables:\n" + "\n".join(f"- {table}" for table in missing_tables))

    audits = [
        audit_table(table_name=plan.table_name, csv_path=plan.csv_path, csv_rows=plan.row_count)
        for plan in plans
    ]

    print_audit(audits)


if __name__ == "__main__":
    main()
