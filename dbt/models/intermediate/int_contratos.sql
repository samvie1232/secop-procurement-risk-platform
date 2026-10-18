-- Una fila por id_contrato: la versión vigente de cada contrato.
--
-- Incremental con merge en Iceberg: cada corrida lee solo las particiones
-- nuevas de raw, se queda con la versión más reciente de cada contrato y la
-- fusiona con lo que ya existe. Repetir una corrida no duplica nada.
{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='id_contrato',
        update_condition="coalesce(src.ultima_actualizacion, date '1900-01-01') >= coalesce(target.ultima_actualizacion, date '1900-01-01')",
        partitioned_by=['year(fecha_de_firma)'],
        on_schema_change='append_new_columns',
    )
}}

{%- set desde = none -%}
{%- if execute and is_incremental() -%}
    {#- La fecha va como literal (no como subconsulta) para que Athena descarte
        las particiones viejas de raw sin leerlas: eso es lo que mantiene barata
        la corrida diaria. Se vuelve a leer la última fecha por si se reintentó. -#}
    {%- set desde = run_query('select max(fecha_carga) from ' ~ this).columns[0].values()[0] -%}
{%- endif %}

with nuevos as (

    select *
    from {{ ref('stg_secop__contratos') }}
    where id_contrato is not null
    {%- if desde is not none %}
      and fecha_carga >= date '{{ desde }}'
    {%- endif %}

),

ordenados as (

    -- Regla del contrato de datos: gana la mayor ultima_actualizacion; si
    -- empatan (o no tiene), gana la extracción más reciente.
    select
        *,
        row_number() over (
            partition by id_contrato
            order by ultima_actualizacion desc nulls last, fecha_carga desc, extraido_en desc
        ) as orden_version
    from nuevos

)

select
    id_contrato,
    proceso_de_compra,
    referencia_del_contrato,
    estado_contrato,
    codigo_de_categoria_principal,
    descripcion_del_proceso,
    objeto_del_contrato,
    tipo_de_contrato,
    modalidad_de_contratacion,
    es_contratacion_directa,
    justificacion_modalidad,
    url_proceso,
    codigo_entidad,
    nit_entidad,
    nombre_entidad,
    departamento,
    ciudad,
    orden,
    sector,
    rama,
    entidad_centralizada,
    codigo_proveedor,
    tipo_documento_proveedor,
    documento_proveedor,
    nombre_proveedor,
    es_grupo,
    es_pyme,
    fecha_de_firma,
    fecha_de_inicio,
    fecha_de_fin,
    ultima_actualizacion,
    duracion_del_contrato,
    dias_adicionados,
    puede_ser_prorrogado,
    valor_del_contrato,
    valor_de_pago_adelantado,
    valor_facturado,
    valor_pagado,
    valor_pendiente_de_pago,
    valor_pendiente_de_ejecucion,
    origen_de_los_recursos,
    destino_gasto,
    recursos_pgn,
    recursos_sgp,
    recursos_regalias,
    recursos_propios,
    recursos_de_credito,
    fecha_carga,
    extraido_en
from ordenados
where orden_version = 1
