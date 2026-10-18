-- Datos actuales de cada proveedor, tomados de su contrato más reciente.
-- Es la entrada del snapshot snp_proveedores, que guarda su historia (SCD2).

with contratos as (

    select *
    from {{ ref('int_contratos') }}
    where codigo_proveedor is not null

),

ordenados as (

    select
        *,
        row_number() over (
            partition by codigo_proveedor
            order by fecha_de_firma desc nulls last, ultima_actualizacion desc nulls last, id_contrato desc
        ) as orden_version
    from contratos

)

select
    codigo_proveedor,
    documento_proveedor,
    tipo_documento_proveedor,
    nombre_proveedor,
    es_grupo,
    es_pyme
from ordenados
where orden_version = 1
