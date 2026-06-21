#!/usr/bin/env python3
"""Fail-closed preflight for the Spark + Delta DEMONSTRATION track (ADR-007 B3/B4).

CRITICAL: Spark reaches S3 through a DIFFERENT client (Hadoop's s3a, configured via
spark.hadoop.fs.s3a.* in SparkConf) than DuckDB's httpfs (scripts/gym_guard.py /
scripts/s3_env.py). The DuckDB guard NEVER inspects Spark's env — without this module,
a Spark drill could be "gym_guard-green" on the DuckDB side and still mutate the live
AWS lake, or the unrelated DuckDB 'gym-lake' bucket, via Spark. This guard is the SOLE
mechanism that makes the Spark track governable (closes the same fail-open hole class
ADR-006-A1 closed for DuckDB, for Spark's separate client).

TWO modes, selected by the explicit SPARK_DEMO_MODE flag (mirrors GYM_MODE's exact-"1"
convention in scripts/gym_guard.py — a typo'd flag value must fail closed, not silently
fall through to "safe"):

DRILL mode (SPARK_DEMO_MODE != "1", the default — unchanged since B3 first shipped):
  - SPARK_S3_BUCKET == 'gym-lake-spark-staging'   (WRITE target. NEVER prod, NEVER the
    DuckDB incubator's 'gym-lake' bucket — the two tracks must stay on physically
    separate WRITE buckets so neither can be mistaken for clearing the other)
  - SPARK_READ_S3_BUCKET is in {'gym-lake', 'gym-lake-spark-staging'}   (READ-ONLY source
    for the ADR-001 star inputs Spark demonstrates against — must never be the prod
    bucket, even for reads)
  - SPARK_S3_ENDPOINT's HOSTNAME (parsed, not a substring match) is exactly one of
    localhost/127.0.0.1/::1/minio    (a substring check would pass a spoofed host like
    'evil-localhost.attacker.com' — flagged in gate-0 independent review, fixed here)
  - SPARK_AWS_ACCESS_KEY_ID / SPARK_AWS_SECRET_ACCESS_KEY are NOT real-looking

DEMO mode (SPARK_DEMO_MODE == "1" exactly — the ONE owner-gated real-AWS run ADR-007 B4
authorizes; built, never auto-invoked by any drill runner):
  - SPARK_S3_BUCKET == 'novartis-pharma-sttm-spark-staging'   (the B4 bucket — WRITE
    target only, NEVER prod, NEVER either gym-mode bucket)
  - SPARK_READ_S3_BUCKET == 'novartis-pharma-sttm-lake'   (the REAL governed star,
    read-only by code discipline — build_delta_slice.py hardcodes the read path to
    gold/_current/ and never calls a write API against it; owner explicitly accepted
    this is software-enforced, not IAM-enforced, when authorizing demo mode)
  - SPARK_S3_ENDPOINT is EMPTY   (real AWS default regional endpoint — a non-empty
    endpoint here, local or not, is rejected: real creds pointed at an attacker-chosen
    endpoint is an exfiltration vector this guard must not allow)
  - SPARK_AWS_ACCESS_KEY_ID / SPARK_AWS_SECRET_ACCESS_KEY MUST look real (inverted from
    drill mode) — a leftover fake gym credential in demo mode just fails auth deep
    inside the JVM with a confusing error; fail fast here instead with a clear message

Every spark_session_factory() call (spark/spark_session_factory.py) routes through
assert_spark_gym_safe() BEFORE constructing a SparkSession. No raw SparkSession.builder
is permitted anywhere else under spark/ — CI (ADR-007 B6) greps for violations.

Usage (drill):  set -a; source gym.env; set +a;  python scripts/spark_gym_guard.py
Usage (demo):   scripts/run_spark_demo_aws.sh  (sets SPARK_DEMO_MODE=1 + the real-AWS
                SPARK_* vars from .env, then calls this guard before anything else runs)
Exit 0 = safe to proceed. Non-zero = ABORTED, nothing ran.
"""
import os
import re
import sys
from urllib.parse import urlsplit

PROD_BUCKET = "novartis-pharma-sttm-lake"
DUCKDB_GYM_BUCKET = "gym-lake"  # the OTHER incubator's bucket — Spark must never share it
SPARK_GYM_BUCKET = "gym-lake-spark-staging"
SPARK_DEMO_BUCKET = "novartis-pharma-sttm-spark-staging"  # ADR-007 B4 real staging bucket
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


def _assert_drill_safe(problems: list) -> None:
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
            f"SPARK_READ_S3_BUCKET is the LIVE prod bucket '{PROD_BUCKET}' — Spark drills must never "
            f"read from prod, even read-only"
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


def _assert_demo_safe(problems: list) -> None:
    bucket = os.environ.get("SPARK_S3_BUCKET", "")
    if bucket == PROD_BUCKET:
        problems.append(
            f"SPARK_S3_BUCKET is the LIVE prod bucket '{PROD_BUCKET}' — the demo may only WRITE to "
            f"the separate B4 staging bucket '{SPARK_DEMO_BUCKET}'"
        )
    elif bucket in (DUCKDB_GYM_BUCKET, SPARK_GYM_BUCKET):
        problems.append(
            f"SPARK_S3_BUCKET='{bucket}' is a drill (MinIO) bucket — SPARK_DEMO_MODE=1 requires the "
            f"real B4 staging bucket '{SPARK_DEMO_BUCKET}', not a drill bucket"
        )
    elif bucket != SPARK_DEMO_BUCKET:
        problems.append(f"SPARK_S3_BUCKET='{bucket or '(empty)'}' — must be '{SPARK_DEMO_BUCKET}'")

    read_bucket = os.environ.get("SPARK_READ_S3_BUCKET", "")
    if read_bucket in (DUCKDB_GYM_BUCKET, SPARK_GYM_BUCKET):
        problems.append(
            f"SPARK_READ_S3_BUCKET='{read_bucket}' is a drill (MinIO) bucket — SPARK_DEMO_MODE=1 "
            f"requires reading the REAL governed star '{PROD_BUCKET}'"
        )
    elif read_bucket == SPARK_DEMO_BUCKET:
        problems.append(
            "SPARK_READ_S3_BUCKET must not equal SPARK_S3_BUCKET (the demo's own write target) — "
            f"set it to '{PROD_BUCKET}'"
        )
    elif read_bucket != PROD_BUCKET:
        problems.append(f"SPARK_READ_S3_BUCKET='{read_bucket or '(empty)'}' — must be '{PROD_BUCKET}'")

    endpoint = os.environ.get("SPARK_S3_ENDPOINT", "").strip()
    if endpoint:
        problems.append(
            f"SPARK_S3_ENDPOINT='{endpoint}' is non-empty — SPARK_DEMO_MODE=1 must leave it EMPTY so "
            f"Hadoop's s3a client resolves the real regional AWS endpoint (a custom endpoint here, "
            f"local or not, paired with real creds is an exfiltration vector, not a drill convenience)"
        )

    akid = os.environ.get("SPARK_AWS_ACCESS_KEY_ID", "")
    if not _looks_real_aws_key(akid):
        problems.append(
            "SPARK_AWS_ACCESS_KEY_ID does not look like a real AWS key (AKIA/ASIA…) — SPARK_DEMO_MODE=1 "
            "requires real creds (did you forget to source .env instead of gym.env?)"
        )

    secret = os.environ.get("SPARK_AWS_SECRET_ACCESS_KEY", "")
    if not _looks_real_aws_secret(secret):
        problems.append(
            "SPARK_AWS_SECRET_ACCESS_KEY does not look like a real AWS secret shape (40+ base64-charset "
            "chars) — SPARK_DEMO_MODE=1 requires the real secret from .env"
        )


def assert_spark_gym_safe() -> None:
    """Abort (raise SparkGymGuardError) unless the env is hard-pointed at either the MinIO drill
    staging bucket (default) or, if SPARK_DEMO_MODE == '1' exactly, the real ADR-007 B4 demo."""
    demo_mode = os.environ.get("SPARK_DEMO_MODE") == "1"
    problems: list = []
    if demo_mode:
        _assert_demo_safe(problems)
    else:
        _assert_drill_safe(problems)

    if problems:
        kind = "DEMO" if demo_mode else "drill"
        raise SparkGymGuardError(
            f"🛑 spark_gym_guard: environment is NOT safe for a Spark {kind} run:\n  - "
            + "\n  - ".join(problems)
            + "\nFix: drills -> `set -a; source gym.env; set +a`; demo -> scripts/run_spark_demo_aws.sh. "
            "Nothing was executed."
        )


def main() -> int:
    demo_mode = os.environ.get("SPARK_DEMO_MODE") == "1"
    try:
        assert_spark_gym_safe()
    except SparkGymGuardError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if demo_mode:
        print("[spark_gym_guard] OK (DEMO mode) — env hard-pointed at the real ADR-007 B4 staging "
              "bucket + the real governed star. Safe to run the demonstration.")
    else:
        print("[spark_gym_guard] OK — env hard-pointed at the Spark staging bucket. Safe to run a drill.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
