-- Enrich (Silver) — Project Gamma reviews. Divergent: free-text drugName + condition.
-- drug_name_norm strips case/whitespace/punctuation for crosswalk matching against dim_drug.
-- condition has a known source DQ defect: scrape artifacts like "74</span> users found this
-- comment helpful." (an HTML tag leaked into the field) instead of a real condition name ->
-- nulled out here, not dropped (rating/drug are still valid signal). Profiled the full 215,063-row
-- column for OTHER anomaly shapes per Business Analyst's Phase 4 review (DEBATE_LOG_phase_4.md):
-- no other HTML tags, no HTML entities, no numeric-only or empty/whitespace values exist beyond
-- this one signature — 1,171 rows is the complete defect count, not just "rows matching one regex."
-- dq_flag/dq_reason (Data Quality Steward's Phase 4 condition) makes the scrub traceable downstream,
-- distinguishing "scrubbed for being garbage" from "source genuinely had no condition" (the other
-- 1,194 null rows, untouched here — that's missing data, not a defect this rule corrects).
-- ADR-005: reads bronze parquet off S3 directly (bronze_parquet() macro), not a relational source.
{{ config(materialized='view') }}

select
    "uniqueID"                                                                 as review_id,
    "drugName"                                                                as drug_name_raw,
    {{ regexp_replace_all("lower(trim(\"drugName\"))", '[^a-z0-9]', '') }}    as drug_name_norm,
    case when regexp_matches("condition", '<[^>]+>') then null else "condition" end as condition_name,
    case when regexp_matches("condition", '<[^>]+>') then true else false end as dq_flag,
    case when regexp_matches("condition", '<[^>]+>') then 'condition: scrape artifact (HTML tag) nulled' end as dq_reason,
    rating,
    "usefulCount"                                                             as useful_count,
    {{ parse_date('"date"', '%d-%b-%y', 'DD-MON-YY') }}                       as review_date,
    load_ts
from {{ bronze_parquet('gamma', 'drug_reviews') }}
where "drugName" is not null
