"""Consultas espaciales del módulo de rutas."""

from dataclasses import dataclass

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.bd.modelos import Estacion

# Radio por defecto para buscar estaciones de origen/destino (F1-3). Es el máximo de
# referencia; el motor lo recorta con distancia_pie_max_m del perfil (F2).
RADIO_CERCANIA_M = 600


@dataclass(frozen=True)
class EstacionCercana:
    clave: str
    nombre: str
    sistema: str
    distancia_m: float


def estaciones_cercanas(
    sesion: Session, lat: float, lon: float, radio_m: float = RADIO_CERCANIA_M
) -> list[EstacionCercana]:
    """Estaciones a menos de ``radio_m`` metros de (lat, lon), de la más cercana a la más lejana.

    Se castea a ``geography`` para que ST_DWithin y ST_Distance trabajen en metros
    sobre el elipsoide WGS84. Con ``geometry`` en EPSG:4326 las unidades serían
    grados, y un grado de longitud no mide lo mismo que uno de latitud.
    """
    punto = cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)
    ubicacion = cast(Estacion.ubicacion, Geography)
    distancia = func.ST_Distance(ubicacion, punto)
    filas = sesion.execute(
        select(Estacion.clave, Estacion.nombre, Estacion.sistema, distancia.label("d"))
        .where(func.ST_DWithin(ubicacion, punto, radio_m))
        .order_by(distancia)
    ).all()
    return [EstacionCercana(f.clave, f.nombre, f.sistema, round(f.d, 1)) for f in filas]
