"""Carga diaria de SECOP II.

Según el contrato de datos: contratos firmados en los últimos 60 días más los
actualizados en los últimos 7, en la partición fecha_carga del día. Volver a
correr un día reemplaza sus archivos, así que los reintentos no duplican datos.
"""

from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task
from secop_comun import ARGS_POR_DEFECTO, EXTRACTOR, FECHA_CARGA, MACROS, contar_filas


@dag(
    schedule="0 7 * * *",  # 7:00 a. m. hora de Colombia
    start_date=pendulum.datetime(2026, 10, 1, tz="America/Bogota"),
    catchup=False,
    max_active_runs=1,
    default_args=ARGS_POR_DEFECTO,
    user_defined_macros=MACROS,
    tags=["secop", "ingesta"],
    doc_md=__doc__,
)
def secop_diario():
    extraer = BashOperator(
        task_id="extraer",
        bash_command=f"{EXTRACTOR} --dias 60 --actualizados-dias 7 --fecha-carga {FECHA_CARGA}",
        pool="socrata",
        execution_timeout=timedelta(hours=2),
    )

    @task
    def verificar_en_athena(fecha_carga: str) -> int:
        filas = contar_filas(fecha_carga)
        if filas == 0:
            raise ValueError(f"La partición fecha_carga={fecha_carga} quedó vacía")
        return filas

    # Aquí se sumarán dbt build y dbt test en el paso 5.
    extraer >> verificar_en_athena(FECHA_CARGA)


secop_diario()
