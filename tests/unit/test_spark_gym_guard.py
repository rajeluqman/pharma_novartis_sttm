"""Fail-closed proof for scripts/spark_gym_guard.py (ADR-007 B3).

Pure env-var logic, no SparkSession/JVM involved — asserts the guard ABORTS on every
non-gym bucket/endpoint/real-key combination, and only passes on the exact gym.env
values. This is the proof artifact ADR-007 B3 requires before any Spark drill may run.

Run: python3 tests/unit/test_spark_gym_guard.py
(or: pytest tests/unit/test_spark_gym_guard.py -v)
"""
import contextlib
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from spark_gym_guard import SparkGymGuardError, assert_spark_gym_safe  # noqa: E402

SAFE_ENV = {
    "SPARK_S3_BUCKET": "gym-lake-spark-staging",
    "SPARK_READ_S3_BUCKET": "gym-lake",
    "SPARK_S3_ENDPOINT": "localhost:9000",
    "SPARK_AWS_ACCESS_KEY_ID": "mang",
    "SPARK_AWS_SECRET_ACCESS_KEY": "mangmang",
}

FAILURES = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(label)


@contextlib.contextmanager
def env(overrides: dict):
    """Set SAFE_ENV with `overrides` applied (None deletes the key), restore after."""
    keys = set(SAFE_ENV) | set(overrides)
    saved = {k: os.environ.get(k) for k in keys}
    try:
        merged = {**SAFE_ENV, **overrides}
        for k in keys:
            v = merged.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def aborts(overrides: dict) -> bool:
    with env(overrides):
        try:
            assert_spark_gym_safe()
            return False  # did NOT abort — guard failed to catch this
        except SparkGymGuardError:
            return True


def passes(overrides: dict) -> bool:
    with env(overrides):
        try:
            assert_spark_gym_safe()
            return True
        except SparkGymGuardError:
            return False


def main() -> int:
    check("baseline gym.env values pass", passes({}))

    check("aborts: SPARK_S3_BUCKET = prod bucket",
          aborts({"SPARK_S3_BUCKET": "novartis-pharma-sttm-lake"}))
    check("aborts: SPARK_S3_BUCKET = DuckDB gym-lake (cross-track collision)",
          aborts({"SPARK_S3_BUCKET": "gym-lake"}))
    check("aborts: SPARK_S3_BUCKET = empty",
          aborts({"SPARK_S3_BUCKET": None}))
    check("aborts: SPARK_S3_BUCKET = arbitrary other bucket",
          aborts({"SPARK_S3_BUCKET": "some-other-bucket"}))

    check("aborts: SPARK_READ_S3_BUCKET = prod bucket",
          aborts({"SPARK_READ_S3_BUCKET": "novartis-pharma-sttm-lake"}))
    check("aborts: SPARK_READ_S3_BUCKET = arbitrary other bucket",
          aborts({"SPARK_READ_S3_BUCKET": "some-other-bucket"}))

    check("aborts: SPARK_S3_ENDPOINT = empty (real-AWS default)",
          aborts({"SPARK_S3_ENDPOINT": None}))
    check("aborts: SPARK_S3_ENDPOINT = non-local host",
          aborts({"SPARK_S3_ENDPOINT": "s3.ap-southeast-1.amazonaws.com"}))

    check("aborts: SPARK_AWS_ACCESS_KEY_ID looks like a real AKIA key",
          aborts({"SPARK_AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE"}))
    check("aborts: SPARK_AWS_ACCESS_KEY_ID looks like a real ASIA (STS) key",
          aborts({"SPARK_AWS_ACCESS_KEY_ID": "ASIAIOSFODNN7EXAMPLE"}))

    # Gate-0 independent review (data-platform-engineer persona, 2026-06-21) flagged two gaps
    # that have since been hardened — regression-pin both here.
    check("aborts: SPARK_S3_ENDPOINT is a spoofed host containing 'localhost' as a substring",
          aborts({"SPARK_S3_ENDPOINT": "evil-localhost.attacker.com:9000"}))
    check("aborts: SPARK_S3_ENDPOINT is a spoofed host containing '127.0.0.1' as a substring",
          aborts({"SPARK_S3_ENDPOINT": "127.0.0.1.attacker.com:9000"}))
    check("aborts: SPARK_S3_ENDPOINT is a spoofed host containing 'minio' as a substring",
          aborts({"SPARK_S3_ENDPOINT": "fake-minio.attacker.com:9000"}))
    check("passes: SPARK_S3_ENDPOINT with an explicit http:// scheme still resolves local",
          passes({"SPARK_S3_ENDPOINT": "http://localhost:9000"}))
    check("aborts: SPARK_AWS_SECRET_ACCESS_KEY looks like a real 40-char AWS secret "
          "(paired with a fake-looking access key id)",
          aborts({"SPARK_AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"}))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        return 1
    print("All spark_gym_guard fail-closed checks PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
