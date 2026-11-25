"""Integración: repositorio PostGIS -> dominio -> planificación (F2-1, F2-5)."""

from datetime import UTC, datetime

import pandas as pd
import pytest
from sqlalchemy.orm import sessionmaker

from app.adaptadores.local.bus import BusEnProceso
from app.adaptadores.local.caminata import CaminataLineaRecta
from app.dominio.red import Perfil
from app.ingesta import gtfs
from app.ingesta import inventario as inv
from app.ingesta.carga import aplicar_escenario, cargar_inventario
from app.modulos.rutas import repositorio
from app.modulos.rutas.servicio import ServicioRutas
from app.workers.contexto import Contexto
from app.workers.estado import recalcular_todos

pytestmark = pytest.mark.bd


@pytest.fixture
def red_cargada(sesion_bd, red_juguete):
    feed, estaciones, _ = red_juguete
    _, parada_a_clave = gtfs.agrupar_estaciones(feed)
    lineas = inv.lineas_por_estacion(
        gtfs.secuencias(feed, parada_a_clave), feed.routes, feed.stops, {"M2", "M3"}
    )
    catalogo = [inv.EntradaCatalogo(c, accesibilidad="COMPLETA") for c in sorted(lineas)]
    wheelchair = dict(zip(estaciones.clave, estaciones.wheelchair_boarding_gtfs, strict=True))
    n, e, c = inv.generar_inventario(catalogo, lineas, wheelchair).como_dataframes()
    cargar_inventario(sesion_bd, n, e, c)
    return sesion_bd


def _silla():
    return Perfil("silla_manual", 0, 6, False, 800, 0.9)


def test_repositorio_construye_la_red(red_cargada):
    red, demo = repositorio.cargar_red(red_cargada)
    assert demo is True
    assert {ln.nombre for ln in red.lineas.values()} == {"2", "3"}
    assert all(c.desde in red.niveles and c.hasta in red.niveles for c in red.conexiones)
    andenes = [n for n in red.niveles.values() if n.tipo == "ANDEN"]
    assert andenes and all(n.route_id in red.lineas for n in andenes)


def test_sin_escenario_todo_desconocido_no_hay_ruta(red_cargada):
    """Regla 1: con todos los equipos en DESCONOCIDO, una silla de ruedas no tiene ruta."""
    red, _ = repositorio.cargar_red(red_cargada)
    servicio = ServicioRutas(red, lambda: repositorio.cargar_estados(red_cargada),
                             CaminataLineaRecta())  # fmt: skip
    r = servicio.planear(servicio.punto_de_estacion("METRO-ALLENDE"),
                         servicio.punto_de_estacion("METRO-JUAREZ"), _silla())  # fmt: skip
    assert not r.hay_ruta_segura and not r.alternativas


def test_con_escenario_hay_ruta_accesible(red_cargada):
    escenario = pd.DataFrame(
        [{"codigo_equipo": "*", "estado": "OPERATIVO", "horas_desde_verificacion": "1-6"}]
    )
    ahora = datetime.now(UTC)
    aplicar_escenario(red_cargada, escenario, ahora)
    # D-21: el escenario sólo crea avisos DEMO; el estado lo calcula el estimador.
    sesiones = sessionmaker(bind=red_cargada.connection(), join_transaction_mode="create_savepoint")
    recalcular_todos(Contexto(sesiones, None, None, BusEnProceso(sincrono=True), lambda: ahora))
    red, _ = repositorio.cargar_red(red_cargada)
    servicio = ServicioRutas(red, lambda: repositorio.cargar_estados(red_cargada),
                             CaminataLineaRecta(), reloj=lambda: ahora)  # fmt: skip
    r = servicio.planear(servicio.punto_de_estacion("METRO-ALLENDE"),
                         servicio.punto_de_estacion("METRO-JUAREZ"), _silla())  # fmt: skip
    assert r.hay_ruta_segura
    mejor = r.alternativas[0]
    # Juárez está a ~510 m de Hidalgo: lo mejor es bajar en Hidalgo y caminar, o transbordar.
    assert mejor.abordajes >= 1
    assert all(e.estado == "OPERATIVO" for e in mejor.equipos)
