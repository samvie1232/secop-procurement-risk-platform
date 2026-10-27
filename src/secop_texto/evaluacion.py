"""Evaluación de la señal de texto contra etiquetas hechas a mano.

La muestra es estratificada: la mitad de contratos con bandera y la mitad sin
bandera. Si se tomara al azar y la bandera fuera rara, casi no habría positivos
para medir la precisión. Cada fila lleva un peso (contratos del estrato /
contratos muestreados del estrato) para que el recall estimado represente a
todos los contratos leídos y no solo a la muestra.
"""

import random

ESTRATOS = ("con_bandera", "sin_bandera")


def _es_verdad(valor) -> bool:
    return str(valor).strip().lower() in ("true", "1", "si", "sí", "s", "yes")


def muestra_estratificada(filas: list[dict], n: int, semilla: int = 42) -> list[dict]:
    """Elige n filas, mitad por estrato (si un estrato no alcanza, el otro
    completa) y les agrega las columnas estrato y peso."""
    azar = random.Random(semilla)
    por_estrato = {e: [] for e in ESTRATOS}
    for f in filas:
        por_estrato["con_bandera" if _es_verdad(f.get("bandera")) else "sin_bandera"].append(f)

    cupos = {"con_bandera": min(n // 2, len(por_estrato["con_bandera"]))}
    cupos["sin_bandera"] = min(n - cupos["con_bandera"], len(por_estrato["sin_bandera"]))
    cupos["con_bandera"] = min(n - cupos["sin_bandera"], len(por_estrato["con_bandera"]))

    muestra = []
    for estrato in ESTRATOS:
        elegidas = azar.sample(por_estrato[estrato], cupos[estrato])
        peso = len(por_estrato[estrato]) / len(elegidas) if elegidas else 0
        muestra += [{**f, "estrato": estrato, "peso": round(peso, 4)} for f in elegidas]
    return muestra


def metricas(etiquetadas: list[dict]) -> dict:
    """Precisión y recall de la bandera contra etiqueta_humana (si/no).

    Las filas sin etiqueta se ignoran. Los conteos son de la muestra; la
    precisión y el recall usan los pesos de la muestra estratificada.
    """
    conteo = {"vp": 0, "fp": 0, "fn": 0, "vn": 0}
    pesos = dict.fromkeys(conteo, 0.0)
    for f in etiquetadas:
        etiqueta = str(f.get("etiqueta_humana") or "").strip().lower()
        if etiqueta not in ("si", "sí", "no"):
            continue
        humano = etiqueta != "no"
        bandera = _es_verdad(f.get("bandera"))
        celda = {
            (True, True): "vp",
            (True, False): "fp",
            (False, True): "fn",
            (False, False): "vn",
        }[(bandera, humano)]
        conteo[celda] += 1
        pesos[celda] += float(f.get("peso") or 1)

    def razon(a: float, b: float) -> float | None:
        return round(a / (a + b), 3) if a + b else None

    precision = razon(pesos["vp"], pesos["fp"])
    recall = razon(pesos["vp"], pesos["fn"])
    f1 = round(2 * precision * recall / (precision + recall), 3) if precision and recall else None
    return {
        "etiquetados": sum(conteo.values()),
        **conteo,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
