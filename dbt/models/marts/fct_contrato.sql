-- Hechos: una fila por contrato, con las llaves a las dimensiones y sus valores.
{{ config(partitioned_by=['year(fecha_de_firma)']) }}

select
    id_contrato,
    codigo_entidad,
    codigo_proveedor,
    proceso_de_compra,
    estado_contrato,
    tipo_de_contrato,
    modalidad_de_contratacion,
    es_contratacion_directa,
    codigo_de_categoria_principal,
    objeto_del_contrato,
    fecha_de_firma,
    fecha_de_inicio,
    fecha_de_fin,
    ultima_actualizacion,
    dias_adicionados,
    valor_del_contrato,
    valor_atipico,
    valor_pagado,
    valor_facturado,
    valor_pendiente_de_ejecucion,
    origen_de_los_recursos,
    url_proceso
from {{ ref('int_contratos') }}
