-- Una fila por entidad estatal, con sus datos del contrato más reciente.

with ordenados as (

    select
        *,
        row_number() over (
            partition by codigo_entidad
            order by fecha_de_firma desc nulls last, ultima_actualizacion desc nulls last, id_contrato desc
        ) as orden_version
    from {{ ref('int_contratos') }}
    where codigo_entidad is not null

)

select
    codigo_entidad,
    nit_entidad,
    nombre_entidad,
    departamento,
    ciudad,
    orden,
    sector,
    rama,
    entidad_centralizada
from ordenados
where orden_version = 1
