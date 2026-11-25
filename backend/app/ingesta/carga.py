"""Escritura en PostGIS de lo que produce la ingesta (F1-3, F1-4, F1-5).

Todas las cargas son **idempotentes** (upsert por llave natural): se pueden repetir
con un GTFS nuevo sin borrar estaciones, porque el inventario (niveles, equipos,
estados) cuelga de ellas con ON DELETE CASCADE y se perdería.
"""

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.bd.modelos import (
    Conexion,
    Estacion,
    EstacionRuta,
    EstadoEquipo,
    InfraestructuraAccesible,
    Nivel,
    RutaTransporte,
)


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


def _o_nulo(valor):
    """NaN de pandas -> None (las columnas opcionales de los CSV llegan como NaN)."""
    return None if valor is None or (isinstance(valor, float) and pd.isna(valor)) else valor


def cargar_inventario(
    sesion: Session, niveles: pd.DataFrame, equipos: pd.DataFrame, conexiones: pd.DataFrame
) -> dict[str, int]:
    """Carga el inventario de demostración (F1-4). Idempotente.

    - Niveles y equipos: upsert por ``codigo``; se eliminan los DEMO de esas estaciones
      que ya no están en los CSV (p. ej. si el catálogo cambió).
    - Conexiones: no tienen llave natural, así que las DEMO de esas estaciones se reemplazan.
    - Estado inicial de cada equipo nuevo: ``DESCONOCIDO`` con Beta(1, 1). Nunca se
      presume que funciona (regla de seguridad 1); el estado lo moverá la evidencia (F4).
    """
    id_estacion = dict(sesion.execute(select(Estacion.clave, Estacion.id_estacion)).all())
    id_ruta = dict(
        sesion.execute(select(RutaTransporte.route_id_gtfs, RutaTransporte.id_ruta)).all()
    )
    faltantes = set(niveles["clave_estacion"]) - set(id_estacion)
    if faltantes:
        raise ValueError(f"Estaciones no cargadas (¿falta cargar_gtfs.py?): {sorted(faltantes)}")
    ids_est = [id_estacion[c] for c in set(niveles["clave_estacion"])]

    # Las conexiones viejas se borran primero: referencian niveles y equipos que pueden desaparecer.
    niveles_existentes = select(Nivel.id_nivel).where(Nivel.id_estacion.in_(ids_est))
    sesion.execute(
        delete(Conexion).where(
            Conexion.fuente == "DEMO", Conexion.id_nivel_desde.in_(niveles_existentes)
        )
    )
    sesion.execute(
        delete(Nivel).where(
            Nivel.fuente == "DEMO",
            Nivel.id_estacion.in_(ids_est),
            Nivel.codigo.not_in(list(niveles["codigo"])),
        )
    )
    sesion.execute(
        delete(InfraestructuraAccesible).where(
            InfraestructuraAccesible.fuente == "DEMO",
            InfraestructuraAccesible.id_estacion.in_(ids_est),
            InfraestructuraAccesible.codigo.not_in(list(equipos["codigo"])),
        )
    )

    for n in niveles.to_dict("records"):
        valores = {
            "codigo": n["codigo"],
            "id_estacion": id_estacion[n["clave_estacion"]],
            "tipo": n["tipo"],
            "id_ruta": id_ruta[n["route_id_gtfs"]] if _o_nulo(n["route_id_gtfs"]) else None,
            "direccion": _o_nulo(n["direccion"]),
            "referencia": _o_nulo(n["referencia"]),
            "ubicacion": _punto_wkt(n["lat"], n["lon"]),
            "fuente": n["fuente"],
        }
        sesion.execute(
            insert(Nivel)
            .values(**valores)
            .on_conflict_do_update(index_elements=["codigo"], set_=valores)
        )

    for e in equipos.to_dict("records"):
        valores = {
            "codigo": e["codigo"],
            "id_estacion": id_estacion[e["clave_estacion"]],
            "tipo": e["tipo"],
            "referencia": _o_nulo(e["referencia"]),
            "ubicacion": _punto_wkt(e["lat"], e["lon"]),
            "fuente": e["fuente"],
        }
        sesion.execute(
            insert(InfraestructuraAccesible)
            .values(**valores)
            .on_conflict_do_update(index_elements=["codigo"], set_=valores)
        )

    id_nivel = dict(sesion.execute(select(Nivel.codigo, Nivel.id_nivel)).all())
    id_equipo = dict(
        sesion.execute(
            select(InfraestructuraAccesible.codigo, InfraestructuraAccesible.id_equipo)
        ).all()
    )

    filas_conexion = [
        {
            "id_nivel_desde": id_nivel[c["nivel_desde"]],
            "id_nivel_hasta": id_nivel[c["nivel_hasta"]],
            "tipo": c["tipo"],
            "id_equipo": id_equipo[c["codigo_equipo"]] if _o_nulo(c["codigo_equipo"]) else None,
            "bidireccional": bool(c["bidireccional"]),
            "escalones": int(c["escalones"]),
            "pendiente_pct": float(c["pendiente_pct"]),
            "longitud_m": float(c["longitud_m"]),
            "tiempo_s": int(c["tiempo_s"]),
            "fuente": c["fuente"],
        }
        for c in conexiones.to_dict("records")
    ]
    if filas_conexion:
        sesion.execute(insert(Conexion), filas_conexion)

    nuevos_estados = [
        {"id_equipo": id_equipo[cod], "estado": "DESCONOCIDO", "prob_operativo": 0.5,
         "alfa": 1.0, "beta": 1.0, "confianza": 0.0, "fuente_ultima": "inventario"}
        for cod in equipos["codigo"]
    ]  # fmt: skip
    if nuevos_estados:
        sesion.execute(insert(EstadoEquipo).values(nuevos_estados).on_conflict_do_nothing())

    return {"niveles": len(niveles), "equipos": len(equipos), "conexiones": len(filas_conexion)}
