# DATA_MODEL.md
**Owner**: Data Architect
**Paradigm**: Kimball **star** (system of record) + **OBT** serving (derived) — see ADR-001
**Status**: locked at Phase 3 sign-off

---

## 1. Conceptual Model
```
[Sales (Alpha)]   --units by ATC over date-->   measures
[Reviews (Gamma)] --rating by condition over date--> measures
[Product Master (Beta/NDC)] --describes--> DRUG

           DRUG (conformed dim_drug)
              ▲            ▲
              │            │
        fact_sales    fact_review
              │            │
           dim_date    dim_date, dim_condition
```
`dim_drug` is the conformed dimension reconciling ATC (Alpha) ↔ pharm_class/name (Beta) ↔
free-text drugName (Gamma) via the crosswalk (ADR-003).

## 2. Logical Model (Data Mart — STAR)

### Fact tables
**fact_sales**
- Grain: **1 row = 1 ATC category × 1 day** (daily). (Optional `fact_sales_hourly` for intraday.)
- Keys: `sales_sk` (PK, surrogate); FK `date_sk`, `drug_sk`.
- Measures: `units_sold`.
- Source: Alpha (`salesdaily.csv` / `saleshourly.csv`).

**fact_review**
- Grain: **1 row = 1 review event**.
- Keys: `review_sk` (PK); FK `date_sk`, `drug_sk`, `condition_sk`.
- Measures: `rating` (1–10), `useful_count`.
- Source: Gamma (UCI Drug Reviews).

### Dimension tables
**dim_drug** — ⭐ conformed, **SCD Type 2** (ADR-003)
- Natural key: `product_ndc` (Beta authoritative) + crosswalk to ATC + free-text.
- Surrogate: `drug_sk`. Attributes: `generic_name`, `proprietary_name`, `atc_code`, `pharm_class`,
  `dosage_form`, `route`, `labeler_name`, `match_confidence`, `valid_from`, `valid_to`, `is_current`.

**dim_date** — SCD Type 0 (static). `date_sk`, `full_date`, `year`, `month`, `day`, `weekday_name`.

**dim_condition** — SCD Type 1 (overwrite). `condition_sk`, `condition_name` (from Gamma).

## 3. Serving Model (RRD — OBT, derived from star; ADR-001)
- `obt_sales_wide` — fact_sales joined to dim_drug + dim_date, denormalized, clustered on `(year, atc_code)`.
- `obt_review_wide` — fact_review joined to dim_drug + dim_condition + dim_date.
- Materialization: dbt `table` (Snowflake clustered) / `table` (DuckDB). Rebuilt from star, never sourced directly.

## 4. Physical Implementation
- Materialization: dims=`table` (SCD2 incremental), facts=`incremental`, OBT=`table`.
- Partition/cluster: Snowflake cluster `fact_sales(year)`, `fact_review(date_sk)`, OBT as above.
- Source pattern: Alpha=snapshot CSV, Beta=daily snapshot (→SCD2), Gamma=append log.

## 5. ADR References
- ADR-001: star core + OBT serving
- ADR-002: four-tier landing zone
- ADR-003: conformed `dim_drug` crosswalk + partial-match policy
