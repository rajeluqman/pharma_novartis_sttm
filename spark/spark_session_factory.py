"""The ONE allowed way to construct a SparkSession in this repo's spark/ DEMONSTRATION
track (ADR-007 B3). Every script under spark/ MUST call spark_session_factory() instead
of SparkSession.builder directly — CI (ADR-007 B6) greps for `SparkSession.builder`
anywhere under spark/ outside this file and fails the build if found.

Fail-closed: spark_session_factory() calls scripts/spark_gym_guard.assert_spark_gym_safe()
FIRST. If the environment is not hard-pointed at either the gym Spark staging bucket
(local MinIO, fake creds — drills) or, with SPARK_DEMO_MODE=1, the real ADR-007 B4 bucket
+ real governed star (the one owner-gated demonstration run), it raises before any
SparkSession/JVM is touched — nothing runs.

S3A config branches on whether SPARK_S3_ENDPOINT is set, NOT on SPARK_DEMO_MODE directly —
the guard has already confirmed the two only ever co-occur one way: drills always set a
local endpoint, demo mode always leaves it empty (real AWS default endpoint, region-pinned
via fs.s3a.endpoint.region). MinIO needs path-style + plain HTTP; real AWS needs
vhost-style + TLS — using the wrong pairing is the #1 cause of S3A auth/connection failures.

local[*] ONLY (ADR-007 fence principle #2). This module never submits to Glue/EMR/any
managed cluster; `master("local[*]")` is hardcoded, not configurable, on purpose.
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from spark_gym_guard import assert_spark_gym_safe  # noqa: E402

from pyspark.sql import SparkSession  # noqa: E402

# Pinned jar coordinates (ADR-007 B2) — MUST match requirements/requirements-spark.txt
# exactly; CI (ADR-007 B6) asserts these two files agree.
HADOOP_AWS_PACKAGES = "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262"
DELTA_PACKAGE = "io.delta:delta-spark_2.12:3.2.1"


def spark_session_factory(app_name: str = "pharma-sttm-spark-demo") -> SparkSession:
    """Construct the gym/demonstration-track SparkSession. Aborts before touching the
    JVM at all unless spark_gym_guard.assert_spark_gym_safe() passes (raises
    SparkGymGuardError otherwise — caller does not need to catch it, just let it abort).
    """
    assert_spark_gym_safe()

    endpoint = os.environ.get("SPARK_S3_ENDPOINT", "").strip()
    access_key = os.environ["SPARK_AWS_ACCESS_KEY_ID"]
    secret_key = os.environ.get("SPARK_AWS_SECRET_ACCESS_KEY", "")
    region = os.environ.get("SPARK_AWS_REGION", "ap-southeast-1")

    builder = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")  # ADR-007 fence principle #2 — never configurable, never submitted elsewhere
        .config("spark.jars.packages", f"{HADOOP_AWS_PACKAGES},{DELTA_PACKAGE}")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.hadoop.fs.s3a.access.key", access_key)
        .config("spark.hadoop.fs.s3a.secret.key", secret_key)
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    )

    if endpoint:
        # Drill (MinIO): explicit endpoint, path-style, plain HTTP.
        builder = (
            builder
            .config("spark.hadoop.fs.s3a.endpoint", endpoint)
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        )
    else:
        # Demo (real AWS): no endpoint override — region-pinned default endpoint, vhost-style, TLS.
        builder = (
            builder
            .config("spark.hadoop.fs.s3a.endpoint.region", region)
            .config("spark.hadoop.fs.s3a.path.style.access", "false")
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "true")
        )

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def read_uri(*parts: str) -> str:
    """s3a://<SPARK_READ_S3_BUCKET>/<parts...> — the READ-ONLY star-input source
    (ADR-007 fence principle #4). Guard already confirmed this bucket is never prod."""
    bucket = os.environ["SPARK_READ_S3_BUCKET"]
    return f"s3a://{bucket}/" + "/".join(p.strip("/") for p in parts)


def staging_uri(*parts: str) -> str:
    """s3a://<SPARK_S3_BUCKET>/<parts...> — the ONLY bucket the Spark track may WRITE to."""
    bucket = os.environ["SPARK_S3_BUCKET"]
    return f"s3a://{bucket}/" + "/".join(p.strip("/") for p in parts)
