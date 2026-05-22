from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from wm_prediction.config import PROJECT_ROOT
from wm_prediction.db.connection import get_engine


RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
RAW_SCHEMA = "raw"
INCLUDED_RAW_SOURCES = {"kaggle_player_scores", "soccerdata"}


@dataclass(frozen=True)
class CsvTablePlan:
    csv_path: Path
    table_name: str
    delimiter: str
    original_columns: list[str]
    columns: list[str]
    row_count: int


def snake_case(value: str) -> str:
    value = value.strip().replace("\ufeff", "")
    value = re.sub(r"[^0-9a-zA-Z]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_").lower()

    if not value:
        value = "unnamed_column"

    if value[0].isdigit():
        value = f"col_{value}"

    return value


def deduplicate_names(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []

    for name in names:
        base = name
        count = seen.get(base, 0)

        if count == 0:
            result.append(base)
        else:
            result.append(f"{base}_{count + 1}")

        seen[base] = count + 1

    return result


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def table_name_for_csv(path: Path) -> str:
    relative = path.relative_to(RAW_DATA_DIR)
    parts = list(relative.parts)

    # Include folder names to avoid collisions like games.csv from different sources.
    stem_parts = parts[:-1] + [path.stem]
    return snake_case("_".join(stem_parts))


def detect_delimiter(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        sample = file.read(65536)

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def build_plan_for_csv(path: Path) -> CsvTablePlan:
    delimiter = detect_delimiter(path)

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, delimiter=delimiter)
        original_columns = next(reader)
        row_count = sum(1 for _ in reader)

    columns = deduplicate_names([snake_case(column) for column in original_columns])

    return CsvTablePlan(
        csv_path=path,
        table_name=table_name_for_csv(path),
        delimiter=delimiter,
        original_columns=original_columns,
        columns=columns,
        row_count=row_count,
    )


def discover_csv_files() -> list[Path]:
    return sorted(
        path
        for path in RAW_DATA_DIR.rglob("*")
        if path.suffix.lower() == ".csv"
        and path.relative_to(RAW_DATA_DIR).parts[0] in INCLUDED_RAW_SOURCES
    )


def print_dry_run(plans: list[CsvTablePlan]) -> None:
    print(f"Raw data directory: {RAW_DATA_DIR}")
    print(f"Target schema:      {RAW_SCHEMA}")
    print(f"CSV files found:    {len(plans)}")

    for plan in plans:
        print("\n" + "=" * 100)
        print(f"CSV:        {plan.csv_path.relative_to(PROJECT_ROOT)}")
        print(f"Table:      {RAW_SCHEMA}.{plan.table_name}")
        print(f"Delimiter:  {repr(plan.delimiter)}")
        print(f"Rows:       {plan.row_count}")
        print(f"Columns:    {len(plan.columns)}")
        print("Column mapping:")

        for original, normalized in zip(plan.original_columns, plan.columns, strict=True):
            marker = "" if original == normalized else "  <- renamed"
            print(f"  {original!r} -> {normalized!r}{marker}")


def create_schema() -> None:
    engine = get_engine()

    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(RAW_SCHEMA)}"))


def create_table(plan: CsvTablePlan, replace: bool) -> None:
    engine = get_engine()

    schema_sql = quote_identifier(RAW_SCHEMA)
    table_sql = quote_identifier(plan.table_name)
    columns_sql = ",\n    ".join(f"{quote_identifier(column)} TEXT" for column in plan.columns)

    with engine.begin() as connection:
        if replace:
            connection.execute(text(f"DROP TABLE IF EXISTS {schema_sql}.{table_sql}"))

        connection.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {schema_sql}.{table_sql} (
                    {columns_sql}
                )
                """
            )
        )


def copy_csv_to_table(plan: CsvTablePlan) -> int:
    engine = get_engine()

    schema_sql = quote_identifier(RAW_SCHEMA)
    table_sql = quote_identifier(plan.table_name)
    columns_sql = ", ".join(quote_identifier(column) for column in plan.columns)

    # NULL '' turns empty CSV fields into SQL NULL.
    # Everything else stays raw TEXT.
    copy_sql = (
        f"COPY {schema_sql}.{table_sql} ({columns_sql}) "
        f"FROM STDIN WITH (FORMAT CSV, HEADER TRUE, DELIMITER ',', NULL '')"
    )

    raw_connection = engine.raw_connection()

    try:
        with raw_connection.cursor() as cursor:
            with cursor.copy(copy_sql) as copy:
                with plan.csv_path.open("rb") as file:
                    while chunk := file.read(1024 * 1024):
                        copy.write(chunk)

            cursor.execute(f"SELECT COUNT(*) FROM {schema_sql}.{table_sql}")
            imported_rows = cursor.fetchone()[0]

        raw_connection.commit()
        return imported_rows

    except Exception:
        raw_connection.rollback()
        raise

    finally:
        raw_connection.close()


def import_csv(plan: CsvTablePlan, replace: bool) -> int:
    create_table(plan, replace=replace)
    return copy_csv_to_table(plan)


def import_all(plans: list[CsvTablePlan], replace: bool) -> None:
    create_schema()

    print(f"Importing {len(plans)} CSV files into schema {RAW_SCHEMA!r}")
    print(f"Replace existing tables: {replace}")

    for index, plan in enumerate(plans, start=1):
        print("\n" + "=" * 100)
        print(f"[{index}/{len(plans)}] {plan.csv_path.relative_to(PROJECT_ROOT)}")
        print(f"Target: {RAW_SCHEMA}.{plan.table_name}")
        print(f"Expected CSV rows: {plan.row_count}")

        imported_rows = import_csv(plan, replace=replace)

        print(f"Imported DB rows:  {imported_rows}")

        if imported_rows != plan.row_count:
            raise RuntimeError(
                f"Row count mismatch for {RAW_SCHEMA}.{plan.table_name}: "
                f"CSV={plan.row_count}, DB={imported_rows}"
            )

    print("\nDone. All CSV row counts match imported DB row counts.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import raw CSV files into PostgreSQL.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the CSV-to-table import plan. Does not write to the database.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Drop and recreate each target raw table before importing.",
    )
    args = parser.parse_args()

    plans = [build_plan_for_csv(path) for path in discover_csv_files()]

    if args.dry_run:
        print_dry_run(plans)
        return

    import_all(plans, replace=args.replace)


if __name__ == "__main__":
    main()
