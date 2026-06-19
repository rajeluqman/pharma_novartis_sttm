#!/usr/bin/env bash
# ============================================================================
# provision_s3.sh — ADR-005 S3-canonical bucket + create-time guardrails
# ----------------------------------------------------------------------------
# Implements Data Architect's ADR-005 build ruling (docs/ADR/ADR-005-build-decisions.md):
#   Decision 4: bucket `novartis-pharma-sttm-lake` in ap-southeast-1, with ALL FOUR
#   guardrails shipped in the SAME create step (a versioned bucket with a policy-less
#   window is the silent-cost / mutation footgun ADR-005 P3 calls out):
#     (a) versioning ON
#     (b) noncurrent-version expiry ~30d lifecycle (caps versioning cost — FinOps)
#     (c) aws:RequestedRegion Deny  -> cross-region access = hard 403, not silent egress (P2)
#     (d) landing/ delete-deny      -> write-once immutability (ADR-002 + ADR-005 Guardrails)
#
# REAL SPEND: creates a real S3 bucket on the live account. S3 storage ~<$1/mo at low-GB.
# Recoverable: the account root can remove/replace the bucket policy if a guardrail is
# ever too strict (the landing delete-deny intentionally blocks even the deployer user).
#
# Idempotent-ish: re-running after the bucket exists re-applies versioning/lifecycle/policy.
# Reads creds + region from .env (AWS_*). Region MUST equal the compute region (FinOps lock).
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."                       # project root
set -a; . ./.env; set +a

AWS="${AWS_BIN:-.venv/bin/aws}"
BUCKET="${S3_BUCKET:-novartis-pharma-sttm-lake}"
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

# ---- 3. versioning ON (immutability + replay) -----------------------------
echo ">> [3/5] enabling versioning"
$AWS s3api put-bucket-versioning --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled

# ---- 4. lifecycle: expire noncurrent versions after 30d (cap cost) --------
echo ">> [4/5] applying lifecycle (noncurrent expiry 30d)"
LIFECYCLE=$(mktemp)
cat > "$LIFECYCLE" <<'JSON'
{
  "Rules": [
    {
      "ID": "expire-noncurrent-30d",
      "Filter": { "Prefix": "" },
      "Status": "Enabled",
      "NoncurrentVersionExpiration": { "NoncurrentDays": 30 }
    }
  ]
}
JSON
$AWS s3api put-bucket-lifecycle-configuration --bucket "$BUCKET" \
  --lifecycle-configuration "file://$LIFECYCLE"
rm -f "$LIFECYCLE"

# ---- 5. bucket policy: region-lock + landing write-once -------------------
echo ">> [5/5] applying bucket policy (region-lock + landing delete-deny)"
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
    },
    {
      "Sid": "LandingWriteOnce",
      "Effect": "Deny",
      "Principal": "*",
      "Action": [ "s3:DeleteObject", "s3:DeleteObjectVersion" ],
      "Resource": "arn:aws:s3:::$BUCKET/landing/*"
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
echo "   lifecycle  : $($AWS s3api get-bucket-lifecycle-configuration --bucket "$BUCKET" --query 'Rules[0].ID' --output text)"
echo "   policy SIDs: $($AWS s3api get-bucket-policy --bucket "$BUCKET" --query Policy --output text | python3 -c 'import sys,json;print(",".join(s["Sid"] for s in json.load(sys.stdin)["Statement"]))')"
