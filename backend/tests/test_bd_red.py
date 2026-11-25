"""Pruebas de integración con PostGIS: migraciones, carga de la red y cercanía (F1-2, F1-3)."""

import pytest
from alembic import command
from sqlalchemy import create_engine, func, inspect, select

from app.bd.modelos import Estacion, EstacionRuta, RutaTransporte
from app.ingesta import gtfs
from app.ingesta.carga import cargar_red
from app.modulos.rutas.consultas import estaciones_cercanas
from tests.conftest import config_alembic

pytestmark = pytest.mark.bd

TABLAS = {
    "usuario",
    "perfil_accesibilidad",
    "estacion",
    "ruta_transporte",
    "estacion_ruta",
    "unidad_transporte",
    "nivel",
    "conexion",
    "infraestructura_accesible",
    "estado_equipo",
    "historial_estado",
    "reporte_comunitario",
    "evidencia_fotografica",
    "validacion_comunitaria",
    "prediccion_falla",
    "recomendacion_ruta",
}


def test_migraciones_ida_y_vuelta(url_bd_pruebas):
    cfg = config_alembic(url_bd_pruebas)
    motor = create_engine(url_bd_pruebas)
    try:
        assert set(inspect(motor).get_table_names()) >= TABLAS
        command.downgrade(cfg, "base")
        assert not TABLAS & set(inspect(motor).get_table_names())
    finally:
        command.upgrade(cfg, "head")  # deja la base lista para las demás pruebas
        motor.dispose()
    assert set(inspect(create_engine(url_bd_pruebas)).get_table_names()) >= TABLAS


def test_carga_red(sesion_bd, red_juguete):
    _, _, conteos = red_juguete
    assert conteos == {"rutas": 3, "estaciones": 5, "estacion_ruta": 6}
    assert sesion_bd.scalar(select(func.count()).select_from(Estacion)) == 5
    hidalgo = sesion_bd.scalars(select(Estacion).where(Estacion.clave == "METRO-HIDALGO")).one()
    # Hidalgo pertenece a dos líneas a través de estacion_ruta.
    lineas = sesion_bd.scalars(
        select(RutaTransporte.nombre_linea)
        .join(EstacionRuta, EstacionRuta.id_ruta == RutaTransporte.id_ruta)
        .where(EstacionRuta.id_estacion == hidalgo.id_estacion)
    ).all()
    assert sorted(lineas) == ["2", "3"]


def test_carga_es_idempotente(sesion_bd, red_juguete):
    feed, estaciones, _ = red_juguete
    ids_antes = set(sesion_bd.scalars(select(Estacion.id_estacion)))
    _, parada_a_clave = gtfs.agrupar_estaciones(feed)
    cargar_red(sesion_bd, feed.routes, estaciones, gtfs.secuencias(feed, parada_a_clave))
    # Mismos UUID: el inventario que cuelga de las estaciones no se pierde al recargar.
    assert set(sesion_bd.scalars(select(Estacion.id_estacion))) == ids_antes
    assert sesion_bd.scalar(select(func.count()).select_from(EstacionRuta)) == 6


@pytest.mark.parametrize(
    ("punto", "esperadas"),
    [
        # En Allende: Bellas Artes está a ~470 m; Hidalgo a ~1 km queda fuera.
        ((19.43566, -99.13715), ["METRO-ALLENDE", "METRO-BELLAS_ARTES"]),
        # En Juárez: Hidalgo Metro (~510 m) y Hidalgo Metrobús (~485 m); Bellas Artes (~740 m) no.
        ((19.43290, -99.14760), ["METRO-JUAREZ", "METROBUS-HIDALGO", "METRO-HIDALGO"]),
        # Lejos de todo: lista vacía (sólo había una parada de RTP, que se filtra).
        ((19.40000, -99.10000), []),
    ],
)
def test_estaciones_a_menos_de_600_m(sesion_bd, red_juguete, punto, esperadas):
    cercanas = estaciones_cercanas(sesion_bd, *punto)
    assert [e.clave for e in cercanas] == esperadas  # ordenadas por distancia
    assert all(e.distancia_m <= 600 for e in cercanas)
