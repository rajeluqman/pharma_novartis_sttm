-- RRD (serving) — OBT, derived from the star (ADR-001). NOT a source of truth.
-- drug_sk always resolves here (fact_sales only ever joins the dim_drug category_seed rows).
-- ADR-005 Decision 1/6: Gold, external -> s3://<bucket>/gold/<run_id>/obt_sales_wide/ (dev/duckdb).
{% if target.type == 'snowflake' %}
{{ config(materialized='table', cluster_by=['year', 'atc_code']) }}
{% else %}
{{ config(materialized='external', location=gold_run_location('obt_sales_wide')) }}
{% endif %}

select
    f.sales_sk,
    f.units_sold,
    dt.full_date    as sale_date,
    dt.year,
    dt.month,
    dt.weekday_name,
    d.atc_code,
    d.generic_name,
    d.pharm_class
from {{ ref('fact_sales') }} f
join {{ ref('dim_date') }} dt on f.date_sk = dt.date_sk
join {{ ref('dim_drug') }} d on f.drug_sk = d.drug_sk
