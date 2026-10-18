"""Baja una ventana de fechas de SECOP II y la escribe como Parquet en raw/.

Distribución en el lago:
    raw/contratos/fecha_carga=AAAA-MM-DD/<ventana>__<corrida>__p00000.parquet

Idempotencia: cada corrida escribe sus archivos con un id propio y, solo cuando
terminó bien, borra los archivos de corridas anteriores de la misma ventana y la
misma fecha de carga. Repetir una corrida reemplaza, no duplica, y nunca queda
un hueco: si algo falla a la mitad, los archivos anteriores siguen ahí.
"""

import io
import json
import logging
import uuid
from datetime import UTC, date, datetime, timedelta

import pyarrow as pa
import pyarrow.parquet as pq

from secop_ingest.columnas import COLUMNAS

log = logging.getLogger(__name__)

# En raw todo es texto, tal como lo entrega la API; los tipos se aplican en staging (dbt).
ESQUEMA = pa.schema(
    [pa.field(c, pa.string()) for c in COLUMNAS]
    + [pa.field("_extraido_en", pa.timestamp("us", tz="UTC"))]
)


def construir_where(desde: date, hasta: date, actualizados_desde: date | None = None) -> str:
    """Contratos firmados entre desde y hasta (ambos incluidos). Si se pasa
    actualizados_desde, suma también los actualizados desde esa fecha."""
    fin = hasta + timedelta(days=1)
    where = f"fecha_de_firma >= '{desde}T00:00:00' AND fecha_de_firma < '{fin}T00:00:00'"
    if actualizados_desde:
        where = f"({where}) OR ultima_actualizacion >= '{actualizados_desde}T00:00:00'"
    return where


def ventanas_mensuales(desde: date, hasta: date) -> list[tuple[date, date]]:
    """Parte un rango en meses calendario. Sirve para el backfill: ventanas
    pequeñas mantienen bajo el $offset y, si una falla, se repite solo esa."""
    ventanas = []
    inicio = desde
    while inicio <= hasta:
        siguiente_mes = (inicio.replace(day=1) + timedelta(days=32)).replace(day=1)
        fin = min(siguiente_mes - timedelta(days=1), hasta)
        ventanas.append((inicio, fin))
        inicio = fin + timedelta(days=1)
    return ventanas


def _a_texto(valor) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, dict):  # las columnas tipo URL llegan como {"url": "..."}
        return valor.get("url") or json.dumps(valor, ensure_ascii=False)
    return str(valor)


def a_tabla(filas: list[dict], extraido_en: datetime) -> pa.Table:
    datos = {c: [_a_texto(f.get(c)) for f in filas] for c in COLUMNAS}
    datos["_extraido_en"] = [extraido_en] * len(filas)
    return pa.Table.from_pydict(datos, schema=ESQUEMA)


def a_parquet(tabla: pa.Table) -> bytes:
    buffer = io.BytesIO()
    pq.write_table(tabla, buffer, compression="zstd")
    return buffer.getvalue()


def nombre_ventana(desde: date, hasta: date, actualizados_desde: date | None) -> str:
    nombre = f"firma_{desde.isoformat()}_{hasta.isoformat()}"
    if actualizados_desde:
        nombre += f"_act_{actualizados_desde.isoformat()}"
    return nombre


def extraer_ventana(
    cliente,
    destino,
    desde: date,
    hasta: date,
    fecha_carga: date,
    actualizados_desde: date | None = None,
    corrida: str | None = None,
) -> int:
    corrida = corrida or uuid.uuid4().hex[:8]
    where = construir_where(desde, hasta, actualizados_desde)
    prefijo = f"contratos/fecha_carga={fecha_carga.isoformat()}/"
    ventana = nombre_ventana(desde, hasta, actualizados_desde)
    extraido_en = datetime.now(UTC)

    esperadas = cliente.contar(where)
    log.info("ventana %s: la API reporta %s filas", ventana, esperadas)

    total = 0
    nuevas = []
    for n, pagina in enumerate(cliente.paginas(where)):
        llave = f"{prefijo}{ventana}__{corrida}__p{n:05d}.parquet"
        destino.escribir(llave, a_parquet(a_tabla(pagina, extraido_en)))
        nuevas.append(llave)
        total += len(pagina)

    # Solo después de escribir todo se borra lo de corridas anteriores.
    viejas = [k for k in destino.listar(f"{prefijo}{ventana}__") if k not in nuevas]
    if viejas:
        destino.borrar(viejas)
        log.info("ventana %s: borrados %s archivos de corridas anteriores", ventana, len(viejas))

    if total != esperadas:
        # La fuente se actualiza durante el día, así que una diferencia pequeña es posible.
        log.warning("ventana %s: se bajaron %s filas, la API reportó %s", ventana, total, esperadas)
    log.info("ventana %s: %s filas en %s archivos", ventana, total, len(nuevas))
    return total
