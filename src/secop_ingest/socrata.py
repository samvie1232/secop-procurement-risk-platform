"""Cliente mínimo de la API SODA de datos.gov.co, con paginación y reintentos."""

import logging
import os
from collections.abc import Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from secop_ingest.columnas import COLUMNAS

URL = "https://www.datos.gov.co/resource/jbjy-vk9h.json"
TAM_PAGINA = 20_000

log = logging.getLogger(__name__)


class ClienteSocrata:
    def __init__(self, url: str = URL, timeout: int = 180):
        self.url = url
        self.timeout = timeout
        self.sesion = requests.Session()
        # 429 (cuota) y 5xx (caídas del portal) se reintentan con espera exponencial: 2, 4, 8... s
        reintentos = Retry(
            total=6,
            backoff_factor=2,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        self.sesion.mount("https://", HTTPAdapter(max_retries=reintentos))
        # El token es opcional: sin él la API funciona, pero con menos cuota.
        token = os.environ.get("SOCRATA_APP_TOKEN")
        if token:
            self.sesion.headers["X-App-Token"] = token

    def _get(self, params: dict) -> list[dict]:
        respuesta = self.sesion.get(self.url, params=params, timeout=self.timeout)
        respuesta.raise_for_status()
        return respuesta.json()

    def contar(self, where: str) -> int:
        filas = self._get({"$select": "count(*) AS n", "$where": where})
        return int(filas[0]["n"])

    def paginas(self, where: str, tam_pagina: int = TAM_PAGINA) -> Iterator[list[dict]]:
        """Recorre el resultado con $limit/$offset. $order=:id (id interno de Socrata)
        da un orden estable, así ninguna fila se repite ni se salta entre páginas."""
        offset = 0
        while True:
            pagina = self._get(
                {
                    "$select": ",".join(COLUMNAS),
                    "$where": where,
                    "$order": ":id",
                    "$limit": tam_pagina,
                    "$offset": offset,
                }
            )
            if not pagina:
                return
            log.info("página offset=%s: %s filas", offset, len(pagina))
            yield pagina
            if len(pagina) < tam_pagina:
                return
            offset += tam_pagina
