#!/usr/bin/env bash
# ============================================================================
# provision_s3_staging.sh — ADR-007 B4: Spark+Delta DEMONSTRATION staging bucket
# ----------------------------------------------------------------------------
# Implements ADR-007 B4 (adopts Data Platform Engineer condition C2): a bucket
# DISTINCT from the canonical lake (novartis-pharma-sttm-lake), so the Spark
# DEMONSTRATION track can never be mistaken for, or accidentally touch, the
# governed star. Guardrails shipped in the SAME create step (same rationale as
# provision_s3.sh's ADR-005 bucket — a policy-less window is the footgun):
#   (a) public-access-block
#   (b) versioning ON
#   (c) noncurrent-version expiry 30d (bucket-wide, mirrors the lake bucket)
#   (d) SHORT-TTL (7d) expiry on the 'delta/' prefix specifically — Delta's
#       transaction log + OPTIMIZE/ZORDER rewrites multiply object versions
#       fast; this is a demonstration artifact, not data anyone needs kept
#       (same cost-footgun class ADR-005 FinOps flagged for gold/<run_id>/)
#   (e) aws:RequestedRegion Deny -> cross-region access = hard 403 (FinOps lock)
# No landing-write-once rule here — this bucket has no landing/ prefix; it only
# ever holds Spark's own Delta output (ADR-007 fence principle #4: derives
# from, never becomes, the governed model — nothing here is a source of truth).
#
# REAL SPEND: creates a real S3 bucket on the live account. ~<$1/mo at low-GB,
# capped further by the 7d staging-prefix TTL. OWNER-GATED per ADR-005 ("no AWS
# apply without explicit owner confirmation") — do not run this without having
# shown it to the owner first.
#
# Idempotent-ish: re-running after the bucket exists re-applies the same config.
# Reads creds + region from .env (AWS_*). Region MUST equal the compute region.
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."                       # project root
set -a; . ./.env; set +a

AWS="${AWS_BIN:-.venv/bin/aws}"
BUCKET="${SPARK_STAGING_S3_BUCKET:-novartis-pharma-sttm-spark-staging}"
REGION="${AWS_DEFAULT_REGION:-ap-southeast-1}"

echo ">> Bucket : $BUCKET"
echo ">> Region : $REGION"
echo ">> Caller : $($AWS sts get-caller-identity --query Arn --output text)"

# ---- 1. create bucket (region-pinned) -------------------------------------
if $AWS s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo ">> [1/5] bucket already exists — skipping create"
else
  echo ">> [1/5] creating bucket in $REGION"
  $AWS s3api create-bucket \
    --bucket "$BUCKET" \
    --region "$REGION" \
    --create-bucket-configuration "LocationConstraint=$REGION"
fi

# ---- 2. block all public access (safety default) --------------------------
echo ">> [2/5] blocking public access"
$AWS s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# ---- 3. versioning ON (Delta's transaction log relies on object immutability) --
echo ">> [3/5] enabling versioning"
$AWS s3api put-bucket-versioning --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled

# ---- 4. lifecycle: 30d noncurrent bucket-wide + 7d SHORT-TTL on delta/ -----
echo ">> [4/5] applying lifecycle (30d noncurrent bucket-wide + 7d short-TTL on delta/)"
LIFECYCLE=$(mktemp)
cat > "$LIFECYCLE" <<'JSON'
{
  "Rules": [
    {
      "ID": "expire-noncurrent-30d-bucket-wide",
      "Filter": { "Prefix": "" },
      "Status": "Enabled",
      "NoncurrentVersionExpiration": { "NoncurrentDays": 30 }
    },
    {
      "ID": "short-ttl-delta-prefix-7d",
      "Filter": { "Prefix": "delta/" },
      "Status": "Enabled",
      "Expiration": { "Days": 7 },
      "NoncurrentVersionExpiration": { "NoncurrentDays": 7 }
    }
  ]
}
JSON
$AWS s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" \
  --lifecycle-configuration "file://$LIFECYCLE"
rm -f "$LIFECYCLE"

# ---- 5. bucket policy: region-lock only (no landing/ here) -----------------
echo ">> [5/5] applying bucket policy (region-lock)"
POLICY=$(mktemp)
cat > "$POLICY" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyCrossRegionRequests",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::$BUCKET",
        "arn:aws:s3:::$BUCKET/*"
      ],
      "Condition": {
        "StringNotEquals": { "aws:RequestedRegion": "$REGION" }
      }
    }
  ]
}
JSON
$AWS s3api put-bucket-policy --bucket "$BUCKET" --policy "file://$POLICY"
rm -f "$POLICY"

echo ""
echo ">> DONE. Verifying:"
echo "   versioning : $($AWS s3api get-bucket-versioning --bucket "$BUCKET" --query Status --output text)"
echo "   region     : $($AWS s3api get-bucket-location --bucket "$BUCKET" --query LocationConstraint --output text)"
echo "   lifecycle  : $($AWS s3api get-bucket-lifecycle-configuration --bucket "$BUCKET" --query 'Rules[*].ID' --output text)"
echo "   policy SIDs: $($AWS s3api get-bucket-policy --bucket "$BUCKET" --query Policy --output text | python3 -c 'import sys,json;print(",".join(s["Sid"] for s in json.load(sys.stdin)["Statement"]))')"
echo ""
echo ">> NOTE: this bucket is NOT yet usable by spark_session_factory()/spark_gym_guard.py —"
echo "   the guard currently hard-rejects any non-MinIO endpoint. A scoped 'demonstration"
echo "   mode' guard extension (ADR-007 B4 follow-up) is required before any real run"
echo "   against this bucket; that change goes through its own DPE/senior-DE/DA review."
