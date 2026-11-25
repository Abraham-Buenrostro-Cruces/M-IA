"""Configuración de api-core a partir de variables de entorno.

`RA_MODO` selecciona la familia de adaptadores (decisión D-10):
- ``local``: implementaciones simuladas y deterministas, sin cuenta de Google Cloud.
- ``gcp``: servicios reales (Cloud Storage, Vision, Gemini, Speech-to-Text, Pub/Sub...).

Se tipa como ``Literal`` a propósito: un valor mal escrito (p. ej. ``RA_MODO=GCP ``)
debe detener el arranque. Caer en silencio a ``local`` en producción haría que el
sistema respondiera con estados de equipos simulados, que es justo el tipo de error
que la plataforma no puede permitirse.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env vive en la raíz del repositorio (lo comparte docker compose).
_RAIZ_REPO = Path(__file__).resolve().parents[2]


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RA_",
        env_file=_RAIZ_REPO / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env también trae variables de Postgres para docker compose
    )

    modo: Literal["local", "gcp"] = "local"
    bd_url: str | None = None


@lru_cache
def obtener_configuracion() -> Configuracion:
    """Configuración única por proceso.

    Se inyecta con ``Depends`` para poder sustituirla en pruebas.
    """
    return Configuracion()
