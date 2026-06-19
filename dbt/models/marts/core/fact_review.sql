-- Data Mart (STAR) — fact_review. Grain: 1 row = 1 review event (Gamma).
-- drug_sk: normalized drug_name match against dim_drug generic_name/proprietary_name.
-- Many NDC products share one generic/brand name (different labelers/packages); each
-- distinct normalized name collapses to ONE representative drug_sk so the join doesn't
-- fan out fact_review past its declared grain. Unmatched -> drug_sk null (ADR-003 honest
-- partial-match policy; coverage tracked as a DQD KPI, not hidden).
-- dq_flag/dq_reason carried through from stg_gamma__reviews so a null condition_sk here is
-- traceable to "scrubbed for being garbage" vs "source had no condition" (Data Quality Steward
-- Phase 4 condition, DEBATE_LOG_phase_4.md).
-- ADR-005 Decision 5: full deterministic rebuild, NOT incremental — see fact_sales.sql for the
-- full reasoning (S3 has no atomic rename; ephemeral catalog has no guaranteed prior state).
{{ config(materialized='external', location=gold_run_location('fact_review')) }}

with reviews as (
    select review_id, drug_name_norm, condition_name, rating, useful_count, review_date, load_ts,
        dq_flag, dq_reason
    from {{ ref('stg_gamma__reviews') }}
),

drug_names as (
    select
        drug_sk,
        {{ regexp_replace_all('lower(trim(generic_name))', '[^a-z0-9]', '') }} as name_norm
    from {{ ref('dim_drug') }}
    where drug_member_type = 'ndc_product' and is_current and generic_name is not null
    union all
    select
        drug_sk,
        {{ regexp_replace_all('lower(trim(proprietary_name))', '[^a-z0-9]', '') }} as name_norm
    from {{ ref('dim_drug') }}
    where drug_member_type = 'ndc_product' and is_current and proprietary_name is not null
),

name_to_sk as (
    select name_norm, min(drug_sk) as drug_sk
    from drug_names
    where name_norm is not null and name_norm != ''
    group by 1
)

select
    {{ dbt_utils.generate_surrogate_key(['reviews.review_id']) }} as review_sk,
    dim_date.date_sk        as date_sk,
    name_to_sk.drug_sk       as drug_sk,
    dim_condition.condition_sk as condition_sk,
    reviews.rating            as rating,
    reviews.useful_count       as useful_count,
    reviews.dq_flag             as dq_flag,
    reviews.dq_reason           as dq_reason,
    reviews.load_ts             as load_ts
from reviews
left join name_to_sk on reviews.drug_name_norm = name_to_sk.name_norm
left join {{ ref('dim_date') }} as dim_date on reviews.review_date = dim_date.full_date
left join {{ ref('dim_condition') }} as dim_condition on reviews.condition_name = dim_condition.condition_name
