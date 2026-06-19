-- RRD (serving) — OBT, derived from the star (ADR-001). NOT a source of truth.
-- drug_sk/condition_sk may be null (ADR-003 partial-match policy) — left joins preserve the
-- review row either way; coverage is measured on fact_review, not hidden by an inner join here.
-- ADR-005 Decision 1/6: Gold, external -> s3://<bucket>/gold/<run_id>/obt_review_wide/ (dev/duckdb).
{% if target.type == 'snowflake' %}
{{ config(materialized='table', cluster_by=['year']) }}
{% else %}
{{ config(materialized='external', location=gold_run_location('obt_review_wide')) }}
{% endif %}

select
    f.review_sk,
    f.rating,
    f.useful_count,
    dt.full_date    as review_date,
    dt.year,
    dt.month,
    c.condition_name,
    d.generic_name,
    d.proprietary_name,
    d.atc_code
from {{ ref('fact_review') }} f
join {{ ref('dim_date') }} dt on f.date_sk = dt.date_sk
left join {{ ref('dim_condition') }} c on f.condition_sk = c.condition_sk
left join {{ ref('dim_drug') }} d on f.drug_sk = d.drug_sk
