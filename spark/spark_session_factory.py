"""The ONE allowed way to construct a SparkSession in this repo's spark/ DEMONSTRATION
track (ADR-007 B3). Every script under spark/ MUST call spark_session_factory() instead
of SparkSession.builder directly — CI (ADR-007 B6) greps for `SparkSession.builder`
anywhere under spark/ outside this file and fails the build if found.

Fail-closed: spark_session_factory() calls scripts/spark_gym_guard.assert_spark_gym_safe()
FIRST. If the environment is not hard-pointed at the gym Spark staging bucket (local
MinIO, fake creds), it raises before any SparkSession/JVM is touched — nothing runs.

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

    endpoint = os.environ["SPARK_S3_ENDPOINT"]
    access_key = os.environ["SPARK_AWS_ACCESS_KEY_ID"]
    secret_key = os.environ.get("SPARK_AWS_SECRET_ACCESS_KEY", "")

    spark = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")  # ADR-007 fence principle #2 — never configurable, never submitted elsewhere
        .config("spark.jars.packages", f"{HADOOP_AWS_PACKAGES},{DELTA_PACKAGE}")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.hadoop.fs.s3a.endpoint", endpoint)
        .config("spark.hadoop.fs.s3a.access.key", access_key)
        .config("spark.hadoop.fs.s3a.secret.key", secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )
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
