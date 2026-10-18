# Imagen de Airflow + uv. El extractor no se instala en el entorno de Airflow:
# cada tarea lo corre con `uv run` en su propio entorno, así sus dependencias
# (pyarrow, boto3...) nunca chocan con las de Airflow.
FROM apache/airflow:3.3.2-python3.11

# botocore[crt] agrega awscrt, que botocore necesita para usar las credenciales de
# `aws login`. Se fija la misma versión de botocore que trae la imagen.
RUN pip install --no-cache-dir uv==0.13.1 \
    "botocore[crt]==$(python -c 'import botocore; print(botocore.__version__)')"
