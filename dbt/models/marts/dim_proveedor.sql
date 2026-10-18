-- Una fila por versión de proveedor (SCD tipo 2), a partir del snapshot.
-- es_actual marca la versión vigente; para cruzar con fct_contrato se usa
-- codigo_proveedor y es_actual = true.

with versiones as (

    select * from {{ ref('snp_proveedores') }}

),

historia as (

    -- Primera aparición en SECOP II: sustituye la fecha de creación del
    -- proveedor, que la fuente no trae (ver docs/data_contract.md).
    select
        codigo_proveedor,
        min(fecha_de_firma) as primera_firma,
        count(*) as contratos_totales
    from {{ ref('int_contratos') }}
    where codigo_proveedor is not null
    group by codigo_proveedor

)

select
    versiones.dbt_scd_id as proveedor_version_id,
    versiones.codigo_proveedor,
    versiones.documento_proveedor,
    versiones.tipo_documento_proveedor,
    versiones.nombre_proveedor,
    versiones.es_grupo,
    versiones.es_pyme,
    historia.primera_firma,
    historia.contratos_totales,
    versiones.dbt_valid_from as vigente_desde,
    versiones.dbt_valid_to as vigente_hasta,
    versiones.dbt_valid_to is null as es_actual
from versiones
left join historia
    on versiones.codigo_proveedor = historia.codigo_proveedor
