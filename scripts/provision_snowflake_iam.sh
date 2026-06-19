#!/usr/bin/env bash
# ============================================================================
# provision_snowflake_iam.sh — IAM role Snowflake assumes to read S3 gold/* (ADR-005)
# ----------------------------------------------------------------------------
# Part of the Snowflake serving-veneer handshake (ADR-005 Decision 3, P1).
# Creates a read-only IAM role + policy scoped to s3://<bucket>/gold/* so the
# Snowflake STORAGE INTEGRATION can read Gold parquet as external tables.
#
# TWO-STEP TRUST HANDSHAKE (S3 storage integration always needs this):
#   1. (this script) create role with a PLACEHOLDER trust (your own account) + the
#      gold/* read policy.
#   2. run provision_snowflake_veneer.sql step 1 (CREATE STORAGE INTEGRATION) ->
#      then `DESC INTEGRATION s3_gold_integration` to read STORAGE_AWS_IAM_USER_ARN
#      + STORAGE_AWS_EXTERNAL_ID.
#   3. re-run this script with those two values (SNOWFLAKE_IAM_USER_ARN / EXTERNAL_ID
#      env vars) to TIGHTEN the trust policy to exactly Snowflake's principal+external-id.
#
# REAL SPEND: IAM is free; this only grants read on gold/*. You run this, not the agent.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

AWS="${AWS_BIN:-.venv/bin/aws}"
BUCKET="${S3_BUCKET:-novartis-pharma-sttm-lake}"
ROLE="snowflake-s3-gold-reader"
ACCOUNT="$($AWS sts get-caller-identity --query Account --output text)"

# Snowflake-provided values (empty on first run -> placeholder self-trust; fill on 2nd run)
SF_IAM_USER_ARN="${SNOWFLAKE_IAM_USER_ARN:-arn:aws:iam::${ACCOUNT}:root}"
SF_EXTERNAL_ID="${SNOWFLAKE_EXTERNAL_ID:-PLACEHOLDER_EXTERNAL_ID}"

echo ">> Account: $ACCOUNT  Role: $ROLE  Bucket: $BUCKET"
echo ">> Trust principal: $SF_IAM_USER_ARN  ExternalId: $SF_EXTERNAL_ID"

TRUST=$(mktemp); POLICY=$(mktemp)
cat > "$TRUST" <<JSON
{ "Version": "2012-10-17", "Statement": [{
  "Effect": "Allow",
  "Principal": { "AWS": "$SF_IAM_USER_ARN" },
  "Action": "sts:AssumeRole",
  "Condition": { "StringEquals": { "sts:ExternalId": "$SF_EXTERNAL_ID" } }
}]}
JSON
cat > "$POLICY" <<JSON
{ "Version": "2012-10-17", "Statement": [
  { "Sid": "ReadGoldObjects", "Effect": "Allow",
    "Action": ["s3:GetObject","s3:GetObjectVersion"],
    "Resource": "arn:aws:s3:::$BUCKET/gold/*" },
  { "Sid": "ListGoldPrefix", "Effect": "Allow",
    "Action": ["s3:ListBucket","s3:GetBucketLocation"],
    "Resource": "arn:aws:s3:::$BUCKET",
    "Condition": { "StringLike": { "s3:prefix": ["gold/*"] } } }
]}
JSON

if $AWS iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  echo ">> role exists — updating trust policy"
  $AWS iam update-assume-role-policy --role-name "$ROLE" --policy-document "file://$TRUST"
else
  echo ">> creating role"
  $AWS iam create-role --role-name "$ROLE" --assume-role-policy-document "file://$TRUST" \
    --description "ADR-005: Snowflake reads S3 gold/* parquet as external tables (read-only)"
fi
$AWS iam put-role-policy --role-name "$ROLE" --policy-name "gold-read" --policy-document "file://$POLICY"
rm -f "$TRUST" "$POLICY"

echo ""
echo ">> Role ARN (paste into provision_snowflake_veneer.sql STORAGE_AWS_ROLE_ARN):"
$AWS iam get-role --role-name "$ROLE" --query Role.Arn --output text
