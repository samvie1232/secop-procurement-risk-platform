-- Contratos que la señal de texto debe leer: los que ya marca al menos uno de
-- los otros indicadores en el periodo de análisis. Una fila por contrato, con
-- los motivos y el texto que se le pasa a Claude.
--
-- Motivos (prioridad = cuántos tiene):
--   fraccionamiento: contrato directo de una pareja entidad-proveedor con la señal.
--   proveedor_nuevo: contrato de un proveedor nuevo con contratos grandes,
--                    firmado en sus primeros 90 días.
--   entidad_alto_puntaje: contrato directo de una entidad con puntaje >=
--                    texto_puntaje_entidad_min (concentración y % de directa).

with periodo as (

    {{ periodo_analisis() }}

),

contratos as (

    select c.*
    from {{ ref('int_contratos') }} as c
    cross join periodo as p
    where c.fecha_de_firma between p.desde and p.hasta
      and c.valor_del_contrato >= 0

),

marcas as (

    select
        c.id_contrato,
        c.es_contratacion_directa and f.codigo_entidad is not null as por_fraccionamiento,
        coalesce(
            pr.alerta_nuevo_con_contrato_grande
            and c.fecha_de_firma <= pr.primera_firma + interval '90' day,
            false
        ) as por_proveedor_nuevo,
        c.es_contratacion_directa
            and coalesce(e.puntaje_riesgo >= {{ var('texto_puntaje_entidad_min') }}, false)
            as por_entidad_alto_puntaje
    from contratos as c
    left join {{ ref('risk_fraccionamiento') }} as f
        on c.codigo_entidad = f.codigo_entidad and c.codigo_proveedor = f.codigo_proveedor
    left join {{ ref('risk_proveedor') }} as pr on c.codigo_proveedor = pr.codigo_proveedor
    left join {{ ref('risk_entidad') }} as e on c.codigo_entidad = e.codigo_entidad

)

select
    c.id_contrato,
    c.codigo_entidad,
    c.codigo_proveedor,
    c.nombre_entidad,
    c.orden,
    c.sector,
    c.tipo_documento_proveedor,
    -- Solo empresas con nombre: muchos proveedores son personas naturales.
    if(upper(c.tipo_documento_proveedor) like '%NIT%', c.nombre_proveedor) as nombre_proveedor,
    c.tipo_de_contrato,
    c.modalidad_de_contratacion,
    c.valor_del_contrato,
    c.fecha_de_firma,
    c.duracion_del_contrato,
    c.codigo_de_categoria_principal,
    c.objeto_del_contrato,
    c.descripcion_del_proceso,
    c.justificacion_modalidad,
    c.url_proceso,
    m.por_fraccionamiento,
    m.por_proveedor_nuevo,
    m.por_entidad_alto_puntaje,
    if(m.por_fraccionamiento, 1, 0)
        + if(m.por_proveedor_nuevo, 1, 0)
        + if(m.por_entidad_alto_puntaje, 1, 0) as prioridad,
    array_join(filter(array[
        if(m.por_fraccionamiento, 'fraccionamiento'),
        if(m.por_proveedor_nuevo, 'proveedor nuevo con contratos grandes'),
        if(m.por_entidad_alto_puntaje, 'entidad con puntaje alto (directa y concentración)')
    ], x -> x is not null), ', ') as motivos
from contratos as c
inner join marcas as m on c.id_contrato = m.id_contrato
where m.por_fraccionamiento or m.por_proveedor_nuevo or m.por_entidad_alto_puntaje
