#!/usr/bin/env python3
"""ADR-007 B5/B8 — Spark + Delta DEMONSTRATION job.

Reads the ADR-001 star (read-only, gold/_current/ in SPARK_READ_S3_BUCKET — never prod,
never written to) via Spark's s3a client, writes each model as a Delta table into the
SEPARATE Spark staging bucket (SPARK_S3_BUCKET), and runs OPTIMIZE ZORDER on the two
largest tables. This is the only thing under spark/ that builds a SparkSession; every
other script in this job reads what THIS script wrote (S3-staging-backed handoff between
tasks, not shared in-process state — the O-AIR-07 trap this track must not repeat).

Invoked as a single subprocess from the new spark_delta_demo_dag (ADR-007 B5), the same
"DAG task shells out to a script" shape as the existing pharma_sttm_pipeline_v1 DAG.

NOT a system of record: this slice is a demonstration artifact in the staging bucket only
(ADR-007 B8(a)) — never read by Snowflake/serving, never published to gold/_current/.
"""
import sys

sys.path.insert(0, "spark")
from spark_session_factory import read_uri, spark_session_factory, staging_uri  # noqa: E402

# The ADR-001 star (fence principle #4) — dims + facts only, NOT the OBT/serving models
# (those are derived, not the star Spark is meant to demonstrate against).
STAR_MODELS = ("dim_date", "dim_condition", "dim_drug", "fact_sales", "fact_review")

# ZORDER target column per model that benefits from it here (skip dim_date/dim_condition —
# too small/low-cardinality for ZORDER to mean anything; this is a demonstration, not theatre).
ZORDER_COLUMNS = {
    "dim_drug": "drug_sk",
    "fact_sales": "drug_sk",
}


def main() -> int:
    spark = spark_session_factory("spark-delta-demo-build-slice")
    try:
        for model in STAR_MODELS:
            src = read_uri("gold", "_current", model, f"{model}.parquet")
            dst = staging_uri("delta", model)

            df = spark.read.parquet(src)
            n = df.count()
            df.write.format("delta").mode("overwrite").save(dst)
            print(f"[build_delta_slice] {model}: {n} rows  {src} -> {dst}")

            zorder_col = ZORDER_COLUMNS.get(model)
            if zorder_col:
                spark.sql(f"OPTIMIZE delta.`{dst}` ZORDER BY ({zorder_col})")
                print(f"[build_delta_slice] {model}: OPTIMIZE ZORDER BY ({zorder_col}) done")

        print(f"[build_delta_slice] DONE — {len(STAR_MODELS)} Delta tables written to "
              f"{staging_uri('delta')}")
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
