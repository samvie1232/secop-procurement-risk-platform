# Contrato de datos: SECOP II – Contratos Electrónicos

| Campo | Valor |
| --- | --- |
| Fuente | datos.gov.co, API Socrata (SODA) |
| Dataset | `jbjy-vk9h` – SECOP II - Contratos Electrónicos |
| Endpoint | `https://www.datos.gov.co/resource/jbjy-vk9h.json` |
| Actualización de la fuente | Diaria |
| Explorado | 2026-10-18 |

## Volumen (medido el 2026-10-18)
- 5.643.434 filas en total; `fecha_de_firma` entre 2015-06-11 y 2026-10-17.
- 2.114.558 filas firmadas desde 2024-10-01 (alcance del MVP: 2 años).
- Cobertura nacional incompleta antes de 2020 (orden Nacional: 80 mil en 2018, 67 mil en 2019, 171 mil en 2020, 307 mil en 2025). Comparaciones entre años se hacen con tasas, no con conteos, y desde 2020.

## Llave
- `id_contrato` (ej. `CO1.PCCNTR.6861643`).
- No es única en la fuente: 148 filas duplicadas en 2 años (2.114.558 filas, 2.114.410 ids). Los duplicados revisados son idénticos en todas las columnas.
- Regla: una fila por `id_contrato`; si dos versiones difieren, gana la de mayor `ultima_actualizacion`.

## Carga incremental
La fuente no tiene un campo confiable de cambios: `ultima_actualizacion` está vacía en el 38 % de las filas (3.494.722 de 5.643.434) y no trae hora.
- Diaria: contratos con `fecha_de_firma` en los últimos 60 días o `ultima_actualizacion` en los últimos 7 días.
- Semanal: recarga completa de la ventana de 2 años.
- Raw en S3 particionado por `fecha_carga=AAAA-MM-DD`; dbt hace merge por `id_contrato` en Iceberg, así que repetir una fecha no duplica datos.
- Fuera del MVP: 66.711 filas sin `fecha_de_firma` ni `ultima_actualizacion` (no se pueden ubicar en una ventana).

## Columnas que se guardan
En raw todas llegan como texto (así las entrega la API); los tipos se aplican en staging.

| Grupo | Columnas | Tipo en staging |
| --- | --- | --- |
| Entidad | `nombre_entidad`, `nit_entidad`, `codigo_entidad`, `departamento`, `ciudad`, `orden`, `sector`, `rama`, `entidad_centralizada` | string (NIT y código normalizados) |
| Contrato | `id_contrato`, `proceso_de_compra`, `referencia_del_contrato`, `estado_contrato`, `codigo_de_categoria_principal`, `descripcion_del_proceso`, `objeto_del_contrato`, `tipo_de_contrato`, `modalidad_de_contratacion`, `justificacion_modalidad_de`, `urlproceso` | string |
| Fechas | `fecha_de_firma`, `fecha_de_inicio_del_contrato`, `fecha_de_fin_del_contrato`, `ultima_actualizacion` | date |
| Plazo | `duraci_n_del_contrato`, `dias_adicionados`, `el_contrato_puede_ser_prorrogado` | string, int, boolean |
| Proveedor | `tipodocproveedor`, `documento_proveedor`, `codigo_proveedor`, `proveedor_adjudicado`, `es_grupo`, `es_pyme` | string, boolean |
| Valores (COP) | `valor_del_contrato`, `valor_de_pago_adelantado`, `valor_facturado`, `valor_pagado`, `valor_pendiente_de_pago`, `valor_pendiente_de_ejecucion` | decimal(18,2) |
| Recursos | `origen_de_los_recursos`, `destino_gasto`, `presupuesto_general_de_la_nacion_pgn`, `sistema_general_de_participaciones`, `sistema_general_de_regal_as`, `recursos_propios`, `recursos_de_credito` | string, decimal(18,2) |

Lista completa de las 95 columnas con su tipo en la fuente: [`secop_columnas.tsv`](secop_columnas.tsv).

## Columnas que NO se guardan (minimización de datos)
Datos personales de terceros que los indicadores no necesitan (Ley 1581 de 2012): nombre, identificación, nacionalidad, domicilio y género del representante legal; nombre y documento del supervisor, del ordenador del gasto y del ordenador de pago; banco, tipo y número de cuenta. También se omiten los campos ambientales, de posconsumo, de reversión y del acuerdo de paz, que no usa el MVP.

## Pruebas mínimas (dbt)
- `id_contrato`: único y no nulo después de deduplicar.
- `fecha_de_firma` no futura; `valor_del_contrato` ≥ 0.
- `orden` en {Nacional, Territorial, Corporación Autónoma, No Definido}.

## Vacíos conocidos
- No hay valor adicionado (solo `dias_adicionados`): el indicador de adiciones usará el dataset de modificaciones de SECOP II (día 5).
- No hay fecha de creación del proveedor: se aproxima con su primera aparición en SECOP II.
