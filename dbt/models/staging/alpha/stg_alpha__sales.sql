-- Enrich (Silver) — Project Alpha sales. Divergent source: ATC category columns, wide.
-- Unpivots the 8 ATC columns -> long (atc_code, units_sold); negative units -> 0 (business rule).
-- ADR-005: reads bronze parquet off S3 directly (bronze_parquet() macro), not a relational source.
{{ config(materialized='view') }}

with base as (
    select
        datum as sale_date,
        "M01AB" as m01ab, "M01AE" as m01ae, "N02BA" as n02ba, "N02BE" as n02be,
        "N05B" as n05b, "N05C" as n05c, "R03" as r03, "R06" as r06,
        load_ts
    from {{ bronze_parquet('alpha', 'sales_daily') }}
),

unpivoted as (
    select sale_date, 'M01AB' as atc_code, m01ab as units_sold, load_ts from base
    union all
    select sale_date, 'M01AE', m01ae, load_ts from base
    union all
    select sale_date, 'N02BA', n02ba, load_ts from base
    union all
    select sale_date, 'N02BE', n02be, load_ts from base
    union all
    select sale_date, 'N05B', n05b, load_ts from base
    union all
    select sale_date, 'N05C', n05c, load_ts from base
    union all
    select sale_date, 'R03', r03, load_ts from base
    union all
    select sale_date, 'R06', r06, load_ts from base
)

select
    sale_date,
    atc_code,
    case when units_sold < 0 then 0 else units_sold end as units_sold,
    load_ts
from unpivoted
