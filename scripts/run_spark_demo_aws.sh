#!/usr/bin/env bash
# ============================================================================
# run_spark_demo_aws.sh — the ONE real-AWS Spark + Delta DEMONSTRATION run (ADR-007 B4)
# ----------------------------------------------------------------------------
# OWNER-GATED. Do not run without explicit confirmation first (ADR-005's "no AWS apply
# without explicit owner confirmation" carries over — this reads the REAL governed star
# and writes to a REAL bucket, small but real spend + real prod-bucket read access).
#
# Sources .env + .env.aws (same real-AWS overlay run_pipeline_aws.sh uses, for reconcile.py's
# DuckDB leg — defensively RESETS S3_BUCKET/S3_ENDPOINT to real-AWS values even if this shell
# previously sourced gym.env), then aliases the real creds onto the SPARK_* names
# spark_session_factory() reads, and sets SPARK_DEMO_MODE=1 so scripts/spark_gym_guard.py
# switches from drill rules to the B4 demo rules (real bucket names, empty endpoint, real
# creds REQUIRED — see that file). The SPARK_* exports below are unconditional (not
# `${VAR:-default}`), so any stale SPARK_* values from a prior `source gym.env` in this same
# shell are overridden too, not just inherited.
#
# Reads:  s3a://novartis-pharma-sttm-lake/gold/_current/   (read-only, the real governed star)
# Writes: s3a://<SPARK_STAGING_S3_BUCKET>/delta/           (the separate, isolated B4 bucket)
# Never:  writes to the prod bucket, never publishes to gold/_current/ (ADR-007 B8(a))
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; . ./.env.aws; set +a

: "${SPARK_STAGING_S3_BUCKET:?SPARK_STAGING_S3_BUCKET not set in .env — run scripts/provision_s3_staging.sh first}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID not set in .env}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY not set in .env}"

export SPARK_DEMO_MODE=1
export SPARK_S3_BUCKET="${SPARK_STAGING_S3_BUCKET}"
export SPARK_READ_S3_BUCKET=novartis-pharma-sttm-lake
export SPARK_S3_ENDPOINT=
export SPARK_AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}"
export SPARK_AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}"
export SPARK_AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-ap-southeast-1}}"
export SPARK_JAVA_HOME="${SPARK_JAVA_HOME:-/usr/local/sdkman/candidates/java/21.0.10-ms}"
# ADR-007 B2: the Codespace default JAVA_HOME is too new for Hadoop 3.3.4 (Subject.getSubject
# was removed in JDK 24+) — override JAVA_HOME/PATH to the pinned Java 21 candidate, same as
# airflow/dags/spark_delta_demo_dag.py's run() helper does per subprocess.
export JAVA_HOME="${SPARK_JAVA_HOME}"
export PATH="${SPARK_JAVA_HOME}/bin:${PATH}"
PY=.venv/bin/python

echo "============================================================"
echo ">> DEMO MODE — real AWS S3, real governed star, isolated write bucket"
echo ">> Read  : s3a://${SPARK_READ_S3_BUCKET}/gold/_current/  (read-only)"
echo ">> Write : s3a://${SPARK_S3_BUCKET}/delta/"
echo "============================================================"

echo ">> [0/2] spark_gym_guard preflight (demo mode)"
$PY scripts/spark_gym_guard.py

echo ">> [1/2] build_delta_slice — read real gold/_current/, write Delta + OPTIMIZE ZORDER"
$PY spark/jobs/build_delta_slice.py

echo ">> [2/2] reconcile — Spark+Delta slice vs the DuckDB mart (same real gold/_current/)"
$PY spark/jobs/reconcile.py

echo ""
echo ">> DEMONSTRATION COMPLETE — s3a://${SPARK_S3_BUCKET}/delta/"
