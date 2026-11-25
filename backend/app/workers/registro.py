"""Conecta los manejadores de los trabajadores con el bus de eventos.

reporte-creado ──▶ worker-validacion ──▶ reporte-validado ──▶ worker-estado ──▶ estado-cambiado
voto-registrado ──▶ worker-validacion (revalida con la corroboración)
aviso-creado ──────────────────────────────────────────────▶ worker-estado
estado-cambiado ──▶ invalida la caché de estados del servicio de rutas
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.workers import contexto as c
from app.workers.estado import recalcular_equipo
from app.workers.validacion import procesar_reporte


def registrar(ctx: c.Contexto, al_cambiar_estado: Callable[[], None] = lambda: None) -> None:
    def por_reporte(datos: dict) -> None:
        procesar_reporte(ctx, uuid.UUID(datos["id"]))

    def por_equipo(datos: dict) -> None:
        if datos.get("id_equipo"):
            recalcular_equipo(ctx, uuid.UUID(datos["id_equipo"]))

    ctx.bus.suscribir(c.REPORTE_CREADO, por_reporte)
    ctx.bus.suscribir(c.VOTO_REGISTRADO, por_reporte)
    ctx.bus.suscribir(c.REPORTE_VALIDADO, por_equipo)
    ctx.bus.suscribir(c.AVISO_CREADO, por_equipo)
    ctx.bus.suscribir(c.ESTADO_CAMBIADO, lambda _: al_cambiar_estado())


def _invalidar_rutas() -> None:
    from app.modulos.rutas.endpoints import obtener_servicio_rutas

    # Sólo si el servicio ya existe: no tiene sentido construir el grafo para invalidarlo.
    if obtener_servicio_rutas.cache_info().currsize:
        obtener_servicio_rutas().invalidar_estados()


@lru_cache
def obtener_contexto() -> c.Contexto:
    """Contexto real (RA_MODO) con los manejadores ya suscritos. Se sustituye en pruebas."""
    from app.adaptadores import fabrica
    from app.bd.sesion import fabrica_sesiones

    ctx = c.Contexto(
        sesiones=fabrica_sesiones(),
        almacen=fabrica.almacen(),
        analizador=fabrica.analizador(),
        bus=fabrica.bus(),
        reloj=lambda: datetime.now(UTC),
    )
    registrar(ctx, _invalidar_rutas)
    return ctx


def obtener_sesion(ctx: Annotated[c.Contexto, Depends(obtener_contexto)]):
    """Sesión de base de datos por petición, de la misma fábrica que usan los trabajadores."""
    with ctx.sesiones() as s:
        yield s
