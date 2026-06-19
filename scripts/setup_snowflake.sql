-- One-time provisioning for the Snowflake trial account.
-- Run once as ACCOUNTADMIN (or a role with CREATE ROLE/WAREHOUSE/DATABASE) before `dbt debug --target prod`.
-- Names must match .env (SNOWFLAKE_ROLE/WAREHOUSE/DATABASE/SCHEMA).
--
-- Grants below are least-privilege per ADR-004 (see docs/ADR/ADR-004-snowflake-rbac.md). The first
-- version of this script used GRANT ALL on the database/schema/future objects — Data Architect
-- vetoed that in the Phase 4 retroactive peer review (DEBATE_LOG_phase_4.md) as an ownership-class
-- over-grant. NOVARTIS_STTM_ROLE only needs USAGE + CREATE SCHEMA at the database level: dbt creates
-- its own working schemas (enrich/data_mart/rrd/snapshots) under that grant and becomes their owner
-- automatically, so no FUTURE SCHEMA/TABLE grants are needed.

USE ROLE ACCOUNTADMIN;

CREATE ROLE IF NOT EXISTS NOVARTIS_STTM_ROLE;
GRANT ROLE NOVARTIS_STTM_ROLE TO USER NOVARTISMANG;

-- XSMALL + short auto-suspend: this is a portfolio build, not a prod workload (cost discipline, COST_LOG.md).
CREATE WAREHOUSE IF NOT EXISTS NOVARTIS_STTM_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

CREATE DATABASE IF NOT EXISTS NOVARTIS_STTM_DB;

-- Revoke the original over-grant (idempotent no-op if already revoked / never granted).
REVOKE ALL ON DATABASE NOVARTIS_STTM_DB FROM ROLE NOVARTIS_STTM_ROLE;
REVOKE ALL ON SCHEMA NOVARTIS_STTM_DB.PUBLIC FROM ROLE NOVARTIS_STTM_ROLE;
REVOKE ALL ON FUTURE SCHEMAS IN DATABASE NOVARTIS_STTM_DB FROM ROLE NOVARTIS_STTM_ROLE;
REVOKE ALL ON FUTURE TABLES IN DATABASE NOVARTIS_STTM_DB FROM ROLE NOVARTIS_STTM_ROLE;

GRANT USAGE ON WAREHOUSE NOVARTIS_STTM_WH TO ROLE NOVARTIS_STTM_ROLE;
GRANT USAGE ON DATABASE NOVARTIS_STTM_DB TO ROLE NOVARTIS_STTM_ROLE;
GRANT CREATE SCHEMA ON DATABASE NOVARTIS_STTM_DB TO ROLE NOVARTIS_STTM_ROLE;
GRANT USAGE ON SCHEMA NOVARTIS_STTM_DB.PUBLIC TO ROLE NOVARTIS_STTM_ROLE;
