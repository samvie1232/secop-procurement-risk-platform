"""Pruebas de las funciones de fecha que usan los DAG de Airflow.

secop_comun no importa Airflow, así que se prueba sin levantar Docker.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "airflow" / "dags"))

from secop_comun import fecha_carga, inicio_recarga  # noqa: E402


def test_fecha_carga_usa_la_fecha_logica_en_hora_de_colombia():
    # 7:00 a. m. en Bogotá son las 12:00 UTC del mismo día.
    corrida = SimpleNamespace(logical_date=datetime(2026, 10, 18, 12, tzinfo=UTC), run_after=None)
    assert fecha_carga(corrida) == "2026-10-18"


def test_fecha_carga_sin_fecha_logica_usa_run_after():
    # 1:30 a. m. UTC del 19 todavía es el 18 en Colombia.
    corrida = SimpleNamespace(
        logical_date=None, run_after=datetime(2026, 10, 19, 1, 30, tzinfo=UTC)
    )
    assert fecha_carga(corrida) == "2026-10-18"


def test_inicio_recarga_es_el_primer_dia_del_mes_de_hace_dos_anios():
    corrida = SimpleNamespace(logical_date=datetime(2026, 10, 18, 12, tzinfo=UTC), run_after=None)
    assert inicio_recarga(corrida) == "2024-10-01"
