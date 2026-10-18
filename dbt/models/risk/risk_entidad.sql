-- Indicadores de riesgo por entidad en el periodo de análisis y un puntaje
-- compuesto (0 a 100) para priorizar revisiones. Son señales, no pruebas.

with periodo as (

    {{ periodo_analisis() }}

),

contratos as (

    select c.*
    from {{ ref('fct_contrato') }} as c
    cross join periodo as p
    where c.fecha_de_firma between p.desde and p.hasta
      and c.valor_del_contrato >= 0

),

por_entidad as (

    select
        codigo_entidad,
        count(*) as contratos,
        sum(valor_del_contrato) as valor_total,
        avg(if(es_contratacion_directa, 1.0, 0.0)) as pct_directa_contratos,
        cast(sum(if(es_contratacion_directa, valor_del_contrato, 0)) as double)
            / nullif(cast(sum(valor_del_contrato) as double), 0) as pct_directa_valor
    from contratos
    group by codigo_entidad

),

valor_por_proveedor as (

    select
        codigo_entidad,
        codigo_proveedor,
        cast(sum(valor_del_contrato) as double) as valor
    from contratos
    where codigo_proveedor is not null
    group by codigo_entidad, codigo_proveedor

),

concentracion as (

    -- Índice Herfindahl-Hirschman: suma de las participaciones (en %) al
    -- cuadrado. 10.000 = un solo proveedor se lleva todo; cerca de 0 = muy repartido.
    select
        codigo_entidad,
        count(*) as proveedores,
        sum(power(100 * valor / nullif(total, 0), 2)) as hhi
    from (
        select *, sum(valor) over (partition by codigo_entidad) as total
        from valor_por_proveedor
    )
    group by codigo_entidad

),

fraccionamiento as (

    select codigo_entidad, count(*) as proveedores_con_fraccionamiento
    from {{ ref('risk_fraccionamiento') }}
    group by codigo_entidad

),

indicadores as (

    select
        e.codigo_entidad,
        e.contratos,
        e.valor_total,
        e.pct_directa_contratos,
        e.pct_directa_valor,
        c.proveedores,
        c.hhi,
        coalesce(f.proveedores_con_fraccionamiento, 0) as proveedores_con_fraccionamiento,
        e.contratos >= {{ var('min_contratos_entidad') }} as muestra_suficiente
    from por_entidad as e
    left join concentracion as c on e.codigo_entidad = c.codigo_entidad
    left join fraccionamiento as f on e.codigo_entidad = f.codigo_entidad

)

select
    i.*,
    -- Percentiles contra entidades con muestra suficiente: 1 = la más alta.
    case when muestra_suficiente then round(100 * (
          0.4 * percent_rank() over (partition by muestra_suficiente order by coalesce(pct_directa_valor, 0))
        + 0.4 * percent_rank() over (partition by muestra_suficiente order by coalesce(hhi, 0))
        + 0.2 * percent_rank() over (partition by muestra_suficiente order by proveedores_con_fraccionamiento)
    ), 1) end as puntaje_riesgo,
    d.nombre_entidad,
    d.orden,
    d.departamento
from indicadores as i
left join {{ ref('dim_entidad') }} as d on i.codigo_entidad = d.codigo_entidad
