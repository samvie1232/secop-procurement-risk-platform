"""Línea de comandos de la señal de texto.

Ejemplos:
    # Prueba: leer 50 contratos marcados y dejar un CSV para revisarlos
    uv run secop-texto leer --destino s3://BUCKET/raw --limite 50

    # Muestra de 100 contratos ya leídos para etiquetar a mano
    uv run secop-texto muestra --n 100 --salida revision/etiquetas.csv

    # Precisión y recall contra las etiquetas
    uv run secop-texto evaluar revision/etiquetas.csv
"""

import argparse
import csv
import io
import json
import logging
import os
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from secop_ingest.destino import crear_destino
from secop_texto.athena import consultar
from secop_texto.evaluacion import metricas, muestra_estratificada
from secop_texto.senal import (
    MODELO_POR_DEFECTO,
    VERSION_PROMPT,
    crear_cliente,
    leer_contrato,
)

log = logging.getLogger(__name__)

# Mismo orden y tipos que la tabla secop_raw.senales_texto (infra/terraform/raw.tf).
ESQUEMA = pa.schema(
    [
        ("id_contrato", pa.string()),
        ("texto_hash", pa.string()),
        ("version_prompt", pa.string()),
        ("modelo", pa.string()),
        ("nivel", pa.string()),
        ("tipos", pa.string()),
        ("cita", pa.string()),
        ("campo_cita", pa.string()),
        ("cita_verificada", pa.bool_()),
        ("explicacion", pa.string()),
        ("bandera", pa.bool_()),
        ("tokens_entrada", pa.int64()),
        ("tokens_salida", pa.int64()),
        ("error", pa.string()),
        ("analizado_en", pa.timestamp("us", tz="UTC")),
    ]
)


def sql_candidatos(limite: int, releer: bool) -> str:
    """Los candidatos más prioritarios que aún no se leyeron con esta versión."""
    pendientes = (
        ""
        if releer
        else f"""
        where not exists (
            select 1 from risk_senal_texto as s
            where s.id_contrato = c.id_contrato
              and s.version_prompt = '{VERSION_PROMPT}'
        )"""
    )
    return f"""
        select c.*
        from risk_contrato_candidato as c{pendientes}
        order by c.prioridad desc, c.valor_del_contrato desc, c.id_contrato
        limit {int(limite)}
    """


SQL_LEIDOS = f"""
    select s.id_contrato, s.bandera, s.nivel, s.tipos, s.cita, s.cita_verificada,
           s.explicacion, i.nombre_entidad, i.modalidad_de_contratacion,
           cast(i.valor_del_contrato as double) as valor_del_contrato,
           i.objeto_del_contrato, i.descripcion_del_proceso, i.justificacion_modalidad,
           i.url_proceso
    from risk_senal_texto as s
    inner join int_contratos as i on s.id_contrato = i.id_contrato
    where s.version_prompt = '{VERSION_PROMPT}'
"""


def a_parquet(filas: list[dict]) -> bytes:
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(filas, schema=ESQUEMA), buffer, compression="zstd")
    return buffer.getvalue()


def escribir_csv(ruta: Path, filas: list[dict], columnas: list[str]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: Excel en Windows abre bien las tildes.
    with ruta.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


def leer_csv(ruta: Path) -> list[dict]:
    texto = ruta.read_text(encoding="utf-8-sig")
    # Excel en español guarda los CSV con punto y coma.
    separador = (
        ";" if texto.split("\n", 1)[0].count(";") > texto.split("\n", 1)[0].count(",") else ","
    )
    return list(csv.DictReader(io.StringIO(texto), delimiter=separador))


def cmd_leer(a) -> None:
    contratos = consultar(sql_candidatos(a.limite, a.releer))
    log.info("%s contratos por leer con %s", len(contratos), a.modelo)
    if not contratos:
        return

    cliente = crear_cliente(a.region)
    with ThreadPoolExecutor(max_workers=a.hilos) as pool:
        filas = list(pool.map(lambda c: leer_contrato(cliente, c, a.modelo), contratos))

    corrida = uuid.uuid4().hex[:8]
    llave = f"senales_texto/fecha_carga={date.today().isoformat()}/lectura__{corrida}.parquet"
    crear_destino(a.destino).escribir(llave, a_parquet(filas))
    log.info("escrito %s", llave)

    # CSV para leer los resultados junto al texto original.
    por_id = {c["id_contrato"]: c for c in contratos}
    revision = [{**por_id[f["id_contrato"]], **f} for f in filas]
    ruta = Path(a.revision) if a.revision else Path("revision") / f"lectura_{corrida}.csv"
    escribir_csv(
        ruta,
        revision,
        [
            "id_contrato", "motivos", "nombre_entidad", "modalidad_de_contratacion",
            "valor_del_contrato", "bandera", "nivel", "tipos", "cita", "cita_verificada",
            "explicacion", "objeto_del_contrato", "descripcion_del_proceso",
            "justificacion_modalidad", "url_proceso", "error",
        ],
    )  # fmt: skip

    resumen = {
        "contratos": len(filas),
        "con_bandera": sum(f["bandera"] for f in filas),
        "por_nivel": dict(Counter(f["nivel"] or "error" for f in filas)),
        "citas_no_encontradas": sum(
            f["cita_verificada"] is False and bool(f["cita"]) for f in filas
        ),
        "errores": dict(Counter(f["error"] for f in filas if f["error"])),
        "tokens_entrada": sum(f["tokens_entrada"] or 0 for f in filas),
        "tokens_salida": sum(f["tokens_salida"] or 0 for f in filas),
        "revision": str(ruta),
    }
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


def cmd_muestra(a) -> None:
    leidos = consultar(SQL_LEIDOS)
    muestra = muestra_estratificada(leidos, a.n, a.semilla)
    escribir_csv(
        Path(a.salida),
        [{**f, "etiqueta_humana": "", "nota": ""} for f in muestra],
        [
            "id_contrato", "etiqueta_humana", "nota", "nombre_entidad",
            "modalidad_de_contratacion", "valor_del_contrato", "objeto_del_contrato",
            "descripcion_del_proceso", "justificacion_modalidad", "url_proceso",
            "bandera", "nivel", "tipos", "cita", "explicacion", "estrato", "peso",
        ],
    )  # fmt: skip
    estratos = Counter(f["estrato"] for f in muestra)
    print(f"{len(muestra)} contratos de {len(leidos)} leídos ({dict(estratos)}) en {a.salida}")


def cmd_evaluar(a) -> None:
    print(json.dumps(metricas(leer_csv(Path(a.etiquetas))), ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="secop-texto",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="comando", required=True)

    leer = sub.add_parser("leer", help="lee con Claude los contratos marcados que faltan")
    leer.add_argument("--destino", required=True, help="s3://bucket/raw o una carpeta local")
    leer.add_argument("--limite", type=int, default=50, help="cuántos contratos leer (50)")
    leer.add_argument("--modelo", default=os.environ.get("SECOP_MODELO", MODELO_POR_DEFECTO))
    leer.add_argument(
        "--region",
        default=os.environ.get("SECOP_BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-2")),
    )
    leer.add_argument("--hilos", type=int, default=4, help="llamadas en paralelo (4)")
    leer.add_argument("--releer", action="store_true", help="vuelve a leer los ya leídos")
    leer.add_argument("--revision", help="ruta del CSV de revisión (por defecto en revision/)")
    leer.set_defaults(func=cmd_leer)

    muestra = sub.add_parser("muestra", help="muestra estratificada para etiquetar a mano")
    muestra.add_argument("--n", type=int, default=100)
    muestra.add_argument("--salida", default="revision/etiquetas.csv")
    muestra.add_argument("--semilla", type=int, default=42)
    muestra.set_defaults(func=cmd_muestra)

    evaluar = sub.add_parser("evaluar", help="precisión y recall contra las etiquetas")
    evaluar.add_argument("etiquetas", help="CSV de muestra con etiqueta_humana llena (si/no)")
    evaluar.set_defaults(func=cmd_evaluar)

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    a.func(a)


if __name__ == "__main__":
    main()
