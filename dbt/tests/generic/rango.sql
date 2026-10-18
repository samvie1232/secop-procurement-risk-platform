{#- Falla con las filas fuera de [min, max]. Los nulos no cuentan: para eso está not_null. -#}
{% test rango(model, column_name, min=none, max=none) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} is not null
  and (
      false
      {%- if min is not none %} or {{ column_name }} < {{ min }}{% endif %}
      {%- if max is not none %} or {{ column_name }} > {{ max }}{% endif %}
  )
{% endtest %}
