# Source-to-Target Mapping (STTM) — Novartis Pharma enVision

> Column-level lineage: every target field traced to its source + transformation rule.
> Three divergent sources (Alpha/Beta/Gamma) converge into one governed mart (ADR-001/002/003).

**Version:** 3.0 · **Owner:** Data Architect · **Status:** APPROVED FOR RE-PUBLISH — Data Architect re-signed off 2026-06-19 (`SIGN_OFF_LOG.md` "AH/ERD/STTM Post-Migration Refresh + Re-Sign-off"). Describes the **as-built MIGRATED** pipeline: ADR-005 S3-canonical storage + ephemeral DuckDB httpfs compute + `external` parquet on S3 + Snowflake external-table serving veneer, **LIVE on real AWS 2026-06-19** (run_id `run-20260619-045115`). The column-level lineage below is **UNCHANGED** by the migration — same source tables/columns/transforms; only the physical **source binding** moved (see note below).

> **Migration note — what changed at the physical layer (not the lineage):** Every `Source table` cell that reads `bronze.<x>` is now physically bound to **`read_parquet('s3://novartis-pharma-sttm-lake/bronze/<src>/<date>/...')`** — the relational `bronze.x` DuckDB tables no longer exist; the same columns (incl. `load_ts`/`source_file`) ride on the bronze **parquet** instead. Silver (`stg_*`, `snap_beta_ndc`) and Gold (`dim_*`, `fact_*`, `obt_*`) are now dbt-duckdb **`external`** parquet on S3 (`silver/`, `snapshots/`, `gold/<run_id>/`→`gold/_current/`). `fact_sales`/`fact_review` are **full deterministic rebuilds** (the `incremental`/`is_incremental()` filter on `load_ts > max(load_ts)` was dropped per ADR-005 Decision 5 — `load_ts` still rides through as a lineage column). The transformation/business-rule columns are identical. KPIs verified identical to baseline (`fact_review` 215,063 · `dim_drug` 133,654 SCD2 · `fact_sales` 16,848 · drug_sk 71.9% · condition_sk 98.9%).

## How to read this
- One row = one **target column**.
- `Transformation / Business Rule` = exact logic that produces the target.
- Empty source = derived/generated (surrogate key, load timestamp, etc.).
- Coverage % rows are DQD KPIs, not bugs — see ADR-003 partial-match policy.

---

## Target: `enrich.stg_alpha__sales` (Project Alpha — pharma sales)
| # | Target column | Type | Source table | Source column | Transformation / Business Rule | Nullable | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `sale_date` | DATE | `bronze.sales_daily` | `datum` | passthrough (already DATE) | N | |
| 2 | `atc_code` | VARCHAR | `bronze.sales_daily` | `M01AB`/`M01AE`/`N02BA`/`N02BE`/`N05B`/`N05C`/`R03`/`R06` (column name) | UNPIVOT 8 wide columns -> long, one row per code | N | grain: 1 row = 1 ATC code x 1 day |
| 3 | `units_sold` | DECIMAL | `bronze.sales_daily` | value of the unpivoted column | negative -> 0 | N | business rule (no observed negatives in this dataset) |
| 4 | `load_ts` | TIMESTAMP | `bronze.sales_daily` | `load_ts` | passthrough from bronze ingest | N | audit |

**Source row count:** 2,106 daily rows -> 16,848 unpivoted (2,106 x 8).

## Target: `enrich.stg_beta__ndc` (Project Beta — openFDA NDC directory, authoritative product master)
| # | Target column | Type | Source table | Source column | Transformation / Business Rule | Nullable | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `product_ndc` | VARCHAR | `bronze.ndc_directory` | `product_ndc` | passthrough, dedupe key | N | natural key |
| 2 | `generic_name` | VARCHAR | `bronze.ndc_directory` | `generic_name` | passthrough | Y | 3/136,038 null (OTC sanitizers with brand_name only) — `warn`-severity test |
| 3 | `proprietary_name` | VARCHAR | `bronze.ndc_directory` | `brand_name` | passthrough, renamed | Y | |
| 4 | `pharm_class` | VARCHAR | `bronze.ndc_directory` | `pharm_class` (array) | `array_to_string(pharm_class, '; ')` | Y | flattened for cross-dialect string matching in `int_drug_crosswalk` |
| 5 | `route` | VARCHAR | `bronze.ndc_directory` | `route` (array) | first element `route[1]` | Y | |
| 6 | `dosage_form` | VARCHAR | `bronze.ndc_directory` | `dosage_form` | passthrough | Y | |
| 7 | `labeler_name` | VARCHAR | `bronze.ndc_directory` | `labeler_name` | passthrough | Y | |
| 8 | `marketing_start_date` | DATE | `bronze.ndc_directory` | `marketing_start_date` | parse `YYYYMMDD` string -> DATE | N | feeds `dim_drug.valid_from` |
| 9 | `marketing_end_date` | DATE | `bronze.ndc_directory` | `marketing_end_date` | parse `YYYYMMDD` string -> DATE | Y | 3,917/136,038 populated; feeds `dim_drug.valid_to` |
| 10 | `load_ts` | TIMESTAMP | `bronze.ndc_directory` | `load_ts` | passthrough | N | audit |

**Dedup rule:** `row_number() over (partition by product_ndc order by marketing_start_date desc)`, keep rn=1. 136,038 raw rows (full openFDA bulk snapshot) -> 133,646 distinct products.

## Target: `enrich.stg_gamma__reviews` (Project Gamma — UCI/drugs.com patient reviews)
| # | Target column | Type | Source table | Source column | Transformation / Business Rule | Nullable | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `review_id` | BIGINT | `bronze.drug_reviews` | `uniqueID` | passthrough | N | natural key, unique across train+test union |
| 2 | `drug_name_raw` | VARCHAR | `bronze.drug_reviews` | `drugName` | passthrough | N | |
| 3 | `drug_name_norm` | VARCHAR | `bronze.drug_reviews` | `drugName` | `lower(trim(x))` then strip all non `[a-z0-9]` chars | N | crosswalk match key into `dim_drug` |
| 4 | `condition_name` | VARCHAR | `bronze.drug_reviews` | `condition` | passthrough, **except**: nulled when value matches HTML-tag scrape-artifact pattern `<[^>]+>` | Y | known source DQ defect — 1,171/215,063 rows; condition unset rather than dropping the review. Full-column profiled (not just this one pattern) — confirmed no other anomaly shapes exist (see DQD.md) |
| 5 | `dq_flag` | BOOLEAN | — | — | `true` iff `condition_name` was nulled for the scrape-artifact defect | N | added per Data Quality Steward's Phase 4 review condition — makes "scrubbed" vs "source had no condition" traceable downstream |
| 6 | `dq_reason` | VARCHAR | — | — | literal reason string when `dq_flag` is true | Y | `not_null` test where `dq_flag = true` |
| 7 | `rating` | INT | `bronze.drug_reviews` | `rating` | passthrough | N | range 1–10, validated |
| 8 | `useful_count` | INT | `bronze.drug_reviews` | `usefulCount` | passthrough | N | |
| 9 | `review_date` | DATE | `bronze.drug_reviews` | `date` | parse `DD-Mon-YY` string -> DATE | N | |
| 10 | `load_ts` | TIMESTAMP | `bronze.drug_reviews` | `load_ts` | passthrough | N | audit |

**Source row count:** 215,063 (drugsComTrain_raw.csv + drugsComTest_raw.csv, unioned).

## Target: `enrich.int_drug_crosswalk` (intermediate, ephemeral — ADR-003)
| # | Target column | Type | Source table | Source column | Transformation / Business Rule | Nullable | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `product_ndc` | VARCHAR | `stg_beta__ndc` | `product_ndc` | passthrough | N | |
| 2 | `atc_code` | VARCHAR | `atc_pharmclass_crosswalk` (seed) | `atc_code` | best-tier match (see below) | Y | null = unmatched |
| 3 | `generic_name` | VARCHAR | `stg_beta__ndc` | `generic_name` | passthrough | Y | |
| 4 | `pharm_class` | VARCHAR | `stg_beta__ndc` | `pharm_class` | passthrough | Y | |
| 5 | `is_combination_product` | BOOLEAN | `stg_beta__ndc` | `generic_name` | `generic_name ilike '% and %' or ilike '% with %' or like '%/%'` | N | added per Business Analyst's Phase 4 review — see below |
| 6 | `match_confidence` | VARCHAR | — | — | tiered match, best wins per `product_ndc` | N | `exact` \| `normalized` \| `fuzzy` \| `combination_unverified` \| `unmatched` |

**Match tiers** (priority order, first hit wins; secondary tie-break `order by atc_code` if two seed rows hit the same tier):
1. `exact` — `lower(trim(generic_name)) = lower(trim(seed.example_generic))`
2. `normalized` — `pharm_class` string contains `seed.pharm_class_hint` (case-insensitive substring)
3. `fuzzy` — word-boundary regex match of `seed.example_generic` (length >= 5) inside `generic_name`, **excluding combination products**
4. `combination_unverified` — would have hit the fuzzy criteria, but `is_combination_product = true` — tagged distinctly rather than confidently assigned one ingredient's ATC code (a combination drug naming one matched ingredient doesn't mean the whole product belongs to that category; the original fuzzy rule treated this as a confident match, which Business Analyst flagged as "worse than unmatched")
5. `unmatched` — none of the above

**Hardening applied 2026-06-18** (Phase 4 retroactive review, `DEBATE_LOG_phase_4.md`): the fuzzy tier
originally used naive `LIKE '%...%'` substring containment with no word-boundary or length guard, and
silently lumped combination products into the same `fuzzy` tag as legitimate single-ingredient
matches. Both fixed as described above.

**Coverage (DQD KPI, measured 2026-06-18, post-hardening):** 5,524/133,646 NDC products matched an
ATC code (4.1%) — `exact`=2,133, `normalized`=3,329, `fuzzy`=322 (down from 419 pre-hardening — the
97 removed were word-boundary false positives), `combination_unverified`=69 (newly surfaced, were
previously silently folded into `fuzzy`). 9,805/133,646 products (7.3%) are flagged
`is_combination_product`. Low overall coverage is **expected and honest**: the seed only covers 8
broad ATC categories against the full national product catalog (ADR-003 explicitly rejects
pretending 100% linkage is achievable) — **this number measures seed reach, not matching-algorithm
quality**; see DQD.md for why those two are reported separately (the conflated single-number
framing was a finding from Business Analyst's Phase 4 review).

## Target: `data_mart.dim_drug` (STAR, SCD2 — ADR-001/003)
| # | Target column | Type | Source table | Source column | Transformation / Business Rule | Nullable | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `drug_sk` | VARCHAR | — | — | `dbt_utils.generate_surrogate_key([product_ndc, dbt_valid_from])` (NDC rows) or `(atc_code)` (category rows) | N | **hash key, not sequence INT** — deviation from original stub, standard dbt pattern |
| 2 | `drug_member_type` | VARCHAR | — | — | literal `'ndc_product'` or `'atc_category'` | N | added per Data Architect's Phase 4 review — see below |
| 3 | `product_ndc` | VARCHAR | `snap_beta_ndc` | `product_ndc` | passthrough | Y | null for category rows |
| 4 | `atc_code` | VARCHAR | `int_drug_crosswalk` / seed | `atc_code` | crosswalk match (NDC rows) or direct (category rows) | Y | |
| 5 | `generic_name` | VARCHAR | `snap_beta_ndc` / seed | `generic_name` / `example_generic` | passthrough | Y | |
| 6 | `proprietary_name` | VARCHAR | `snap_beta_ndc` | `proprietary_name` | passthrough | Y | null for category rows |
| 7 | `pharm_class` | VARCHAR | `snap_beta_ndc` / seed | `pharm_class` / `pharm_class_hint` | passthrough | Y | |
| 8 | `dosage_form` | VARCHAR | `snap_beta_ndc` | `dosage_form` | passthrough | Y | null for category rows |
| 9 | `route` | VARCHAR | `snap_beta_ndc` | `route` | passthrough | Y | null for category rows |
| 10 | `labeler_name` | VARCHAR | `snap_beta_ndc` | `labeler_name` | passthrough | Y | null for category rows |
| 11 | `match_confidence` | VARCHAR | `int_drug_crosswalk` | `match_confidence` | `coalesce(crosswalk.match_confidence, 'unmatched')` for NDC rows; **null** for category rows | conditional | `exact`\|`normalized`\|`fuzzy`\|`combination_unverified`\|`unmatched` where `drug_member_type='ndc_product'`; null where `'atc_category'` — by design, not a defect (`not_null`/`accepted_values` tests scoped via `config.where`) |
| 12 | `is_combination_product` | BOOLEAN | `int_drug_crosswalk` | `is_combination_product` | passthrough; `false` for category rows | N | |
| 13 | `valid_from` | DATE | `snap_beta_ndc` | `dbt_valid_from` (snapshot SCD2 metadata) | cast to date; literal `1900-01-01` for category rows | N | |
| 14 | `valid_to` | DATE | `snap_beta_ndc` | `dbt_valid_to` | cast to date; null for category rows | Y | |
| 15 | `is_current` | BOOLEAN | — | — | `dbt_valid_to is null`; literal `true` for category rows | N | |

**Two member types, one conformed dimension, distinguished by `drug_member_type` (not by
`match_confidence`):**
- **`ndc_product` rows** (133,646): authoritative source Beta, true SCD2 via `dbt snapshot` (`snap_beta_ndc`, `check` strategy on business columns).
- **`atc_category` rows** (exactly 8, enforced by a singular test `dbt/tests/dim_drug_category_row_count.sql`): synthesized from the seed. Alpha sales report only at ATC-category grain (no NDC) — `fact_sales` needs *some* stable join target, and a real NDC product would misrepresent an entire category as one product. These rows exist purely so `fact_sales.drug_sk` always resolves honestly.

**Revision note (Phase 4 retroactive review):** the original build overloaded `match_confidence`
with a literal `'category_seed'` value to mark the synthetic rows — Data Architect flagged this as
corrupting the crosswalk coverage KPI (anyone grouping by `match_confidence` would get 8 phantom rows
in the denominator). `drug_member_type` now carries that distinction structurally; `match_confidence`
is null for category rows rather than a fifth pseudo-tier value.

## Target: `data_mart.dim_date` (SCD0)
| # | Target column | Type | Source | Transformation | Notes |
|---|---|---|---|---|---|
| 1 | `date_sk` | INT | generated | `to_char(date, 'YYYYMMDD')::int` | yyyymmdd |
| 2 | `full_date` | DATE | generated | `dbt_utils.date_spine('day', 2008-01-01, 2020-01-01)` | covers Gamma (2008-2017) + Alpha (2014-2019) |
| 3 | `year`/`month`/`day` | INT | generated | `extract(... from full_date)` | |
| 4 | `weekday_name` | VARCHAR | generated | `dayname()` (duckdb) / `to_char(.., 'DY')` (snowflake) | dialect-dispatched |

## Target: `data_mart.dim_condition` (SCD1)
| # | Target column | Type | Source table | Source column | Transformation | Nullable | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `condition_sk` | VARCHAR | — | — | `dbt_utils.generate_surrogate_key([condition_name])` | N | hash key |
| 2 | `condition_name` | VARCHAR | `stg_gamma__reviews` | `condition_name` | `distinct`, nulls excluded | N | |

## Target: `data_mart.fact_sales` — grain: 1 row = 1 ATC category x 1 day
| # | Target column | Type | Source table | Source column | Transformation / Business Rule | Nullable | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `sales_sk` | VARCHAR | — | — | `generate_surrogate_key([sale_date, atc_code])` | N | PK; hash key |
| 2 | `date_sk` | INT | `dim_date` | `date_sk` | FK lookup on `full_date = sale_date` | N | 100% resolved |
| 3 | `drug_sk` | VARCHAR | `dim_drug` (`drug_member_type='atc_category'` rows only) | `drug_sk` | FK lookup on `atc_code` | N | 100% resolved by design (category seed always covers Alpha's 8 codes) |
| 4 | `units_sold` | DECIMAL | `stg_alpha__sales` | `units_sold` | passthrough (already business-ruled in Enrich) | N | |
| 5 | `load_ts` | TIMESTAMP | `stg_alpha__sales` | `load_ts` | passthrough; drives `is_incremental()` filter | N | |

**Row count:** 16,848. **Coverage:** date_sk 100%, drug_sk 100%.

## Target: `data_mart.fact_review` — grain: 1 row = 1 review event
| # | Target column | Type | Source table | Source column | Transformation / Business Rule | Nullable | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `review_sk` | VARCHAR | — | — | `generate_surrogate_key([review_id])` | N | PK; hash key |
| 2 | `date_sk` | INT | `dim_date` | `date_sk` | FK lookup on `full_date = review_date` | N | 100% resolved |
| 3 | `drug_sk` | VARCHAR | `dim_drug` (`drug_member_type='ndc_product'` rows only) | `drug_sk` | normalized `drug_name_norm` matched against `generic_name`/`proprietary_name` (both normalized); many NDC rows per name collapse to **one** representative `drug_sk` (`min(drug_sk)`) to avoid fan-out past fact grain | Y | unmatched -> null (ADR-003 honest partial-match); see DQD.md SLA (≥65%, measured 71.9%) and the manufacturer-attribution caveat below |
| 4 | `condition_sk` | VARCHAR | `dim_condition` | `condition_sk` | FK lookup on `condition_name` | Y | unmatched/null condition -> null |
| 5 | `rating` | INT | `stg_gamma__reviews` | `rating` | passthrough | N | range 1–10 |
| 6 | `useful_count` | INT | `stg_gamma__reviews` | `useful_count` | passthrough | N | |
| 7 | `dq_flag` | BOOLEAN | `stg_gamma__reviews` | `dq_flag` | passthrough | N | distinguishes "condition scrubbed" from "condition genuinely absent" when `condition_sk` is null |
| 8 | `dq_reason` | VARCHAR | `stg_gamma__reviews` | `dq_reason` | passthrough | Y | |
| 9 | `load_ts` | TIMESTAMP | `stg_gamma__reviews` | `load_ts` | passthrough; drives `is_incremental()` filter | N | |

**Row count:** 215,063. **Coverage (DQD KPI):** date_sk 100%, drug_sk 71.9% (154,641/215,063, SLA ≥65% — see DQD.md), condition_sk 98.9% (212,698/215,063, target ≥90%).

**Manufacturer-attribution caveat (added per Business Analyst's Phase 4 review):**
`fact_review.drug_sk` resolves to generic/brand drug **identity** only. Because the `min(drug_sk)`
collapse picks an arbitrary representative across all NDC products sharing a name, **this column
does NOT support manufacturer/labeler-level questions** — joining it back to
`dim_drug.labeler_name`/`product_ndc` and reporting "reviews by labeler" would be a real but
meaningless number. Any future OBT/serving column built from this join must carry this caveat
forward or omit labeler-identifying fields entirely.

## Target: `rrd.obt_sales_wide` / `rrd.obt_review_wide` (serving, derived — NOT source of truth)
Denormalized join of the corresponding fact + its dimensions (`dim_date`, `dim_drug`, and for review also `dim_condition`). No new transformation logic — see ADR-001. **As-built (MIGRATED):** materialized as `external` parquet under `gold/_current/` and exposed read-only via Snowflake **external tables** `obt_sales_wide_ext` (16,848 rows) / `obt_review_wide_ext` (215,063 rows) reading the same S3 Gold — a "warehouse over lakehouse" veneer (ADR-005 Decision 1/3). Snowflake holds zero dbt-written tables; the S3 parquet is the source of truth.

## Exceptions (ADR-003 partial-match policy)
| Source | Defect | Volume | Handling |
|---|---|---|---|
| Beta NDC | `generic_name` null (brand-only OTC products) | 3 / 136,038 | kept, `warn`-severity test, not quarantined |
| Beta NDC | unmatched to any ATC code | 128,122 / 133,646 (95.9%) | kept in `dim_drug` with `match_confidence='unmatched'`, `atc_code` null — not exceptions-tabled separately; the column *is* the exception flag |
| Beta NDC | combination product, ATC assignment unverifiable from name alone | 9,805 / 133,646 (7.3%) flagged `is_combination_product`; 69 of those would otherwise have hit `fuzzy` | tagged `match_confidence='combination_unverified'` rather than silently assigned one ingredient's ATC code |
| Gamma reviews | `condition` = HTML-tag scrape artifact (`...</span> users found this comment helpful.`) | 1,171 / 215,063 | `condition_name` nulled, `dq_flag=true`, review row kept |
| Gamma reviews | `drug_name_norm` has no match in `dim_drug` | 60,422 / 215,063 (28.1%) | `fact_review.drug_sk` null; SLA floor ≥65% resolution (DQD.md) |

## Change log (version control)
| Date | Version | Change | Author |
|---|---|---|---|
| 2026-06-18 | 0.1 | Initial template | — |
| 2026-06-18 | 1.0 | Full Phase 4 build: all Enrich/Mart/RRD columns mapped, crosswalk + coverage KPIs measured on real landed data | build session |
| 2026-06-18 | 1.1 | Retroactive peer review remediation (`DEBATE_LOG_phase_4.md`): added `drug_member_type` (dim_drug), `is_combination_product` (crosswalk/dim_drug), `dq_flag`/`dq_reason` (gamma staging/fact_review); hardened crosswalk fuzzy tier (word-boundary + length guard, combination exclusion, deterministic tie-break); split seed-coverage vs. match-quality KPIs; added manufacturer-attribution caveat to fact_review.drug_sk | review remediation session |
| 2026-06-19 | 3.0 | Post-migration refresh — ADR-005 MIGRATED & LIVE (run_id `run-20260619-045115`). **Lineage rows UNCHANGED** (same source tables/columns/transforms). Updated status banner → as-built migrated; added migration note (relational `bronze.x` → `read_parquet('s3://.../bronze/<src>/<date>/...')`, Silver/Gold now `external` parquet on S3, snapshot externalized to `snapshots/`, `fact_*` full deterministic rebuild per ADR-005 Decision 5); refreshed OBT serving section to the Snowflake external-table veneer. Version jumps 1.1→3.0 to align with AH v3. | Data Architect (post-migration re-sign-off) |
