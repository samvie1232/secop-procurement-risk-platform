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
- Seguro: cero llaves de AWS en el repo; credenciales temporales y OIDC.

Las señales de riesgo sirven para priorizar revisión; no son prueba de irregularidad.
