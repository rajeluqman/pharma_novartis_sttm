# OPS_RUNBOOK.md
**Owner**: Data Platform Engineer

---

## Monitoring Endpoints
| Tool | URL | Use For |
|------|-----|---------|
| Airflow | http://localhost:8080 (aws-mwaa-local-runner; user/pass `airflow`/`airflow` per `.env.example`) | DAG runs, task logs, SLA-miss banner for `pharma_sttm_pipeline_v1` |
| AWS MWAA | *not yet provisioned — no environment exists.* Once a spike is run, the console URL is `https://<region>.console.aws.amazon.com/mwaa/home?region=<region>#/environments/<MWAA_ENVIRONMENT_NAME>` (`novartis-pharma-mwaa` per `.env.example`); fill in after the next spike. | DAG runs in the cloud window |
| Snowflake | *trial account — not a public URL to record here.* Use Snowsight → Activity → Query History, filtered to `NOVARTIS_STTM_ROLE` / `NOVARTIS_STTM_WH`. | Query history, warehouse credit burn during the cloud window |
| DuckDB (local warehouse) | `data/warehouse.duckdb` (no UI — inspect via `duckdb data/warehouse.duckdb` CLI or `dbt docs serve`) | Local dev target for all dbt runs (`DBT_TARGET=dev`) |

Note: this project's locked stack has no Databricks (see `ARCHITECTURE.md` Stack table) — do not stand one up or look for one.

## Known Gaps
- **RESOLVED 2026-06-20 (O-AIR-07, P-PMR-07).** The DAG-cannot-complete defect (O-AIR-07) and the non-idempotent stg_beta__ndc dedup (P-PMR-07) are both FIXED and independently re-verified against the local MinIO gym-lake incubator (never the live AWS bucket). O-AIR-07: staging flipped view→external (dbt_project.yml:51), register_external_upstreams() macro (dbt/macros/register_external.sql) re-registers external ancestors through ephemeral nodes per subprocess, load/export hooks extended to survive run/test boundaries; 6 genuinely-separate dbt subprocesses all exit 0, dbt test 54 PASS/1 WARN/0 ERROR. P-PMR-07: deterministic secondary tie-break over every carried column incl. load_ts (dbt/models/staging/beta/stg_beta__ndc.sql:26-38); two byte-identical reps both yield dim_drug=133,654 (no SCD2 inflation). No ADR amendment (documentation hygiene). See SIGN_OFF_LOG.md 2026-06-20.
- **DAG never publishes Gold to `gold/_current/`** — `pharma_sttm_pipeline_v1` (`airflow/dags/pharma_sttm_pipeline.py`) has no task that calls `scripts/publish_gold.py`, and none of its `dbt(...)` calls pass `--vars '{"run_id": ...}'`, so every DAG-orchestrated run *would* write Gold to the fixed `gold/dev/` location (`dbt/dbt_project.yml:18` default + `dbt/macros/s3_paths.sql:25-26`) — **NOTE: O-AIR-07 (the run-cannot-complete defect) is now RESOLVED (2026-06-20), so the DAG can reach this point — this gap is now LIVE and is the next pickup.** `scripts/run_ge_validation.py:35` and the Snowflake external-table veneer both read ONLY `gold/_current/`, which today is updated exclusively by manually running `scripts/run_pipeline_aws.sh` (the only call site of `publish_gold.py` in the repo). Found and detailed (file:line evidence + fix) in `cheatsheets/troubleshooting/02_orchestration_airflow.md` → `O-AIR-01`; cross-referenced from `01_triage_blast_radius.md` → `T-TRI-05` and `08_postmortem_recovery.md` → `P-PMR-03`. Fix (not yet implemented): add a `publish_gold` task as the new DAG terminal step, gated after `dq_checks()`, with a real `run_id` threaded through every `dbt(...)` call.

## Alert SLA
| Severity | Response | Channel |
|----------|----------|---------|
| CRITICAL | 15 min | PagerDuty (sim) |
| HIGH | 1 hour | Slack |
| MEDIUM | Business day | Email |

Mapping to this pipeline:
- **CRITICAL** — `dq_checks()` fails on a `severity: error` dbt test (e.g. `dim_drug.drug_sk` uniqueness, `fact_sales` FK resolution <100%), or the DAG misses its 07:00 SLA (240-min budget from the 03:00 start) entirely.
- **HIGH** — a single bronze ingestion task (`alpha`/`beta`/`gamma` `land()`) fails (rate-limit/auth), or a GE suite fails a coverage threshold (`fact_review.drug_sk` <65%, `condition_sk` <90%).
- **MEDIUM** — a `severity: warn` dbt test trips (e.g. the known `stg_beta__ndc.generic_name` warn) or a non-blocking row-count drift is flagged.

## Playbook Scenarios

### SCENARIO: Bronze ingestion fail
- Symptom: `alpha.land`, `beta.land`, or `gamma.land` task FAILED in the Airflow UI (task group `alpha`/`beta`/`gamma`).
- Check:
  - Task log for the failing task — `alpha`/`gamma` shell out to `kaggle datasets download` (`scripts/ingest_alpha_sales.sh`, `scripts/ingest_gamma_reviews.sh`); `beta` calls `urllib.request.urlopen` against `https://download.open.fda.gov/...` (`scripts/ingest_beta_ndc.py`).
  - Confirm `KAGGLE_USERNAME`/`KAGGLE_KEY` (alpha, gamma) or reachability of `download.open.fda.gov` (beta) — see `.env.example`.
  - Confirm `LAND_DIR=data/landing/{alpha,beta,gamma}/{ds}` was actually created (`land()` passes Airflow's logical date `ds` as `LAND_DIR`/`LAND_DATE` env vars).
- Fix 1 (most common): Kaggle auth failure (expired/missing API key) or openFDA rate-limit/timeout (`ingest_beta_ndc.py` uses a 180s timeout on the bulk zip) — refresh `KAGGLE_KEY` or retry; openFDA bulk download has no required API key but `OPENFDA_API_KEY` raises the rate limit if repeated failures are rate-related.
- Fix 2 (second most common): upstream dataset/schema drift — Kaggle dataset `milanzdravkovic/pharma-sales-data` or `jessicali9530/kuc-hackathon-winter-2018` renamed/removed a file `load_bronze.py` expects by exact name (`salesdaily.csv`, `saleshourly.csv`, `drugsComTrain_raw.csv`, `drugsComTest_raw.csv`) — `load_bronze.py`'s `latest_dir()` will fall back to the most recent prior landing date if today's dir doesn't exist, masking a fresh failure as stale data; check the bronze row-count log line (`[bronze] <table>: <n> rows`) against the DQD.md baselines (alpha 2,106/50,532, beta ~136,038, gamma 215,063) to catch this.
- Rerun: clear just the failed task group in the Airflow UI (Grid view → task → Clear), which reruns `land()` then `bronze()` for that source only — `bronze()`'s `CREATE OR REPLACE TABLE` is idempotent so reruns are always safe.
- Escalate: if Kaggle/openFDA is down/rate-limited for >1 hour (HIGH SLA) or the row-count drift exceeds the DQD.md alert thresholds (beta shrinking, alpha/gamma row count off-baseline) — escalate to Data Quality Steward before letting `dbt_enrich()` proceed on bad bronze data.

### SCENARIO: DQ CRITICAL fail
- Symptom: `dq_checks()` task FAILED — either the `dbt test` step (severity: error) or `scripts/run_ge_validation.py` exits non-zero/prints `OVERALL: FAIL`.
- Check:
  - dbt test output in the task log for which of the 50 schema tests failed (`dbt/models/**/_*.yml`) — CRITICAL tests are `severity: error` by default (e.g. `drug_sk`/`sales_sk`/`review_sk`/`date_sk`/`condition_sk` uniqueness, `dim_drug_category_row_count` singular test, FK `relationships` tests).
  - If the GE step failed instead, check `data_quality/validations/*_result.json` (written by `run_ge_validation.py`) for which suite (`dim_drug`, `fact_sales`, `fact_review`) and which expectation tripped.
  - **Known gap**: `run_ge_validation.py` connects directly to `data/warehouse.duckdb` (hardcoded `DB_PATH`) — it validates DuckDB only, even when `DBT_TARGET=prod` just ran the dbt tasks against Snowflake. A GE "PASS" during a cloud run does not confirm the Snowflake tables are correct; only the preceding `dbt test` step (which is target-aware) does. This is a documented, not-yet-closed gap — do not assume GE coverage extends to Snowflake.
- Fix 1: a real data defect upstream (e.g. a new unmatched FK, a duplicate key introduced by a source change) — this blocks `severity: error` by design; do not override without Data Quality Steward sign-off. Trace via the failing model's `dbt test` SQL (compiled in `dbt/target/compiled/...`) to find the offending rows.
- Fix 2: a known/accepted exception was mis-classified — e.g. confirm the `stg_beta__ndc.generic_name` warn (3 legitimate brand-only OTC products, documented in `STTM.md`) hasn't silently regressed in row count (still 3, not growing) before assuming it's "fine."
- Rerun: `dbt test --project-dir dbt --profiles-dir dbt` standalone to iterate without rerunning the whole DAG, then clear `dq_checks()` in Airflow once green.
- Escalate: any CRITICAL (severity: error) failure escalates immediately to Data Quality Steward (15-min PagerDuty-sim SLA) — do not manually downgrade a CRITICAL test to unblock the DAG; that requires a documented exception (see DQD.md's pattern for the `generic_name` warn) and Data Quality Steward approval first.

### SCENARIO: dbt model compile/run error (`dbt_enrich` / `dbt_marts` / `dbt_serving`)
- Symptom: `dbt_enrich`, `dbt_marts`, or `dbt_serving` task FAILED with a dbt compile error or a model run failure (not a test failure).
- Check: task log for the dbt error — common causes are a cross-dialect SQL difference between `dev` (DuckDB) and `prod` (Snowflake) targets (DQD.md notes `parse_date`/`regexp_replace_all` macros exist specifically to keep these two targets consistent — a new model bypassing those macros is the likely culprit), or `dbt_marts()`'s ordering dependency: `dbt snapshot` (builds `snap_beta_ndc`) must succeed before `dbt run -s marts.core` builds `dim_drug` from it.
- Fix 1: if `dbt_marts()` fails on `dim_drug` with a missing-relation error, confirm the `dbt snapshot` step actually ran first and succeeded — check the task log for the `snapshot` sub-step before the `run -s marts.core` sub-step (both are in the same Airflow task body, `dbt_marts()`, run sequentially via `subprocess.run` with `check=True`, so the snapshot failing will abort before the run starts).
- Fix 2: a target-specific SQL function used directly instead of through the cross-dialect macro — fix in the model, not by branching logic per target ad hoc.
- Rerun: `dbt run -s staging` / `dbt snapshot && dbt run -s marts.core` / `dbt run -s marts.serving` standalone against `--target dev` first to confirm green locally before clearing the task in Airflow (which will run against whatever `DBT_TARGET` the environment is configured for).
- Escalate: to Senior Data Engineer for a model logic fix; to Data Architect if the fix implies a Data Model change (grain, SCD type) rather than a SQL bug.

### SCENARIO: SLA miss (DAG not done by 07:00)
- Symptom: Airflow's SLA-miss banner/email on `pharma_sttm_pipeline_v1` (`default_args={"sla": SLA, ...}`, 240 min from the 03:00 `schedule="0 3 * * *"`).
- Check: Gantt/Grid view in the Airflow UI to find which task is the bottleneck — most likely the `beta.land` task (full ~136k-row openFDA bulk JSON download, `urlopen(..., timeout=180)`) or a `dbt_marts()` snapshot diffing a large `snap_beta_ndc` history.
- Fix 1: a single source's land/bronze task running long due to upstream slowness (Kaggle/openFDA) — this is expected variance for external dependencies wired directly into a daily schedule; not itself a defect.
- Fix 2: if a step is *systematically* slow (not one-off), this is exactly the class of problem Track B's SLA Gym (`learning/CURRICULUM.md`) is built to diagnose with self-review (critical path analysis) — treat a recurring SLA miss as a signal to run that diagnostic, not just rerun and hope.
- Rerun: N/A for the SLA banner itself (it's informational once the threshold is crossed) — let the DAG finish; investigate root cause for next run.
- Escalate: HIGH (1-hour Slack) on first miss; CRITICAL if it recurs 2+ days running (now a chronic capacity/design problem, not a one-off external dependency hiccup).

## Backfill Procedure
This pipeline has no quarantine table or partition-delete pattern (per DQD.md's "Action on Failure" — HIGH severity is currently null-in-place with `dq_flag`, not a separate quarantine table) and every load is `CREATE OR REPLACE TABLE` (`scripts/load_bronze.py`) — backfill here means **rerun for a given logical date**, not delete-then-reload a partition.

1. Identify the failed logical date (`ds`) from the Airflow UI Grid view.
2. Re-trigger the affected task group(s) (`alpha`/`beta`/`gamma`) for that `ds` — Airflow passes `ds` into `land()`'s `LAND_DIR` and `bronze()`'s `LAND_DATE` env vars automatically on a Clear/rerun, so this re-lands and reloads bronze for that exact date. `bronze()`'s `CREATE OR REPLACE TABLE` makes this idempotent — safe to rerun any number of times.
3. Rerun downstream in order: `dbt_enrich()` (`dbt run -s staging`) → `dbt_marts()` (`dbt snapshot` then `dbt run -s marts.core` — note the snapshot's `check` strategy will NOT close `dbt_valid_to` if a product was delisted from the Beta NDC feed since the last snapshot; this is a known, accepted limitation, not a bug to chase during backfill) → `dbt_serving()` (`dbt run -s marts.serving`) → `dq_checks()` (`dbt test` then `scripts/run_ge_validation.py`).
4. Verify reconciliation against the DQD.md baselines: Bronze row counts exact-match source (alpha 2,106/50,532, beta ~136,038, gamma 215,063); Silver vs Gold row counts exact (`fact_sales` 16,848, `fact_review` 215,063 — unmatched FKs are nulled, not dropped, per ADR-003).
5. **Cloud-window backfill only**: if the backfill happened against `DBT_TARGET=prod` (Snowflake), the last step is tearing down the Snowflake objects — there is **no `scripts/teardown_snowflake.sql`** today (only `scripts/setup_snowflake.sql` provisioning exists). Teardown is manual: `DROP DATABASE NOVARTIS_STTM_DB; DROP WAREHOUSE NOVARTIS_STTM_WH; DROP ROLE NOVARTIS_STTM_ROLE;` as `ACCOUNTADMIN`, executed by Data Platform Engineer immediately after the backfill is verified — do not leave the warehouse running (XSMALL with `AUTO_SUSPEND=60` limits idle cost, but the $3-5/day spike budget assumes same-day teardown, not multi-day idle).

## Session Start Checklist
- [ ] Airflow running locally (aws-mwaa-local-runner at http://localhost:8080 — `airflow`/`airflow` login per `.env.example`)
- [x] **Before any MWAA spike** (parse gate — CLOSED 2026-06-19): MWAA targets a pinned Airflow 2.10.x via the SEPARATE `requirements/requirements-mwaa.txt` (constraints `constraints-2.10.3/3.11`), NOT the dev `.venv` (unpinned 3.x — wrong target). `pharma_sttm_pipeline` parsed CLEAN (zero import errors) on MWAA Airflow 2.10.3 via `aws-mwaa-local-runner` — reproduce on demand with `bash scripts/parse_test_mwaa.sh` ($0, local-only, one-shot DagBag import). The dev `requirements/requirements.txt` still deliberately doesn't pin core Airflow ("match MWAA-provided version, do not override"); the cloud pin lives only in `requirements-mwaa.txt`. NOTE: this closes ADR-005 P5 (parse gate) only — actual MWAA provisioning remains owner-gated and not yet done.
- [ ] `.env` populated from `.env.example` (Kaggle creds, and `SNOWFLAKE_*`/`AWS_*` only if working the cloud window)
- [ ] Local tooling / data connections verified

## Session End Checklist
- [ ] Update `PROJECT_STATUS.md`
- [ ] Commit changes
- [ ] Stop expensive services — if a Snowflake/MWAA cloud window was opened this session, confirm teardown happened (manual Snowflake teardown per Backfill Procedure step 5; no MWAA environment exists yet, but once one does, delete it the same day — MWAA has no free tier, ~$0.49/hr ≈ $350+/mo if left running)
