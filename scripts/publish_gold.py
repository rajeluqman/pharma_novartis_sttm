#!/usr/bin/env python3
"""Gold publish step (ADR-005-build-decisions.md Decision 1 — mechanism B).

dbt's `marts.core`/`marts.serving` models materialize `external` to
s3://<bucket>/gold/<run_id>/<model>/<model>.parquet (gold_run_location() macro). That write is
the FULL run output, already complete by the time `dbt run` exits successfully — there is no
partial-write risk dbt leaves behind for this script to worry about beyond "did dbt run succeed".

This script is the publish step: it (1) verifies every expected Gold object exists and is
non-empty at gold/<run_id>/, then (2) copies each object into the fixed gold/_current/ prefix —
copy, not move/rename (S3 has no atomic rename, ADR-005 Condition A) — so `_current/` always
holds either the previous good run (untouched until every new object is verified) or the fully-
published new run, never a half-written one. Snowflake (later) reads ONLY gold/_current/, never
gold/<run_id>/ directly (Decision 1) — the per-run history is retained for lineage/rollback.

Rollback = re-run this script with an older --run-id (re-copies that prior run's objects back
into _current/) — a pure data operation, no DDL, no Snowflake privilege needed.
"""
import argparse
import sys

import duckdb

import s3_env

GOLD_MODELS = (
    "dim_date", "dim_condition", "dim_drug",
    "fact_sales", "fact_review",
    "obt_sales_wide", "obt_review_wide",
)


def run_uri(run_id: str, model: str) -> str:
    return s3_env.s3_uri("gold", run_id, model, f"{model}.parquet")


def current_uri(model: str) -> str:
    return s3_env.s3_uri("gold", "_current", model, f"{model}.parquet")


def verify_run(con, run_id: str) -> dict:
    """Step 1: verify every expected Gold object exists at gold/<run_id>/ and is non-empty.
    Returns {model: row_count}. Raises if anything is missing/empty (publish must not proceed)."""
    counts = {}
    for model in GOLD_MODELS:
        uri = run_uri(run_id, model)
        try:
            n = con.execute(f"SELECT count(*) FROM read_parquet('{uri}')").fetchone()[0]
        except Exception as exc:
            raise RuntimeError(f"Gold verify FAILED — {model} missing at {uri}: {exc}") from exc
        if n == 0:
            raise RuntimeError(f"Gold verify FAILED — {model} at {uri} is empty (0 rows)")
        counts[model] = n
        print(f"[publish:verify] {model}: {n} rows at {uri}")
    return counts


def publish_to_current(con, run_id: str) -> None:
    """Step 2: copy each verified gold/<run_id>/<model>/ object into gold/_current/<model>/.
    Copy (read_parquet -> COPY TO), not a rename — S3 has no atomic rename (Condition A).
    Each model's _current/ object is only overwritten after the corresponding run object passed
    verify_run() above, so a failed publish never leaves _current/ partially updated for that
    model; on a partial failure mid-loop, untouched models keep their last-good _current/ state."""
    for model in GOLD_MODELS:
        src = run_uri(run_id, model)
        dst = current_uri(model)
        con.execute(f"""
            COPY (SELECT * FROM read_parquet('{src}')) TO '{dst}' (FORMAT PARQUET)
        """)
        print(f"[publish:copy] {model}: {src} -> {dst}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True, help="run_id matching the dbt --vars run_id used for this build")
    args = ap.parse_args()

    con = duckdb.connect(":memory:")
    s3_env.configure_httpfs(con)

    print(f"[publish] verifying gold/{args.run_id}/ is complete before touching gold/_current/ ...")
    counts = verify_run(con, args.run_id)

    print(f"[publish] all {len(counts)} Gold objects verified — publishing to gold/_current/ ...")
    publish_to_current(con, args.run_id)

    print(f"[publish] DONE — gold/_current/ now serves run_id={args.run_id}")
    print(f"[publish] lineage retained at gold/{args.run_id}/ (not deleted)")
    con.close()


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"[publish] ABORTED: {e}")
        sys.exit(1)
