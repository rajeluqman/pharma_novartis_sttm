{# ADR-005 Decision 2 — documented deviation (see scripts/snapshot_beta_ndc.py docstring for the
   full why). dbt-core's `snapshot` materialization has no `external`/`location` hook, so the S3
   persistence Decision 2 requires is implemented as on-run-start (load prior state) /
   on-run-end (export new state) hooks around the stock relational `snapshot` materialization,
   inside the SAME ephemeral :memory: DuckDB session for the whole `dbt snapshot` invocation. #}

{% macro load_snap_beta_ndc_from_s3() %}
  {%- if execute and target.type == 'duckdb' and flags.WHICH in ['snapshot', 'build'] -%}
    {%- set s3_path = snapshot_location('snap_beta_ndc') -%}
    {%- set glob_path = s3_bucket() ~ '/snapshots/snap_beta_ndc/*.parquet' -%}
    {%- set check_sql -%}
      select count(*) from glob('s3://{{ glob_path }}')
    {%- endset -%}
    {%- set exists_result = run_query(check_sql) -%}
    {%- set file_count = exists_result.columns[0].values()[0] if exists_result else 0 -%}
    {%- if file_count and file_count > 0 -%}
      {{ log("snap_beta_ndc: loading prior SCD2 state from " ~ s3_path, info=True) }}
      {%- do run_query("create schema if not exists snapshots") -%}
      {%- do run_query("create or replace table snapshots.snap_beta_ndc as select * from read_parquet('" ~ s3_path ~ "')") -%}
      {#- The table above is created via raw run_query(), which bypasses dbt's adapter relation
          cache. The snapshot materialization's existence check (get_or_create_relation ->
          adapter.get_relation) reads ONLY that cache, not a live catalog query — so without
          registering this relation, dbt thinks snapshots.snap_beta_ndc doesn't exist, takes the
          initial-build branch, and its `create table` collides with the table we just made.
          adapter.cache_added() is dbt's own blessed way to tell the cache about a relation
          created outside its normal materialization flow (same mechanism dbt uses internally
          after seed/snapshot DDL). Must register AFTER the table physically exists. -#}
      {%- set loaded_relation = api.Relation.create(
            database=target.database, schema='snapshots', identifier='snap_beta_ndc', type='table'
          ) -%}
      {%- do adapter.cache_added(loaded_relation) -%}
    {%- else -%}
      {{ log("snap_beta_ndc: no prior S3 state found at " ~ s3_path ~ " — first run, dbt will build fresh", info=True) }}
    {%- endif -%}
  {%- endif -%}
{% endmacro %}

{% macro export_snap_beta_ndc_to_s3() %}
  {%- if execute and target.type == 'duckdb' and flags.WHICH in ['snapshot', 'build'] -%}
    {%- set s3_path = snapshot_location('snap_beta_ndc') -%}
    {%- set relation_exists_sql -%}
      select count(*) from information_schema.tables
      where table_schema = 'snapshots' and table_name = 'snap_beta_ndc'
    {%- endset -%}
    {%- set check = run_query(relation_exists_sql) -%}
    {%- set tbl_count = check.columns[0].values()[0] if check else 0 -%}
    {%- if tbl_count and tbl_count > 0 -%}
      {{ log("snap_beta_ndc: exporting post-snapshot SCD2 state to " ~ s3_path, info=True) }}
      {%- do run_query("copy (select * from snapshots.snap_beta_ndc) to '" ~ s3_path ~ "' (format parquet)") -%}
    {%- else -%}
      {{ log("snap_beta_ndc: snapshots.snap_beta_ndc table not found post-run — nothing to export (snapshot may have failed)", info=True) }}
    {%- endif -%}
  {%- endif -%}
{% endmacro %}
