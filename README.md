# SECOP II Procurement Risk Platform

Plataforma de datos en AWS que ingiere a diario los contratos públicos de SECOP II (datos.gov.co), los modela con dbt y prioriza entidades y proveedores por señales de riesgo: contratación directa, concentración de proveedores, fraccionamiento, adiciones desproporcionadas y proveedores recién creados.

> Estado: en construcción.

## Stack
AWS (S3, Glue Data Catalog, Athena) · dbt (dbt-athena, Iceberg) · Airflow (Docker) · Terraform · GitHub Actions (OIDC, sin llaves) · Streamlit

## Arquitectura (planeada)
API SECOP → extractor Python → S3 raw (Parquet) → dbt sobre Athena (staging → intermediate → marts → risk) → tablero

## Principios
- Reproducible: todo se recrea con `terraform apply` y un backfill.
- Barato: 100 % serverless, presupuesto con alertas y límite de escaneo en Athena.
- Seguro: cero llaves de AWS en el repo; Airflow usa credenciales temporales y el CI una llave de alcance mínimo guardada en los secretos de GitHub.

Las señales de riesgo sirven para priorizar revisión; no son prueba de irregularidad.

## Orquestación con Airflow

El DAG `secop_diario` corre todos los días a las 7:00 (hora de Colombia) en Airflow 3 local con Docker Compose. Extrae de la API los contratos firmados en los últimos 60 días y los actualizados en los últimos 7, verifica en Athena que la partición del día no quedó vacía y luego corre `dbt build`.

![DAG secop_diario en Airflow: la tarea extraer terminó bien en el segundo intento](docs/img/airflow-secop-diario.png)

La captura muestra por qué la ingesta es idempotente. El primer intento falló y Airflow lo reintentó solo; el segundo bajó los 184.250 contratos de la ventana y, al terminar, borró los 10 archivos que habían dejado corridas anteriores de esa misma ventana y fecha de carga (última línea del log). Repetir una fecha reemplaza sus datos en vez de duplicarlos.

## CI en cada pull request

`main` está protegida: solo acepta cambios por pull request y con los dos checks de GitHub Actions en verde.

- **python**: `ruff check`, `ruff format --check` y `pytest`, sin tocar AWS.
- **dbt**: `dbt build` completo contra Athena (modelos, snapshot, pruebas de datos y la prueba unitaria de deduplicación) sobre una muestra: la última partición de raw y los contratos firmados en sus últimos 30 días. Construye en una base aparte (`secop_ci`), así un PR nunca escribe en `secop_analytics`. Tarda poco más de un minuto y cuesta fracciones de centavo.

![PR #1 con los checks python y dbt en verde](docs/img/ci-pr-checks.png)

El CI entra a AWS con un usuario IAM cuya política solo permite leer `raw/` y escribir en `secop_ci`. La llave vive únicamente en los secretos del repositorio. Lo ideal sería OIDC (credenciales temporales sin llaves), pero la organización de AWS de esta cuenta lo prohíbe con una SCP; en una cuenta sin esa restricción, el cambio es reemplazar el usuario por un rol y una línea del workflow.
