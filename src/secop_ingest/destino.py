"""Dónde se escriben los archivos: una carpeta local (pruebas) o S3 (el lago)."""

from pathlib import Path

import boto3


class DestinoLocal:
    def __init__(self, raiz: str):
        self.raiz = Path(raiz)

    def escribir(self, llave: str, datos: bytes) -> None:
        ruta = self.raiz / llave
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(datos)

    def listar(self, prefijo: str) -> list[str]:
        carpeta, _, inicio = prefijo.rpartition("/")
        base = self.raiz / carpeta
        if not base.exists():
            return []
        return sorted(f"{carpeta}/{p.name}" for p in base.iterdir() if p.name.startswith(inicio))

    def borrar(self, llaves: list[str]) -> None:
        for llave in llaves:
            (self.raiz / llave).unlink()


class DestinoS3:
    def __init__(self, bucket: str, prefijo: str = ""):
        self.bucket = bucket
        self.prefijo = prefijo.strip("/")
        self.s3 = boto3.client("s3")

    def _completa(self, llave: str) -> str:
        return f"{self.prefijo}/{llave}" if self.prefijo else llave

    def escribir(self, llave: str, datos: bytes) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=self._completa(llave), Body=datos)

    def listar(self, prefijo: str) -> list[str]:
        completo = self._completa(prefijo)
        recorte = len(self.prefijo) + 1 if self.prefijo else 0  # devuelve llaves relativas
        llaves = []
        for pagina in self.s3.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=completo
        ):
            llaves += [o["Key"][recorte:] for o in pagina.get("Contents", [])]
        return sorted(llaves)

    def borrar(self, llaves: list[str]) -> None:
        for i in range(0, len(llaves), 1000):  # delete_objects acepta hasta 1000 por llamada
            lote = [{"Key": self._completa(k)} for k in llaves[i : i + 1000]]
            self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": lote})


def crear_destino(uri: str):
    """s3://bucket/prefijo → S3; cualquier otra cosa → carpeta local."""
    if uri.startswith("s3://"):
        bucket, _, prefijo = uri.removeprefix("s3://").partition("/")
        return DestinoS3(bucket, prefijo)
    return DestinoLocal(uri)
