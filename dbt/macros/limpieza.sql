{#- Conversión de los textos de la API a tipos. try_cast devuelve null en vez
    de fallar, así un valor raro no tumba la carga: las pruebas lo detectan. -#}

{% macro texto(columna) -%}
    nullif(trim({{ columna }}), '')
{%- endmacro %}

{% macro a_fecha(columna) -%}
    {#- La API entrega '2025-03-04T00:00:00.000'; basta con los 10 primeros caracteres. -#}
    try_cast(substr(trim({{ columna }}), 1, 10) as date)
{%- endmacro %}

{% macro a_valor(columna) -%}
    try_cast(trim({{ columna }}) as decimal(18, 2))
{%- endmacro %}

{% macro a_entero(columna) -%}
    try_cast(trim({{ columna }}) as integer)
{%- endmacro %}

{% macro a_booleano(columna) -%}
    case lower(trim({{ columna }}))
        when 'si' then true
        when 'sí' then true
        when 'true' then true
        when 'no' then false
        when 'false' then false
    end
{%- endmacro %}

{% macro normalizar_documento(columna) -%}
    {#- '900.123.456-7' y '900123456' son el mismo NIT: se quita el dígito de
        verificación (lo que va después del guion) y todo lo que no sea letra o número. -#}
    nullif(regexp_replace(split_part(trim({{ columna }}), '-', 1), '[^0-9A-Za-z]', ''), '')
{%- endmacro %}
