"""Consultas a Athena que devuelven filas como diccionarios (todo texto)."""

import logging
import time

import boto3

log = logging.getLogger(__name__)

WORKGROUP = "secop"


def consultar(sql: str, base: str = "secop_analytics") -> list[dict]:
    athena = boto3.client("athena")
    consulta = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": base},
        WorkGroup=WORKGROUP,
    )["QueryExecutionId"]

    while True:
        estado = athena.get_query_execution(QueryExecutionId=consulta)["QueryExecution"]
        if estado["Status"]["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(2)
    if estado["Status"]["State"] != "SUCCEEDED":
        raise RuntimeError(f"Athena: {estado['Status'].get('StateChangeReason')}")
    log.info("Athena escaneó %s bytes", estado["Statistics"]["DataScannedInBytes"])

    filas = []
    columnas = None
    for pagina in athena.get_paginator("get_query_results").paginate(QueryExecutionId=consulta):
        for fila in pagina["ResultSet"]["Rows"]:
            valores = [d.get("VarCharValue") for d in fila["Data"]]
            if columnas is None:  # la primera fila de la primera página es el encabezado
                columnas = valores
                continue
            filas.append(dict(zip(columnas, valores, strict=True)))
    return filas
