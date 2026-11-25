"""Selección de adaptadores según RA_MODO (D-10)."""

from functools import lru_cache
from pathlib import Path

from app.adaptadores.puertos import CaminataProveedor, Geocodificador
from app.config import obtener_configuracion

# Lugares de prueba del geocodificador local (data/demo/lugares.csv en la raíz del repositorio).
RUTA_LUGARES = Path(__file__).resolve().parents[3] / "data" / "demo" / "lugares.csv"


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


def geocodificador(estaciones) -> Geocodificador:
    modo = obtener_configuracion().modo
    if modo == "local":
        from app.adaptadores.local.geocodificador import GeocodificadorLocal, leer_lugares

        return GeocodificadorLocal(estaciones, leer_lugares(RUTA_LUGARES))
    raise AdaptadorNoDisponibleError("Geocodificador para RA_MODO=gcp llega en la Fase 6 (F6-3).")
