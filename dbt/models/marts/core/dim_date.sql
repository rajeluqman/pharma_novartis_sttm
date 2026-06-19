-- Data Mart (STAR) — conformed dim_date, SCD Type 0 (static). Shared by all facts.
-- Spans 2008-01-01..2019-12-31 to cover both Alpha sales (2014-2019) and Gamma reviews (2008-2017).
-- ADR-005 Decision 1/6: Gold, external -> s3://<bucket>/gold/<run_id>/dim_date/.
{{ config(materialized='external', location=gold_run_location('dim_date')) }}

with spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2008-01-01' as date)",
        end_date="cast('2020-01-01' as date)"
    ) }}
)

select
{% if target.type == 'duckdb' %}
    cast(strftime(date_day, '%Y%m%d') as int) as date_sk,
    date_day                                  as full_date,
    extract(year from date_day)               as year,
    extract(month from date_day)              as month,
    extract(day from date_day)                as day,
    dayname(date_day)                         as weekday_name
{% else %}
    cast(to_char(date_day, 'YYYYMMDD') as int) as date_sk,
    date_day                                   as full_date,
    extract(year from date_day)                as year,
    extract(month from date_day)               as month,
    extract(day from date_day)                 as day,
    to_char(date_day, 'DY')                    as weekday_name
{% endif %}
from spine
