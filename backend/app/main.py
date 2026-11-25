"""Punto de entrada de api-core (monolito modular, decisión D-02)."""

from importlib.metadata import version
from typing import Annotated

from fastapi import Depends, FastAPI

from app.config import Configuracion, obtener_configuracion
from app.modulos.estaciones.endpoints import router as router_estaciones
from app.modulos.rutas.endpoints import router as router_rutas

VERSION = version("rutaaccesible-backend")

app = FastAPI(
    title="RutaAccesible — api-core",
    version=VERSION,
    description="Planificación de viajes accesibles en Metro, Metrobús y Tren Ligero de la CDMX.",
)
app.include_router(router_rutas)
app.include_router(router_estaciones)


@app.get("/salud", tags=["operación"])
def salud(config: Annotated[Configuracion, Depends(obtener_configuracion)]) -> dict[str, str]:
    """Verificación de vida para Cloud Run y para la demo.

    Reporta el modo para que siempre sea visible si la instancia usa adaptadores
    simulados (``local``) o reales (``gcp``).
    """
    return {"estado": "ok", "modo": config.modo, "version": VERSION}
