#!/usr/bin/env python3
"""Landing -> Bronze (ADR-005 S3-canonical migration).

No cleaning here (PIPELINE_SPEC.md Bronze Spec) — raw columns as-is plus load
metadata (load_ts, source_file). Cleaning/typing happens in dbt staging (Enrich).

ADR-005 Condition C: ephemeral DuckDB catalog (in-memory, no warehouse.duckdb). Reads
Landing from S3 via httpfs, writes Bronze back to S3 as parquet
(s3://<bucket>/bronze/<src>/<date>/<table>.parquet) — a per-<date> deterministic overwrite
(Condition A), never a relational table. load_ts/source_file ride through as columns
(Decision 6 load-meta contract).

Env-var contract (see scripts/s3_env.py) — MinIO now, real AWS later, same code:
  S3_BUCKET, S3_ENDPOINT, S3_USE_SSL, S3_URL_STYLE, AWS_ACCESS_KEY_ID/SECRET/REGION.
"""
import datetime as dt
import os

import duckdb

import s3_env

LAND_DATE = os.environ.get("LAND_DATE", f"{dt.date.today():%Y-%m-%d}")

BRONZE_TABLES = ("sales_daily", "sales_hourly", "ndc_directory", "drug_reviews")


def landing_uri(source: str, filename: str) -> str:
    return s3_env.s3_uri("landing", source, LAND_DATE, filename)


def bronze_uri(source: str, table: str) -> str:
    return s3_env.s3_uri("bronze", source, LAND_DATE, f"{table}.parquet")


def main() -> None:
    con = duckdb.connect(":memory:")  # Condition C: ephemeral catalog, no warehouse.duckdb
    s3_env.configure_httpfs(con)

    # alpha
    con.execute(f"""
        COPY (
            SELECT *, current_timestamp AS load_ts, 'salesdaily.csv' AS source_file
            FROM read_csv_auto('{landing_uri("alpha", "salesdaily.csv")}')
        ) TO '{bronze_uri("alpha", "sales_daily")}' (FORMAT PARQUET)
    """)
    con.execute(f"""
        COPY (
            SELECT *, current_timestamp AS load_ts, 'saleshourly.csv' AS source_file
            FROM read_csv_auto('{landing_uri("alpha", "saleshourly.csv")}')
        ) TO '{bronze_uri("alpha", "sales_hourly")}' (FORMAT PARQUET)
    """)

    # beta
    con.execute(f"""
        COPY (
            SELECT *, current_timestamp AS load_ts, 'ndc_directory.json' AS source_file
            FROM read_json_auto('{landing_uri("beta", "ndc_directory.json")}')
        ) TO '{bronze_uri("beta", "ndc_directory")}' (FORMAT PARQUET)
    """)

    # gamma
    train_uri = landing_uri("gamma", "drugsComTrain_raw.csv")
    test_uri = landing_uri("gamma", "drugsComTest_raw.csv")
    con.execute(f"""
        COPY (
            SELECT *, current_timestamp AS load_ts, 'drugsComTrain_raw.csv' AS source_file
            FROM read_csv_auto('{train_uri}', quote='"', escape='"')
            UNION ALL
            SELECT *, current_timestamp AS load_ts, 'drugsComTest_raw.csv' AS source_file
            FROM read_csv_auto('{test_uri}', quote='"', escape='"')
        ) TO '{bronze_uri("gamma", "drug_reviews")}' (FORMAT PARQUET)
    """)

    # Validate via read_parquet (round-trip through S3, not just "COPY didn't error")
    sources = {
        "sales_daily": "alpha", "sales_hourly": "alpha",
        "ndc_directory": "beta", "drug_reviews": "gamma",
    }
    for tbl in BRONZE_TABLES:
        uri = bronze_uri(sources[tbl], tbl)
        n = con.execute(f"SELECT count(*) FROM read_parquet('{uri}')").fetchone()[0]
        print(f"[bronze] {tbl}: {n} rows -> {uri}")

    con.close()


if __name__ == "__main__":
    main()
