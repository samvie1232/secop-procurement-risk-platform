-- Validación manual de las 5 entidades con más riesgo en el tablero.
-- Para cada una: los 2 proveedores que más valor se llevaron en el periodo de
-- análisis, su participación y el contrato más grande de cada uno (con su
-- enlace a SECOP II para revisarlo a mano). Escanea unos pocos cientos de MB.
with periodo as (

    select
        max(fecha_de_firma) - interval '365' day as desde,
        max(fecha_de_firma) as hasta
    from secop_analytics.fct_contrato
    where fecha_de_firma <= current_date

),

contratos as (

    select c.*
    from secop_analytics.fct_contrato as c
    cross join periodo as p
    where c.fecha_de_firma between p.desde and p.hasta
      and c.valor_del_contrato >= 0
      and c.codigo_entidad in (
          '700077019',  -- Ministerio de Minas y Energía
          '710593401',  -- Alcaldía de Santo Tomás, Atlántico
          '700409022',  -- Fuerza Aeroespacial Colombiana
          '700637051',  -- Ministerio de Salud y Protección Social
          '700774011'   -- Inder Medellín
      )

),

por_proveedor as (

    select
        codigo_entidad,
        codigo_proveedor,
        count(*) as contratos,
        cast(sum(valor_del_contrato) as double) as valor,
        max_by(modalidad_de_contratacion, valor_del_contrato) as modalidad_mayor,
        max_by(objeto_del_contrato, valor_del_contrato) as objeto_mayor,
        max_by(url_proceso, valor_del_contrato) as url_mayor
    from contratos
    group by codigo_entidad, codigo_proveedor

),

ranking as (

    select
        *,
        valor / sum(valor) over (partition by codigo_entidad) as participacion,
        row_number() over (partition by codigo_entidad order by valor desc) as puesto
    from por_proveedor

)

select
    e.nombre_entidad,
    r.puesto,
    case
        when r.codigo_proveedor is null then 'Sin proveedor'
        when upper(d.tipo_documento_proveedor) like '%NIT%' then d.nombre_proveedor
        else 'Persona natural'
    end as proveedor,
    r.contratos,
    round(r.valor / 1e9, 1) as valor_miles_millones,
    round(100 * r.participacion, 1) as pct_valor_entidad,
    r.modalidad_mayor,
    substr(r.objeto_mayor, 1, 150) as objeto_contrato_mayor,
    r.url_mayor
from ranking as r
left join secop_analytics.dim_entidad as e
    on r.codigo_entidad = e.codigo_entidad
left join secop_analytics.dim_proveedor as d
    on r.codigo_proveedor = d.codigo_proveedor and d.es_actual
where r.puesto <= 2
order by e.nombre_entidad, r.puesto
