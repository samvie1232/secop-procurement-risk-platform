"""Recarga completa de SECOP II, y backfill por rango de fechas.

Cada domingo vuelve a bajar los últimos 2 años por meses, para recoger cambios
en contratos viejos que no traen ultima_actualizacion (38 % de la fuente).
Para un backfill, dispáralo a mano con otras fechas en desde y hasta.
"""

from datetime import timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import CronTriggerTimetable, Param, dag
from secop_comun import ARGS_POR_DEFECTO, EXTRACTOR, FECHA_CARGA, MACROS

# Sin parámetros: desde el primer día del mes de hace 2 años hasta la fecha de la corrida.
DESDE = "{{ params.desde or inicio_recarga(dag_run) }}"
HASTA = "{{ params.hasta or fecha_carga(dag_run) }}"


@dag(
    # Domingos a la 1:00 a. m., antes de la carga diaria. Sin start_date, al
    # activarlo espera al próximo domingo en vez de arrancar una recarga de una.
    schedule=CronTriggerTimetable("0 1 * * 0", timezone="America/Bogota"),
    catchup=False,
    max_active_runs=1,
    default_args=ARGS_POR_DEFECTO,
    user_defined_macros=MACROS,
    params={
        "desde": Param("", type="string", description="AAAA-MM-DD; vacío = hace 2 años"),
        "hasta": Param("", type="string", description="AAAA-MM-DD; vacío = fecha de la corrida"),
    },
    tags=["secop", "ingesta"],
    doc_md=__doc__,
)
def secop_recarga():
    BashOperator(
        task_id="extraer_por_mes",
        bash_command=(
            f"{EXTRACTOR} --desde {DESDE} --hasta {HASTA} --por-mes --fecha-carga {FECHA_CARGA}"
        ),
        pool="socrata",
        execution_timeout=timedelta(hours=8),
    )


secop_recarga()
