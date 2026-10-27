-- Lecturas de la señal de texto tal como las escribe `secop-texto leer`.
-- Mismo grano que raw: un contrato aparece una vez por cada corrida que lo leyó.
--
-- Si la tabla de raw todavía no existe en Glue (antes del terraform apply que
-- la crea), el modelo sale vacío con las mismas columnas en vez de fallar.

{%- set fuente = source('secop_raw', 'senales_texto') %}
{%- set existe = execute and adapter.get_relation(
        database=fuente.database, schema=fuente.schema, identifier=fuente.identifier) %}

{%- if existe %}

select
    {{ texto('id_contrato') }} as id_contrato,
    texto_hash,
    version_prompt,
    modelo,
    nivel,
    {{ texto('tipos') }} as tipos,
    {{ texto('cita') }} as cita,
    campo_cita,
    cita_verificada,
    explicacion,
    coalesce(bandera, false) as bandera,
    tokens_entrada,
    tokens_salida,
    error,
    analizado_en,
    fecha_carga
from {{ fuente }}

{%- else %}

select
    cast(null as varchar) as id_contrato,
    cast(null as varchar) as texto_hash,
    cast(null as varchar) as version_prompt,
    cast(null as varchar) as modelo,
    cast(null as varchar) as nivel,
    cast(null as varchar) as tipos,
    cast(null as varchar) as cita,
    cast(null as varchar) as campo_cita,
    cast(null as boolean) as cita_verificada,
    cast(null as varchar) as explicacion,
    cast(null as boolean) as bandera,
    cast(null as bigint) as tokens_entrada,
    cast(null as bigint) as tokens_salida,
    cast(null as varchar) as error,
    cast(null as timestamp) as analizado_en,
    cast(null as date) as fecha_carga
where false

{%- endif %}
