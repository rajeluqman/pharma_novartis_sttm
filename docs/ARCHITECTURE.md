# ARCHITECTURE.md
**Owners**: Data Architect + Senior Data Engineer
**Stack**: HYBRID (dev local · deploy AWS MWAA + Snowflake short window) — see ARCHITECTURE.md
**ADRs**: ADR-001 (star+OBT) · ADR-002 (4-tier landing) · ADR-003 (conformed dim_drug)

---

## 1. Architecture Diagram (4-tier, 3-source convergence)

```
 SOURCES (divergent)        LANDING        BRONZE          ENRICH (Silver)     GOLD (Data Mart + RRD)
 ──────────────────         ───────        ──────          ───────────────     ──────────────────────
 Alpha  Kaggle sales  ─►  landing/alpha ─► bronze.alpha ─► enrich.alpha  ┐
 Beta   openFDA NDC   ─►  landing/beta  ─► bronze.beta  ─► enrich.beta   ┼─► STAR ───► OBT (serving)
 Gamma  UCI reviews   ─►  landing/gamma ─► bronze.gamma ─► enrich.gamma  ┘   dim_drug    obt_sales_wide
                          (immutable raw)  (+load meta)    (clean,divergent)  (SCD2)      obt_review_wide
                                                                              fact_sales
                                                                              fact_review
 enVision:  Source    →   Landing        →  Bronze       →  Enrich          →  Data Mart  →  RRD
```
Divergence ends at Enrich; Gold is the single consolidated, governed layer (conformed `dim_drug`).

## 2. Tool Selection (with justification)

| Layer | Dev (local) | Cloud (artifact) | Why |
|-------|-------------|------------------|-----|
| Ingestion | Python (Kaggle CLI, requests/openFDA) | same | 3 source shapes: CSV, REST API, CSV |
| Landing | `data/landing/` files | S3 prefixes | immutable raw, replay/audit |
| Bronze/Storage | DuckDB | Snowflake raw | columnar; ACID |
| Transform | dbt Core | dbt → Snowflake | staging→intermediate→marts; one codebase, two targets |
| Orchestration | aws-mwaa-local-runner | AWS MWAA | runtime parity → clean transition (ADR-002) |
| Quality | Great Expectations | same | per-layer suites + crosswalk coverage KPI |
| Modeling | dbdiagram.io (Erwin clone) | same | Enrich/Data Mart/RRD ERD |

## 3. Layer Responsibilities
- **Landing**: raw files exactly as received, immutable, partitioned by source + load date. No parsing.
- **Bronze**: load raw → table + metadata (`load_ts`, `source_file`, `batch_id`). No business logic.
- **Enrich (Silver)**: dedupe, type-cast, standardize naming, conform per-source. Pass DQ. Still per-source.
- **Gold**: consolidate → star (`dim_drug` SCD2 + crosswalk, facts) → OBT serving. Governance + STTM target.

## 4. Non-Functional Requirements
- **SLA**: consolidated daily pipeline complete by **07:00** (03:00 start → 240-min budget).
- Recovery: Landing is replay source (RPO = last landed batch).
- Cost: local-first; cloud only in a teardown-bound artifact window (~$3–5/spike).

## 5. ADRs
See `docs/ADR/` — ADR-001, ADR-002, ADR-003.

## 6. Cost Estimate
| Resource | Cost/run | Notes |
|----------|----------|-------|
| Dev (local) | $0 | DuckDB + mwaa-local-runner |
| MWAA spike | ~$3–5 | same-day create→run→**teardown** |
| Snowflake | trial | $400 credits / 30 days |
