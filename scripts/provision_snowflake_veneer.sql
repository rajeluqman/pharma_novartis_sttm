-- ============================================================================
-- provision_snowflake_veneer.sql — ADR-005 Snowflake serving veneer over S3 gold/*
-- ----------------------------------------------------------------------------
-- Implements Data Architect ADR-005 build ruling (docs/ADR/ADR-005-build-decisions.md):
--   Decision 1: Snowflake reads the FIXED gold/_current/ prefix (immutable copy-on-publish)
--   Decision 3: NEW read-only role `snowflake_gold_reader` (do NOT widen NOVARTIS_STTM_ROLE)
--
-- Run order + privileges (run in Snowsight, or via scripts/run_snowflake_sql.py):
--   STEP 1 + STEP 2 need ACCOUNTADMIN (CREATE INTEGRATION / CREATE ROLE).
--   Between STEP 1 and STEP 3 you MUST do the IAM trust handshake (see RUNBOOK).
--
-- Placeholders to fill (from provision_snowflake_iam.sh output + your account):
--   <ROLE_ARN>  = arn:aws:iam::<ACCOUNT_ID>:role/snowflake-s3-gold-reader
--   <BUCKET>    = novartis-pharma-sttm-lake
-- ============================================================================

-- ───────────────────────────── STEP 1 (ACCOUNTADMIN) ─────────────────────────
-- Create the storage integration. After this, run `DESC INTEGRATION s3_gold_integration`
-- and copy STORAGE_AWS_IAM_USER_ARN + STORAGE_AWS_EXTERNAL_ID back into
-- provision_snowflake_iam.sh (2nd run) to tighten the IAM role trust. THEN do STEP 3+.
USE ROLE ACCOUNTADMIN;

CREATE STORAGE INTEGRATION IF NOT EXISTS s3_gold_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = '<ROLE_ARN>'
  STORAGE_ALLOWED_LOCATIONS = ('s3://<BUCKET>/gold/')
  COMMENT = 'ADR-005: read-only external tables over S3 gold/_current parquet';

-- Run this, copy the two values into the IAM handshake, then continue:
-- DESC INTEGRATION s3_gold_integration;

-- ───────────────────────────── STEP 2 (ACCOUNTADMIN) ─────────────────────────
-- New scoped read-only role (ADR-004 owner-vs-scoped principle; do NOT touch NOVARTIS_STTM_ROLE).
CREATE ROLE IF NOT EXISTS snowflake_gold_reader;
GRANT USAGE ON INTEGRATION s3_gold_integration TO ROLE snowflake_gold_reader;
GRANT USAGE ON WAREHOUSE NOVARTIS_STTM_WH       TO ROLE snowflake_gold_reader;
GRANT USAGE ON DATABASE  NOVARTIS_STTM_DB        TO ROLE snowflake_gold_reader;
GRANT USAGE ON SCHEMA    NOVARTIS_STTM_DB.PUBLIC  TO ROLE snowflake_gold_reader;
-- so the role can create/own the stage + external tables it serves:
GRANT CREATE STAGE          ON SCHEMA NOVARTIS_STTM_DB.PUBLIC TO ROLE snowflake_gold_reader;
GRANT CREATE EXTERNAL TABLE ON SCHEMA NOVARTIS_STTM_DB.PUBLIC TO ROLE snowflake_gold_reader;
GRANT ROLE snowflake_gold_reader TO USER NOVARTISMANG;   -- so you can use it

-- ─────────────────── STEP 3 (after IAM trust handshake done) ──────────────────
USE ROLE snowflake_gold_reader;
USE WAREHOUSE NOVARTIS_STTM_WH;
USE SCHEMA NOVARTIS_STTM_DB.PUBLIC;

CREATE FILE FORMAT IF NOT EXISTS parquet_fmt TYPE = PARQUET;

-- Stage points at the FIXED gold/_current/ prefix (Decision 1 — never re-pointed per run).
CREATE OR REPLACE STAGE gold_stage
  STORAGE_INTEGRATION = s3_gold_integration
  URL = 's3://<BUCKET>/gold/_current/'
  FILE_FORMAT = parquet_fmt
  COMMENT = 'ADR-005: S3 gold/_current serving prefix';

-- External tables — schema auto-inferred from the published parquet (no hand-typed columns).
CREATE OR REPLACE EXTERNAL TABLE obt_sales_wide_ext
  USING TEMPLATE (
    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
    FROM TABLE(INFER_SCHEMA(LOCATION=>'@gold_stage/obt_sales_wide/', FILE_FORMAT=>'parquet_fmt'))
  )
  LOCATION = @gold_stage/obt_sales_wide/
  FILE_FORMAT = parquet_fmt
  AUTO_REFRESH = FALSE;

CREATE OR REPLACE EXTERNAL TABLE obt_review_wide_ext
  USING TEMPLATE (
    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*))
    FROM TABLE(INFER_SCHEMA(LOCATION=>'@gold_stage/obt_review_wide/', FILE_FORMAT=>'parquet_fmt'))
  )
  LOCATION = @gold_stage/obt_review_wide/
  FILE_FORMAT = parquet_fmt
  AUTO_REFRESH = FALSE;

-- ───────────────────────────── STEP 4 verify ─────────────────────────────────
-- After each publish (gold/_current/ refreshed), refresh the external table metadata:
--   ALTER EXTERNAL TABLE obt_sales_wide_ext REFRESH;
--   ALTER EXTERNAL TABLE obt_review_wide_ext REFRESH;
SELECT COUNT(*) AS sales_rows  FROM obt_sales_wide_ext;
SELECT COUNT(*) AS review_rows FROM obt_review_wide_ext;   -- expect ~215,063
