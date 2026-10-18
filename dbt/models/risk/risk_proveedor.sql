-- Indicadores de riesgo por proveedor en el periodo de análisis y un puntaje
-- compuesto (0 a 100). Señales para priorizar revisiones, no pruebas.

with periodo as (

    {{ periodo_analisis() }}

),

contratos as (

    select c.*
    from {{ ref('fct_contrato') }} as c
    cross join periodo as p
    where c.fecha_de_firma between p.desde and p.hasta
      and c.codigo_proveedor is not null
      and c.valor_del_contrato >= 0

),

umbral as (

    -- "Contrato grande" = dentro del 5 % de mayor valor del periodo.
    select approx_percentile(cast(valor_del_contrato as double), 0.95) as valor_p95
    from contratos

),

proveedores as (

    select codigo_proveedor, nombre_proveedor, primera_firma
    from {{ ref('dim_proveedor') }}
    where es_actual

),

por_proveedor as (

    select
        c.codigo_proveedor,
        count(*) as contratos,
        count(distinct c.codigo_entidad) as entidades,
        sum(c.valor_del_contrato) as valor_total,
        cast(sum(if(c.es_contratacion_directa, c.valor_del_contrato, 0)) as double)
            / nullif(cast(sum(c.valor_del_contrato) as double), 0) as pct_directa_valor,
        -- Contratos grandes en sus primeros 90 días en SECOP II.
        count_if(
            cast(c.valor_del_contrato as double) >= u.valor_p95
            and c.fecha_de_firma <= p.primera_firma + interval '90' day
        ) as contratos_grandes_al_inicio
    from contratos as c
    inner join proveedores as p on c.codigo_proveedor = p.codigo_proveedor
    cross join umbral as u
    group by c.codigo_proveedor

),

fraccionamiento as (

    select codigo_proveedor, count(*) as entidades_con_fraccionamiento
    from {{ ref('risk_fraccionamiento') }}
    group by codigo_proveedor

),

indicadores as (

    select
        x.*,
        p.nombre_proveedor,
        p.primera_firma,
        -- "Nuevo" solo si apareció 6 meses después del inicio de la historia
        -- cargada; antes no se puede saber si ya existía.
        p.primera_firma >= date '{{ var("inicio_historia") }}' + interval '180' day as es_nuevo,
        coalesce(f.entidades_con_fraccionamiento, 0) as entidades_con_fraccionamiento
    from por_proveedor as x
    inner join proveedores as p on x.codigo_proveedor = p.codigo_proveedor
    left join fraccionamiento as f on x.codigo_proveedor = f.codigo_proveedor

)

select
    *,
    es_nuevo and contratos_grandes_al_inicio > 0 as alerta_nuevo_con_contrato_grande,
    round(100 * (
          0.5 * if(es_nuevo and contratos_grandes_al_inicio > 0, 1, 0)
        + 0.3 * percent_rank() over (order by entidades_con_fraccionamiento)
        + 0.2 * percent_rank() over (order by coalesce(pct_directa_valor, 0))
    ), 1) as puntaje_riesgo
from indicadores
