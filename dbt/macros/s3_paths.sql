{# ADR-005 S3-canonical migration — S3 path macros, env-driven (MinIO now, real AWS later, same code).
   Bucket comes from S3_BUCKET env var (default novartis-pharma-sttm-lake, ADR-005 Decision 4). #}

{% macro s3_bucket() %}
{{ return(env_var('S3_BUCKET', 'novartis-pharma-sttm-lake')) }}
{% endmacro %}

{# Bronze source replacement for the old relational {{ source(src, table) }} pattern (Decision 6).
   load_date passed via --vars '{"load_date": "<date>"}'; defaults to today if not supplied (dev convenience). #}
{% macro bronze_parquet(src, table) %}
{%- set load_date = var('load_date') -%}
{%- set path = "s3://" ~ s3_bucket() ~ "/bronze/" ~ src ~ "/" ~ load_date ~ "/" ~ table ~ ".parquet" -%}
read_parquet('{{ path }}')
{% endmacro %}

{# Silver (staging-equivalent canonical) location — not used while staging stays `view`,
   kept for any model that needs an explicit Silver S3 location. #}
{% macro silver_location(model_name) %}
{{ return("s3://" ~ s3_bucket() ~ "/silver/" ~ model_name ~ "/" ~ model_name ~ ".parquet") }}
{% endmacro %}

{# Gold per-run location (Decision 1: write to gold/<run_id>/ first, publish step copies to gold/_current/).
   run_id passed via --vars '{"run_id": "<id>"}'; defaults to 'dev' for ad-hoc local runs. #}
{% macro gold_run_location(model_name) %}
{%- set run_id = var('run_id', 'dev') -%}
{{ return("s3://" ~ s3_bucket() ~ "/gold/" ~ run_id ~ "/" ~ model_name ~ "/" ~ model_name ~ ".parquet") }}
{% endmacro %}

{# Snapshot history location (Decision 2). #}
{% macro snapshot_location(snapshot_name) %}
{{ return("s3://" ~ s3_bucket() ~ "/snapshots/" ~ snapshot_name ~ "/" ~ snapshot_name ~ ".parquet") }}
{% endmacro %}
