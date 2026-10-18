"""Columnas que se guardan en raw, según docs/data_contract.md.

Se piden con $select, así que los datos personales que el contrato excluye
nunca salen de la API: la minimización ocurre en el origen.
"""

COLUMNAS = (
    # Entidad
    "nombre_entidad", "nit_entidad", "codigo_entidad", "departamento", "ciudad",
    "orden", "sector", "rama", "entidad_centralizada",
    # Contrato
    "id_contrato", "proceso_de_compra", "referencia_del_contrato", "estado_contrato",
    "codigo_de_categoria_principal", "descripcion_del_proceso", "objeto_del_contrato",
    "tipo_de_contrato", "modalidad_de_contratacion", "justificacion_modalidad_de",
    "urlproceso",
    # Fechas
    "fecha_de_firma", "fecha_de_inicio_del_contrato", "fecha_de_fin_del_contrato",
    "ultima_actualizacion",
    # Plazo
    "duraci_n_del_contrato", "dias_adicionados", "el_contrato_puede_ser_prorrogado",
    # Proveedor
    "tipodocproveedor", "documento_proveedor", "codigo_proveedor", "proveedor_adjudicado",
    "es_grupo", "es_pyme",
    # Valores (COP)
    "valor_del_contrato", "valor_de_pago_adelantado", "valor_facturado", "valor_pagado",
    "valor_pendiente_de_pago", "valor_pendiente_de_ejecucion",
    # Recursos
    "origen_de_los_recursos", "destino_gasto", "presupuesto_general_de_la_nacion_pgn",
    "sistema_general_de_participaciones", "sistema_general_de_regal_as", "recursos_propios",
    "recursos_de_credito",
)
