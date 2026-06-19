{# Cross-dialect global regex replace — duckdb needs the 'g' flag, snowflake replaces all by default. #}
{% macro regexp_replace_all(column, pattern, replacement) %}
{% if target.type == 'duckdb' %}
    regexp_replace({{ column }}, '{{ pattern }}', '{{ replacement }}', 'g')
{% else %}
    regexp_replace({{ column }}, '{{ pattern }}', '{{ replacement }}')
{% endif %}
{% endmacro %}
