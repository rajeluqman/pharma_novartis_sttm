-- Enrich (Silver) — Project Beta NDC product master. Authoritative for dim_drug (ADR-003).
-- One row per product_ndc (dedupe on latest marketing_start_date); marketing_start/end -> SCD2 dates.
-- pharm_class: openFDA returns 0..N classes/product -> flattened to one delimited string so the
-- crosswalk match (int_drug_crosswalk) is a plain string op, portable across duckdb/snowflake.
-- ADR-005: reads bronze parquet off S3 directly (bronze_parquet() macro), not a relational source.
{{ config(materialized='view') }}

with ranked as (
    select
        product_ndc,
        generic_name,
        brand_name as proprietary_name,
        pharm_class,
        route,
        dosage_form,
        labeler_name,
        marketing_start_date,
        marketing_end_date,
        load_ts,
        row_number() over (
            partition by product_ndc
            order by marketing_start_date desc
        ) as rn
    from {{ bronze_parquet('beta', 'ndc_directory') }}
    where product_ndc is not null
)

select
    product_ndc,
    generic_name,
    proprietary_name,
    array_to_string(pharm_class, '; ')                             as pharm_class,
    route[1]                                                       as route,
    dosage_form,
    labeler_name,
    {{ parse_date('marketing_start_date', '%Y%m%d', 'YYYYMMDD') }} as marketing_start_date,
    {{ parse_date('marketing_end_date', '%Y%m%d', 'YYYYMMDD') }}   as marketing_end_date,
    load_ts
from ranked
where rn = 1
