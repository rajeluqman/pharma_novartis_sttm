# RUNBOOK — ADR-005 Cloud Migration (real AWS S3 + Snowflake serving veneer)

**You run the commands; the agent preps + verifies.** (The harness blocks the agent from
executing real cloud-mutating calls — so every `aws`/Snowflake step here is yours to run.)
All commands assume:

```bash
cd <repo-root>   # the project root after cloning
```

Scope this round: **S3 (canonical) + Snowflake serving veneer. MWAA is OUT** (orchestration
stays on local aws-mwaa-local-runner, $0). Design basis: `docs/ADR/ADR-005-build-decisions.md`.

Migration code is already validated end-to-end against a local MinIO mock (KPIs reproduced
exactly). Real AWS = same code, env re-pointed via `.env.aws`. After each step, **paste the
output back** and I'll confirm before you proceed.

---

## STEP 1 — Create the S3 bucket + guardrails  ✅ script ready
```bash
bash scripts/provision_s3.sh
```
Creates `novartis-pharma-sttm-lake` (ap-southeast-1) + versioning + lifecycle(30d noncurrent)
+ policy (region-lock 403 + `landing/` write-once). **Paste the final verification block.**

---

## STEP 2 — Seed landing → real S3
```bash
set -a; . ./.env; . ./.env.aws; set +a      # real-AWS toggle (HTTPS, vhost, no MinIO endpoint)
.venv/bin/python scripts/seed_landing_to_s3.py
```
Uploads `data/landing/{alpha,beta,gamma}/<date>/` → `s3://.../landing/...` unchanged.
**Expect ~7 files. Paste the `[seed]` lines.**

---

## STEP 3 — Run the full pipeline → real S3 (DuckDB compute, S3 storage)
```bash
set -a; . ./.env; . ./.env.aws; set +a
export RUN_ID="run-$(date -u +%Y%m%d-%H%M%S)"

.venv/bin/python scripts/load_bronze.py                         # landing -> bronze/*.parquet (S3)
DBT_TARGET=dev .venv/bin/dbt build --project-dir dbt --profiles-dir dbt \
    --vars "{load_date: '<DATE>', run_id: '$RUN_ID'}"           # staging+snapshot+marts+serving+tests
.venv/bin/python scripts/publish_gold.py --run-id "$RUN_ID"     # gold/<run_id> -> copy to gold/_current
.venv/bin/python scripts/run_ge_validation.py                  # 13 GE expectations vs gold/_current
```
Replace `<DATE>` with the landing partition (e.g. `2026-06-18`).
**Acceptance (paste these):** dbt `PASS=.. WARN=1 ERROR=0`; GE 13/13; `fact_review` ≈ 215,063;
drug_sk ≈ 71.9%; condition_sk ≈ 98.9%. Confirm `gold/_current/` populated:
```bash
.venv/bin/aws s3 ls s3://novartis-pharma-sttm-lake/gold/_current/ --recursive | head
```

---

## STEP 4 — Snowflake serving veneer (external tables over gold/_current)
**Needs ACCOUNTADMIN for the integration + role. Includes a mandatory IAM trust handshake.**

**4a. Create the IAM role Snowflake will assume:**
```bash
bash scripts/provision_snowflake_iam.sh
```
Note the printed **Role ARN**.

**4b. In Snowsight (ACCOUNTADMIN), STEP 1 of `scripts/provision_snowflake_veneer.sql`:**
put the Role ARN into `STORAGE_AWS_ROLE_ARN`, run `CREATE STORAGE INTEGRATION`, then:
```sql
DESC INTEGRATION s3_gold_integration;
```
Copy `STORAGE_AWS_IAM_USER_ARN` and `STORAGE_AWS_EXTERNAL_ID`.

**4c. Tighten the IAM trust with those two values:**
```bash
SNOWFLAKE_IAM_USER_ARN='<paste>' SNOWFLAKE_EXTERNAL_ID='<paste>' bash scripts/provision_snowflake_iam.sh
```

**4d. Run STEP 2–4 of `scripts/provision_snowflake_veneer.sql`** (role, stage, external tables, verify).
**Paste:** `sales_rows` and `review_rows` (review ≈ 215,063) — that's the veneer proving
"warehouse over lakehouse" reading the exact same S3 Gold the DuckDB pipeline wrote.

---

## After the cloud is up (agent does these, $0)
- Update `COST_LOG.md` (steady-state S3 <$1/mo; remove stale "$3–5 teardown" line) + `PROJECT_STATUS.md`.
- Commit the migration + the new README (business-Q&A format).
- SLA gym self-play (Senior Data Engineer creates + solves; logged).
- Handover to self-review.

## Re-point back to local MinIO anytime
Just **don't** source `.env.aws` (and have MinIO up): `set -a; . ./.env; . ./.env.minio; set +a`.
