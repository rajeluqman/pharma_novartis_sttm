-- Data Mart (STAR) — dim_condition, SCD Type 1 (overwrite). From Gamma reviews.
-- condition_sk is a stable hash of condition_name (varchar), not a sequence int — see STTM notes.
-- ADR-005 Decision 1/6: Gold, external -> s3://<bucket>/gold/<run_id>/dim_condition/.
{{ config(materialized='external', location=gold_run_location('dim_condition')) }}

with distinct_conditions as (
    select distinct condition_name
    from {{ ref('stg_gamma__reviews') }}
    where condition_name is not null
)

select
    {{ dbt_utils.generate_surrogate_key(['condition_name']) }} as condition_sk,
    condition_name
from distinct_conditions
