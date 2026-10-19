"""Tablero de señales de riesgo en la contratación pública (SECOP II).

Lee los Parquet de tablero/datos/ (los genera tablero/exportar.py desde
Athena), así que no necesita credenciales de AWS para publicarse.
"""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATOS = Path(__file__).parent / "datos"

# Colores (paleta validada para daltonismo): una serie por tipo de entidad y
# una escala de un solo tono (azul) para magnitudes.
COLOR_ORDEN = {"Nacional": "#2a78d6", "Territorial": "#eb6834"}
ESCALA_AZUL = ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]

# Capital de cada departamento, para el mapa de burbujas.
COORDENADAS = {
    "Amazonas": (-4.215, -69.940),
    "Antioquia": (6.244, -75.581),
    "Arauca": (7.084, -70.759),
    "Atlántico": (10.964, -74.796),
    "Bolívar": (10.391, -75.479),
    "Boyacá": (5.535, -73.367),
    "Caldas": (5.070, -75.513),
    "Caquetá": (1.614, -75.606),
    "Casanare": (5.337, -72.395),
    "Cauca": (2.444, -76.614),
    "Cesar": (10.463, -73.253),
    "Chocó": (5.694, -76.661),
    "Córdoba": (8.748, -75.881),
    "Cundinamarca": (5.026, -74.030),  # Zipaquirá, para no tapar a Bogotá
    "Distrito Capital de Bogotá": (4.711, -74.072),
    "Guainía": (3.865, -67.924),
    "Guaviare": (2.570, -72.645),
    "Huila": (2.927, -75.282),
    "La Guajira": (11.544, -72.907),
    "Magdalena": (11.241, -74.199),
    "Meta": (4.142, -73.627),
    "Nariño": (1.214, -77.281),
    "Norte de Santander": (7.894, -72.508),
    "Putumayo": (1.152, -76.648),
    "Quindío": (4.534, -75.681),
    "Risaralda": (4.814, -75.695),
    "San Andrés, Providencia y Santa Catalina": (12.584, -81.701),
    "Santander": (7.119, -73.123),
    "Sucre": (9.304, -75.398),
    "Tolima": (4.439, -75.232),
    "Valle del Cauca": (3.452, -76.532),
    "Vaupés": (1.258, -70.234),
    "Vichada": (6.189, -67.486),
}

st.set_page_config(page_title="Riesgo en contratación pública · SECOP II", layout="wide")


@st.cache_data
def cargar():
    tablas = {
        n: pd.read_parquet(DATOS / f"{n}.parquet")
        for n in ("entidades", "proveedores", "fraccionamiento", "tendencia")
    }
    meta = json.loads((DATOS / "metadatos.json").read_text())
    return tablas, meta


def miles(n: float) -> str:
    """Entero con punto de miles, como se escribe en Colombia."""
    return f"{n:,.0f}".replace(",", ".")


def en_millones(df: pd.DataFrame, *columnas: str) -> pd.DataFrame:
    """Para las tablas: pesos a millones de pesos, sin decimales."""
    return df.assign(**{c: (df[c] / 1e6).round() for c in columnas})


def pesos(valor: float) -> str:
    """Valor en pesos, abreviado: 1,2 billones, 350 mil millones..."""
    for limite, sufijo in ((1e12, "billones"), (1e9, "mil millones"), (1e6, "millones")):
        if abs(valor) >= limite:
            return (
                f"$ {valor / limite:,.1f} {sufijo}".replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )
    return f"$ {valor:,.0f}".replace(",", ".")


t, meta = cargar()

st.title("Señales de riesgo en la contratación pública colombiana")
st.caption(
    f"SECOP II · contratos firmados entre {meta['desde']} y {meta['hasta']} · "
    f"datos exportados el {meta['exportado_en'][:10]}"
)
st.info(
    "Son **señales para priorizar revisiones**, no prueba de irregularidad. Una entidad "
    "con mucha contratación directa o pocos proveedores puede tener razones legítimas.",
    icon="ℹ️",
)

# Filtros en una sola fila, encima de todo.
c1, c2 = st.columns(2)
ordenes = c1.multiselect(
    "Tipo de entidad", ["Nacional", "Territorial"], default=["Nacional", "Territorial"]
)
departamentos = sorted(
    d for d in t["entidades"]["departamento"].dropna().unique() if d != "No Definido"
)
depto = c2.selectbox("Departamento", ["Todos", *departamentos])


def filtrar(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["orden"].isin(ordenes)]
    return df if depto == "Todos" else df[df["departamento"] == depto]


entidades = filtrar(t["entidades"])
puntuadas = entidades[entidades["muestra_suficiente"]]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Entidades", miles(len(entidades)))
k2.metric("Contratos", miles(entidades["contratos"].sum()))
k3.metric("Valor contratado", pesos(entidades["valor_total"].sum()))
directa = (entidades["pct_directa_valor"] * entidades["valor_total"]).sum() / entidades[
    "valor_total"
].sum()
k4.metric("Contratación directa (por valor)", f"{directa:.0%}")

tab_ent, tab_prov, tab_frac, tab_tend, tab_mapa = st.tabs(
    ["Entidades", "Proveedores", "Fraccionamiento", "Tendencia", "Mapa"]
)

with tab_ent:
    st.subheader("Entidades con mayor puntaje de riesgo")
    st.caption(
        f"Puntaje de 0 a 100: 40 % contratación directa por valor, 40 % concentración de "
        f"proveedores (HHI) y 20 % proveedores con señal de fraccionamiento, en percentiles. "
        f"Solo entidades con 30 contratos o más "
        f"({miles(len(puntuadas))} de {miles(len(entidades))})."
    )
    st.dataframe(
        en_millones(puntuadas, "valor_total").sort_values("puntaje_riesgo", ascending=False)[
            [
                "nombre_entidad",
                "orden",
                "departamento",
                "puntaje_riesgo",
                "contratos",
                "valor_total",
                "pct_directa_valor",
                "hhi",
                "proveedores_con_fraccionamiento",
            ]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "nombre_entidad": "Entidad",
            "orden": "Tipo",
            "departamento": "Departamento",
            "puntaje_riesgo": st.column_config.ProgressColumn(
                "Puntaje", min_value=0, max_value=100, format="%.0f"
            ),
            "contratos": st.column_config.NumberColumn("Contratos", format="localized"),
            "valor_total": st.column_config.NumberColumn(
                "Valor (millones de COP)", format="localized"
            ),
            "pct_directa_valor": st.column_config.NumberColumn(
                "% directa (valor)", format="percent"
            ),
            "hhi": st.column_config.NumberColumn("HHI", format="%.0f"),
            "proveedores_con_fraccionamiento": "Proveedores con fraccionamiento",
        },
    )

with tab_prov:
    st.subheader("Proveedores (empresas) con mayor puntaje de riesgo")
    st.caption(
        "Puntaje de 0 a 100: 50 % proveedor nuevo (primer contrato hace poco) que ya recibió un "
        "contrato del 5 % más grande, 30 % entidades donde muestra fraccionamiento y 20 % "
        "contratación directa. Solo proveedores con NIT: las personas naturales no se listan."
    )
    solo_alerta = st.toggle("Solo proveedores nuevos con contrato grande")
    prov = t["proveedores"]
    if solo_alerta:
        prov = prov[prov["alerta_nuevo_con_contrato_grande"]]
    st.dataframe(
        en_millones(prov, "valor_total")[
            [
                "nombre_proveedor",
                "puntaje_riesgo",
                "contratos",
                "entidades",
                "valor_total",
                "pct_directa_valor",
                "primera_firma",
                "alerta_nuevo_con_contrato_grande",
                "entidades_con_fraccionamiento",
            ]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "nombre_proveedor": "Proveedor",
            "puntaje_riesgo": st.column_config.ProgressColumn(
                "Puntaje", min_value=0, max_value=100, format="%.0f"
            ),
            "contratos": st.column_config.NumberColumn("Contratos", format="localized"),
            "entidades": "Entidades",
            "valor_total": st.column_config.NumberColumn(
                "Valor (millones de COP)", format="localized"
            ),
            "pct_directa_valor": st.column_config.NumberColumn(
                "% directa (valor)", format="percent"
            ),
            "primera_firma": st.column_config.DateColumn("Primer contrato"),
            "alerta_nuevo_con_contrato_grande": st.column_config.CheckboxColumn(
                "Nuevo con contrato grande"
            ),
            "entidades_con_fraccionamiento": "Entidades con fraccionamiento",
        },
    )

with tab_frac:
    st.subheader("Posible fraccionamiento")
    st.caption(
        "Parejas entidad-proveedor con 3 o más contratos directos en 30 días o menos. "
        "SECOP no publica los topes de cada entidad, así que se mide la repetición, no la "
        "cercanía al tope."
    )
    frac = filtrar(t["fraccionamiento"]).sort_values("max_contratos_ventana", ascending=False)
    st.dataframe(
        en_millones(frac, "valor_directo", "valor_ventana_pico")[
            [
                "nombre_entidad",
                "proveedor",
                "max_contratos_ventana",
                "valor_ventana_pico",
                "fecha_pico",
                "contratos_directos",
                "valor_directo",
            ]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "nombre_entidad": "Entidad",
            "proveedor": "Proveedor",
            "max_contratos_ventana": "Contratos en 30 días (máx.)",
            "valor_ventana_pico": st.column_config.NumberColumn(
                "Valor en esos 30 días (millones)", format="localized"
            ),
            "fecha_pico": st.column_config.DateColumn("Fecha del pico"),
            "contratos_directos": "Contratos directos (año)",
            "valor_directo": st.column_config.NumberColumn(
                "Valor directo en el año (millones)", format="localized"
            ),
        },
    )

with tab_tend:
    st.subheader("Contratación directa por mes")
    st.caption("Porcentaje del valor contratado cada mes que se adjudicó por contratación directa.")
    tend = t["tendencia"]
    tend = (
        tend[tend["orden"].isin(ordenes)]
        .groupby(["mes", "orden"], as_index=False)[["valor", "valor_directo", "contratos"]]
        .sum()
    )
    tend["pct_directa"] = tend["valor_directo"] / tend["valor"]
    fig = px.line(
        tend,
        x="mes",
        y="pct_directa",
        color="orden",
        color_discrete_map=COLOR_ORDEN,
        labels={"mes": "", "pct_directa": "% directa (valor)", "orden": "Tipo de entidad"},
        hover_data={"contratos": ":,", "pct_directa": ":.1%"},
    )
    fig.update_traces(line_width=2)
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    fig.update_layout(hovermode="x unified", legend_title_text="")
    st.plotly_chart(fig, width="stretch")
    if depto != "Todos":
        st.caption("La tendencia es nacional: no se filtra por departamento.")

with tab_mapa:
    st.subheader("Contratación directa por departamento")
    st.caption(
        "Cada burbuja es un departamento, en su capital: el tamaño es el valor contratado y "
        "el color, el porcentaje de ese valor adjudicado por contratación directa."
    )
    por_depto = (
        filtrar(t["entidades"])
        .assign(valor_directo=lambda d: d["pct_directa_valor"] * d["valor_total"])
        .groupby("departamento", as_index=False)
        .agg(
            entidades=("codigo_entidad", "count"),
            contratos=("contratos", "sum"),
            valor=("valor_total", "sum"),
            valor_directo=("valor_directo", "sum"),
        )
    )
    por_depto["pct_directa"] = por_depto["valor_directo"] / por_depto["valor"]
    por_depto = por_depto[por_depto["departamento"].isin(COORDENADAS)]
    por_depto["lat"] = por_depto["departamento"].map(lambda d: COORDENADAS[d][0])
    por_depto["lon"] = por_depto["departamento"].map(lambda d: COORDENADAS[d][1])
    por_depto["valor_texto"] = por_depto["valor"].map(pesos)
    mapa = px.scatter_geo(
        por_depto,
        lat="lat",
        lon="lon",
        size="valor",
        color="pct_directa",
        color_continuous_scale=ESCALA_AZUL,
        size_max=45,
        height=620,
        hover_name="departamento",
        hover_data={
            "lat": False,
            "lon": False,
            "valor": False,
            "valor_texto": True,
            "pct_directa": ":.1%",
            "entidades": True,
            "contratos": ":,",
        },
        labels={
            "pct_directa": "% directa",
            "valor_texto": "Valor",
            "entidades": "Entidades",
            "contratos": "Contratos",
        },
    )
    # Mapa base sin teselas externas: solo el contorno de Colombia y sus vecinos.
    mapa.update_geos(
        fitbounds="locations",
        projection_type="mercator",
        resolution=50,
        showcountries=True,
        countrycolor="#c3c2b7",
        showland=True,
        landcolor="#f4f3ef",
        showocean=True,
        oceancolor="#e8f1fb",
        bgcolor="rgba(0,0,0,0)",
    )
    mapa.update_traces(marker_line_width=1, marker_line_color="#ffffff")
    mapa.update_coloraxes(colorbar_tickformat=".0%", colorbar_title_text="% directa")
    mapa.update_layout(margin={"l": 0, "r": 0, "t": 0, "b": 0})
    st.plotly_chart(mapa, width="stretch")
    st.dataframe(
        en_millones(por_depto, "valor").sort_values("pct_directa", ascending=False)[
            ["departamento", "pct_directa", "valor", "contratos", "entidades"]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "departamento": "Departamento",
            "pct_directa": st.column_config.NumberColumn("% directa (valor)", format="percent"),
            "valor": st.column_config.NumberColumn("Valor (millones de COP)", format="localized"),
            "contratos": st.column_config.NumberColumn("Contratos", format="localized"),
            "entidades": "Entidades",
        },
    )

st.divider()
st.caption(
    "Fuente: SECOP II, Contratos Electrónicos (datos.gov.co). Pipeline: Python → S3 → dbt "
    "sobre Athena con Iceberg, orquestado con Airflow. Código: "
    "[github.com/samvie1232/secop-procurement-risk-platform]"
    "(https://github.com/samvie1232/secop-procurement-risk-platform)"
)
