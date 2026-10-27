-- Quinto indicador: señal de texto por contrato. Una fila por contrato leído
-- con la lectura más reciente sin error de cada versión del prompt (la versión
-- más nueva gana).
--
-- bandera = nivel medio o alto y una cita que de verdad está en el contrato.
-- Es una señal para revisión humana, no prueba de irregularidad.

with lecturas as (

    select
        *,
        row_number() over (
            partition by id_contrato
            order by version_prompt desc, analizado_en desc
        ) as orden_lectura
    from {{ ref('stg_secop__senales_texto') }}
    where error is null and id_contrato is not null

)

select
    l.id_contrato,
    i.codigo_entidad,
    i.codigo_proveedor,
    l.nivel,
    l.bandera,
    l.tipos,
    l.cita,
    l.campo_cita,
    l.cita_verificada,
    l.explicacion,
    l.version_prompt,
    l.modelo,
    l.texto_hash,
    l.analizado_en
from lecturas as l
left join {{ ref('int_contratos') }} as i on l.id_contrato = i.id_contrato
where l.orden_lectura = 1
