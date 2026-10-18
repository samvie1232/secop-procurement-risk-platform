# Imagen de Airflow + uv. El extractor no se instala en el entorno de Airflow:
# cada tarea lo corre con `uv run` en su propio entorno, así sus dependencias
# (pyarrow, boto3...) nunca chocan con las de Airflow.
FROM apache/airflow:3.3.2-python3.11

RUN pip install --no-cache-dir uv==0.13.1
