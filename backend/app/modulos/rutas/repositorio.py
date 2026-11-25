"""Lectura de la red y de los estados desde PostGIS hacia los tipos del dominio (F2-1).

Sólo se cargan las líneas que tienen andenes en el inventario: fuera del corredor no
hay niveles, así que esas líneas no aportarían rutas transitables y sólo harían más
grande el grafo.
"""

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.bd.modelos import (
    Conexion,
    Estacion,
    EstacionRuta,
    EstadoEquipo,
    InfraestructuraAccesible,
    Nivel,
    RutaTransporte,
)
from app.dominio import red as d

# Si una ruta no trae frequencies.txt: valor conservador (espera esperada de 2.5 min).
INTERVALO_POR_DEFECTO_S = 300


def cargar_red(sesion: Session) -> tuple[d.Red, bool]:
    """Devuelve la red y si contiene datos de demostración (regla 4: se etiqueta en la UI)."""
    filas_nivel = sesion.execute(
        select(
            Nivel.codigo, Nivel.tipo, Nivel.referencia, Nivel.direccion, Nivel.fuente,
            Estacion.clave, Estacion.nombre, RutaTransporte.route_id_gtfs,
            func.ST_Y(Nivel.ubicacion).label("lat"), func.ST_X(Nivel.ubicacion).label("lon"),
        )
        .join(Estacion, Estacion.id_estacion == Nivel.id_estacion)
        .outerjoin(RutaTransporte, RutaTransporte.id_ruta == Nivel.id_ruta)
    ).all()  # fmt: skip
    niveles = {
        f.codigo: d.Nivel(f.codigo, f.clave, f.nombre, f.tipo, f.lat, f.lon, f.referencia or "",
                          f.route_id_gtfs, f.direccion)
        for f in filas_nivel
    }  # fmt: skip
    demo = any(f.fuente == "DEMO" for f in filas_nivel)

    desde, hasta = aliased(Nivel), aliased(Nivel)
    filas_con = sesion.execute(
        select(
            desde.codigo.label("desde"), hasta.codigo.label("hasta"), Conexion.tipo,
            Conexion.tiempo_s, Conexion.longitud_m, Conexion.escalones, Conexion.pendiente_pct,
            Conexion.bidireccional, InfraestructuraAccesible.codigo.label("equipo"),
        )
        .join(desde, desde.id_nivel == Conexion.id_nivel_desde)
        .join(hasta, hasta.id_nivel == Conexion.id_nivel_hasta)
        .outerjoin(InfraestructuraAccesible,
                   InfraestructuraAccesible.id_equipo == Conexion.id_equipo)
    ).all()  # fmt: skip
    conexiones = tuple(
        d.Conexion(f.desde, f.hasta, f.tipo, f.tiempo_s, f.longitud_m, f.escalones,
                   f.pendiente_pct, f.bidireccional, f.equipo)
        for f in filas_con
    )  # fmt: skip

    equipos = {
        f.codigo: d.Equipo(f.codigo, f.clave, f.tipo, f.referencia or f.codigo)
        for f in sesion.execute(
            select(InfraestructuraAccesible.codigo, InfraestructuraAccesible.tipo,
                   InfraestructuraAccesible.referencia, Estacion.clave)
            .join(Estacion, Estacion.id_estacion == InfraestructuraAccesible.id_estacion)
        )
    }  # fmt: skip

    rutas_con_anden = {n.route_id for n in niveles.values() if n.route_id}
    lineas = {
        f.route_id_gtfs: d.Linea(f.route_id_gtfs, f.sistema, f.nombre_linea,
                                 f.intervalo_medio_s or INTERVALO_POR_DEFECTO_S)
        for f in sesion.execute(
            select(RutaTransporte).where(RutaTransporte.route_id_gtfs.in_(rutas_con_anden))
        ).scalars()
    }  # fmt: skip

    paradas: dict[tuple[str, str], list] = defaultdict(list)
    for f in sesion.execute(
        select(RutaTransporte.route_id_gtfs, EstacionRuta.direccion, EstacionRuta.secuencia,
               Estacion.clave, EstacionRuta.tiempo_desde_anterior_s)
        .join(RutaTransporte, RutaTransporte.id_ruta == EstacionRuta.id_ruta)
        .join(Estacion, Estacion.id_estacion == EstacionRuta.id_estacion)
        .where(RutaTransporte.route_id_gtfs.in_(rutas_con_anden))
        .order_by(RutaTransporte.route_id_gtfs, EstacionRuta.direccion, EstacionRuta.secuencia)
    ):  # fmt: skip
        paradas[(f.route_id_gtfs, f.direccion)].append((f.clave, f.tiempo_desde_anterior_s or 0))
    secuencias = tuple(d.Secuencia(r, dr, tuple(p)) for (r, dr), p in paradas.items())

    cerradas = frozenset(
        sesion.scalars(select(Estacion.clave).where(Estacion.estado_operacion != "abierta"))
    )
    return d.Red(niveles, conexiones, equipos, lineas, secuencias, cerradas), demo


def cargar_estados(sesion: Session) -> dict[str, d.EstadoEquipo]:
    return {
        f.codigo: d.EstadoEquipo(f.estado, f.prob_operativo, f.actualizado_en,
                                 f.fuente_ultima or "")
        for f in sesion.execute(
            select(InfraestructuraAccesible.codigo, EstadoEquipo.estado,
                   EstadoEquipo.prob_operativo, EstadoEquipo.actualizado_en,
                   EstadoEquipo.fuente_ultima)
            .join(EstadoEquipo, EstadoEquipo.id_equipo == InfraestructuraAccesible.id_equipo)
        )
    }  # fmt: skip
