# Revisión manual de 5 alertas

*English summary below.*

Las 5 entidades con mayor puntaje de riesgo en el tablero (periodo 2025-10-17 a 2026-10-17) se revisaron a mano. Para cada una se buscaron los 2 proveedores que más valor recibieron y se abrió en SECOP II su contrato más grande. La consulta está en [validar_alertas.sql](validar_alertas.sql).

## Resultado

| Entidad | Puntaje | Qué dispara la alerta | Contrato que la explica | Lectura |
| --- | --- | --- | --- | --- |
| Ministerio de Minas y Energía | 98,3 | HHI 5.031; 99 % del valor por contratación directa | GECELCA S.A. E.S.P. (empresa de generación de mayoría estatal), 1 contrato de 4,2 billones de pesos (70 % del valor de la entidad) para administrar el programa Colombia Solar. [Ver en SECOP](https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.9341296&isFromPublicArea=True&isModal=true&asPopupView=true) | Explicable: un programa nacional se entrega completo a un solo operador público. La señal es útil para seguir su ejecución, no por la modalidad. |
| Alcaldía de Santo Tomás (Atlántico) | 98,1 | HHI 9.589; 99,6 % directa | Asociación de Juntas de Acción Comunal del municipio: 5 contratos por 282,8 mil millones de pesos (97,9 %), el mayor para un parque en el barrio El Lucero 2. [Ver en SECOP](https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.10958105&isFromPublicArea=True&isModal=true&asPopupView=true) | **Error de digitación confirmado.** El proceso en SECOP vale 282.523.591 pesos, pero el contrato (CO1.PCCNTR.9991604) se publicó con 282.523.591.100: mil veces más. El valor llega así desde la API, no es un error del pipeline. Pasa el filtro de atípicos porque está por debajo de 100 billones. |
| Inder Medellín | 93,6 | HHI 5.737; 95 % directa | Empresa de Desarrollo Urbano de Medellín (EDU, empresa del mismo municipio): concesión del estadio Atanasio Girardot por 1,27 billones (75 %). [Ver en SECOP](https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.10907814&isFromPublicArea=True&isModal=true&asPopupView=true) | Explicable: acuerdo entre entidades públicas. Además, el valor de una concesión es el de toda su vida, no gasto de un año. |
| Fuerza Aeroespacial Colombiana | 93,5 | HHI 6.646; 94 % directa | Un solo contrato de 1,57 billones (81 %) para comprar aeronaves de transporte táctico militar pesado, con entrenamiento y soporte logístico. [Ver en SECOP](https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.10608290&isFromPublicArea=True&isModal=true&asPopupView=true) | Explicable: compra estratégica de defensa a un único fabricante. El proveedor salió como "Persona natural" porque no tiene NIT colombiano (es extranjero): la regla de anonimización del tablero lo clasifica mal. |
| Ministerio de Salud y Protección Social | 92,0 | HHI 6.289; 95 % directa | Hospital Universitario San Juan de Dios y Materno Infantil: 1 convenio de 1,62 billones (79 %) para infraestructura y dotación del hospital. [Ver en SECOP](https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.9342330&isFromPublicArea=True&isModal=true&asPopupView=true) | Explicable: convenio con una entidad pública para un proyecto puntual. |

## Qué se aprende

- **4 de 5 alertas se explican por un solo contrato enorme con otra entidad pública o un proveedor único.** Los convenios y contratos interadministrativos son contratación directa por ley, y un único contrato grande dispara el HHI. El puntaje los trata igual que a un contrato directo con un privado.
- **1 de 5 es un error de datos de la fuente.** Un solo contrato publicado con un valor mil veces mayor que el de su proceso basta para llevar a un municipio pequeño al segundo lugar del ranking.
- **La regla de "persona natural" falla con proveedores extranjeros**, que no tienen NIT colombiano.

## Mejoras que salen de esta revisión

1. Separar los contratos interadministrativos (la columna `justificacion_modalidad` lo indica) y calcular el % de directa y el HHI sin ellos.
2. Comparar el valor del contrato con el del proceso (dataset de procesos de SECOP II) y marcar los que difieren por órdenes de magnitud, o, más simple, los que superan el total que la entidad contrató el año anterior.
3. Anonimizar solo los documentos de persona natural (cédulas) en vez de todo lo que no sea NIT.

## English summary

The five highest-scoring entities were reviewed by hand in SECOP II. Four are explained by a single very large contract with another public body or a sole supplier (a national solar program, a stadium concession, a defense aircraft purchase and a hospital agreement): inter-administrative agreements are legally direct awards and one big contract is enough to push the concentration index up. The fifth is a data-entry error at the source: the contract was published at 1,000 times the value of its tender (COP 282.5 billion instead of 282.5 million). The review leads to three improvements: score inter-administrative contracts separately, flag contract values that are orders of magnitude away from their tender or from the entity's usual spending, and only anonymize suppliers identified with a personal ID, since foreign companies were being labeled as natural persons.
