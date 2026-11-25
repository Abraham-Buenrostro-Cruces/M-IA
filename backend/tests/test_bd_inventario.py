"""Pruebas de integración: inventario de demostración y perfiles semilla en PostGIS (F1-4, F1-5)."""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.bd.modelos import (
    Conexion,
    EstadoEquipo,
    InfraestructuraAccesible,
    Nivel,
    PerfilAccesibilidad,
)
from app.ingesta import gtfs
from app.ingesta import inventario as inv
from app.ingesta.carga import cargar_inventario
from app.ingesta.perfiles import PERFILES_SEMILLA, cargar_perfiles

pytestmark = pytest.mark.bd


@pytest.fixture
def inventario_juguete(red_juguete):
    feed, estaciones, _ = red_juguete
    _, parada_a_clave = gtfs.agrupar_estaciones(feed)
    lineas = inv.lineas_por_estacion(
        gtfs.secuencias(feed, parada_a_clave), feed.routes, feed.stops, {"M2", "M3"}
    )
    catalogo = [
        inv.EntradaCatalogo("METRO-ALLENDE"),
        inv.EntradaCatalogo("METRO-BELLAS_ARTES", accesibilidad="COMPLETA"),
        inv.EntradaCatalogo("METRO-HIDALGO", accesibilidad="COMPLETA"),
        inv.EntradaCatalogo("METRO-JUAREZ"),
    ]
    wheelchair = dict(zip(estaciones.clave, estaciones.wheelchair_boarding_gtfs, strict=True))
    return inv.generar_inventario(catalogo, lineas, wheelchair).como_dataframes()


def _contar(sesion, modelo):
    return sesion.scalar(select(func.count()).select_from(modelo))


def test_carga_inventario_y_estado_inicial_desconocido(sesion_bd, inventario_juguete):
    niveles, equipos, conexiones = inventario_juguete
    conteos = cargar_inventario(sesion_bd, niveles, equipos, conexiones)
    assert conteos == {
        "niveles": len(niveles),
        "equipos": len(equipos),
        "conexiones": len(conexiones),
    }
    assert _contar(sesion_bd, Nivel) == len(niveles)
    # Regla de seguridad 1: ningún equipo nuevo se presume operativo.
    estados = set(sesion_bd.scalars(select(EstadoEquipo.estado)))
    assert estados == {"DESCONOCIDO"}
    assert _contar(sesion_bd, EstadoEquipo) == len(equipos)


def test_carga_inventario_es_idempotente(sesion_bd, inventario_juguete):
    niveles, equipos, conexiones = inventario_juguete
    cargar_inventario(sesion_bd, niveles, equipos, conexiones)
    ids = set(sesion_bd.scalars(select(InfraestructuraAccesible.id_equipo)))
    cargar_inventario(sesion_bd, niveles, equipos, conexiones)
    assert set(sesion_bd.scalars(select(InfraestructuraAccesible.id_equipo))) == ids
    assert _contar(sesion_bd, Conexion) == len(conexiones)


def test_quitar_un_equipo_del_inventario_lo_borra(sesion_bd, inventario_juguete):
    niveles, equipos, conexiones = inventario_juguete
    cargar_inventario(sesion_bd, niveles, equipos, conexiones)
    quitado = equipos["codigo"].iloc[0]
    cargar_inventario(
        sesion_bd,
        niveles,
        equipos[equipos["codigo"] != quitado],
        conexiones[conexiones["codigo_equipo"] != quitado],
    )
    codigos = set(sesion_bd.scalars(select(InfraestructuraAccesible.codigo)))
    assert quitado not in codigos


def test_check_impide_pasillo_con_equipo(sesion_bd, inventario_juguete):
    niveles, equipos, conexiones = inventario_juguete
    cargar_inventario(sesion_bd, niveles, equipos, conexiones)
    a, b = sesion_bd.scalars(select(Nivel.id_nivel).limit(2)).all()
    equipo = sesion_bd.scalars(select(InfraestructuraAccesible.id_equipo).limit(1)).one()
    sesion_bd.add(
        Conexion(id_conexion=uuid.uuid4(), id_nivel_desde=a, id_nivel_hasta=b, tipo="PASILLO",
                 id_equipo=equipo, longitud_m=10, tiempo_s=10, fuente="DEMO")
    )  # fmt: skip
    with pytest.raises(IntegrityError, match="equipo_segun_tipo"):
        sesion_bd.flush()


def test_perfiles_semilla_idempotentes(sesion_bd):
    assert cargar_perfiles(sesion_bd) == 5
    cargar_perfiles(sesion_bd)
    perfiles = sesion_bd.scalars(
        select(PerfilAccesibilidad).where(PerfilAccesibilidad.id_usuario.is_(None))
    ).all()
    assert len(perfiles) == len(PERFILES_SEMILLA)
    silla = next(p for p in perfiles if p.tipo_movilidad == "silla_manual")
    assert silla.escalones_max == 0 and not silla.puede_escalera_electrica
