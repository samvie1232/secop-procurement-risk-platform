"""Exporta a Parquet las tablas pequeñas que lee el tablero.

El tablero (Streamlit Community Cloud) no se conecta a AWS: lee estos archivos
desde el repo. Así no necesita credenciales, no cuesta nada mientras nadie
exporta y sigue vivo después de un terraform destroy.

Uso, desde la raíz del repo y con la sesión de AWS activa:

    AWS_PROFILE=secop-airflow uv run python tablero/exportar.py

Privacidad: muchos proveedores son personas naturales. Al tablero solo llegan
con nombre los proveedores con NIT (empresas); en el fraccionamiento, las
personas naturales aparecen sin nombre. Son señales para priorizar revisión,
no prueba de irregularidad, y no se publica una lista de personas.
"""

import io
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import boto3
import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.parquet as pq

WORKGROUP = "secop"
DESTINO = Path(__file__).parent / "datos"
ES_EMPRESA = "upper(d.tipo_documento_proveedor) like '%NIT%'"
TOP_PROVEEDORES = 1000

CONSULTAS = {
    "entidades": """
        select codigo_entidad, nombre_entidad, orden, departamento, contratos,
               cast(valor_total as double) as valor_total, pct_directa_contratos,
               pct_directa_valor, proveedores, hhi, proveedores_con_fraccionamiento,
               muestra_suficiente, puntaje_riesgo
        from secop_analytics.risk_entidad
    """,
    "proveedores": f"""
        select r.codigo_proveedor, r.nombre_proveedor, r.contratos, r.entidades,
               cast(r.valor_total as double) as valor_total, r.pct_directa_valor,
               r.primera_firma, r.es_nuevo, r.contratos_grandes_al_inicio,
               r.entidades_con_fraccionamiento, r.alerta_nuevo_con_contrato_grande,
               r.puntaje_riesgo
        from secop_analytics.risk_proveedor as r
        inner join secop_analytics.dim_proveedor as d
            on r.codigo_proveedor = d.codigo_proveedor and d.es_actual
        where {ES_EMPRESA}
        order by r.puntaje_riesgo desc, r.valor_total desc
        limit {TOP_PROVEEDORES}
    """,
    "fraccionamiento": f"""
        select f.codigo_entidad, e.nombre_entidad, e.orden, e.departamento,
               case when {ES_EMPRESA} then d.nombre_proveedor
                    else 'Persona natural (nombre oculto)' end as proveedor,
               f.contratos_directos, cast(f.valor_directo as double) as valor_directo,
               f.max_contratos_ventana, cast(f.valor_ventana_pico as double) as valor_ventana_pico,
               f.fecha_pico
        from secop_analytics.risk_fraccionamiento as f
        left join secop_analytics.dim_entidad as e on f.codigo_entidad = e.codigo_entidad
        left join secop_analytics.dim_proveedor as d
            on f.codigo_proveedor = d.codigo_proveedor and d.es_actual
    """,
    "tendencia": """
        select date_trunc('month', c.fecha_de_firma) as mes,
               coalesce(e.orden, 'No Definido') as orden,
               count(*) as contratos,
               count_if(c.es_contratacion_directa) as contratos_directos,
               cast(sum(c.valor_del_contrato) as double) as valor,
               cast(sum(if(c.es_contratacion_directa, c.valor_del_contrato, 0)) as double)
                   as valor_directo
        from secop_analytics.fct_contrato as c
        left join secop_analytics.dim_entidad as e on c.codigo_entidad = e.codigo_entidad
        where c.fecha_de_firma between date '2024-10-01' and current_date
          and c.valor_del_contrato >= 0
        group by 1, 2
    """,
}

# Misma ventana que los indicadores (macro periodo_analisis de dbt).
PERIODO = """
    select max(fecha_de_firma) - interval '365' day as desde, max(fecha_de_firma) as hasta
    from secop_analytics.fct_contrato
    where fecha_de_firma <= current_date
"""

# Solo para revisar en consola qué valores trae el tipo de documento.
TIPOS_DOCUMENTO = """
    select tipo_documento_proveedor, count(*) as proveedores
    from secop_analytics.dim_proveedor
    where es_actual
    group by 1
    order by 2 desc
"""


def consultar(athena, s3, sql: str) -> pa.Table:
    """Corre una consulta en Athena y devuelve el resultado como tabla de Arrow."""
    qid = athena.start_query_execution(QueryString=sql, WorkGroup=WORKGROUP)["QueryExecutionId"]
    while True:
        ejecucion = athena.get_query_execution(QueryExecutionId=qid)["QueryExecution"]
        estado = ejecucion["Status"]["State"]
        if estado in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if estado != "SUCCEEDED":
        raise RuntimeError(f"Athena {estado}: {ejecucion['Status'].get('StateChangeReason')}")

    escaneado = ejecucion["Statistics"].get("DataScannedInBytes", 0) / 1e6
    bucket, llave = ejecucion["ResultConfiguration"]["OutputLocation"][5:].split("/", 1)
    csv = s3.get_object(Bucket=bucket, Key=llave)["Body"].read()
    # Los códigos parecen números pero son identificadores: se leen como texto.
    tipos = {c: pa.string() for c in ("codigo_entidad", "codigo_proveedor")}
    tabla = pv.read_csv(
        io.BytesIO(csv),
        convert_options=pv.ConvertOptions(column_types=tipos, strings_can_be_null=True),
    )
    print(f"  {tabla.num_rows:>7,} filas · {escaneado:,.1f} MB escaneados")
    return tabla


def main() -> None:
    athena = boto3.client("athena", region_name="us-east-2")
    s3 = boto3.client("s3", region_name="us-east-2")
    DESTINO.mkdir(exist_ok=True)

    print("tipos de documento de proveedor:")
    for fila in consultar(athena, s3, TIPOS_DOCUMENTO).to_pylist()[:10]:
        print(f"    {fila['tipo_documento_proveedor']}: {fila['proveedores']:,}")

    for nombre, sql in CONSULTAS.items():
        print(f"{nombre}:")
        pq.write_table(consultar(athena, s3, sql), DESTINO / f"{nombre}.parquet")

    print("periodo:")
    periodo = consultar(athena, s3, PERIODO).to_pylist()[0]
    metadatos = {
        "desde": str(periodo["desde"]),
        "hasta": str(periodo["hasta"]),
        "exportado_en": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (DESTINO / "metadatos.json").write_text(json.dumps(metadatos, indent=2) + "\n")
    print(f"listo: {DESTINO}")


if __name__ == "__main__":
    main()
