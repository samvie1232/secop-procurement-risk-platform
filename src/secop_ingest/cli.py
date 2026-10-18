"""Línea de comandos del extractor.

Ejemplos:
    # Carga diaria: firmados en los últimos 60 días o actualizados en los últimos 7
    uv run secop-extract --destino s3://BUCKET/raw --dias 60 --actualizados-dias 7

    # Backfill por meses (una ventana por mes)
    uv run secop-extract --destino s3://BUCKET/raw --desde 2024-10-01 --hasta 2026-10-17 --por-mes
"""

import argparse
import logging
from datetime import date, timedelta

from secop_ingest.destino import crear_destino
from secop_ingest.extract import extraer_ventana, ventanas_mensuales
from secop_ingest.socrata import ClienteSocrata


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="secop-extract", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--destino", required=True, help="s3://bucket/prefijo o una carpeta local")
    p.add_argument("--desde", type=date.fromisoformat, help="primera fecha de firma (AAAA-MM-DD)")
    p.add_argument("--hasta", type=date.fromisoformat, help="última fecha de firma, incluida")
    p.add_argument("--dias", type=int, help="atajo: firmados en los últimos N días hasta hoy")
    p.add_argument("--actualizados-dias", type=int,
                   help="suma los contratos con ultima_actualizacion en los últimos N días")
    p.add_argument("--por-mes", action="store_true", help="parte el rango en ventanas mensuales")
    p.add_argument("--fecha-carga", type=date.fromisoformat, default=date.today(),
                   help="partición fecha_carga (por defecto, hoy)")
    a = p.parse_args(argv)

    if a.dias:
        hasta = a.fecha_carga
        desde = hasta - timedelta(days=a.dias)
    elif a.desde and a.hasta:
        desde, hasta = a.desde, a.hasta
    else:
        p.error("usa --dias N, o --desde y --hasta")
    if desde > hasta:
        p.error("--desde no puede ser posterior a --hasta")
    if a.por_mes and a.actualizados_dias:
        # Los actualizados caerían en todas las ventanas y se repetirían.
        p.error("--actualizados-dias no se combina con --por-mes")
    actualizados_desde = (
        a.fecha_carga - timedelta(days=a.actualizados_dias) if a.actualizados_dias else None
    )

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cliente = ClienteSocrata()
    destino = crear_destino(a.destino)
    ventanas = ventanas_mensuales(desde, hasta) if a.por_mes else [(desde, hasta)]

    total = 0
    for d, h in ventanas:
        total += extraer_ventana(cliente, destino, d, h, a.fecha_carga, actualizados_desde)
    logging.info("listo: %s filas en %s ventanas", total, len(ventanas))


if __name__ == "__main__":
    main()
