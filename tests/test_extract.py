from datetime import date

import boto3
import pyarrow.parquet as pq
import pytest
from moto import mock_aws

from secop_ingest.columnas import COLUMNAS
from secop_ingest.destino import DestinoLocal, crear_destino
from secop_ingest.extract import (
    a_tabla,
    construir_where,
    extraer_ventana,
    ventanas_mensuales,
)


class ClienteFalso:
    """Imita la API: devuelve las filas en páginas, sin red."""

    def __init__(self, filas, tam_pagina=2):
        self.filas = filas
        self.tam_pagina = tam_pagina

    def contar(self, where):
        return len(self.filas)

    def paginas(self, where):
        for i in range(0, len(self.filas), self.tam_pagina):
            yield self.filas[i : i + self.tam_pagina]


def filas(n):
    return [
        {
            "id_contrato": f"CO1.PCCNTR.{i}",
            "valor_del_contrato": str(i * 1000),
            "urlproceso": {"url": f"https://community.secop.gov.co/{i}"},
            "nombre_representante_legal": "no debe guardarse",
        }
        for i in range(n)
    ]


def test_where_incluye_el_ultimo_dia():
    w = construir_where(date(2026, 8, 1), date(2026, 8, 31))
    assert w == (
        "fecha_de_firma >= '2026-08-01T00:00:00' AND fecha_de_firma < '2026-09-01T00:00:00'"
    )


def test_where_con_actualizados():
    w = construir_where(date(2026, 8, 1), date(2026, 8, 31), date(2026, 10, 11))
    assert w.endswith("OR ultima_actualizacion >= '2026-10-11T00:00:00'")


def test_ventanas_mensuales_cubren_el_rango_sin_huecos():
    v = ventanas_mensuales(date(2024, 10, 15), date(2025, 1, 10))
    assert v == [
        (date(2024, 10, 15), date(2024, 10, 31)),
        (date(2024, 11, 1), date(2024, 11, 30)),
        (date(2024, 12, 1), date(2024, 12, 31)),
        (date(2025, 1, 1), date(2025, 1, 10)),
    ]


def test_tabla_solo_trae_columnas_del_contrato():
    from datetime import UTC, datetime

    t = a_tabla(filas(1), datetime.now(UTC))
    assert t.column_names == [*COLUMNAS, "_extraido_en"]
    assert t["urlproceso"][0].as_py() == "https://community.secop.gov.co/0"
    assert t["nit_entidad"][0].as_py() is None  # columna ausente → nulo


def leer(raiz):
    return pq.read_table(raiz / "contratos").num_rows


def test_repetir_una_corrida_no_duplica(tmp_path):
    destino = DestinoLocal(tmp_path)
    args = dict(desde=date(2026, 8, 1), hasta=date(2026, 8, 31), fecha_carga=date(2026, 10, 18))

    assert extraer_ventana(ClienteFalso(filas(5)), destino, corrida="a", **args) == 5
    assert extraer_ventana(ClienteFalso(filas(5)), destino, corrida="b", **args) == 5

    archivos = destino.listar("contratos/fecha_carga=2026-10-18/firma_")
    assert len(archivos) == 3  # 5 filas en páginas de 2: solo quedan los de la corrida b
    assert all("__b__" in a for a in archivos)
    assert leer(tmp_path) == 5


def test_otra_ventana_no_se_toca(tmp_path):
    destino = DestinoLocal(tmp_path)
    carga = date(2026, 10, 18)
    extraer_ventana(ClienteFalso(filas(3)), destino, date(2026, 8, 1), date(2026, 8, 31), carga)
    extraer_ventana(ClienteFalso(filas(4)), destino, date(2026, 9, 1), date(2026, 9, 30), carga)
    assert leer(tmp_path) == 7


def test_si_falla_a_la_mitad_quedan_los_archivos_anteriores(tmp_path):
    destino = DestinoLocal(tmp_path)
    args = dict(desde=date(2026, 8, 1), hasta=date(2026, 8, 31), fecha_carga=date(2026, 10, 18))
    extraer_ventana(ClienteFalso(filas(4)), destino, corrida="a", **args)

    class ClienteQueFalla(ClienteFalso):
        def paginas(self, where):
            yield self.filas[:2]
            raise ConnectionError("se cayó la API")

    with pytest.raises(ConnectionError):
        extraer_ventana(ClienteQueFalla(filas(4)), destino, corrida="b", **args)
    viejos = [a for a in destino.listar("contratos/fecha_carga=2026-10-18/") if "__a__" in a]
    assert len(viejos) == 2


@mock_aws
def test_escribe_y_reemplaza_en_s3():
    s3 = boto3.client("s3", region_name="us-east-2")
    s3.create_bucket(Bucket="lago", CreateBucketConfiguration={"LocationConstraint": "us-east-2"})
    destino = crear_destino("s3://lago/raw")
    args = dict(desde=date(2026, 8, 1), hasta=date(2026, 8, 31), fecha_carga=date(2026, 10, 18))

    extraer_ventana(ClienteFalso(filas(3)), destino, corrida="a", **args)
    extraer_ventana(ClienteFalso(filas(3)), destino, corrida="b", **args)

    llaves = [o["Key"] for o in s3.list_objects_v2(Bucket="lago")["Contents"]]
    assert len(llaves) == 2
    assert all(
        k.startswith("raw/contratos/fecha_carga=2026-10-18/firma_2026-08-01_2026-08-31__b__")
        for k in llaves
    )
