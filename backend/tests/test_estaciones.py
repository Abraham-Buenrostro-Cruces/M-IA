"""Pruebas de F3 en el backend: geocodificador local, estado por estación y endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.adaptadores.fabrica import RUTA_LUGARES
from app.adaptadores.local.geocodificador import GeocodificadorLocal, leer_lugares, normalizar
from app.dominio import estaciones as est
from app.main import app
from app.modulos.estaciones.endpoints import obtener_catalogo, obtener_geocodificador
from app.modulos.rutas.endpoints import obtener_servicio_rutas
from app.modulos.rutas.servicio import ServicioRutas
from tests.red_motor_juguete import AHORA, construir_red, estados_ok, falla
from tests.test_endpoint_rutas import CaminataPrueba

CATALOGO = (
    est.EstacionResumen("METRO-TASQUENA", "Tasqueña", "METRO", 19.3438, -99.1395, ("2",), 1),
    est.EstacionResumen("TREN_LIGERO-TASQUENA", "Tasqueña", "TREN_LIGERO", 19.343, -99.140,
                        ("1",), 1),
    est.EstacionResumen("METROBUS-CALZADA_TAXQUENA", "Calzada Taxqueña", "METROBUS", 19.34,
                        -99.13, ("5",), 1),
    est.EstacionResumen("METRO-ZOCALO", "Zócalo", "METRO", 19.4325, -99.1322, ("2",), 1),
    est.EstacionResumen("METRO-CUATRO_CAMINOS", "Cuatro Caminos", "METRO", 19.459, -99.215,
                        ("2",), 1),
    est.EstacionResumen("A", "Estación A", "METRO", 19.30, -99.10, ("2",), 1),
    est.EstacionResumen("Z", "Estación Z", "METRO", 19.31, -99.09, ("3",), 2),
)  # fmt: skip


@pytest.fixture(scope="module")
def geo():
    return GeocodificadorLocal(list(CATALOGO), leer_lugares(RUTA_LUGARES))


# --------------------------------------------------------------------------- geocodificador


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [("Tasqueña", "tasquena"), ("TAXQUEÑA", "tasquena"), ("Zócalo!", "zocalo"),
     ("  C.U. ", "c u")],
)  # fmt: skip
def test_normalizar(texto, esperado):
    assert normalizar(texto) == esperado


@pytest.mark.parametrize(
    ("consulta", "primero"),
    [
        ("taxqueña", "Tasqueña"),
        ("tasquna", "Tasqueña"),  # error de escritura
        ("zocalo", "Zócalo"),
        ("CU", "Ciudad Universitaria"),  # alias de un lugar de prueba
        ("museo ciudad", "Museo de la Ciudad de México"),
        ("siglo xxi", "Centro Médico Nacional Siglo XXI"),
    ],
)
def test_busqueda_aproximada(geo, consulta, primero):
    assert geo.buscar(consulta)[0].nombre == primero


def test_estaciones_traen_clave_y_lugares_no(geo):
    tasquena = geo.buscar("tasqueña")[0]
    assert tasquena.tipo == "estacion" and tasquena.clave_estacion == "METRO-TASQUENA"
    cu = geo.buscar("CU")[0]
    assert cu.tipo == "lugar" and cu.clave_estacion is None


def test_sin_resultados_para_ruido(geo):
    assert geo.buscar("qwxzy") == []
    assert geo.buscar("   ") == []


def test_un_lugar_con_varios_alias_aparece_una_vez(geo):
    nombres = [x.nombre for x in geo.buscar("zocalo plaza de la constitucion", limite=10)]
    assert nombres.count("Plaza de la Constitución") == 1


def test_lugares_de_prueba_estan_en_la_cdmx():
    for lugar, _ in leer_lugares(RUTA_LUGARES):
        assert 19.0 < lugar.lat < 19.8 and -99.5 < lugar.lon < -98.8, lugar.nombre


# --------------------------------------------------------------------------- estado por estación


def test_estado_accesibilidad_con_red_de_juguete():
    red = construir_red()
    assert est.estado_accesibilidad(red, estados_ok()) == {
        "A": est.ACCESIBLE, "B": est.ACCESIBLE, "C": est.ACCESIBLE, "Z": est.NO_ACCESIBLE,
    }  # fmt: skip


def test_equipo_en_falla_marca_con_fallas():
    red = construir_red()
    assert est.estado_accesibilidad(red, estados_ok(E_C2=falla()))["C"] == est.CON_FALLAS


def test_una_salida_alternativa_mantiene_la_estacion_accesible():
    # C tiene dos salidas con elevador: si falla una, sigue siendo accesible.
    red = construir_red()
    assert est.estado_accesibilidad(red, estados_ok(E_C1=falla()))["C"] == est.ACCESIBLE


def test_sin_estado_es_con_fallas_no_accesible():
    """Regla 1: equipos sin dato no cuentan como accesibles, pero la estación sí tiene
    infraestructura accesible: se muestra 'con fallas', no 'no accesible'."""
    assert est.estado_accesibilidad(construir_red(), {})["A"] == est.CON_FALLAS


# --------------------------------------------------------------------------- endpoints


@pytest.fixture
def cliente(geo):
    servicio = ServicioRutas(construir_red(), lambda: estados_ok(E_C2=falla()), CaminataPrueba(),
                             reloj=lambda: AHORA)  # fmt: skip
    app.dependency_overrides.update({
        obtener_servicio_rutas: lambda: servicio,
        obtener_catalogo: lambda: CATALOGO,
        obtener_geocodificador: lambda: geo,
    })  # fmt: skip
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_get_perfiles(cliente):
    perfiles = cliente.get("/perfiles").json()
    assert [p["tipo_movilidad"] for p in perfiles] == [
        "silla_manual", "silla_electrica", "andadera", "adulto_mayor", "carriola"
    ]  # fmt: skip


def test_get_lugares(cliente):
    r = cliente.get("/lugares", params={"q": "taxqueña"})
    assert r.status_code == 200 and r.json()[0]["clave_estacion"] == "METRO-TASQUENA"
    assert cliente.get("/lugares", params={"q": "a"}).status_code == 422  # mínimo 2 caracteres


def test_get_estaciones(cliente):
    cuerpo = cliente.get("/estaciones").json()
    por_clave = {e["clave"]: e["accesibilidad"] for e in cuerpo["estaciones"]}
    assert por_clave["A"] == "ACCESIBLE"
    assert por_clave["Z"] == "NO_ACCESIBLE"
    assert por_clave["METRO-ZOCALO"] == "SIN_DATOS"  # no está en la red de juguete
    assert cuerpo["datos_demostracion"] is True
    solo_tl = cliente.get("/estaciones", params={"sistema": "TREN_LIGERO"}).json()
    assert [e["clave"] for e in solo_tl["estaciones"]] == ["TREN_LIGERO-TASQUENA"]


def test_get_estado_de_estacion(cliente):
    cuerpo = cliente.get("/estaciones/A/estado").json()
    assert cuerpo["accesibilidad"] == "ACCESIBLE"
    assert [e["codigo"] for e in cuerpo["equipos"]] == ["E-A1"]
    assert cliente.get("/estaciones/NO-EXISTE/estado").status_code == 404
