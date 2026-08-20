{#
    dbt's default behaviour prefixes a model's custom schema with the target
    schema, so a model configured for "staging" would land in "public_staging".
    The demo shows lineage on screen, and raw -> staging -> analytics reads as
    an actual pipeline where public_staging does not.

    This override uses the configured schema verbatim and falls back to the
    target schema when a model configures none.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
