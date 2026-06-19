{# Cross-dialect string->date parsing (dev=duckdb, prod=snowflake — see profiles.yml). #}
{% macro parse_date(column, duckdb_fmt, snowflake_fmt) %}
{% if target.type == 'duckdb' %}
    strptime({{ column }}, '{{ duckdb_fmt }}')::date
{% elif target.type == 'snowflake' %}
    to_date({{ column }}, '{{ snowflake_fmt }}')
{% else %}
    {{ exceptions.raise_compiler_error("parse_date: unsupported target type " ~ target.type) }}
{% endif %}
{% endmacro %}
