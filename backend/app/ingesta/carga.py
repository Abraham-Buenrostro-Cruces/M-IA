"""Escritura en PostGIS de lo que produce la ingesta (F1-3, F1-4, F1-5).

Todas las cargas son **idempotentes** (upsert por llave natural): se pueden repetir
con un GTFS nuevo sin borrar estaciones, porque el inventario (niveles, equipos,
estados) cuelga de ellas con ON DELETE CASCADE y se perdería.
"""

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.bd.modelos import Estacion, EstacionRuta, RutaTransporte


def _punto_wkt(lat: float, lon: float) -> str:
    # WKT usa el orden (x, y) = (lon, lat); invertirlo es el error clásico con PostGIS.
    return f"SRID=4326;POINT({lon} {lat})"


def cargar_red(
    sesion: Session, rutas: pd.DataFrame, estaciones: pd.DataFrame, secuencias: pd.DataFrame
) -> dict[str, int]:
    """Carga rutas, estaciones y estacion_ruta. Devuelve conteos para el reporte."""
    for r in rutas.itertuples():
        color = (getattr(r, "route_color", "") or "").strip()
        valores = {
            "route_id_gtfs": r.route_id,
            "sistema": r.sistema,
            "nombre_linea": r.route_short_name,
            "nombre_largo": r.route_long_name or None,
            "color": f"#{color}" if color else None,
        }
        sesion.execute(
            insert(RutaTransporte)
            .values(**valores)
            .on_conflict_do_update(index_elements=["route_id_gtfs"], set_=valores)
        )

    for e in estaciones.itertuples():
        valores = {
            "clave": e.clave,
            "nombre": e.nombre,
            "sistema": e.sistema,
            "ubicacion": _punto_wkt(e.lat, e.lon),
            "wheelchair_boarding_gtfs": int(e.wheelchair_boarding_gtfs),
        }
        sesion.execute(
            insert(Estacion)
            .values(**valores)
            .on_conflict_do_update(index_elements=["clave"], set_=valores)
        )

    id_ruta = dict(
        sesion.execute(select(RutaTransporte.route_id_gtfs, RutaTransporte.id_ruta)).all()
    )
    id_estacion = dict(sesion.execute(select(Estacion.clave, Estacion.id_estacion)).all())

    # La secuencia sí se reemplaza completa: no tiene dependientes y puede cambiar entre feeds.
    sesion.execute(
        delete(EstacionRuta).where(EstacionRuta.id_ruta.in_([id_ruta[x] for x in rutas.route_id]))
    )
    filas = [
        {
            "id_ruta": id_ruta[s.route_id],
            "direccion": s.direccion,
            "secuencia": int(s.secuencia),
            "id_estacion": id_estacion[s.clave_estacion],
            "stop_id_gtfs": s.stop_id,
            "tiempo_desde_anterior_s": (
                None if pd.isna(s.tiempo_desde_anterior_s) else int(s.tiempo_desde_anterior_s)
            ),
        }
        for s in secuencias.itertuples()
    ]
    if filas:
        sesion.execute(insert(EstacionRuta), filas)
    return {"rutas": len(rutas), "estaciones": len(estaciones), "estacion_ruta": len(filas)}
