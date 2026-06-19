-- Data Mart (STAR) — conformed dim_drug, SCD Type 2 (ADR-001, ADR-003).
-- Two member types in one conformed dimension, distinguished by drug_member_type (not by
-- match_confidence — Data Architect's Phase 4 review condition, DEBATE_LOG_phase_4.md: overloading
-- match_confidence with row provenance corrupted the crosswalk coverage KPI denominator):
--   1. 'ndc_product' rows (authoritative source: Beta, via snap_beta_ndc SCD2 snapshot),
--      atc_code attached via int_drug_crosswalk; match_confidence ∈ {exact,normalized,fuzzy,unmatched}.
--   2. 'atc_category' rows (one per seed code) — Alpha sales only ever report at category
--      grain (no NDC), so fact_sales needs a stable join target the NDC rows can't give it.
--      match_confidence is NULL for these — crosswalk confidence doesn't apply to a seed row, and
--      the coverage KPI (computed only where match_confidence is not null) is now correct by
--      construction instead of needing a manual WHERE drug_member_type filter.
-- drug_sk is a hash key (varchar), not a sequence int — see STTM notes.
-- ADR-005 Decision 1/6: Gold, external -> s3://<bucket>/gold/<run_id>/dim_drug/.
{{ config(materialized='external', location=gold_run_location('dim_drug')) }}

with snapshot as (
    select
        product_ndc, generic_name, proprietary_name, pharm_class, route, dosage_form,
        labeler_name, dbt_valid_from, dbt_valid_to
    from {{ ref('snap_beta_ndc') }}
),

crosswalk as (
    select product_ndc, atc_code, match_confidence, is_combination_product
    from {{ ref('int_drug_crosswalk') }}
),

ndc_rows as (
    select
        {{ dbt_utils.generate_surrogate_key(['snapshot.product_ndc', 'snapshot.dbt_valid_from']) }} as drug_sk,
        'ndc_product'                             as drug_member_type,
        snapshot.product_ndc                    as product_ndc,
        crosswalk.atc_code                       as atc_code,
        snapshot.generic_name                    as generic_name,
        snapshot.proprietary_name                as proprietary_name,
        snapshot.pharm_class                      as pharm_class,
        snapshot.dosage_form                      as dosage_form,
        snapshot.route                            as route,
        snapshot.labeler_name                     as labeler_name,
        coalesce(crosswalk.match_confidence, 'unmatched') as match_confidence,
        coalesce(crosswalk.is_combination_product, false) as is_combination_product,
        cast(snapshot.dbt_valid_from as date)     as valid_from,
        cast(snapshot.dbt_valid_to as date)       as valid_to,
        (snapshot.dbt_valid_to is null)           as is_current
    from snapshot
    left join crosswalk on snapshot.product_ndc = crosswalk.product_ndc
),

category_rows as (
    select
        {{ dbt_utils.generate_surrogate_key(['atc_code']) }} as drug_sk,
        'atc_category'           as drug_member_type,
        cast(null as varchar)  as product_ndc,
        atc_code                as atc_code,
        example_generic         as generic_name,
        cast(null as varchar)  as proprietary_name,
        pharm_class_hint        as pharm_class,
        cast(null as varchar)  as dosage_form,
        cast(null as varchar)  as route,
        cast(null as varchar)  as labeler_name,
        cast(null as varchar)  as match_confidence,
        false                    as is_combination_product,
        cast('1900-01-01' as date) as valid_from,
        cast(null as date)     as valid_to,
        true                    as is_current
    from {{ ref('atc_pharmclass_crosswalk') }}
)

select * from ndc_rows
union all
select * from category_rows
