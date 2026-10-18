-- Señal de fraccionamiento: un mismo proveedor recibe varios contratos
-- directos de la misma entidad en pocos días. Una fila por pareja
-- entidad-proveedor con alerta en el periodo de análisis.
--
-- Limitación: el brief pide además que cada contrato quede "justo bajo un
-- tope", pero los topes dependen del presupuesto de cada entidad y SECOP no
-- los publica; aquí solo se mide la repetición.

with periodo as (

    {{ periodo_analisis() }}

),

directos as (

    select
        c.id_contrato,
        c.codigo_entidad,
        c.codigo_proveedor,
        c.fecha_de_firma,
        c.valor_del_contrato,
        date_diff('day', date '2000-01-01', c.fecha_de_firma) as dia
    from {{ ref('fct_contrato') }} as c
    cross join periodo as p
    where c.es_contratacion_directa
      and c.codigo_proveedor is not null
      and c.fecha_de_firma between p.desde and p.hasta

),

ventanas as (

    -- Para cada contrato: cuántos contratos (y cuánto valor) firmó la misma
    -- pareja en los N días anteriores, contándolo a él.
    select
        *,
        count(*) over (
            partition by codigo_entidad, codigo_proveedor
            order by dia
            range between {{ var('fraccionamiento_dias') }} preceding and current row
        ) as contratos_ventana,
        sum(valor_del_contrato) over (
            partition by codigo_entidad, codigo_proveedor
            order by dia
            range between {{ var('fraccionamiento_dias') }} preceding and current row
        ) as valor_ventana
    from directos

)

select
    codigo_entidad,
    codigo_proveedor,
    count(*) as contratos_directos,
    sum(valor_del_contrato) as valor_directo,
    max(contratos_ventana) as max_contratos_ventana,
    max_by(valor_ventana, contratos_ventana) as valor_ventana_pico,
    max_by(fecha_de_firma, contratos_ventana) as fecha_pico
from ventanas
group by codigo_entidad, codigo_proveedor
having max(contratos_ventana) >= {{ var('fraccionamiento_min_contratos') }}
