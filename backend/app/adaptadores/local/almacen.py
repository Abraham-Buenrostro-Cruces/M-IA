"""AlmacenEvidencias local: carpeta en disco + URL de subida firmada (emula Cloud Storage).

La URL de subida lleva un token JWT de vida corta que sólo autoriza a escribir **un**
objeto cuyo nombre generó el servidor (documento 07: la persona no controla la ruta).
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt

PROPOSITO = "subida-evidencia"


class TokenSubidaInvalidoError(PermissionError):
    pass


class AlmacenLocal:
    def __init__(self, carpeta: Path, secreto: str, prefijo_url: str = "/api/evidencias/subidas"):
        self.carpeta = carpeta
        self.secreto = secreto
        self.prefijo_url = prefijo_url
        for sub in ("originales", "redactadas"):
            (carpeta / sub).mkdir(parents=True, exist_ok=True)

    def _ruta(self, tipo: str, id_objeto: str) -> Path:
        # id_objeto lo genera el servidor (UUID); se valida igual para evitar rutas ajenas.
        if not id_objeto.replace("-", "").isalnum():
            raise ValueError("Identificador de objeto inválido")
        return self.carpeta / tipo / id_objeto

    def url_subida(self, id_objeto: str, segundos: int) -> str:
        token = jwt.encode(
            {"obj": id_objeto, "uso": PROPOSITO,
             "exp": datetime.now(UTC) + timedelta(seconds=segundos)},
            self.secreto, algorithm="HS256",
        )  # fmt: skip
        return f"{self.prefijo_url}/{token}"

    def objeto_de_token(self, token: str) -> str:
        try:
            datos = jwt.decode(token, self.secreto, algorithms=["HS256"])
        except jwt.ExpiredSignatureError as e:
            raise TokenSubidaInvalidoError("La URL de subida venció.") from e
        except jwt.InvalidTokenError as e:
            raise TokenSubidaInvalidoError("URL de subida inválida.") from e
        if datos.get("uso") != PROPOSITO:
            raise TokenSubidaInvalidoError("URL de subida inválida.")
        return datos["obj"]

    def guardar_original(self, id_objeto: str, contenido: bytes) -> None:
        ruta = self._ruta("originales", id_objeto)
        if ruta.exists():
            raise TokenSubidaInvalidoError("Esta URL de subida ya se usó.")  # un solo uso
        ruta.write_bytes(contenido)

    def leer_original(self, id_objeto: str) -> bytes | None:
        ruta = self._ruta("originales", id_objeto)
        return ruta.read_bytes() if ruta.exists() else None

    def guardar_redactada(self, id_objeto: str, contenido: bytes) -> None:
        self._ruta("redactadas", id_objeto).write_bytes(contenido)

    def leer_redactada(self, id_objeto: str) -> bytes | None:
        ruta = self._ruta("redactadas", id_objeto)
        return ruta.read_bytes() if ruta.exists() else None
