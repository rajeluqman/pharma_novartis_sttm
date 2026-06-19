-- Singular test (Data Architect condition, DEBATE_LOG_phase_4.md): dim_drug must carry exactly
-- one 'atc_category' member per row in the ATC seed — no more, no fewer. Returns 0 rows = pass.
with counts as (
    select
        (select count(*) from {{ ref('dim_drug') }} where drug_member_type = 'atc_category') as category_rows,
        (select count(*) from {{ ref('atc_pharmclass_crosswalk') }}) as seed_rows
)
select * from counts where category_rows != seed_rows
