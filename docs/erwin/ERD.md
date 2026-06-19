# Erwin Data Model (ERD) — Novartis Pharma STTM Lab

> Erwin is a proprietary data-modeling tool. This is a free clone using **dbdiagram.io**
> DBML. Paste the block below into https://dbdiagram.io to render the ER diagram, then
> export a PNG into this folder. Covers the enVision layers: **Enrich / Data Mart / RRD**.

**Version:** 2.0 · **Owner:** Data Architect · **Last filled:** 2026-06-18 · **Last approved:** 2026-06-19 (post-migration refresh — physical layer now S3 external parquet; logical model unchanged)

> **Lead Deliverable owned by Data Architect.** Ships to Confluence only after
> Data Architect sign-off; Data Platform Engineer runs `scripts/publish_to_confluence.py`,
> Project Manager logs the event in `SIGN_OFF_LOG.md`. **Filling ≠ approval** — this
> draft returns to Data Architect for review before any publish.

> **Status: AS-BUILT — ADR-005 MIGRATED & LIVE 2026-06-19.**
> The **logical model below is UNCHANGED** — same tables, keys, grains, and SCD types as before the
> migration. Only the **physical layer** moved: Silver/Gold are now dbt-duckdb **`external` parquet on
> S3** (`s3://novartis-pharma-sttm-lake/{silver,gold}/`), staging reads
> `read_parquet('s3://.../bronze/<src>/<date>/...')` instead of relational `bronze.x`, `snap_beta_ndc`
> SCD2 history is externalized to `snapshots/snap_beta_ndc/`, and `fact_*` are full deterministic
> rebuilds (the `incremental` strategy was dropped — ADR-005 Decision 5). The **OBT serving tables**
> (`obt_*_wide`) are now exposed read-only as **Snowflake external tables** (`obt_sales_wide_ext`,
> `obt_review_wide_ext`) reading the same S3 Gold (`gold/_current/`) — a "warehouse over lakehouse"
> veneer, not a source of truth. See `docs/architecture_handbook/AH.md` §3/§3a. This ERD did not need
> re-cutting: no grain or key changed.

## Legend (read before the diagram)
- All `_sk` surrogate keys are **`varchar` MD5 hash keys** (`dbt_utils.generate_surrogate_key`),
  **EXCEPT `date_sk`**, which is a `YYYYMMDD` **smart integer** — the only non-hash SK, by design
  (avoids cross-`UNION` collision issues; see `DECISION_LOG.md`).
- `dim_drug` is **one** conformed SCD2 table holding **two member types** (`ndc_product` +
  `atc_category`) discriminated by `drug_member_type` — *not* two tables (ADR-003, Phase-4 review).
- OBT (`obt_*_wide`) tables are **DERIVED**, rebuilt from the star (ADR-001). They are **not** a
  source of truth and have no keys / no outbound FKs.

## Data model — DBML
```dbml
//==============================================================================
// ENRICH (Silver) — per-source, still divergent. dbt views (+ 1 snapshot, 1 ephemeral).
//==============================================================================

Table stg_alpha__sales {
  sale_date  date     [not null, note: 'Alpha salesdaily.csv, unpivoted from 8 wide ATC columns']
  atc_code   varchar  [not null, note: 'one of 8 seed ATC categories']
  units_sold int      [not null, note: 'negative units coerced to 0 (business rule)']
  load_ts    timestamp
  Note: 'view · grain: 1 row = 1 ATC code x 1 day'
}

Table stg_beta__ndc {
  product_ndc          varchar [pk, note: 'authoritative natural key for dim_drug (ADR-003)']
  generic_name         varchar
  proprietary_name     varchar [note: 'openFDA brand_name']
  pharm_class          varchar [note: '0..N openFDA classes flattened to one "; "-delimited string']
  route                varchar [note: 'first element of openFDA route array']
  dosage_form          varchar
  labeler_name         varchar
  marketing_start_date date    [note: '-> SCD2 valid_from candidate']
  marketing_end_date   date
  load_ts              timestamp
  Note: 'view · one row per product_ndc (dedupe on latest marketing_start_date)'
}

Table stg_gamma__reviews {
  review_id      varchar [pk, note: 'source uniqueID']
  drug_name_raw  varchar [not null]
  drug_name_norm varchar [note: 'case/space/punctuation stripped for crosswalk match']
  condition_name varchar [note: 'scrape-artifact (HTML-tag) values nulled, not dropped']
  dq_flag        boolean [not null, note: 'true when condition_name nulled for a defect']
  dq_reason      varchar [note: 'populated when dq_flag = true (audit trail)']
  rating         int     [note: '1..10']
  useful_count   int
  review_date    date
  load_ts        timestamp
  Note: 'view · grain: 1 row = 1 review event'
}

Table snap_beta_ndc {
  product_ndc    varchar [pk]
  generic_name   varchar
  proprietary_name varchar
  pharm_class    varchar
  route          varchar
  dosage_form    varchar
  labeler_name   varchar
  marketing_start_date date
  marketing_end_date   date
  dbt_valid_from timestamp [note: '-> dim_drug.valid_from']
  dbt_valid_to   timestamp [note: 'null = current -> dim_drug.is_current']
  Note: 'dbt snapshot · SCD2, check strategy on business columns (no source updated_at)'
}

Table int_drug_crosswalk {
  product_ndc            varchar [note: 'ephemeral — no physical table, inlined as CTE']
  atc_code               varchar [note: 'matched ATC seed code; null when unmatched']
  generic_name           varchar
  pharm_class            varchar
  is_combination_product boolean [note: 'combination products excluded from fuzzy tier']
  match_confidence       varchar [note: 'exact | normalized | fuzzy | combination_unverified | unmatched']
  Note: 'ephemeral · tiered NDC<->ATC reconciliation (ADR-003); coverage is a DQD KPI, not 100%'
}

//==============================================================================
// DATA MART (Gold, STAR) — conformed, governed. dbt table/incremental.
//==============================================================================

Table dim_date {
  date_sk      int  [pk, note: 'smart key YYYYMMDD — the ONLY non-hash SK, by design']
  full_date    date [not null, unique]
  year         int
  month        int
  day          int
  weekday_name varchar
  Note: 'SCD0 (static) · date spine 2008-01-01..2019-12-31 · conformed, shared by both facts'
}

Table dim_drug {
  drug_sk                varchar [pk, note: 'hash(product_ndc, dbt_valid_from) for ndc_product; hash(atc_code) for atc_category']
  drug_member_type       varchar [not null, note: 'DISCRIMINATOR: ndc_product | atc_category. Two member types in one conformed SCD2 dim (ADR-003, Phase-4 review condition).']
  product_ndc            varchar [note: 'natural key; NULL for atc_category rows']
  atc_code               varchar
  generic_name           varchar
  proprietary_name       varchar [note: 'NULL for atc_category rows']
  pharm_class            varchar
  dosage_form            varchar [note: 'NULL for atc_category rows']
  route                  varchar [note: 'NULL for atc_category rows']
  labeler_name           varchar [note: 'NULL for atc_category rows']
  match_confidence       varchar [note: 'NULL by design for atc_category rows; populated only for ndc_product. Do NOT overload with provenance — that was a vetoed pattern (DEBATE_LOG_phase_4).']
  is_combination_product boolean
  valid_from             date    [note: 'SCD2; 1900-01-01 for atc_category rows']
  valid_to               date    [note: 'SCD2; NULL = current']
  is_current             boolean
  Note: 'SCD2 · ONE conformed table, two member types (see drug_member_type). NOT a clean 1:1 product dimension and NOT two tables.'
}

Table dim_condition {
  condition_sk   varchar [pk, note: 'hash(condition_name)']
  condition_name varchar [not null, unique]
  Note: 'SCD1 (overwrite) · distinct conditions from Gamma reviews'
}

Table fact_sales {
  sales_sk   varchar [pk, note: 'hash(sale_date, atc_code)']
  date_sk    int     [not null]
  drug_sk    varchar [not null, note: 'resolves ONLY to dim_drug atc_category rows (Alpha reports at category grain)']
  units_sold int     [not null, note: 'measure; >= 0']
  load_ts    timestamp
  Note: 'incremental · grain: 1 row = 1 ATC category x 1 day (Alpha)'
}

Table fact_review {
  review_sk    varchar [pk, note: 'hash(review_id)']
  date_sk      int     [not null]
  drug_sk      varchar [note: 'resolves ONLY to dim_drug ndc_product rows; NULLABLE (ADR-003 partial match, 71.9% coverage)']
  condition_sk varchar [note: 'NULLABLE (ADR-003 partial match, 98.9% coverage)']
  rating       int     [not null, note: 'measure; 1..10']
  useful_count int     [note: 'measure']
  dq_flag      boolean [not null, note: 'carried from stg_gamma__reviews for null-condition traceability']
  dq_reason    varchar
  load_ts      timestamp
  Note: 'incremental · grain: 1 row = 1 review event (Gamma)'
}

//==============================================================================
// RRD (Serving) — OBT, DERIVED from the star (ADR-001). NOT a source of truth.
// No PK, no outbound FKs. Rebuilt from the star, never sourced directly.
// As-built (MIGRATED): materialized as `external` parquet under gold/_current/ and
// exposed read-only via Snowflake external tables (obt_sales_wide_ext / obt_review_wide_ext).
//==============================================================================

Table obt_sales_wide {
  sales_sk     varchar
  units_sold   int
  sale_date    date
  year         int
  month        int
  weekday_name varchar
  atc_code     varchar
  generic_name varchar
  pharm_class  varchar
  Note: 'DERIVED — rebuilt from fact_sales + dim_date + dim_drug (ADR-001). NOT a source of truth. As-built: external parquet on S3 (gold/_current/), served read-only as Snowflake external table obt_sales_wide_ext (16,848 rows).'
}

Table obt_review_wide {
  review_sk        varchar
  rating           int
  useful_count     int
  review_date      date
  year             int
  month            int
  condition_name   varchar
  generic_name     varchar
  proprietary_name varchar
  atc_code         varchar
  Note: 'DERIVED — rebuilt from fact_review + dim_date + dim_condition + dim_drug (ADR-001). NOT a source of truth. As-built: external parquet on S3 (gold/_current/), served read-only as Snowflake external table obt_review_wide_ext (215,063 rows).'
}

//------------------------------------------------------------------------------
// Relationships
//------------------------------------------------------------------------------

// Enrich lineage into the star (annotated; not classic referential FKs)
Ref: snap_beta_ndc.product_ndc - stg_beta__ndc.product_ndc          // SCD2 snapshot OF the Beta master
Ref: int_drug_crosswalk.product_ndc > stg_beta__ndc.product_ndc      // crosswalk reads the Beta master
Ref: dim_drug.product_ndc - snap_beta_ndc.product_ndc                // ndc_product rows sourced from the snapshot

// Star foreign keys (the real referential structure)
Ref: fact_sales.date_sk > dim_date.date_sk
Ref: fact_sales.drug_sk > dim_drug.drug_sk        // -> atc_category members only
Ref: fact_review.date_sk > dim_date.date_sk
Ref: fact_review.drug_sk > dim_drug.drug_sk        // -> ndc_product members only; nullable
Ref: fact_review.condition_sk > dim_condition.condition_sk   // nullable

// NOTE: obt_sales_wide / obt_review_wide intentionally have NO outbound refs —
// they are denormalized derived outputs, not keyed entities (ADR-001).

TableGroup "Enrich (Silver) — per-source, divergent" {
  stg_alpha__sales
  stg_beta__ndc
  stg_gamma__reviews
  snap_beta_ndc
  int_drug_crosswalk
}

TableGroup "Data Mart (Gold) — conformed STAR" {
  dim_date
  dim_drug
  dim_condition
  fact_sales
  fact_review
}

TableGroup "RRD (Serving) — OBT, derived" {
  obt_sales_wide
  obt_review_wide
}
```

## SCD decisions (confirmed by Data Architect — ERD ruling R5, 2026-06-18)
| Dimension | SCD Type | Why (as-built) |
|-----------|----------|----------------|
| dim_date | Type 0 (static) | date spine; dates never mutate (`dim_date.sql`) |
| dim_drug | Type 2 | `snap_beta_ndc` check-strategy snapshot → `valid_from`/`valid_to`/`is_current` (`dim_drug.sql`) |
| dim_condition | Type 1 (overwrite) | distinct `condition_name`, hash key, no history kept (`dim_condition.sql`) |

## Model consolidation log (Enrich / Data Mart / RRD)
| Date | Model area | Source team | Up to date? | Notes |
|------|-----------|-------------|-------------|-------|
| 2026-06-18 | Enrich | Alpha / Beta / Gamma | ✅ | `stg_alpha__sales`, `stg_beta__ndc`, `stg_gamma__reviews` + `snap_beta_ndc` (SCD2) + `int_drug_crosswalk` (ephemeral); all 3 sources land & build green |
| 2026-06-18 | Data Mart | conformed (all 3 converge) | ✅ | star locked at Phase 3, built Phase 4; `dim_drug` SCD2 conformed crosswalk; 49/50 dbt tests pass, 1 documented warn |
| 2026-06-18 | RRD | derived from star | ✅ | `obt_sales_wide`, `obt_review_wide` rebuilt from star (ADR-001); never sourced directly |

## Open items
- ADR-005 migration — **DONE & LIVE 2026-06-19** (no longer open). Logical model unchanged; physical
  substrate is now S3-canonical + `external` parquet + Snowflake external-table veneer. No grain/key
  changed, so this ERD was not re-cut — only the status banner + OBT physical notes were refreshed
  (see AH.md §3/§3a). MWAA remains OUT (local orchestration); not an ERD concern.
