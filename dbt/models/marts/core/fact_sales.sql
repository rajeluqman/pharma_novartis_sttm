-- Data Mart (STAR) — fact_sales. Grain: 1 row = 1 ATC category x 1 day (Alpha).
-- drug_sk resolves to the dim_drug "atc_category" member (Alpha never reports at NDC/product
-- grain, so the category row is the only honest join target — see dim_drug.sql).
-- ADR-005 Decision 5: full deterministic rebuild, NOT incremental — S3 has no atomic rename, so
-- dbt-duckdb's incremental MERGE/this-relation read-modify-write can't be made atomic/replay-safe
-- over an `external` S3 location, and it would need to read {{ this }}'s prior state, which fights
-- the ephemeral catalog (Condition C: no guarantee a prior fact table exists on a cold worker).
-- Facts are small + surrogate keys are content-hashed, so a full rebuild is cheap and idempotent.
-- load_ts still rides through as a column (lineage) — only the incremental filter is removed.
{{ config(materialized='external', location=gold_run_location('fact_sales')) }}

with sales as (
    select sale_date, atc_code, units_sold, load_ts
    from {{ ref('stg_alpha__sales') }}
),

drug_category as (
    select drug_sk, atc_code
    from {{ ref('dim_drug') }}
    where drug_member_type = 'atc_category'
)

select
    {{ dbt_utils.generate_surrogate_key(['sales.sale_date', 'sales.atc_code']) }} as sales_sk,
    dim_date.date_sk        as date_sk,
    drug_category.drug_sk   as drug_sk,
    sales.units_sold         as units_sold,
    sales.load_ts             as load_ts
from sales
left join {{ ref('dim_date') }} as dim_date on sales.sale_date = dim_date.full_date
left join drug_category on sales.atc_code = drug_category.atc_code
