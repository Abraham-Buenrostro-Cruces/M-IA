"""Selección de adaptadores según RA_MODO (D-10)."""

from functools import lru_cache

from app.adaptadores.puertos import CaminataProveedor
from app.config import obtener_configuracion


class AdaptadorNoDisponibleError(RuntimeError):
    pass


@lru_cache
def caminata() -> CaminataProveedor:
    modo = obtener_configuracion().modo
    if modo == "local":
        from app.adaptadores.local.caminata import CaminataLineaRecta

        return CaminataLineaRecta()
    # Se implementa con Routes API en la Fase 6. Fallar al pedirlo es preferible a
    # degradar en silencio a la línea recta en producción.
    raise AdaptadorNoDisponibleError(
        "CaminataProveedor para RA_MODO=gcp llega en la Fase 6 (F6-3)."
    )
