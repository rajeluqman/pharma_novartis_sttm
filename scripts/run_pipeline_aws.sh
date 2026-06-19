#!/usr/bin/env bash
# ============================================================================
# run_pipeline_aws.sh — full ADR-005 pipeline against REAL AWS S3 (DuckDB compute)
# ----------------------------------------------------------------------------
# Same validated code as the MinIO run; only the env is re-pointed (.env.aws):
#   seed landing -> S3  |  load_bronze -> S3 parquet  |  dbt build (staging+snapshot
#   +marts+serving+tests)  |  publish_gold (gold/<run_id> -> gold/_current)  |  GE validation
# Self-contained: cd's to project root, sources .env + .env.aws (real-AWS toggle).
# REAL (small) SPEND: ~300MB to S3 (cents) + GET/PUT requests. Bucket already provisioned.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; . ./.env.aws; set +a

export LAND_DATE="${LAND_DATE:-2026-06-18}"
export RUN_ID="${RUN_ID:-run-$(date -u +%Y%m%d-%H%M%S)}"
PY=.venv/bin/python
DBT=.venv/bin/dbt

echo "============================================================"
echo ">> Target : s3://${S3_BUCKET}  (endpoint='${S3_ENDPOINT:-<real-aws>}', ssl=${S3_USE_SSL})"
echo ">> LAND_DATE=${LAND_DATE}  RUN_ID=${RUN_ID}"
echo "============================================================"

echo ">> [1/5] seed landing -> S3"
$PY scripts/seed_landing_to_s3.py

echo ">> [2/5] load_bronze -> S3 parquet"
$PY scripts/load_bronze.py

echo ">> [3/5] dbt build (staging + snapshot + marts + serving + tests)"
DBT_TARGET=dev $DBT build --project-dir dbt --profiles-dir dbt --vars "{run_id: '${RUN_ID}'}"

echo ">> [4/5] publish gold/${RUN_ID} -> gold/_current"
$PY scripts/publish_gold.py --run-id "${RUN_ID}"

echo ">> [5/5] Great Expectations validation vs gold/_current"
$PY scripts/run_ge_validation.py

echo ""
echo ">> gold/_current objects:"
.venv/bin/aws s3 ls "s3://${S3_BUCKET}/gold/_current/" --recursive | sed 's/^/   /'
echo ">> PIPELINE COMPLETE — run_id=${RUN_ID}"
