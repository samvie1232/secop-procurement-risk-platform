"""Piezas compartidas por los DAG de SECOP: argumentos, comando del extractor,
verificación en Athena y aviso de fallas por SNS."""

import logging
import os
import time
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import boto3

log = logging.getLogger(__name__)

# El repo está montado en /opt/secop; uv crea el entorno del extractor la primera vez.
EXTRACTOR = "cd /opt/secop && uv run --frozen --no-dev secop-extract --destino $SECOP_LAGO"


def fecha_carga(dag_run) -> str:
    """Día de la corrida en hora de Colombia, para la partición fecha_carga.

    Las corridas manuales de Airflow 3 pueden no tener fecha lógica; ahí se usa
    el momento en que se pidió la corrida (run_after).
    """
    momento = dag_run.logical_date or dag_run.run_after
    return momento.astimezone(ZoneInfo("America/Bogota")).date().isoformat()


def inicio_recarga(dag_run) -> str:
    """Primer día del mes de hace 2 años, contado desde la fecha de la corrida."""
    hoy = date.fromisoformat(fecha_carga(dag_run))
    return hoy.replace(year=hoy.year - 2, day=1).isoformat()


# Funciones que se pueden usar dentro de las plantillas {{ }} de los DAG.
MACROS = {"fecha_carga": fecha_carga, "inicio_recarga": inicio_recarga}
FECHA_CARGA = "{{ fecha_carga(dag_run) }}"


def avisar_falla(context) -> None:
    """Se llama cuando una tarea falla después de agotar sus reintentos."""
    ti = context["ti"]
    asunto = f"[secop] Falló {ti.dag_id}.{ti.task_id}"
    cuerpo = (
        f"Corrida: {context['run_id']}\n"
        f"Intento: {ti.try_number}\n"
        f"Error: {context.get('exception')}\n"
        f"Detalle: http://localhost:8080/dags/{ti.dag_id}/runs/{context['run_id']}"
    )
    log.error("%s\n%s", asunto, cuerpo)
    tema = os.environ.get("SECOP_ALERTAS_SNS")
    if tema:
        boto3.client("sns").publish(TopicArn=tema, Subject=asunto[:100], Message=cuerpo)


ARGS_POR_DEFECTO = {
    "owner": "santiago",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "on_failure_callback": avisar_falla,
}


def contar_filas(fecha_carga: str) -> int:
    """Cuenta las filas de una partición de secop_raw.contratos con Athena.

    Con Parquet, un count(*) se responde con los metadatos de los archivos:
    escanea muy poco y cuesta prácticamente nada.
    """
    athena = boto3.client("athena")
    consulta = athena.start_query_execution(
        QueryString=f"SELECT count(*) FROM contratos WHERE fecha_carga = DATE '{fecha_carga}'",
        QueryExecutionContext={"Database": "secop_raw"},
        WorkGroup="secop",
    )["QueryExecutionId"]

    while True:
        estado = athena.get_query_execution(QueryExecutionId=consulta)["QueryExecution"]
        if estado["Status"]["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(2)
    if estado["Status"]["State"] != "SUCCEEDED":
        raise RuntimeError(f"Athena: {estado['Status'].get('StateChangeReason')}")

    escaneado = estado["Statistics"]["DataScannedInBytes"]
    filas = athena.get_query_results(QueryExecutionId=consulta)["ResultSet"]["Rows"]
    total = int(filas[1]["Data"][0]["VarCharValue"])  # la fila 0 es el encabezado
    log.info("fecha_carga=%s: %s filas (Athena escaneó %s bytes)", fecha_carga, total, escaneado)
    return total
