-- Limpieza y tipos sobre raw, sin cambiar el grano: sigue habiendo una fila
-- por contrato y por extracción. Los nombres raros de la API se renombran.

with fuente as (

    select * from {{ source('secop_raw', 'contratos') }}
    {%- if var('muestra_fecha_carga', none) %}
    -- Muestra para el CI: una sola partición de raw y solo los contratos
    -- firmados en sus últimos 30 días. Fuera del CI la var no existe.
    where fecha_carga = date '{{ var("muestra_fecha_carga") }}'
      and {{ a_fecha('fecha_de_firma') }} >= date '{{ var("muestra_fecha_carga") }}' - interval '30' day
    {%- endif %}

)

select
    -- Contrato
    {{ texto('id_contrato') }} as id_contrato,
    {{ texto('proceso_de_compra') }} as proceso_de_compra,
    {{ texto('referencia_del_contrato') }} as referencia_del_contrato,
    {{ texto('estado_contrato') }} as estado_contrato,
    {{ texto('codigo_de_categoria_principal') }} as codigo_de_categoria_principal,
    {{ texto('descripcion_del_proceso') }} as descripcion_del_proceso,
    {{ texto('objeto_del_contrato') }} as objeto_del_contrato,
    {{ texto('tipo_de_contrato') }} as tipo_de_contrato,
    {{ texto('modalidad_de_contratacion') }} as modalidad_de_contratacion,
    coalesce(lower(modalidad_de_contratacion) like '%directa%', false) as es_contratacion_directa,
    {{ texto('justificacion_modalidad_de') }} as justificacion_modalidad,
    {{ texto('urlproceso') }} as url_proceso,

    -- Entidad
    {{ texto('codigo_entidad') }} as codigo_entidad,
    {{ normalizar_documento('nit_entidad') }} as nit_entidad,
    {{ texto('nombre_entidad') }} as nombre_entidad,
    {{ texto('departamento') }} as departamento,
    {{ texto('ciudad') }} as ciudad,
    {{ texto('orden') }} as orden,
    {{ texto('sector') }} as sector,
    {{ texto('rama') }} as rama,
    {{ texto('entidad_centralizada') }} as entidad_centralizada,

    -- Proveedor
    {{ texto('codigo_proveedor') }} as codigo_proveedor,
    {{ texto('tipodocproveedor') }} as tipo_documento_proveedor,
    {{ normalizar_documento('documento_proveedor') }} as documento_proveedor,
    {{ texto('proveedor_adjudicado') }} as nombre_proveedor,
    {{ a_booleano('es_grupo') }} as es_grupo,
    {{ a_booleano('es_pyme') }} as es_pyme,

    -- Fechas y plazo
    {{ a_fecha('fecha_de_firma') }} as fecha_de_firma,
    {{ a_fecha('fecha_de_inicio_del_contrato') }} as fecha_de_inicio,
    {{ a_fecha('fecha_de_fin_del_contrato') }} as fecha_de_fin,
    {{ a_fecha('ultima_actualizacion') }} as ultima_actualizacion,
    {{ texto('duraci_n_del_contrato') }} as duracion_del_contrato,
    {{ a_entero('dias_adicionados') }} as dias_adicionados,
    {{ a_booleano('el_contrato_puede_ser_prorrogado') }} as puede_ser_prorrogado,

    -- Valores en pesos
    -- Valores imposibles (errores de digitación en SECOP) quedan en null para
    -- que no entren a sumas ni indicadores; el valor reportado se conserva.
    if({{ a_valor('valor_del_contrato') }} <= {{ var('valor_maximo_plausible') }},
       {{ a_valor('valor_del_contrato') }}) as valor_del_contrato,
    {{ a_valor('valor_del_contrato') }} as valor_del_contrato_reportado,
    coalesce({{ a_valor('valor_del_contrato') }} > {{ var('valor_maximo_plausible') }}, false)
        as valor_atipico,
    {{ a_valor('valor_de_pago_adelantado') }} as valor_de_pago_adelantado,
    {{ a_valor('valor_facturado') }} as valor_facturado,
    {{ a_valor('valor_pagado') }} as valor_pagado,
    {{ a_valor('valor_pendiente_de_pago') }} as valor_pendiente_de_pago,
    {{ a_valor('valor_pendiente_de_ejecucion') }} as valor_pendiente_de_ejecucion,

    -- Recursos
    {{ texto('origen_de_los_recursos') }} as origen_de_los_recursos,
    {{ texto('destino_gasto') }} as destino_gasto,
    {{ a_valor('presupuesto_general_de_la_nacion_pgn') }} as recursos_pgn,
    {{ a_valor('sistema_general_de_participaciones') }} as recursos_sgp,
    {{ a_valor('sistema_general_de_regal_as') }} as recursos_regalias,
    {{ a_valor('recursos_propios') }} as recursos_propios,
    {{ a_valor('recursos_de_credito') }} as recursos_de_credito,

    -- Linaje de la carga
    fecha_carga,
    _extraido_en as extraido_en

from fuente
