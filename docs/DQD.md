# DQD — Data Quality Document
**Owner**: Data Quality Steward

Filled 2026-06-18 (Phase 4 retroactive peer review, `DEBATE_LOG_phase_4.md`) — previously a
template despite Gold being built. dbt schema tests (`dbt/models/**/_*.yml`, 50 tests) implement
most of this directly; a small Great Expectations suite (`data_quality/expectations/`) covers the
distributional/row-count checks dbt's generic tests don't do well, per the condition raised in that
review (either populate the owned GE directory or formally document dbt-supersedes-GE — chose to
populate it, since GE is still named in ARCHITECTURE.md's locked stack table).

---

## DQ Dimensions
- **Completeness**: row counts per source land what's expected; FK resolution rates measured as KPIs, not assumed 100%.
- **Accuracy**: crosswalk match tiers (exact > normalized > fuzzy > combination_unverified > unmatched), range checks on rating/units_sold.
- **Consistency**: cross-dialect SQL (duckdb dev / snowflake prod) via `parse_date`/`regexp_replace_all` macros — same logic, same result, both targets.
- **Timeliness**: not yet measured — no recurring schedule exists yet (DAG is still unwired, see PROJECT_STATUS.md).
- **Uniqueness**: enforced via `unique` tests on every natural/surrogate key (`product_ndc`, `review_id`, `drug_sk`, `sales_sk`, `review_sk`, `date_sk`, `condition_sk`).

## Suites

### bronze_alpha_suite (sales_daily, sales_hourly)
Run: after `scripts/load_bronze.py`, before any Enrich model runs.

| Expectation | Severity | Action |
|-------------|----------|--------|
| `datum` NOT NULL | CRITICAL | Reject row (not currently observed — 0 nulls in 2,106 rows) |
| `row_count` = 2,106 (daily) / 50,532 (hourly) ± landing-date variance | HIGH | Alert if row count drifts on a re-land |
| 8 ATC columns numeric, no negative values pre-Enrich-fix | MEDIUM | Flag (Enrich applies the negative->0 rule; bronze itself never had negatives in this dataset) |

### bronze_beta_suite (ndc_directory)
Run: after `scripts/load_bronze.py`.

| Expectation | Severity | Action |
|-------------|----------|--------|
| `product_ndc` NOT NULL | CRITICAL | Reject row |
| `row_count` ≈ 136,038 (full openFDA bulk snapshot — will grow slowly over time as FDA adds products) | MEDIUM | Alert only if it *shrinks* significantly (possible truncated download) |
| `marketing_start_date` NOT NULL | CRITICAL | Reject row (100% populated today) |

### bronze_gamma_suite (drug_reviews)
| Expectation | Severity | Action |
|-------------|----------|--------|
| `uniqueID` NOT NULL + UNIQUE | CRITICAL | Reject row |
| `row_count` = 215,063 (train+test union) | HIGH | Alert on drift |
| `rating` BETWEEN 1 AND 10 | HIGH | Quarantine — not currently needed (0 out-of-range in 215,063 rows) |

### silver_stg_beta__ndc_suite
| Expectation | Threshold | Severity | Action |
|-------------|-----------|----------|--------|
| `product_ndc` UNIQUE | 100% | CRITICAL | Reject duplicate (dedup logic already enforces this) |
| `generic_name` NOT NULL | ≥99.99% | MEDIUM | **Downgraded to WARN** — 3/136,038 (0.0022%) are legitimate brand-only OTC products, investigated and accepted (STTM.md exceptions table). Was CRITICAL by default; downgrade required documented investigation, which exists. |

### silver_stg_gamma__reviews_suite
| Expectation | Threshold | Severity | Action |
|-------------|-----------|----------|--------|
| `condition` HTML-artifact rows fully profiled (not just one regex) | — | done | Profiled the full 215,063-row column: confirmed no other HTML tags, no entities, no numeric-only/empty values beyond the one `<[^>]+>` signature — 1,171 is the complete count, not a partial one. |
| `dq_flag` NOT NULL | 100% | CRITICAL | Reject row missing this audit column |
| `rating` BETWEEN 1 AND 10 | 100% | HIGH | Quarantine (0 violations currently) |

### gold_dim_drug_suite
| Expectation | Threshold | Severity | Action |
|-------------|-----------|----------|--------|
| `drug_sk` UNIQUE + NOT NULL | 100% | CRITICAL | Reject |
| exactly 8 `atc_category` rows (= seed row count) | exact | CRITICAL | Singular test `dbt/tests/dim_drug_category_row_count.sql` |
| `match_confidence` NOT NULL only where `drug_member_type='ndc_product'` | 100% | CRITICAL | enforced via dbt test `config.where` |

### gold_fact_sales_suite
| Expectation | Threshold | Severity | Action |
|-------------|-----------|----------|--------|
| `date_sk`/`drug_sk` FK resolution | 100% | CRITICAL | By construction (atc_category member always exists for all 8 Alpha codes) — any drop below 100% means the seed and Alpha's ATC codes have diverged and is a real incident |
| `units_sold` >= 0 | 100% | HIGH | Quarantine (0 violations currently — no negatives observed pre-rule either) |

### gold_fact_review_suite
| Expectation | Threshold | Severity | Action |
|-------------|-----------|----------|--------|
| `date_sk` FK resolution | 100% | CRITICAL | dim_date spans 2008-2020, covers all review dates by construction |
| **`drug_sk` FK resolution (coverage KPI)** | **≥65% target, currently 71.9% (154,641/215,063)** | HIGH if below target | Below 65%: investigate before next Gold rebuild — top unmatched `drug_name_norm` values by frequency should be sampled (not yet automated; manual spot-check recommended each time the Beta NDC bulk snapshot is refreshed, since coverage depends on what's in that catalog) |
| `condition_sk` FK resolution | ≥90% target, currently 98.9% (212,698/215,063) | MEDIUM if below target | The ~1.1% gap is exactly the known scrape-artifact-nulled rows (dq_flag=true) — expected, not a new defect |
| `dq_flag` NOT NULL | 100% | CRITICAL | Reject row missing audit trail |

**On the 71.9%/65% SLA number — addressing Business Analyst's Phase 4 review finding** that this
metric conflated two different things: "how good is the matching algorithm" vs. "how much of the
NDC catalog could possibly match Gamma's free-text names at all." These are now reported separately:
- **Crosswalk seed coverage** (ATC code assignment to NDC products): 4.4% (5,881/133,646) — this
  number measures the 8-row ATC seed's reach against the full national catalog, **not** matching
  algorithm quality. It will only go up if Business Analyst expands the seed beyond 8 ATC codes.
- **fact_review name-match coverage** (Gamma free-text -> any NDC product by generic/brand name,
  independent of ATC): 71.9% — this is the number with the ≥65% SLA above, and it measures matching
  algorithm quality against the full NDC catalog (not gated by the narrow ATC seed at all, since
  `fact_review.drug_sk` resolves through `dim_drug.generic_name`/`proprietary_name`, not through
  `atc_code`).

These two coverage numbers are **independent of each other** — improving the ATC seed does not move
the 71.9% number, and improving free-text name matching does not move the 4.4% number. Conflating
them in a single headline (as the original Phase 4 build did) was the defect this section corrects.

## Reconciliation
| Check | Tolerance | Measured (2026-06-18) |
|-------|-----------|------------------------|
| Source (Kaggle/openFDA) vs Bronze | Exact | Alpha 2,106/2,106 daily rows; Beta 136,038/136,038; Gamma 215,063/215,063 — exact |
| Bronze vs Silver (Beta dedup) | <5% drop expected from dedup | 136,038 -> 133,646 = 1.8% drop (dedup on `product_ndc`, expected and correct) |
| Bronze vs Silver (Alpha unpivot) | exact row multiplication (x8) | 2,106 -> 16,848 = exactly x8 — exact |
| Silver vs Gold (fact_sales) | Exact match to Silver row count | 16,848 Silver rows -> 16,848 fact_sales rows — exact |
| Silver vs Gold (fact_review) | Exact match to Silver row count | 215,063 Silver rows -> 215,063 fact_review rows — exact (no rows dropped; unmatched FKs are null, not dropped, per ADR-003) |

## Action on Failure
- CRITICAL → block + alert (enforced today via dbt test `severity: error`, which fails the `dbt test` run / CI step)
- HIGH → quarantine + continue (no dedicated quarantine *table* exists yet — current practice is null-in-place with `dq_flag`/`dq_reason` for traceability; a real quarantine table is the natural next step if HIGH-severity volumes grow beyond the single `condition` defect type)
- MEDIUM → flag + log (`severity: warn` in dbt tests, e.g. `stg_beta__ndc.generic_name`)
