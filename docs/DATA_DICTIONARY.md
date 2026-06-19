# DATA_DICTIONARY.md
**Owner**: Data Quality Steward

For EVERY column in EVERY layer. Filled 2026-06-18 (Phase 4 retroactive peer review,
`DEBATE_LOG_phase_4.md`) — previously a template despite Gold being built; see that log for context.
Column meanings cross-reference `docs/sttm/STTM.md`, which carries the full transformation logic.

---

## Bronze.sales_daily (Alpha — landed as-is, no cleaning)
| Column | Type | Nullable | Source | Business Meaning | DQ Rule |
|--------|------|----------|--------|------------------|---------|
| datum | DATE | No | Kaggle `salesdaily.csv` | Sale date | NOT NULL |
| M01AB / M01AE / N02BA / N02BE / N05B / N05C / R03 / R06 | DOUBLE | Yes | same | Units sold that day for the named ATC category | none at bronze (validated in Enrich) |
| Year / Month / Hour / Weekday Name | BIGINT/VARCHAR | Yes | same | Source-provided date parts (passthrough, not used downstream — `datum` is re-derived from) | none |
| load_ts | TIMESTAMP | No | ingest script | Bronze load time | NOT NULL |
| source_file | VARCHAR | No | ingest script | `'salesdaily.csv'` literal | NOT NULL |

## Bronze.sales_hourly (Alpha — landed, NOT used downstream)
Same shape as `sales_daily` at hourly grain. Landed for raw-archive fidelity (ADR-002 immutable
Landing/Bronze); no Enrich/Gold model consumes it — `fact_sales` grain is daily, per ADR's locked
grain definition.

## Bronze.ndc_directory (Beta — landed as-is, openFDA bulk JSON, nested types preserved)
| Column | Type | Nullable | Source | Business Meaning | DQ Rule |
|--------|------|----------|--------|------------------|---------|
| product_ndc | VARCHAR | No | openFDA bulk `drug-ndc-0001-of-0001.json` | National Drug Code, product-level | NOT NULL |
| generic_name | VARCHAR | Yes | same | Generic drug name | 3/136,038 null — see Enrich warn-test note |
| brand_name | VARCHAR | Yes | same | Proprietary/brand name | |
| pharm_class | VARCHAR[] | Yes | same | 0..N FDA pharmacologic class tags | |
| route | VARCHAR[] | Yes | same | 0..N administration routes | |
| dosage_form | VARCHAR | Yes | same | e.g. TABLET, GEL | |
| labeler_name | VARCHAR | Yes | same | Manufacturer/labeler code | |
| marketing_start_date | VARCHAR | No | same | `YYYYMMDD` string | NOT NULL (100% populated) |
| marketing_end_date | VARCHAR | Yes | same | `YYYYMMDD` string | populated for 3,917/136,038 (still-marketed products have none) |
| load_ts / source_file | TIMESTAMP/VARCHAR | No | ingest script | audit | NOT NULL |

## Bronze.drug_reviews (Gamma — landed as-is, train+test unioned)
| Column | Type | Nullable | Source | Business Meaning | DQ Rule |
|--------|------|----------|--------|------------------|---------|
| uniqueID | BIGINT | No | UCI/drugs.com CSV (train+test) | Natural key, unique across the union (verified: 215,063 rows = 215,063 distinct IDs) | NOT NULL, UNIQUE |
| drugName | VARCHAR | No | same | Free-text drug name | NOT NULL |
| condition | VARCHAR | Yes | same | Free-text condition; **1,171 rows contain an HTML-tag scrape artifact** (e.g. `"74</span> users found this comment helpful."`) instead of a real condition — see Enrich layer `dq_flag` | known defect, handled in Enrich |
| review | VARCHAR | Yes | same | Free-text review body (not modeled downstream) | |
| rating | BIGINT | No | same | 1–10 | range-checked in Enrich |
| date | VARCHAR | No | same | `DD-Mon-YY` string | NOT NULL |
| usefulCount | BIGINT | No | same | Helpful-vote count | NOT NULL |
| load_ts / source_file | TIMESTAMP/VARCHAR | No | ingest script | audit | NOT NULL |

---

## Enrich (Silver) — full transformation logic is in `docs/sttm/STTM.md`; this table is the
## condensed DQ-rule view per column.

### enrich.stg_alpha__sales
| Column | Type | Nullable | Derived From | Transform Logic | DQ Rule |
|--------|------|----------|--------------|----------------|---------|
| sale_date | DATE | No | bronze.sales_daily.datum | passthrough | NOT NULL |
| atc_code | VARCHAR | No | column name (unpivoted) | UNPIVOT 8 wide cols -> long | NOT NULL, one of the 8 known codes |
| units_sold | DECIMAL | No | unpivoted value | negative -> 0 | NOT NULL, >= 0 |
| load_ts | TIMESTAMP | No | bronze | passthrough | NOT NULL |

### enrich.stg_beta__ndc
| Column | Type | Nullable | Derived From | Transform Logic | DQ Rule |
|--------|------|----------|--------------|----------------|---------|
| product_ndc | VARCHAR | No | bronze.product_ndc | dedup, keep latest marketing_start_date per product | NOT NULL, UNIQUE |
| generic_name | VARCHAR | Yes | bronze.generic_name | passthrough | **WARN** if null (3/136,038 — legitimate brand-only OTC products, investigated and accepted, see STTM exceptions) |
| proprietary_name | VARCHAR | Yes | bronze.brand_name | renamed | |
| pharm_class | VARCHAR | Yes | bronze.pharm_class (array) | `array_to_string(..., '; ')` — flattened for cross-dialect string matching | |
| route | VARCHAR | Yes | bronze.route (array) | first element `route[1]` | |
| dosage_form / labeler_name | VARCHAR | Yes | bronze | passthrough | |
| marketing_start_date | DATE | No | bronze (string) | parse `YYYYMMDD` | NOT NULL |
| marketing_end_date | DATE | Yes | bronze (string) | parse `YYYYMMDD` | feeds SCD2 `valid_to` |
| load_ts | TIMESTAMP | No | bronze | passthrough | NOT NULL |

### enrich.stg_gamma__reviews
| Column | Type | Nullable | Derived From | Transform Logic | DQ Rule |
|--------|------|----------|--------------|----------------|---------|
| review_id | BIGINT | No | bronze.uniqueID | passthrough | NOT NULL, UNIQUE |
| drug_name_raw | VARCHAR | No | bronze.drugName | passthrough | NOT NULL |
| drug_name_norm | VARCHAR | No | bronze.drugName | lower/trim, strip non-`[a-z0-9]` | crosswalk match key |
| condition_name | VARCHAR | Yes | bronze.condition | NULL if `<[^>]+>` HTML-tag pattern detected (full-column profiled, see JOURNEY_LOG [006]) | CRITICAL→none (kept, not quarantined — rating/drug signal is independent of condition validity); flagged via dq_flag |
| **dq_flag** | BOOLEAN | No | derived | `true` iff condition_name was nulled for the scrape-artifact defect | NOT NULL — added per Data Quality Steward's Phase 4 review condition |
| **dq_reason** | VARCHAR | Yes | derived | literal reason string when dq_flag is true | NOT NULL where dq_flag=true |
| rating | INT | No | bronze | passthrough | NOT NULL, 1–10 |
| useful_count | INT | No | bronze.usefulCount | passthrough | NOT NULL |
| review_date | DATE | No | bronze.date (string) | parse `DD-Mon-YY` | NOT NULL |
| load_ts | TIMESTAMP | No | bronze | passthrough | NOT NULL |

### enrich.int_drug_crosswalk (intermediate, ephemeral)
| Column | Type | Nullable | Derived From | Transform Logic | DQ Rule |
|--------|------|----------|--------------|----------------|---------|
| product_ndc | VARCHAR | No | stg_beta__ndc | passthrough | NOT NULL |
| atc_code | VARCHAR | Yes | seed (best-tier match) | see tier logic below | null = unmatched |
| generic_name / pharm_class | VARCHAR | Yes | stg_beta__ndc | passthrough | |
| **is_combination_product** | BOOLEAN | No | derived | `generic_name` contains `" and "`/`" with "`/`"/"` | added per Business Analyst's Phase 4 review — excludes combination products from the fuzzy tier (was a confident-wrong-answer risk) |
| match_confidence | VARCHAR | No | derived | `exact` (generic_name = seed.example_generic) > `normalized` (pharm_class contains seed.pharm_class_hint) > `fuzzy` (word-boundary match on seed.example_generic, length>=5, non-combination only) > `combination_unverified` (would-be-fuzzy but flagged combination) > `unmatched` | coverage tracked, not enforced to 100% (ADR-003) |

---

## Gold — Data Mart (STAR)

### data_mart.dim_drug
| Column | Type | Nullable | Aggregation/Derivation | DQ Rule |
|--------|------|----------|------------------------|---------|
| drug_sk | VARCHAR | No | hash(`product_ndc`,`dbt_valid_from`) or hash(`atc_code`) | UNIQUE, NOT NULL |
| drug_member_type | VARCHAR | No | literal `'ndc_product'` or `'atc_category'` | NOT NULL, one of the two |
| product_ndc | VARCHAR | Yes | passthrough (ndc_product rows only) | |
| atc_code | VARCHAR | Yes | crosswalk match (ndc_product) or direct (atc_category) | |
| generic_name / proprietary_name / pharm_class / dosage_form / route / labeler_name | VARCHAR | Yes | passthrough / seed | null for atc_category rows |
| match_confidence | VARCHAR | conditional | see crosswalk | NOT NULL only where `drug_member_type='ndc_product'` (atc_category rows: null by design, not a defect) |
| is_combination_product | BOOLEAN | No | from crosswalk, `false` for atc_category rows | NOT NULL |
| valid_from / valid_to / is_current | DATE/DATE/BOOLEAN | varies | SCD2 from `dbt snapshot` (ndc_product) or literal epoch (atc_category) | |

### data_mart.dim_date
date_sk (INT, yyyymmdd) · full_date (DATE) · year/month/day (INT) · weekday_name (VARCHAR) — all
generated via `dbt_utils.date_spine`, no source DQ risk (SCD0, fully deterministic).

### data_mart.dim_condition
condition_sk (VARCHAR hash, NOT NULL UNIQUE) · condition_name (VARCHAR, NOT NULL UNIQUE) — distinct
`condition_name` values from `stg_gamma__reviews` (nulls already excluded upstream).

### data_mart.fact_sales — grain: 1 row = 1 ATC code x 1 day
| Column | Type | Nullable | Aggregation | DQ Rule |
|--------|------|----------|-------------|---------|
| sales_sk | VARCHAR | No | hash(sale_date, atc_code) | UNIQUE, NOT NULL |
| date_sk | INT | No | FK -> dim_date | NOT NULL, FK valid (100% resolved) |
| drug_sk | VARCHAR | No | FK -> dim_drug (atc_category member) | NOT NULL, FK valid (100% resolved by design) |
| units_sold | DECIMAL | No | passthrough from Enrich | NOT NULL, >= 0 |

### data_mart.fact_review — grain: 1 row = 1 review event
| Column | Type | Nullable | Aggregation | DQ Rule |
|--------|------|----------|-------------|---------|
| review_sk | VARCHAR | No | hash(review_id) | UNIQUE, NOT NULL |
| date_sk | INT | No | FK -> dim_date | NOT NULL, FK valid (100% resolved) |
| drug_sk | VARCHAR | Yes | FK -> dim_drug (ndc_product members, name-normalized match, collapsed to one rep per name) | FK valid where not null; **coverage SLA: ≥65%, current 71.9%** (see DQD.md) |
| condition_sk | VARCHAR | Yes | FK -> dim_condition | FK valid where not null; current 98.9% |
| rating | INT | No | passthrough | NOT NULL, 1–10 |
| useful_count | INT | No | passthrough | NOT NULL |
| dq_flag | BOOLEAN | No | passthrough from Enrich | NOT NULL — distinguishes "condition scrubbed" from "condition genuinely absent" |
| dq_reason | VARCHAR | Yes | passthrough from Enrich | NOT NULL where dq_flag=true |

---

## Gold — RRD (serving, derived OBT — NOT source of truth)
`rrd.obt_sales_wide` / `rrd.obt_review_wide`: straight denormalizing join of the fact + its
dimensions (no new derivation, no new DQ surface — inherits the fact/dim rules above verbatim).
