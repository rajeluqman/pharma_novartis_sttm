#!/usr/bin/env python3
"""Fail-closed preflight for the Incident-Response / SLA Incubator (ADR-006-A1).

CRITICAL: scripts/s3_env.py FAILS OPEN — an unset S3_ENDPOINT defaults to REAL AWS and the
default S3_BUCKET is the LIVE 'novartis-pharma-sttm-lake'. So "the gym never touches prod" must
be enforced MECHANICALLY, not by prose. Every Track-I / Track-S drill runner calls
`assert_gym_safe()` (or runs this module) BEFORE executing any sabotaged pipeline step.

Rule (abort unless ALL hold):
  - GYM_MODE == "1"                      (drill must declare itself a gym run)
  - S3_BUCKET == "gym-lake"             (NOT the prod bucket — the load-bearing guard)
  - S3_ENDPOINT is a local endpoint     (localhost/127.0.0.1/minio — never empty = real AWS)
  - creds are NOT real-looking          (no real 20-char AKIA... access key id)

Source gym.env first:  set -a; source gym.env; set +a;  python scripts/gym_guard.py
Exit 0 = safe to run a drill. Non-zero = ABORTED, nothing ran.
"""
import os
import sys

PROD_BUCKET = "novartis-pharma-sttm-lake"
GYM_BUCKET = "gym-lake"
LOCAL_HINTS = ("localhost", "127.0.0.1", "minio")


class GymGuardError(RuntimeError):
    """Raised when the environment is NOT safe for a sabotage/drill run."""


def _looks_real_aws_key(key: str) -> bool:
    # Real AWS access key ids start with AKIA/ASIA and are 20 chars. Fake gym creds won't.
    k = key.strip().upper()
    return k.startswith(("AKIA", "ASIA")) and len(key.strip()) >= 20


def assert_gym_safe() -> None:
    """Abort (raise GymGuardError) unless the env is hard-pointed at the local gym-lake."""
    problems = []

    if os.environ.get("GYM_MODE") != "1":
        problems.append("GYM_MODE != '1' — refusing to run a drill outside gym mode "
                        "(did you `source gym.env`?)")

    bucket = os.environ.get("S3_BUCKET", "")
    if bucket == PROD_BUCKET:
        problems.append(f"S3_BUCKET is the LIVE prod bucket '{PROD_BUCKET}' — drills must use "
                        f"'{GYM_BUCKET}'")
    elif bucket != GYM_BUCKET:
        problems.append(f"S3_BUCKET='{bucket or '(empty)'}' — must be '{GYM_BUCKET}'")

    endpoint = os.environ.get("S3_ENDPOINT", "").strip()
    if not endpoint:
        problems.append("S3_ENDPOINT is empty — that resolves to REAL AWS. Drills require a "
                        "local MinIO endpoint (e.g. localhost:9000)")
    elif not any(h in endpoint for h in LOCAL_HINTS):
        problems.append(f"S3_ENDPOINT='{endpoint}' does not look local "
                        f"(expected one of {LOCAL_HINTS})")

    akid = os.environ.get("AWS_ACCESS_KEY_ID", "")
    if _looks_real_aws_key(akid):
        problems.append("AWS_ACCESS_KEY_ID looks like a REAL AWS key (AKIA/ASIA…) — drills "
                        "must use fake local creds")

    if problems:
        raise GymGuardError(
            "🛑 gym_guard: environment is NOT safe for a sabotage/drill run:\n  - "
            + "\n  - ".join(problems)
            + "\nFix: `set -a; source gym.env; set +a` then re-run. Nothing was executed."
        )


def main() -> int:
    try:
        assert_gym_safe()
    except GymGuardError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("[gym_guard] OK — env hard-pointed at local gym-lake. Safe to run a drill.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
