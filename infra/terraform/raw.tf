# ---------------------------------------------------------------------------
# Tabla externa sobre raw/contratos (lo que escribe el extractor).
# Partition projection: Athena calcula las particiones fecha_carga a partir de
# la fecha, sin crawlers ni MSCK REPAIR. Todo es texto, como llega de la API;
# los tipos se aplican en staging con dbt.
# ---------------------------------------------------------------------------
locals {
  raw_contratos = "s3://${aws_s3_bucket.lake.bucket}/raw/contratos"

  columnas_raw = [
    "nombre_entidad", "nit_entidad", "codigo_entidad", "departamento", "ciudad",
    "orden", "sector", "rama", "entidad_centralizada",
    "id_contrato", "proceso_de_compra", "referencia_del_contrato", "estado_contrato",
    "codigo_de_categoria_principal", "descripcion_del_proceso", "objeto_del_contrato",
    "tipo_de_contrato", "modalidad_de_contratacion", "justificacion_modalidad_de",
    "urlproceso",
    "fecha_de_firma", "fecha_de_inicio_del_contrato", "fecha_de_fin_del_contrato",
    "ultima_actualizacion",
    "duraci_n_del_contrato", "dias_adicionados", "el_contrato_puede_ser_prorrogado",
    "tipodocproveedor", "documento_proveedor", "codigo_proveedor", "proveedor_adjudicado",
    "es_grupo", "es_pyme",
    "valor_del_contrato", "valor_de_pago_adelantado", "valor_facturado", "valor_pagado",
    "valor_pendiente_de_pago", "valor_pendiente_de_ejecucion",
    "origen_de_los_recursos", "destino_gasto", "presupuesto_general_de_la_nacion_pgn",
    "sistema_general_de_participaciones", "sistema_general_de_regal_as", "recursos_propios",
    "recursos_de_credito",
  ]
}

resource "aws_glue_catalog_table" "raw_contratos" {
  name          = "contratos"
  database_name = aws_glue_catalog_database.this["secop_raw"].name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    EXTERNAL                               = "TRUE"
    classification                         = "parquet"
    "projection.enabled"                   = "true"
    "projection.fecha_carga.type"          = "date"
    "projection.fecha_carga.format"        = "yyyy-MM-dd"
    "projection.fecha_carga.range"         = "2026-01-01,NOW"
    "projection.fecha_carga.interval"      = "1"
    "projection.fecha_carga.interval.unit" = "DAYS"
    "storage.location.template"            = "${local.raw_contratos}/fecha_carga=$${fecha_carga}"
  }

  partition_keys {
    name = "fecha_carga"
    type = "date"
  }

  storage_descriptor {
    location      = local.raw_contratos
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    dynamic "columns" {
      for_each = local.columnas_raw
      content {
        name = columns.value
        type = "string"
      }
    }

    columns {
      name = "_extraido_en"
      type = "timestamp"
    }
  }
}
