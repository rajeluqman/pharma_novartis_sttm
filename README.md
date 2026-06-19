# Helvetia Pharma Commercial — enVision Architecture / STTM Lead

A Data Engineering portfolio simulation of a pharma **Architecture / STTM Governance Lead** role:
three real datasets, ingested and modeled to three deliberately different standards by three
"teams," then reconciled by one Lead into a single governed star + OBT data mart with full
column-level lineage.

## Overview
This is not a hands-on-Spark showcase — it's a governance showcase. The JD this simulates weights
**40% STTM governance · 30% documentation governance · 20% data-model governance · 10% DAG
analysis**, so the substrate pipelines (Alpha/Beta/Gamma below) are kept deliberately thin while the
consolidation work — one conformed `dim_drug` crosswalk, one source-to-target mapping, one Erwin-style
model, one daily DAG meeting a 7AM SLA — is the actual deliverable. Stack: dbt Core + DuckDB (dev) /
Snowflake (cloud artifact) + Airflow + Great Expectations, developed under a disciplined review
process with explicit architecture and data-quality sign-off gates at every phase — real veto
power over design decisions, not a rubber stamp.

## The Scenario

You've just joined the Architecture / STTM governance team at **Helvetia Pharma AG**
(fictional), which runs the **enVision** commercial analytics platform. Three project
teams have each shipped a pipeline from a different real pharma data source — built to
three different standards. None of them agree on what "a drug" even is: one team
identifies it by ATC code, another by NDC code + pharmacologic class, the third by
free-text drug name. Your task as the incoming Architecture/STTM Lead is not to rebuild
their pipelines — it's to **review, reconcile, and consolidate** their mappings, models,
and architecture into one governed warehouse, and guarantee the consolidated data is
ready by **07:00** every morning.

The business needs this data to answer questions like:
- Can the three sources' columns (Alpha sales, Beta NDC, Gamma reviews) consolidate into one source-to-target mapping with full lineage?
- How do we reconcile three different definitions of "a drug" into one conformed `dim_drug`?
- If a number in the Data Mart looks wrong, which layer do we trace back to find the root cause?
- What is the data freshness and completeness for each of the three sources?

## Architecture

No rendered diagram exists yet — `docs/erwin/ERD.md` is filled and architecture-approved (see
Business Questions below), but it's a DBML/Erwin-style text spec, not a rendered image — here's the
real topology this build implements, straight from `PROJECT_BRIEF.md`:

```
 SOURCES (divergent)      LANDING          BRONZE         ENRICH (Silver)    GOLD (Data Mart + RRD)
 Alpha sales (CSV)   ─► landing/alpha ─► bronze.alpha ─► enrich.alpha ┐
 Beta  NDC (API)     ─► landing/beta  ─► bronze.beta  ─► enrich.beta  ┼─► STAR ───► OBT serving
 Gamma reviews (CSV) ─► landing/gamma ─► bronze.gamma ─► enrich.gamma ┘   dim_drug    obt_sales_wide
                        (immutable raw)  (+load meta)   (clean, per-src)   SCD2        obt_review_wide
```

Divergence lives in Landing/Bronze/Enrich (three separate sets — the substrate). Convergence and
governance live in Gold: one conformed `dim_drug` SCD2 + crosswalk, with an OBT layer materialized
from the star for BI. As of ADR-005, every tier above is physically S3-canonical parquet
(`s3://novartis-pharma-sttm-lake/{landing,bronze,silver,gold}/...`), read/written via DuckDB httpfs;
Snowflake reads only the published `gold/_current/` files through external tables. See `docs/ADR/`
for the five accepted ADRs governing this (star+OBT, 4-tier landing, conformed crosswalk, Snowflake
least-privilege RBAC, S3-canonical storage pivot).

> **Note**: `ADR-005` (S3-canonical storage pivot) is **migrated and live on real AWS as of
> 2026-06-19** (run_id `run-20260619-045115`). Storage is now S3-canonical across all tiers
> (`s3://novartis-pharma-sttm-lake/`), DuckDB is ephemeral httpfs-only compute, and Snowflake is
> demoted to a read-only external-table serving veneer over `gold/_current/`. Verified end-to-end:
> dbt build PASS=63/WARN=1/ERROR=0, Great Expectations PASS, KPIs identical to the pre-migration
> baseline. Everything below describes this as-built, migrated state. MWAA orchestration is the one
> piece still not stood up — the DAG runs locally via `aws-mwaa-local-runner` only.

## Tech Stack
| Layer | Tool |
|-------|------|
| Ingestion | Python (Kaggle CLI for Alpha/Gamma; openFDA bulk-zip download for Beta) |
| Storage (current) | **S3-canonical** — `s3://novartis-pharma-sttm-lake/` (`ap-southeast-1`), versioned + lifecycle-managed, all 4 tiers (landing/bronze/silver/gold) as parquet. Migrated live 2026-06-19 (ADR-005) |
| Compute | DuckDB via httpfs — ephemeral catalog, no persistent `warehouse.duckdb` as source of truth; dbt Core models target it through dbt-duckdb's `external` materialization |
| Serving | **Snowflake external-table veneer** — `STORAGE INTEGRATION` + scoped `snowflake_gold_reader` role reading `gold/_current/` directly (`obt_sales_wide_ext` 16,848 rows, `obt_review_wide_ext` 215,063 rows); zero dbt-written tables in Snowflake |
| Orchestration | Apache Airflow — `aws-mwaa-local-runner` (dev, localhost:8080); AWS MWAA **not yet deployed** (parse-gate closed, stand-up still owner-gated) |
| Data Quality | dbt tests (schema + singular) + Great Expectations |
| Modeling | dbdiagram.io (Erwin clone) |
| Publish | Markdown → Confluence (`scripts/publish_to_confluence.py`), gated behind `Data Architect` approval — run twice (2026-06-18 initial publish, 2026-06-19 post-migration re-publish) |

No Databricks, PySpark, or Delta Lake in this build — outside the locked stack (see `ARCHITECTURE.md`).

## Business Questions Answered

This project is governance-weighted, so most answers are KPIs + documents, not single SQL queries.
Honest status as of the ADR-005 migration pass (2026-06-19) — including the items that are still
**not** actually exercised yet:

### Group A — STTM Governance (~40%)
| # | Question | KPI / Target | Status | Evidence |
|---|----------|--------------|--------|----------|
| G1 | Do all three sources' columns consolidate into ONE STTM with full lineage? | 100% of Enrich/Mart/RRD columns mapped, 0 orphans | ✅ Done — v3.0 (refreshed post-migration; lineage rows unchanged) | [`docs/sttm/STTM.md`](docs/sttm/STTM.md) |
| G2 | How do you reconcile three "what is a drug" definitions into one dimension? | One approved `dim_drug` + crosswalk, coverage % tracked | ✅ Done (partial coverage, by design — see caveats) | `int_drug_crosswalk` model, [`docs/DQD.md`](docs/DQD.md) |
| G3 | A Data Mart field looks wrong — where do you trace it? | Documented backward-trace pattern | ⏳ Pattern exists in STTM (source→target per column); no live drill run yet | [`docs/sttm/STTM.md`](docs/sttm/STTM.md) |
| G4 | A source schema changes (NDC adds/withdraws) — how does STTM stay accurate? | Versioned STTM + re-validated lineage on change | ⏳ Versioning convention in place (STTM now at v3.0); no simulated NDC delta drill run yet | — |

### Group B — Documentation Governance (~30%)
| # | Question | KPI / Target | Status | Evidence |
|---|----------|--------------|--------|----------|
| D1 | Consolidate all three teams' architecture into ONE Architecture Handbook | Approved `AH.md`, `Data Architect` sign-off | ✅ Done — v3.0, architecture-approved, Confluence-published (page 131460, v3) | [`docs/architecture_handbook/AH.md`](docs/architecture_handbook/AH.md) |
| D2 | Version control + changelog discipline across AH and STTM | Every published doc carries version + approver + date | ✅ Done — both carry version + approver + date (AH v3.0, STTM v3.0), bumped again on the post-migration refresh | — |

### Group C — Data-Model Governance (~20%)
| # | Question | KPI / Target | Status | Evidence |
|---|----------|--------------|--------|----------|
| M1 | One governed model across all three teams' tables | One Erwin-style ERD across Enrich/Mart/RRD | ✅ Done — v2.0, architecture-approved, Confluence-published (page 98553, v2); logical model unchanged by the ADR-005 migration | [`docs/erwin/ERD.md`](docs/erwin/ERD.md) |
| M2 | How do you model NDC products added/withdrawn over time? | SCD Type 2 on `dim_drug` | ✅ Done — real `dbt snapshot` (check strategy), now externalized to `s3://novartis-pharma-sttm-lake/snapshots/` | `dbt/snapshots/`, [ADR-003](docs/ADR/) |

### Group D — DAG Analysis (~10%)
| # | Question | KPI / Target | Status | Evidence |
|---|----------|--------------|--------|----------|
| S1 | Does the consolidated daily pipeline finish before 07:00? | Runtime vs. 240-min budget, critical path identified | ⏳ DAG fully wired (real subprocess calls); never run end-to-end against a live scheduler — no runtime measured yet | [`airflow/dags/pharma_sttm_pipeline.py`](airflow/dags/pharma_sttm_pipeline.py) |

**Honest summary**: the STTM and SCD2 work (the largest JD weight, 40%+20%) is genuinely done and
review team-reviewed. The Architecture Handbook and Erwin ERD (30%+20% combined) are filled,
architecture-approved, and Confluence-published (see Documentation below). DAG analysis (10%)
is wired but still unexercised against a live scheduler.

## Build Evidence

No real screenshots exist yet (`docs/screenshots/` has only placeholder instructions) — rather than
fake a "Build Evidence" gallery, here's what's actually verifiable right now. Row counts below are
the verified baseline (last re-checked pre-migration against the local DuckDB build); the ADR-005
migration re-ran the full pipeline against real S3 and reproduced these same numbers exactly
(dbt build PASS=63/WARN=1/ERROR=0, GE PASS):

| Layer | Verified state |
|-------|-----------------|
| Landing | All 3 sources landed, now S3-canonical (`s3://novartis-pharma-sttm-lake/landing/{alpha,beta,gamma}/...`) |
| Bronze | Exact row-count match to source: alpha 2,106/50,532 · beta 136,038 · gamma 215,063 — parquet on S3 |
| Enrich (Silver) | `stg_alpha__sales` (16,848 unpivoted), `stg_beta__ndc` (133,646 deduped), `stg_gamma__reviews` (215,063) — S3 `external` materialization |
| Data Mart (Gold) | `dim_drug` = 133,654 rows (133,646 `ndc_product` + 8 `atc_category`); `fact_sales` = 16,848; `fact_review` = 215,063 — published to `gold/<run_id>/` then promoted to `gold/_current/` |
| RRD / Serving | `obt_sales_wide`, `obt_review_wide` materialized on S3; also exposed in Snowflake as external tables `obt_sales_wide_ext` (16,848 rows) / `obt_review_wide_ext` (215,063 rows) |
| dbt run | All models green against real S3 + DuckDB httpfs, reproducible from a clean run |
| Tests | 50 dbt tests (49 pass, 1 documented `warn`) + 9 Python integration tests, all passing |
| Great Expectations | 3/3 suites passing (`dim_drug`, `fact_sales`, `fact_review`) |
| Airflow run | **Not yet executed** — DAG is wired for real but has never run against a live scheduler; MWAA itself not stood up |
| Confluence publish | **Done** — AH (page 131460, v3), ERD (page 98553, v2), STTM (page 98534, v3), space NSL, refreshed 2026-06-19 to reflect the migrated state |

## Performance Optimizations
None logged yet — data volume at this scale (max ~215k rows) runs in low single-digit seconds on
DuckDB (now via httpfs against S3 rather than a local file), so no performance wall has been hit
that required an optimization pass. This section will fill in honestly if/when Track B's SLA-gym
work surfaces one (`docs/sla/SLA_ANALYSIS.md`) — no new perf numbers are claimed here beyond the
verified baseline above.

## Data Quality
- **dbt tests**: 50 (schema + 1 singular row-count test) — 49 pass, 1 documented `warn`
  (3 NDC products with `brand_name` but no `generic_name` — real data, not a bug)
- **Great Expectations**: 3/3 suites passing (`dim_drug`, `fact_sales`, `fact_review`)
- **Integration tests**: 9/9 passing (`tests/integration/test_pipeline_reconciliation.py`) — source→Bronze exact match, Bronze→Silver within 5% drop tolerance, Silver→Gold grain preservation
- **Coverage KPIs** (re-verified live against the warehouse during this Phase 5 pass):

| Metric | Result |
|--------|--------|
| Beta NDC products matched to an ATC code (seed reach, not match quality) | 4.1% (5,524/133,646) |
| Beta NDC products flagged as combination products | 7.3% (9,805/133,646) |
| `fact_sales` date_sk / drug_sk resolution | 100% / 100% |
| `fact_review` date_sk resolution | 100% |
| `fact_review` drug_sk resolution (free-text match quality) | 71.9% (154,641/215,063) — SLA floor ≥65% |
| `fact_review` condition_sk resolution | 98.9% (212,698/215,063) — target ≥90% |

Full detail and the rationale for each threshold: [`docs/DQD.md`](docs/DQD.md).

## How to Run
```bash
# 1. Setup
cp .env.example .env   # fill in Kaggle creds; SNOWFLAKE_*/AWS_* required for the S3-canonical target
pip install -r requirements/requirements.txt

# 2. Land + load each source manually (no Airflow scheduler required for this)
bash scripts/ingest_alpha_sales.sh
python scripts/ingest_beta_ndc.py
bash scripts/ingest_gamma_reviews.sh
python scripts/load_bronze.py   # writes to s3://novartis-pharma-sttm-lake/bronze/ via DuckDB httpfs

# 3. Run the dbt pipeline (S3-canonical target — dbt-duckdb `external` materialization)
cd dbt
dbt snapshot --target dev   # snapshot externalized to s3://.../snapshots/
dbt run --target dev
dbt test --target dev

# 4. Validate with Great Expectations
cd ..
python scripts/run_ge_validation.py

# Or run the whole thing via Airflow (aws-mwaa-local-runner, localhost:8080) — MWAA itself not yet deployed
# DAG: pharma_sttm_pipeline — see airflow/dags/pharma_sttm_pipeline.py
```

## Repo Structure
```
novartis_pharma_sttm_dag_lab/
├── airflow/dags/pharma_sttm_pipeline.py   # Orchestration — alpha/beta/gamma land+bronze, dbt_enrich, dbt_marts, dbt_serving, dq_checks
├── scripts/                               # Ingestion (ingest_*), bronze load, GE runner, Snowflake setup
├── dbt/
│   ├── models/staging/{alpha,beta,gamma}  # Enrich (Silver)
│   ├── models/intermediate/               # int_drug_crosswalk (ephemeral)
│   ├── models/marts/core/                 # Data Mart star — dim_drug (SCD2), dim_date, dim_condition, fact_sales, fact_review
│   ├── models/marts/serving/              # RRD / OBT — obt_sales_wide, obt_review_wide
│   ├── snapshots/                         # dbt snapshot for dim_drug SCD2 (externalized to S3 snapshots/)
│   └── profiles.yml                       # dev=DuckDB (httpfs, S3-canonical), prod=Snowflake (external-table veneer) via DBT_TARGET
├── data_quality/expectations/             # Great Expectations suites (dim_drug, fact_sales, fact_review)
├── tests/integration/                      # Source→Bronze→Silver→Gold reconciliation tests
├── cheatsheets/                            # Personal references built while working
├── docs/
│   ├── ADR/                                # ADR-001..005 (ADR-005 = S3-canonical pivot, migrated & live)
│   ├── sttm/STTM.md                        # Source-to-target mapping (real, v3.0, post-migration refresh)
│   ├── architecture_handbook/AH.md         # Architecture Handbook (real, v3.0, architecture-approved)
│   ├── erwin/ERD.md                        # Erwin-style model (real, v2.0, architecture-approved)
│   ├── DQD.md, DATA_DICTIONARY.md          # Data quality definitions + dictionary
│   ├── OPS_RUNBOOK.md                      # On-call playbooks
│   └── INTERVIEW_GUIDE.md                  # Interview prep, sourced from real logs
```

## Documentation
- [BRD](docs/BRD.md) / [DRD](docs/DRD.md) — Business + data requirements
- [Architecture](docs/ARCHITECTURE.md) · [Pipeline Spec](docs/PIPELINE_SPEC.md) · [Data Model](docs/DATA_MODEL.md)
- [ADRs](docs/ADR/) — architecture decisions, including ADR-005 (S3-canonical storage pivot — migrated & live 2026-06-19)
- [STTM](docs/sttm/STTM.md) — source-to-target mapping (real, v3.0, post-migration refresh)
- [DQD](docs/DQD.md) / [Data Dictionary](docs/DATA_DICTIONARY.md) — data quality rules + coverage KPIs
- [OPS Runbook](docs/OPS_RUNBOOK.md) — monitoring, alert SLAs, playbooks, backfill procedure
- [Interview Guide](docs/INTERVIEW_GUIDE.md) — STAR stories, decision logic, resume bullets, all sourced from real logs
- [Debate Log — Phase 4](docs/DEBATE_LOG_phase_4.md) — a real, contested peer review (2 hard vetoes, 2 soft vetoes, all resolved)

## Author
rajeluqman
