import io
import json
from types import SimpleNamespace

import anthropic
import httpx2
import pyarrow.parquet as pq
import pytest

from secop_texto import cli
from secop_texto.evaluacion import metricas, muestra_estratificada
from secop_texto.senal import (
    Lectura,
    armar_mensaje,
    cita_verificada,
    hash_texto,
    leer_contrato,
)

CONTRATO = {
    "id_contrato": "CO1.PCCNTR.1",
    "nombre_entidad": "Alcaldía de Prueba",
    "orden": "Territorial",
    "sector": "Servicio Público",
    "tipo_documento_proveedor": "NIT",
    "nombre_proveedor": "Servicios Integrales SAS",
    "tipo_de_contrato": "Prestación de servicios",
    "modalidad_de_contratacion": "Contratación directa",
    "valor_del_contrato": "350000000.00",
    "fecha_de_firma": "2026-05-04",
    "duracion_del_contrato": "15 Dia(s)",
    "codigo_de_categoria_principal": "V1.80111600",
    "objeto_del_contrato": "Apoyo  a la gestión en  actividades varias de la Secretaría",
    "descripcion_del_proceso": "Apoyo a la gestión",
    "justificacion_modalidad": "Ley 1150 de 2007",
    "motivos": "fraccionamiento",
}


class ClienteFalso:
    """Imita client.messages.parse sin red."""

    def __init__(self, respuesta=None, error=None):
        self.respuesta = respuesta
        self.error = error
        self.llamadas = []
        self.messages = self

    def parse(self, **kwargs):
        self.llamadas.append(kwargs)
        if self.error:
            raise self.error
        return self.respuesta


def respuesta(lectura=None, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        parsed_output=lectura,
        usage=SimpleNamespace(input_tokens=1200, output_tokens=150),
    )


def lectura(nivel="medio", cita="actividades varias de la Secretaría"):
    return Lectura(
        explicacion="Objeto genérico por un valor alto y 15 días.",
        tipos=["objeto_vago", "valor_desproporcionado"],
        cita=cita,
        campo_cita="objeto",
        nivel=nivel,
    )


def test_mensaje_lleva_contexto_y_los_tres_campos():
    m = armar_mensaje(CONTRATO)
    assert "350.000.000 pesos" in m
    assert "Servicios Integrales SAS (NIT)" in m
    assert "<justificacion>\nLey 1150 de 2007\n</justificacion>" in m
    assert "Indicadores que lo marcaron: fraccionamiento" in m


def test_campo_vacio_se_marca_como_vacio():
    m = armar_mensaje({**CONTRATO, "justificacion_modalidad": None})
    assert "<justificacion>\n(vacío)\n</justificacion>" in m


def test_cita_tolera_tildes_mayusculas_y_espacios():
    assert cita_verificada(CONTRATO, "APOYO A LA GESTION EN ACTIVIDADES VARIAS")
    assert cita_verificada(CONTRATO, '"actividades varias de la secretaria."')


def test_cita_inventada_o_muy_corta_no_cuenta():
    assert not cita_verificada(CONTRATO, "suministro de computadores portátiles")
    assert not cita_verificada(CONTRATO, "apoyo")


def test_hash_cambia_solo_si_cambia_el_texto():
    assert hash_texto(CONTRATO) == hash_texto({**CONTRATO, "valor_del_contrato": "1"})
    assert hash_texto(CONTRATO) != hash_texto({**CONTRATO, "objeto_del_contrato": "Otro"})


def test_bandera_con_nivel_medio_y_cita_verificada():
    cliente = ClienteFalso(respuesta(lectura()))
    fila = leer_contrato(cliente, CONTRATO, "anthropic.claude-opus-5-5")
    assert fila["bandera"] is True
    assert fila["cita_verificada"] is True
    assert fila["tipos"] == "objeto_vago,valor_desproporcionado"
    assert fila["tokens_entrada"] == 1200
    llamada = cliente.llamadas[0]
    assert llamada["model"] == "anthropic.claude-opus-5-5"
    assert llamada["output_format"] is Lectura
    assert llamada["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_sin_bandera_si_la_cita_no_esta_en_el_contrato():
    fila = leer_contrato(
        ClienteFalso(respuesta(lectura(cita="pago anticipado del 90 %"))), CONTRATO
    )
    assert fila["nivel"] == "medio"
    assert fila["cita_verificada"] is False
    assert fila["bandera"] is False


def test_sin_bandera_con_nivel_bajo():
    fila = leer_contrato(ClienteFalso(respuesta(lectura(nivel="bajo"))), CONTRATO)
    assert fila["bandera"] is False


def test_rechazo_y_errores_quedan_en_la_fila():
    fila = leer_contrato(ClienteFalso(respuesta(stop_reason="refusal")), CONTRATO)
    assert fila["error"] == "rechazo" and fila["nivel"] is None and fila["bandera"] is False

    peticion = httpx2.Request("POST", "https://bedrock-mantle.us-east-2.api.aws")
    error = anthropic.BadRequestError(
        "malo", response=httpx2.Response(400, request=peticion), body=None
    )
    fila = leer_contrato(ClienteFalso(error=error), CONTRATO)
    assert fila["error"] == "api_400"


def test_parquet_respeta_el_esquema_de_glue():
    filas = [leer_contrato(ClienteFalso(respuesta(lectura())), CONTRATO)]
    tabla = pq.read_table(io.BytesIO(cli.a_parquet(filas)))
    assert tabla.schema.equals(cli.ESQUEMA)
    assert tabla.num_rows == 1


def test_candidatos_excluye_los_ya_leidos_salvo_releer():
    assert "not exists" in cli.sql_candidatos(50, releer=False)
    assert "not exists" not in cli.sql_candidatos(50, releer=True)
    assert "limit 50" in cli.sql_candidatos(50, releer=False)


def test_leer_escribe_parquet_y_csv_de_revision(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "consultar", lambda sql: [CONTRATO])
    monkeypatch.setattr(cli, "crear_cliente", lambda region: ClienteFalso(respuesta(lectura())))
    revision = tmp_path / "revision.csv"
    cli.main(["leer", "--destino", str(tmp_path / "raw"), "--revision", str(revision)])

    archivos = list((tmp_path / "raw" / "senales_texto").rglob("*.parquet"))
    assert len(archivos) == 1 and archivos[0].parent.name.startswith("fecha_carga=")
    filas = cli.leer_csv(revision)
    assert filas[0]["id_contrato"] == "CO1.PCCNTR.1" and filas[0]["bandera"] == "True"
    resumen = json.loads(capsys.readouterr().out)
    assert resumen["con_bandera"] == 1


def leidos(con, sin):
    return [{"id_contrato": f"c{i}", "bandera": "true"} for i in range(con)] + [
        {"id_contrato": f"s{i}", "bandera": "false"} for i in range(sin)
    ]


def test_muestra_mitad_y_mitad_con_pesos():
    m = muestra_estratificada(leidos(40, 360), 100)
    con = [f for f in m if f["estrato"] == "con_bandera"]
    sin = [f for f in m if f["estrato"] == "sin_bandera"]
    assert len(con) == 40 and len(sin) == 60  # no hay 50 con bandera: completa el otro estrato
    assert con[0]["peso"] == 1.0 and sin[0]["peso"] == 6.0
    assert m == muestra_estratificada(leidos(40, 360), 100)  # misma semilla, misma muestra


def test_metricas_usan_los_pesos():
    filas = (
        [{"bandera": "True", "peso": "1", "etiqueta_humana": "si"}] * 8
        + [{"bandera": "True", "peso": "1", "etiqueta_humana": "no"}] * 2
        + [{"bandera": "False", "peso": "10", "etiqueta_humana": "si"}] * 1
        + [{"bandera": "False", "peso": "10", "etiqueta_humana": "no"}] * 9
        + [{"bandera": "False", "peso": "10", "etiqueta_humana": ""}]  # sin etiquetar: no cuenta
    )
    r = metricas(filas)
    assert r["etiquetados"] == 20
    assert r["precision"] == 0.8
    assert r["recall"] == pytest.approx(8 / 18, abs=0.001)


def test_csv_de_excel_en_espanol(tmp_path):
    ruta = tmp_path / "etiquetas.csv"
    ruta.write_text(
        "id_contrato;bandera;peso;etiqueta_humana\nc1;True;1;si\n", encoding="utf-8-sig"
    )
    assert cli.leer_csv(ruta) == [
        {"id_contrato": "c1", "bandera": "True", "peso": "1", "etiqueta_humana": "si"}
    ]
