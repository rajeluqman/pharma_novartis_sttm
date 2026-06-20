{# O-AIR-07 (ADR-007 B1, rep-corrected) — transitive external-upstream registration.
   ----------------------------------------------------------------------------------
   dbt-duckdb's stock register_upstream_external_models() registers ONLY the DIRECT
   external upstreams of the selected nodes. That is insufficient here: dim_drug's
   external Silver dependency stg_beta__ndc is hidden behind the EPHEMERAL int_drug_crosswalk
   (dim_drug -> int_drug_crosswalk[ephemeral] -> stg_beta__ndc[external]). Ephemeral models
   are inlined as CTEs, so the external grandparent must be registered as a view too, or the
   compiled SQL fails with "Table stg_beta__ndc does not exist" in the fresh marts subprocess.

   This macro walks the dependency graph from the selected nodes, recursing THROUGH ephemeral
   nodes, and registers every external ANCESTOR that is not itself being built in this run
   (selected_resources are excluded — their parquet may not exist yet). It deliberately does
   NOT touch downstream external models (e.g. serving OBTs on a marts.core run), so it never
   tries to read a not-yet-written parquet. Replaces the stock call in on-run-start. #}
{% macro register_external_upstreams() %}
{%- if execute and target.type == 'duckdb' -%}
  {% set to_visit = [] %}
  {% for node in selected_resources %}{% do to_visit.append(node) %}{% endfor %}
  {% set seen = {} %}
  {% set to_register = {} %}
  {# bounded worklist traversal (Jinja has no while) — graph is tiny, 1000 is ample #}
  {% for _ in range(1000) %}
    {% if to_visit %}
      {% set cur = to_visit.pop() %}
      {% if cur not in seen %}
        {% do seen.update({cur: None}) %}
        {% set n = graph['nodes'].get(cur) %}
        {% if n %}
          {% for dep in n['depends_on']['nodes'] %}
            {% set dn = graph['nodes'].get(dep) %}
            {% if dn and dn.resource_type in ('model', 'seed') %}
              {% if dn.config.materialized == 'external' and dep not in selected_resources %}
                {% do to_register.update({dep: None}) %}
              {% elif dn.config.materialized == 'ephemeral' %}
                {% do to_visit.append(dep) %}
              {% endif %}
            {% endif %}
          {% endfor %}
        {% endif %}
      {% endif %}
    {% endif %}
  {% endfor %}

  {% set registered_schemas = {} %}
  {% for unique_id in to_register %}
    {% set node = graph['nodes'][unique_id] %}
    {%- set rel = api.Relation.create(
          database=node['database'], schema=node['schema'], identifier=node['alias']
        ) -%}
    {%- set location = node.config.get('location', external_location(rel, node.config)) -%}
    {%- set rendered_options = render_write_options(node.config) -%}
    {%- set read_location = adapter.external_read_location(location, rendered_options) -%}
    {% if rel.schema not in registered_schemas %}
      {% call statement('main', language='sql') -%}
        create schema if not exists {{ rel.without_identifier() }}
      {%- endcall %}
      {% do registered_schemas.update({rel.schema: None}) %}
    {% endif %}
    {{ log("register_external_upstreams: " ~ rel ~ " -> " ~ read_location, info=True) }}
    {% call statement('main', language='sql') -%}
      create or replace view {{ rel }} as (select * from '{{ read_location }}')
    {%- endcall %}
  {% endfor %}
  {% if registered_schemas %}{% do adapter.commit() %}{% endif %}
{%- endif -%}
{% endmacro %}
