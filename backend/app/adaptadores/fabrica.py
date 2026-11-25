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


# Catálogo de fotos sintéticas que reconoce el analizador simulado.
RUTA_ANALISIS_DEMO = (
    Path(__file__).resolve().parents[3] / "data" / "demo" / "fotos" / "analisis.json"
)


@lru_cache
def almacen():
    config = obtener_configuracion()
    if config.modo == "local":
        from app.adaptadores.local.almacen import AlmacenLocal

        if not config.jwt_secreto:
            raise AdaptadorNoDisponibleError("Falta RA_JWT_SECRETO para firmar URL de subida.")
        return AlmacenLocal(config.almacen_local, config.jwt_secreto)
    raise AdaptadorNoDisponibleError("AlmacenEvidencias para RA_MODO=gcp llega en la Fase 6.")


@lru_cache
def analizador():
    if obtener_configuracion().modo == "local":
        from app.adaptadores.local.analizador import AnalizadorSimulado

        return AnalizadorSimulado(RUTA_ANALISIS_DEMO)
    raise AdaptadorNoDisponibleError("AnalizadorImagen para RA_MODO=gcp llega en la Fase 6.")


@lru_cache
def bus():
    if obtener_configuracion().modo == "local":
        from app.adaptadores.local.bus import BusEnProceso

        return BusEnProceso()
    raise AdaptadorNoDisponibleError("BusEventos (Pub/Sub) para RA_MODO=gcp llega en la Fase 6.")


# Audios SINTÉTICOS de demostración que reconoce el transcriptor simulado (F5-2).
RUTA_AUDIOS_DEMO = (
    Path(__file__).resolve().parents[3] / "data" / "demo" / "audios" / "transcripciones.json"
)


@lru_cache
def transcriptor():
    config = obtener_configuracion()
    if config.modo == "local":
        from app.adaptadores.local.transcriptor import TranscriptorSimulado

        return TranscriptorSimulado(RUTA_AUDIOS_DEMO, config.voz_frase_demo)
    raise AdaptadorNoDisponibleError("TranscriptorVoz (Speech-to-Text v2) llega en la Fase 6.")


@lru_cache
def interprete():
    if obtener_configuracion().modo == "local":
        from app.adaptadores.local.interprete import InterpreteReglas

        return InterpreteReglas()
    raise AdaptadorNoDisponibleError("InterpreteLenguaje (Gemini) llega en la Fase 6.")
