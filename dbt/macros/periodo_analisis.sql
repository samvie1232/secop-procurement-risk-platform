{#- Ventana de los indicadores: los últimos N días hasta la firma más reciente
    (no hasta hoy), así el resultado no cambia según el día en que se corra. -#}
{% macro periodo_analisis() -%}
    select
        max(fecha_de_firma) - interval '{{ var("dias_analisis") }}' day as desde,
        max(fecha_de_firma) as hasta
    from {{ ref('fct_contrato') }}
    where fecha_de_firma <= current_date
{%- endmacro %}
