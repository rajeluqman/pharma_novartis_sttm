#!/usr/bin/env python3
"""Fail-closed preflight for the Spark + Delta DEMONSTRATION track (ADR-007 B3).

CRITICAL: Spark reaches S3 through a DIFFERENT client (Hadoop's s3a, configured via
spark.hadoop.fs.s3a.* in SparkConf) than DuckDB's httpfs (scripts/gym_guard.py /
scripts/s3_env.py). The DuckDB guard NEVER inspects Spark's env — without this module,
a Spark drill could be "gym_guard-green" on the DuckDB side and still mutate the live
AWS lake, or the unrelated DuckDB 'gym-lake' bucket, via Spark. This guard is the SOLE
mechanism that makes the Spark track governable (closes the same fail-open hole class
ADR-006-A1 closed for DuckDB, for Spark's separate client).

Rule (abort unless ALL hold):
  - SPARK_S3_BUCKET == 'gym-lake-spark-staging'   (WRITE target. NEVER prod, NEVER the
    DuckDB incubator's 'gym-lake' bucket — the two tracks must stay on physically
    separate WRITE buckets so neither can be mistaken for clearing the other)
  - SPARK_READ_S3_BUCKET is in {'gym-lake', 'gym-lake-spark-staging'}   (READ-ONLY source
    for the ADR-001 star inputs Spark demonstrates against, per ADR-007 fence principle
    #4 — must never be the prod bucket, even for reads)
  - SPARK_S3_ENDPOINT's HOSTNAME (parsed, not a substring match) is exactly one of
    localhost/127.0.0.1/::1/minio    (a substring check would pass a spoofed host like
    'evil-localhost.attacker.com' — flagged in gate-0 independent review, fixed here)
  - SPARK_AWS_ACCESS_KEY_ID is NOT real-looking     (no real AKIA/ASIA access key id)
  - SPARK_AWS_SECRET_ACCESS_KEY is NOT real-looking  (not a 40+ char base64 AWS-secret
    shape — also flagged in gate-0 review: the access-key-id check alone let a real
    secret slip through paired with a fake-looking access key id)

Every spark_session_factory() call (spark/spark_session_factory.py) routes through
assert_spark_gym_safe() BEFORE constructing a SparkSession. No raw SparkSession.builder
is permitted anywhere else under spark/ — CI (ADR-007 B6) greps for violations.

Usage:  set -a; source gym.env; set +a;  python scripts/spark_gym_guard.py  &&  <drill cmd>
Exit 0 = safe to run a Spark drill. Non-zero = ABORTED, nothing ran.
"""
import os
import re
import sys
from urllib.parse import urlsplit

PROD_BUCKET = "novartis-pharma-sttm-lake"
DUCKDB_GYM_BUCKET = "gym-lake"  # the OTHER incubator's bucket — Spark must never share it
SPARK_GYM_BUCKET = "gym-lake-spark-staging"
LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "minio"}
_SECRET_SHAPE = re.compile(r"[A-Za-z0-9+/=]+")


class SparkGymGuardError(RuntimeError):
    """Raised when the environment is NOT safe for a Spark demonstration/drill run."""


def _looks_real_aws_key(key: str) -> bool:
    # Real AWS access key ids start with AKIA/ASIA and are 20 chars. Fake gym creds won't.
    k = key.strip().upper()
    return k.startswith(("AKIA", "ASIA")) and len(key.strip()) >= 20


def _looks_real_aws_secret(secret: str) -> bool:
    # Real AWS secret access keys are 40 base64-charset chars. Fake gym creds (e.g.
    # 'mangmang') are short and won't match — catches a real secret slipping through
    # paired with a fake-looking access key id (the access-key-only check missed this).
    s = secret.strip()
    return len(s) >= 40 and bool(_SECRET_SHAPE.fullmatch(s))


def _endpoint_hostname(endpoint: str) -> str:
    # Parse the actual hostname rather than substring-matching — a substring check
    # would pass a spoofed host like 'evil-localhost.attacker.com' or
    # '127.0.0.1.attacker.com'. Tolerates an optional scheme ('http://host:port') or
    # bare 'host:port' / 'host' (urlsplit needs a '//'-prefixed netloc to parse either).
    e = endpoint.strip()
    if "//" not in e:
        e = "//" + e
    return (urlsplit(e).hostname or "").lower()


def assert_spark_gym_safe() -> None:
    """Abort (raise SparkGymGuardError) unless the env is hard-pointed at the Spark staging bucket."""
    problems = []

    bucket = os.environ.get("SPARK_S3_BUCKET", "")
    if bucket == PROD_BUCKET:
        problems.append(
            f"SPARK_S3_BUCKET is the LIVE prod bucket '{PROD_BUCKET}' — Spark drills must use "
            f"'{SPARK_GYM_BUCKET}'"
        )
    elif bucket == DUCKDB_GYM_BUCKET:
        problems.append(
            f"SPARK_S3_BUCKET is the DuckDB incubator's bucket '{DUCKDB_GYM_BUCKET}' — Spark and "
            f"DuckDB drills must stay on physically separate buckets (ADR-007 B3); use "
            f"'{SPARK_GYM_BUCKET}'"
        )
    elif bucket != SPARK_GYM_BUCKET:
        problems.append(f"SPARK_S3_BUCKET='{bucket or '(empty)'}' — must be '{SPARK_GYM_BUCKET}'")

    read_bucket = os.environ.get("SPARK_READ_S3_BUCKET", "")
    if read_bucket == PROD_BUCKET:
        problems.append(
            f"SPARK_READ_S3_BUCKET is the LIVE prod bucket '{PROD_BUCKET}' — Spark must never read "
            f"from prod, even read-only (ADR-007 fence principle #3)"
        )
    elif read_bucket not in (DUCKDB_GYM_BUCKET, SPARK_GYM_BUCKET):
        problems.append(
            f"SPARK_READ_S3_BUCKET='{read_bucket or '(empty)'}' — must be one of "
            f"'{DUCKDB_GYM_BUCKET}' or '{SPARK_GYM_BUCKET}'"
        )

    endpoint = os.environ.get("SPARK_S3_ENDPOINT", "").strip()
    if not endpoint:
        problems.append(
            "SPARK_S3_ENDPOINT is empty — that resolves to real-AWS s3a defaults. Spark drills "
            "require a local MinIO endpoint (e.g. localhost:9000)"
        )
    elif _endpoint_hostname(endpoint) not in LOCAL_HOSTNAMES:
        problems.append(
            f"SPARK_S3_ENDPOINT='{endpoint}' (hostname='{_endpoint_hostname(endpoint)}') is not "
            f"exactly one of {sorted(LOCAL_HOSTNAMES)}"
        )

    akid = os.environ.get("SPARK_AWS_ACCESS_KEY_ID", "")
    if _looks_real_aws_key(akid):
        problems.append(
            "SPARK_AWS_ACCESS_KEY_ID looks like a REAL AWS key (AKIA/ASIA…) — Spark drills must "
            "use fake local creds"
        )

    secret = os.environ.get("SPARK_AWS_SECRET_ACCESS_KEY", "")
    if _looks_real_aws_secret(secret):
        problems.append(
            "SPARK_AWS_SECRET_ACCESS_KEY looks like a REAL AWS secret key shape (40+ base64-charset "
            "chars) — Spark drills must use a short fake local secret"
        )

    if problems:
        raise SparkGymGuardError(
            "🛑 spark_gym_guard: environment is NOT safe for a Spark drill run:\n  - "
            + "\n  - ".join(problems)
            + "\nFix: `set -a; source gym.env; set +a` then re-run. Nothing was executed."
        )


def main() -> int:
    try:
        assert_spark_gym_safe()
    except SparkGymGuardError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("[spark_gym_guard] OK — env hard-pointed at the Spark staging bucket. Safe to run a drill.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
