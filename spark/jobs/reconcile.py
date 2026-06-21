#!/usr/bin/env python3
"""ADR-007 B8 — two-engine reconciliation: Spark+Delta slice vs the DuckDB mart.

Both derive from the SAME ADR-001 star, but DuckDB+S3 remains the SOLE system of record
(B8(a) — this script never writes to gold/_current/, it only reads). This proves the two
engines saw the SAME data: for every star model, the Delta slice's row count and key set
(its surrogate-key column) must exactly match gold/_current/ read through DuckDB. A
divergence is a defect to investigate, not an accepted fork (B8(b)).

Run AFTER spark/jobs/build_delta_slice.py has written that run's Delta tables (separate
DAG task / separate subprocess — state flows through S3, not shared memory).
Exit 0 = every model reconciled. Non-zero = at least one mismatch, printed in full.
"""
import sys

import duckdb

sys.path.insert(0, "scripts")
import s3_env  # noqa: E402

sys.path.insert(0, "spark")
from spark_session_factory import spark_session_factory, staging_uri  # noqa: E402

STAR_MODELS = ("dim_date", "dim_condition", "dim_drug", "fact_sales", "fact_review")

KEY_COLUMN = {
    "dim_date": "date_sk",
    "dim_condition": "condition_sk",
    "dim_drug": "drug_sk",
    "fact_sales": "sales_sk",
    "fact_review": "review_sk",
}


def duckdb_mart_keys(con, model: str) -> tuple[int, set]:
    uri = s3_env.s3_uri("gold", "_current", model, f"{model}.parquet")
    col = KEY_COLUMN[model]
    rows = con.execute(f"SELECT {col} FROM read_parquet('{uri}')").fetchall()
    keys = {r[0] for r in rows}
    return len(rows), keys


def spark_slice_keys(spark, model: str) -> tuple[int, set]:
    uri = staging_uri("delta", model)
    col = KEY_COLUMN[model]
    df = spark.read.format("delta").load(uri).select(col)
    rows = [r[0] for r in df.collect()]
    return len(rows), set(rows)


def main() -> int:
    con = duckdb.connect(":memory:")
    s3_env.configure_httpfs(con)

    spark = spark_session_factory("spark-delta-demo-reconcile")
    mismatches = []
    try:
        for model in STAR_MODELS:
            duck_n, duck_keys = duckdb_mart_keys(con, model)
            spark_n, spark_keys = spark_slice_keys(spark, model)

            count_ok = duck_n == spark_n
            keyset_ok = duck_keys == spark_keys
            status = "PASS" if (count_ok and keyset_ok) else "FAIL"
            print(f"[reconcile] {model}: DuckDB={duck_n} rows, Spark+Delta={spark_n} rows "
                  f"-> {status}")

            if not count_ok or not keyset_ok:
                only_duck = duck_keys - spark_keys
                only_spark = spark_keys - duck_keys
                mismatches.append(
                    f"{model}: count duckdb={duck_n} spark={spark_n}; "
                    f"keys only-in-duckdb={len(only_duck)} only-in-spark={len(only_spark)}"
                )

        if mismatches:
            print("\n[reconcile] MISMATCH — Spark+Delta slice diverged from the DuckDB mart "
                  "(system of record). This is a defect to investigate, not an accepted fork "
                  "(ADR-007 B8):")
            for m in mismatches:
                print(f"  - {m}")
            return 1

        print(f"\n[reconcile] DONE — all {len(STAR_MODELS)} star models reconciled "
              f"(row count + key set exact match).")
        return 0
    finally:
        spark.stop()
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
