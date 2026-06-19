-- SCD2 history for the Beta NDC product master — feeds dim_drug (ADR-003).
-- check strategy: openFDA has no reliable updated_at field, so we diff the business columns.
{% snapshot snap_beta_ndc %}

{{
    config(
        target_schema='snapshots',
        unique_key='product_ndc',
        strategy='check',
        check_cols=[
            'generic_name', 'proprietary_name', 'pharm_class', 'route',
            'dosage_form', 'labeler_name', 'marketing_start_date', 'marketing_end_date'
        ],
    )
}}

select * from {{ ref('stg_beta__ndc') }}

{% endsnapshot %}
