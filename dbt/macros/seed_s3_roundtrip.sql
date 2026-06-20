{# O-AIR-07 (ADR-007 B1, rep-corrected) — seed S3 roundtrip, mirroring snapshot_s3_roundtrip.sql.
   ----------------------------------------------------------------------------------------------
   dbt-duckdb seeds load into the ephemeral :memory: catalog as a relational table — like the
   snapshot, they have no `external`/`location` hook, so they do NOT survive the orchestrated DAG's
   per-task subprocess boundary (ADR-005 Condition C). atc_pharmclass_crosswalk is read by
   int_drug_crosswalk + dim_drug, both built in the `dbt run -s marts.core` subprocess, where the
   seed table is absent. (register_external_upstreams can't cover it: a seed is not an `external`
   model.) So we persist the seed to S3 (under the ADR-005 silver/ prefix) on seed/build, and reload
   it on run/snapshot — the SAME documented-deviation pattern Decision 2 uses for snap_beta_ndc.
   Static reference data; deterministic-overwrite at a fixed path (idempotent). #}

{% macro _seed_s3_path() %}{{ return("s3://" ~ s3_bucket() ~ "/silver/seeds/atc_pharmclass_crosswalk/atc_pharmclass_crosswalk.parquet") }}{% endmacro %}

{% macro export_seed_to_s3() %}
  {%- if execute and target.type == 'duckdb' and flags.WHICH in ['seed', 'build'] -%}
    {%- set s3_path = _seed_s3_path() -%}
    {%- set check_sql -%}
      select count(*) from information_schema.tables
      where table_name = 'atc_pharmclass_crosswalk'
    {%- endset -%}
    {%- set check = run_query(check_sql) -%}
    {%- set tbl_count = check.columns[0].values()[0] if check else 0 -%}
    {%- if tbl_count and tbl_count > 0 -%}
      {{ log("atc_pharmclass_crosswalk: exporting seed to " ~ s3_path, info=True) }}
      {%- do run_query("copy (select * from " ~ target.schema ~ "_enrich.atc_pharmclass_crosswalk) to '" ~ s3_path ~ "' (format parquet)") -%}
    {%- else -%}
      {{ log("atc_pharmclass_crosswalk: seed table not found post-run — nothing to export", info=True) }}
    {%- endif -%}
  {%- endif -%}
{% endmacro %}

{% macro load_seed_from_s3() %}
  {#- run/snapshot/build/test: restore the seed table from S3 so marts.core (and the seed's own
      unique/not_null tests in the `dbt test` subprocess) can read it across the task boundary.
      seed/build pass through harmlessly (the real table is rebuilt by `dbt seed` itself; this
      just no-ops if S3 has no copy yet on the very first seed). -#}
  {%- if execute and target.type == 'duckdb' and flags.WHICH in ['run', 'snapshot', 'build', 'test'] -%}
    {%- set s3_path = _seed_s3_path() -%}
    {%- set glob_path = s3_bucket() ~ '/silver/seeds/atc_pharmclass_crosswalk/*.parquet' -%}
    {%- set exists_result = run_query("select count(*) from glob('s3://" ~ glob_path ~ "')") -%}
    {%- set file_count = exists_result.columns[0].values()[0] if exists_result else 0 -%}
    {%- if file_count and file_count > 0 -%}
      {%- set schema_name = target.schema ~ '_enrich' -%}
      {{ log("atc_pharmclass_crosswalk: loading seed from " ~ s3_path, info=True) }}
      {%- do run_query("create schema if not exists " ~ schema_name) -%}
      {%- do run_query("create or replace table " ~ schema_name ~ ".atc_pharmclass_crosswalk as select * from read_parquet('" ~ s3_path ~ "')") -%}
      {%- set loaded_relation = api.Relation.create(
            database=target.database, schema=schema_name, identifier='atc_pharmclass_crosswalk', type='table'
          ) -%}
      {%- do adapter.cache_added(loaded_relation) -%}
    {%- endif -%}
  {%- endif -%}
{% endmacro %}
