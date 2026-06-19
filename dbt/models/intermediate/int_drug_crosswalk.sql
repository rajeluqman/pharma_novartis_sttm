-- Consolidation step — conformed drug crosswalk (ADR-003).
-- Reconciles: ATC (alpha, via seed) <-> pharm_class/generic_name (beta NDC).
-- Tiered match (best wins per product_ndc): exact generic name > normalized pharm_class
-- substring > fuzzy generic_name word-boundary match > unmatched. Coverage is a DQD KPI, not 100%.
--
-- Hardened per Business Analyst's Phase 4 review (DEBATE_LOG_phase_4.md):
--   1. is_combination_product flag (generic_name contains " and "/" with "/"/") — combination
--      products are EXCLUDED from the fuzzy tier entirely rather than confidently (and wrongly)
--      tagged with one ingredient's ATC code; they fall to 'combination_unverified' instead of a
--      silently-misleading 'fuzzy' match. This was flagged as "worse than unmatched": a confident
--      wrong answer.
--   2. fuzzy tier uses a word-boundary regex match, not naive LIKE substring containment, so e.g.
--      a hypothetical short seed generic can't false-positive inside an unrelated longer word.
--   3. fuzzy tier requires length(example_generic) >= 5 — guards against short generic names ever
--      added to the seed matching too promiscuously (no current seed row is short enough to trigger
--      this today; it documents the boundary rather than changing today's result).
--   4. deterministic tie-break (secondary `order by atc_code`) if two seed rows ever hit the same
--      tier for one product — previously unordered beyond tier rank.
{{ config(materialized='ephemeral') }}

with ndc as (
    select
        product_ndc,
        generic_name,
        pharm_class,
        (generic_name ilike '% and %' or generic_name ilike '% with %' or generic_name like '%/%')
            as is_combination_product
    from {{ ref('stg_beta__ndc') }}
),

atc as (
    select atc_code, pharm_class_hint, example_generic
    from {{ ref('atc_pharmclass_crosswalk') }}
),

candidates as (
    select
        ndc.product_ndc,
        ndc.is_combination_product,
        atc.atc_code,
        case
            when lower(trim(ndc.generic_name)) = lower(trim(atc.example_generic))
                then 'exact'
            when ndc.pharm_class is not null
                 and lower(ndc.pharm_class) like '%' || lower(atc.pharm_class_hint) || '%'
                then 'normalized'
            when not ndc.is_combination_product
                 and length(atc.example_generic) >= 5
                 and regexp_matches(lower(ndc.generic_name), '\b' || lower(atc.example_generic) || '\b')
                then 'fuzzy'
            when ndc.is_combination_product
                 and length(atc.example_generic) >= 5
                 and regexp_matches(lower(ndc.generic_name), '\b' || lower(atc.example_generic) || '\b')
                then 'combination_unverified'
        end as match_confidence
    from ndc
    cross join atc
),

ranked as (
    select
        product_ndc,
        atc_code,
        match_confidence,
        row_number() over (
            partition by product_ndc
            order by
                case match_confidence
                    when 'exact' then 1
                    when 'normalized' then 2
                    when 'fuzzy' then 3
                    when 'combination_unverified' then 4
                end,
                atc_code
        ) as rn
    from candidates
    where match_confidence is not null
)

select
    ndc.product_ndc,
    ranked.atc_code,
    ndc.generic_name,
    ndc.pharm_class,
    ndc.is_combination_product,
    coalesce(ranked.match_confidence, 'unmatched') as match_confidence
from ndc
left join ranked on ndc.product_ndc = ranked.product_ndc and ranked.rn = 1
