# Architecture Handbook (AH) — Novartis Pharma STTM Lab

> Single consolidated source of truth for pipeline architecture. In an enVision-style
> role this is owned, consolidated from project teams, and uploaded to Confluence. Here
> it lives in git (version-controlled clone of that responsibility).

**Version:** 3.0 · **Owner:** Data Architect · **Last approved:** 2026-06-19 (Data Architect — post-migration refresh; ADR-005 now MIGRATED & LIVE)

> **Lead Deliverable owned by Data Architect.** Ships to Confluence only after
> Data Architect sign-off; Data Platform Engineer runs `scripts/publish_to_confluence.py`,
> Project Manager logs the event in `SIGN_OFF_LOG.md`. **Filling ≠ approval** — this
> draft returns to Data Architect for review before any publish.

---

## 1. Purpose & Scope
This handbook governs the **currently-running** pipeline: a 3-source pharma data-consolidation
build (Alpha sales, Beta NDC product master, Gamma drug reviews) flowing through a 4-tier
enVision topology (Landing → Bronze → Enrich → Gold) into a Kimball star + OBT serving layer.
As of **2026-06-19** the **ADR-005 S3-canonical / DuckDB-ephemeral architecture is MIGRATED and LIVE
on real AWS**, verified end-to-end (run_id `run-20260619-045115`). Storage is **S3-canonical**
(`s3://novartis-pharma-sttm-lake/`, ap-southeast-1), compute is **ephemeral DuckDB via `httpfs`**
reading/writing S3 parquet, Silver/Gold are dbt-duckdb **`external`** materializations, and a
**Snowflake external-table veneer** serves the OBTs read-only. Orchestration remains on local
`aws-mwaa-local-runner` (MWAA is **not** stood up).

- **In scope:** the as-built **MIGRATED** pipeline (ingestion → S3 landing → S3 bronze parquet →
  enrich → data mart → RRD → Snowflake external-table serving), its local orchestration, quality
  gates, naming, and lineage.
- **Historical / superseded:** the original **DuckDB-local-file** build (persistent `warehouse.duckdb`,
  relational `bronze.x` tables, `table`/`incremental` materializations) was the pre-ADR-005
  predecessor. It is retained as history in §3b and is **no longer what runs**. Earlier Data Architect
  ruling R1 (2026-06-18) — "do not document an unmigrated target as current state" — is now satisfied
  by the inverse: the migration is done, so the as-built section below describes S3-canonical reality.
- **Out of scope:** Track B SLA gym (`docs/sla/`), the MWAA spike (P4/P5, not in play this round),
  Confluence publishing mechanics.

## 2. Architecture Principles (org standards)
- **Layered flow:** **Bronze → Enrich (Silver) → Data Mart (Gold) → Serving/RRD.** Logic lives at
  the right layer; no business rules in Bronze, no source-of-truth in RRD.
- **Star is the system of record; OBT is derived and rebuildable** from the star — never sourced
  directly (ADR-001).
- **Honest partial-match.** Crosswalk coverage (`dim_drug` NDC↔ATC, free-text name match) is a
  tracked DQD KPI, **never forced to 100%**; unmatched rows are kept and flagged, not dropped (ADR-003).
- **Idempotent, re-runnable tasks** — every layer rebuilds deterministically from Landing (the replay
  source); `dbt build` reproduces the whole warehouse from a dropped file.
- **Every dataset has an owner and documented lineage** — the source-to-target map is `docs/sttm/STTM.md`.
- **Least-privilege RBAC.** No `GRANT ALL`, no `FUTURE` grants; a role owns what it creates (ADR-004).
  *Non-negotiable — Data Architect Phase-4 veto.* As-built the serving veneer uses a **new, separate,
  read-only** role `snowflake_gold_reader` (`USAGE` on `s3_gold_integration` + `SELECT` on the external
  tables), deliberately **not** widening `NOVARTIS_STTM_ROLE` (ADR-005 Decision 3 — keeps the reader's
  object class distinct from the transformer's, per the ADR-004 owner-vs-scoped-grant split).
- **Quality gates before any downstream consumption** — dbt tests + Great Expectations per layer.

## 3. Layer Definitions — AS-BUILT (S3-canonical + DuckDB httpfs + external materialization + Snowflake veneer · MIGRATED & LIVE 2026-06-19)
> **Status: AS-BUILT — ADR-005 MIGRATED & LIVE on real AWS, verified end-to-end 2026-06-19**
> (run_id `run-20260619-045115`; dbt build PASS=63/WARN=1/ERROR=0, GE PASS, KPIs identical to baseline).
> Storage is S3-canonical (`s3://novartis-pharma-sttm-lake/`, ap-southeast-1); compute is ephemeral
> DuckDB via `httpfs`. **MWAA is OUT** — orchestration is local `aws-mwaa-local-runner`. The design
> basis is `docs/ADR/ADR-005-build-decisions.md` (six build decisions, all implemented as-built).

| Layer | Purpose | Tool (as-built, MIGRATED) | Owner |
|-------|---------|---------------------------|-------|
| Landing | Raw files exactly as received, immutable, **versioned, write-once** (policy-enforced), partitioned by source + load date. No parsing. | Python ingest → `s3://novartis-pharma-sttm-lake/landing/{alpha,beta,gamma}/<date>/` | Data Engineer |
| Bronze | Raw → **S3 parquet** + load metadata (`load_ts`, `source_file`). No business logic. Per-`<date>` deterministic overwrite. | `scripts/load_bronze.py` → `bronze/<src>/<date>/*.parquet` (DuckDB httpfs write) | Data Engineer |
| Enrich (Silver) | Dedupe, type-cast, standardize naming, conform per-source. Still per-source. Staging reads `read_parquet('s3://.../bronze/<src>/<date>/...')` (no relational `bronze.x`). | dbt-duckdb **`external`** parquet on S3 (`silver/`) for `stg_*`; `snap_beta_ndc` SCD2 externalized to `snapshots/snap_beta_ndc/`; `int_drug_crosswalk` ephemeral CTE | Analytics Engineer |
| Data Mart (Gold) | Kimball star: conformed `dim_drug` SCD2 + crosswalk, `dim_date`, `dim_condition`, `fact_sales`, `fact_review`. | dbt-duckdb **`external`** parquet → `gold/<run_id>/`, verified, copy-into immutable `gold/_current/` (Decision 1, mechanism B). Facts = **full deterministic rebuild** (Decision 5, `incremental` dropped). | Data Architect + Analytics Engineer |
| Serving / RRD (veneer, LIVE) | Reporting-ready denormalized OBT, rebuilt from the star, served read-only over the lakehouse. | Snowflake `STORAGE INTEGRATION s3_gold_integration` + scoped role `snowflake_gold_reader` (ADR-005 Decision 3) + `gold_stage`→`gold/_current/` + **external tables** `obt_sales_wide_ext` (16,848 rows) / `obt_review_wide_ext` (215,063 rows) reading the same S3 Gold | Analytics Engineer |

**enVision mapping:** Bronze = Raw (S3 parquet) · Enrich = Silver (staging + intermediate, S3 external) · Data Mart = Gold (star, S3 external + `_current/` pointer) · RRD = serving (OBT via Snowflake external tables).

**Snowflake holds ZERO dbt-written tables.** The veneer is external-table-only ("warehouse over lakehouse"); the S3 Gold parquet is the single source of truth. Old Snowflake transform artifacts (`dim_date`/seed from the earlier failed prod build) are **not** part of the veneer and are not authoritative.

### 3a. Migration evidence (as-built verification, 2026-06-19)
> **Status: LIVE — verified end-to-end, numbers identical to the pre-migration baseline.**

- **dbt build**: PASS=63 / WARN=1 / ERROR=0. **Great Expectations**: PASS.
- **KPIs identical to baseline** (proving the migration changed substrate, not semantics):
  `fact_review` = 215,063 · `dim_drug` = 133,654 (SCD2) · `fact_sales` = 16,848 · `drug_sk` coverage = 71.9% · `condition_sk` coverage = 98.9%.
- **Gold publish**: write `gold/run-20260619-045115/` → verify → copy-into `gold/_current/`; Snowflake external tables read `gold/_current/` only (ADR-005 Decision 1).
- **Storage guardrails live**: versioning ON, 30-day noncurrent-version expiry, `aws:RequestedRegion` Deny (region-locked to ap-southeast-1), `landing/` delete-deny (write-once) — all per ADR-005 Decision 4.
- **Snapshot state externalized** to `snapshots/snap_beta_ndc/` parquet (ADR-005 Decision 2 — the one accepted persistent *data* store; the DuckDB catalog remains ephemeral).

The **logical model is UNCHANGED** by ADR-005 — same tables, keys, grains, and SCD types as the ERD.
Only the physical substrate moved (relational DuckDB → S3 parquet + external materialization + a
Snowflake external-table read veneer). The ERD did not need re-cutting (no grain/key change).

### 3b. Historical / superseded — the original DuckDB-local-file build (pre-ADR-005)
> **Status: SUPERSEDED 2026-06-19. Retained for history; NOT what runs.**

Before the ADR-005 migration the pipeline ran entirely on a local persistent DuckDB file:
Landing on local disk (`data/landing/...`), Bronze as relational `bronze.*` DuckDB tables
(`scripts/load_bronze.py` writing into the catalog), Silver/Gold as dbt-duckdb `table`/`incremental`
materializations inside a persistent `warehouse.duckdb`, and OBTs as local `table` models with no
external serving layer. ADR-005 pivoted **storage** (not the logical model) to S3-canonical +
ephemeral DuckDB compute; that pivot is now complete (§3 / §3a). This paragraph is the only place the
local-file build is described — everywhere else "as-built" means the MIGRATED S3 architecture.

## 4. End-to-End Data Flow (lineage)
Matches the ERD exactly — no invented nodes.
All paths are S3 prefixes under `s3://novartis-pharma-sttm-lake/`; bronze nodes are `read_parquet('s3://.../bronze/<src>/<date>/...')`, not relational `bronze.x`.
```
Alpha (Kaggle sales CSV) ─► landing/alpha ─► bronze/alpha/<date>/*.parquet ─► stg_alpha__sales ┐
Beta  (openFDA NDC zip)  ─► landing/beta  ─► bronze/beta/<date>/*.parquet  ─► stg_beta__ndc ─► snap_beta_ndc (SCD2, snapshots/) ┐
Gamma (UCI reviews CSV)  ─► landing/gamma ─► bronze/gamma/<date>/*.parquet ─► stg_gamma__reviews ┐                  │
                                                                                │                  │
                              int_drug_crosswalk (ephemeral) ◄── stg_beta__ndc ─┘                  │
                                                                                                   ▼
                                          dim_drug (SCD2, conformed) ◄── snap_beta_ndc + int_drug_crosswalk
                                          dim_date · dim_condition
                                                  │
                                          fact_sales · fact_review   (STAR)
                                                  │
                                          obt_sales_wide · obt_review_wide   (RRD, derived)
                                                  │
                  Snowflake external tables  obt_sales_wide_ext · obt_review_wide_ext  (serving veneer, reads gold/_current/)
```
Divergence ends at Enrich; **Gold is the single consolidated, governed layer** (conformed `dim_drug`),
materialized as S3 parquet under `gold/<run_id>/` and published to `gold/_current/`. The Snowflake
external tables read `gold/_current/` only (read-only veneer). Full column-level mapping:
`docs/sttm/STTM.md`. Physical model: `docs/erwin/ERD.md`.

## 5. Orchestration & SLA
- DAG: `airflow/dags/pharma_sttm_pipeline.py` — every task shells out to the real `scripts/`/`dbt`
  commands (no stubs).
- **SLA:** consolidated daily pipeline complete by **07:00** (03:00 start → 240-min budget). Critical
  path / Gantt analysis: `docs/sla/SLA_ANALYSIS.md`.
- Recovery: Landing (S3, versioned, write-once) is the replay source (RPO = last landed batch).
- **Orchestration host:** local `aws-mwaa-local-runner` (localhost:8080) — the same DuckDB ELT that
  will run on MWAA. **MWAA is NOT stood up** this round; P4/P5 (the MWAA Airflow-version gates) are
  not in play. The DAG parses clean against pinned MWAA 2.10.3 (`requirements-mwaa.txt`, parse gate
  CLOSED 2026-06-19) — the version gap is resolved on the local runner; the actual MWAA spike remains
  a deferred, owner-gated future step. Not papered over.

## 6. Standards & Conventions (enforced)
| Object | Convention | Example |
|--------|-----------|---------|
| Staging | `stg_<source>__<entity>` (double underscore) | `stg_beta__ndc` |
| Intermediate | `int_<noun>` | `int_drug_crosswalk` |
| Snapshot | `snap_<source>_<entity>` | `snap_beta_ndc` |
| Dimension | `dim_<entity>` | `dim_drug` |
| Fact | `fact_<process>` | `fact_sales` |
| Serving / OBT | `obt_<subject>_wide` | `obt_sales_wide` |
| Seed | `<domain>_crosswalk` | `atc_pharmclass_crosswalk` |
| Surrogate key | `_sk` suffix; **varchar MD5 hash** (`date_sk` is the `YYYYMMDD` int exception) | `drug_sk`, `date_sk` |
| Business/natural key | keep source name | `product_ndc`, `atc_code` |
| Audit columns | `load_ts`, `source_file` | — |
| DQ columns | `dq_flag`, `dq_reason` | — |

## 7. Consolidation Log (who contributed what)
| Date | Project team | Input gathered | Validated? | Merged into AH? |
|------|--------------|----------------|-----------|-----------------|
| 2026-06-18 | Alpha (sales) | Kaggle pharma-sales daily CSV; 8 ATC categories, unpivoted | ✅ (49/50 dbt tests) | ✅ §3/§4 |
| 2026-06-18 | Beta (NDC) | openFDA bulk NDC directory (136,038 products) → SCD2 master | ✅ (1 documented warn) | ✅ §3/§4 |
| 2026-06-18 | Gamma (reviews) | UCI drug reviews (215,063 rows); free-text drug/condition, DQ-scrubbed | ✅ (GE + integration tests) | ✅ §3/§4 |
| 2026-06-19 | ADR-005 migration (all 3) | Lift to S3-canonical (`novartis-pharma-sttm-lake`) + ephemeral DuckDB httpfs + `external` parquet + Snowflake external-table veneer; run_id `run-20260619-045115` | ✅ (dbt 63 PASS/1 WARN/0 ERR, GE PASS, KPIs == baseline) | ✅ §3/§3a/§3b |

## 8. Open Questions
- ADR-005 migration — **DONE & LIVE 2026-06-19** (no longer open). S3-canonical storage, ephemeral
  DuckDB httpfs compute, `external` materialization, and the Snowflake external-table veneer are all
  in production (§3 / §3a). **MWAA remains OUT** — the only outstanding ADR-005 item is the deferred,
  owner-gated MWAA spike (P4/P5); orchestration stays on local `aws-mwaa-local-runner` until then.
- Beta-side seed coverage — `atc_pharmclass_crosswalk` seed covers only 8 ATC categories (4.1% NDC
  seed reach). Raising it is a Business Analyst call (separate number from the 71.9% match-quality KPI).
- Confluence RE-PUBLISH — this v3 (and the refreshed ERD v2 / STTM v3) supersede the
  2026-06-18 published versions, which now describe a stale pre-migration state. Re-publish is
  Data Platform Engineer's next step after this Data Architect re-sign-off (see `SIGN_OFF_LOG.md`).
