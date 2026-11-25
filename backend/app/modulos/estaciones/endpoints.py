"""Catálogo de estaciones, lugares y perfiles predefinidos (F3-1, F3-2, F3-3)."""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.adaptadores import fabrica
from app.adaptadores.puertos import Geocodificador
from app.dominio import estaciones as est
from app.dominio.restricciones import estado_de
from app.ingesta.perfiles import PERFILES_SEMILLA
from app.modulos.rutas.endpoints import obtener_servicio_rutas
from app.modulos.rutas.servicio import ServicioRutas

router = APIRouter()

EstadoEstacion = Literal["ACCESIBLE", "CON_FALLAS", "NO_ACCESIBLE", "SIN_DATOS"]
Sistema = Literal["METRO", "METROBUS", "TREN_LIGERO"]


class EstacionSalida(BaseModel):
    clave: str
    nombre: str
    sistema: Sistema
    lat: float
    lon: float
    lineas: list[str]
    accesibilidad: EstadoEstacion
    wheelchair_boarding_gtfs: int


class CatalogoEstaciones(BaseModel):
    estaciones: list[EstacionSalida]
    datos_demostracion: bool
    calculado_en: datetime


class EquipoEstado(BaseModel):
    codigo: str
    tipo: str
    referencia: str
    estado: str
    prob_operativo: float
    ultima_verificacion: datetime | None


class EstadoEstacionSalida(BaseModel):
    clave: str
    nombre: str
    accesibilidad: EstadoEstacion
    equipos: list[EquipoEstado]
    datos_demostracion: bool


class LugarSalida(BaseModel):
    tipo: Literal["estacion", "lugar"]
    nombre: str
    detalle: str
    lat: float
    lon: float
    clave_estacion: str | None


class PerfilPredefinido(BaseModel):
    tipo_movilidad: str
    nombre: str
    escalones_max: int
    pendiente_max_pct: float
    puede_escalera_electrica: bool
    distancia_pie_max_m: int
    peso_seguridad_vs_tiempo: float


@lru_cache
def obtener_catalogo() -> tuple[est.EstacionResumen, ...]:
    """Catálogo estático: se lee una vez por proceso."""
    from app.bd.sesion import fabrica_sesiones
    from app.modulos.rutas.repositorio import cargar_estaciones

    with fabrica_sesiones()() as s:
        return tuple(cargar_estaciones(s))


@lru_cache
def obtener_geocodificador() -> Geocodificador:
    return fabrica.geocodificador(list(obtener_catalogo()))


Catalogo = Annotated[tuple[est.EstacionResumen, ...], Depends(obtener_catalogo)]
Servicio = Annotated[ServicioRutas, Depends(obtener_servicio_rutas)]


class LineaSalida(BaseModel):
    route_id: str
    sistema: Sistema
    nombre: str
    nombre_largo: str | None
    color: str | None
    trazos: list[list[tuple[float, float]]] = Field(description="Polilíneas (lat, lon)")


class RedSalida(BaseModel):
    lineas: list[LineaSalida]
    estaciones: list[EstacionSalida]
    datos_demostracion: bool
    calculado_en: datetime


@lru_cache
def obtener_lineas() -> tuple[dict, ...]:
    """Líneas y trazos: estáticos, se leen una vez por proceso."""
    from app.bd.sesion import fabrica_sesiones
    from app.modulos.rutas.repositorio import cargar_lineas

    with fabrica_sesiones()() as s:
        return tuple(cargar_lineas(s))


Lineas = Annotated[tuple[dict, ...], Depends(obtener_lineas)]


@router.get("/red", response_model=RedSalida, tags=["estaciones"])
def red(lineas: Lineas, catalogo: Catalogo, servicio: Servicio) -> RedSalida:
    """Red completa para el mapa: Metro, Metrobús y Tren Ligero con su trazo real y color
    oficial (GTFS), y cada estación con su accesibilidad actual (SIN_DATOS fuera del
    corredor piloto: dibujar una línea no significa tener su inventario, D-17)."""
    cat = estaciones(catalogo, servicio)
    return RedSalida(
        lineas=[LineaSalida(**ln) for ln in lineas],
        estaciones=cat.estaciones,
        datos_demostracion=cat.datos_demostracion,
        calculado_en=cat.calculado_en,
    )


@router.get("/estaciones", response_model=CatalogoEstaciones, tags=["estaciones"])
def estaciones(
    catalogo: Catalogo, servicio: Servicio, sistema: Sistema | None = None
) -> CatalogoEstaciones:
    """Estaciones con su accesibilidad **actual** para quien no puede usar escalones (F3-3)."""
    accesibilidad = est.estado_accesibilidad(servicio.red, servicio.estados())
    return CatalogoEstaciones(
        estaciones=[
            EstacionSalida(
                clave=e.clave,
                nombre=e.nombre,
                sistema=e.sistema,
                lat=e.lat,
                lon=e.lon,
                lineas=list(e.lineas),
                accesibilidad=accesibilidad.get(e.clave, est.SIN_DATOS),
                wheelchair_boarding_gtfs=e.wheelchair_boarding_gtfs,
            )
            for e in catalogo
            if sistema is None or e.sistema == sistema
        ],
        datos_demostracion=servicio.datos_demostracion,
        calculado_en=datetime.now(UTC),
    )


@router.get("/estaciones/{clave}/estado", response_model=EstadoEstacionSalida, tags=["estaciones"])
def estado_estacion(clave: str, catalogo: Catalogo, servicio: Servicio) -> EstadoEstacionSalida:
    """Equipos de una estación con su estado vigente."""
    estacion = next((e for e in catalogo if e.clave == clave), None)
    if estacion is None:
        raise HTTPException(404, "Estación no encontrada")
    estados = servicio.estados()
    equipos = []
    for q in servicio.red.equipos.values():
        if q.clave_estacion != clave:
            continue
        s = estado_de(q.codigo, estados)
        equipos.append(
            EquipoEstado(
                codigo=q.codigo,
                tipo=q.tipo,
                referencia=q.referencia,
                estado=s.estado,
                prob_operativo=s.prob_operativo,
                ultima_verificacion=s.actualizado_en,
            )
        )
    return EstadoEstacionSalida(
        clave=clave,
        nombre=estacion.nombre,
        accesibilidad=est.estado_accesibilidad(servicio.red, estados).get(clave, est.SIN_DATOS),
        equipos=equipos,
        datos_demostracion=servicio.datos_demostracion,
    )


@router.get("/lugares", response_model=list[LugarSalida], tags=["lugares"])
def lugares(
    geocodificador: Annotated[Geocodificador, Depends(obtener_geocodificador)],
    q: Annotated[str, Query(min_length=2, max_length=80)],
) -> list[LugarSalida]:
    """Autocompletado de origen y destino: estaciones y lugares (F3-1)."""
    return [
        LugarSalida(
            tipo=x.tipo,
            nombre=x.nombre,
            detalle=x.detalle,
            lat=x.lat,
            lon=x.lon,
            clave_estacion=x.clave_estacion,
        )
        for x in geocodificador.buscar(q)
    ]


@router.get("/perfiles", response_model=list[PerfilPredefinido], tags=["perfiles"])
def perfiles() -> list[PerfilPredefinido]:
    """Perfiles de movilidad predefinidos. Son plantillas, no datos de una persona."""
    return [
        PerfilPredefinido(**{k: v for k, v in p.items() if k != "requiere_elevador"})
        for p in PERFILES_SEMILLA
    ]
