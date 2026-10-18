"""Carga diaria de SECOP II.

Según el contrato de datos: contratos firmados en los últimos 60 días más los
actualizados en los últimos 7, en la partición fecha_carga del día. Volver a
correr un día reemplaza sus archivos, así que los reintentos no duplican datos.

Después, dbt build actualiza los modelos (merge por id_contrato en Iceberg) y
corre sus pruebas: si una prueba falla, los modelos que dependen de ella no se
construyen y llega el aviso de falla.
"""

from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task
from secop_comun import (
    ARGS_POR_DEFECTO,
    DBT,
    DBT_ARGS,
    EXTRACTOR,
    FECHA_CARGA,
    MACROS,
    contar_filas,
)


@dag(
    schedule="0 7 * * *",  # 7:00 a. m. hora de Colombia
    start_date=pendulum.datetime(2026, 10, 1, tz="America/Bogota"),
    catchup=False,
    max_active_runs=1,
    default_args=ARGS_POR_DEFECTO,
    user_defined_macros=MACROS,
    tags=["secop", "ingesta", "dbt"],
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

    # build = run + snapshot + test en orden: cada modelo se prueba apenas se
    # construye, antes de que lo usen los siguientes. Las pruebas unitarias
    # validan la lógica del SQL, no los datos: se corren al desarrollar y en CI.
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"{DBT} build --exclude-resource-type unit_test {DBT_ARGS}",
        execution_timeout=timedelta(hours=1),
    )

    extraer >> verificar_en_athena(FECHA_CARGA) >> dbt_build


secop_diario()
