"""Pruebas de ``POST /rutas/plan`` con la red de juguete inyectada (sin base de datos)."""

import logging

import pytest
from fastapi.testclient import TestClient

from app.dominio.red import Punto, Tramo, distancia_m
from app.main import app
from app.modulos.rutas.endpoints import obtener_servicio_rutas
from app.modulos.rutas.servicio import ServicioRutas
from tests.red_motor_juguete import AHORA, DESTINO_EN_Z, DESTINO_PUNTO, construir_red, estados_ok
from tests.red_motor_juguete import falla as falla_confirmada


class CaminataPrueba:
    def tramo(self, origen: Punto, destino: Punto) -> Tramo:
        return Tramo(distancia_m(origen, destino))


@pytest.fixture
def cliente():
    estados = {"actual": estados_ok()}
    servicio = ServicioRutas(construir_red(), lambda: estados["actual"], CaminataPrueba(),
                             reloj=lambda: AHORA)  # fmt: skip
    app.dependency_overrides[obtener_servicio_rutas] = lambda: servicio
    try:
        yield TestClient(app), estados, servicio
    finally:
        app.dependency_overrides.clear()


def _peticion(destino=DESTINO_PUNTO, **perfil):
    return {
        "origen": {"clave_estacion": "A"},
        "destino": {"lat": destino.lat, "lon": destino.lon},
        "perfil": {"tipo_movilidad": "silla_manual", **perfil},
    }


def test_plan_devuelve_alternativas_con_iar_y_etiqueta_demo(cliente):
    c, _, _ = cliente
    r = c.post("/rutas/plan", json=_peticion())
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["hay_ruta_segura"] is True
    assert cuerpo["datos_demostracion"] is True
    alt = cuerpo["alternativas"][0]
    assert alt["recomendada"] and alt["orden"] == 1
    assert alt["categoria_iar"] == "alta"
    assert alt["equipos_criticos"] and alt["planes_b"] and alt["pasos"] and alt["trazo"]
    assert len(cuerpo["alternativas"]) <= 3


def test_falla_confirmada_aparece_como_descartada(cliente):
    c, estados, servicio = cliente
    estados["actual"] = estados_ok(E_C2=falla_confirmada())
    servicio._leido_en = float("-inf")  # fuerza a releer (la caché es de 60 s)
    cuerpo = c.post("/rutas/plan", json=_peticion()).json()
    assert "Estación B" in cuerpo["alternativas"][0]["resumen"]
    assert "falla confirmada" in cuerpo["descartadas"][0]["motivo"]


def test_sin_ruta_segura(cliente):
    c, _, _ = cliente
    cuerpo = c.post("/rutas/plan", json=_peticion(DESTINO_EN_Z)).json()
    assert cuerpo["hay_ruta_segura"] is False
    assert cuerpo["alternativas"] == []
    assert cuerpo["aviso"] and cuerpo["obstaculos"]


def test_perfil_ajustado_cambia_resultado(cliente):
    c, _, _ = cliente
    # Con capacidad para escaleras, Z sí es alcanzable.
    cuerpo = c.post(
        "/rutas/plan", json=_peticion(DESTINO_EN_Z, escalones_max=30, puede_escalera_electrica=True)
    ).json()
    assert cuerpo["hay_ruta_segura"] is True


@pytest.mark.parametrize(
    "ubicacion",
    [
        {},
        {"lat": 19.3},
        {"lat": 19.3, "lon": -99.1, "clave_estacion": "A"},
        {"lat": 25, "lon": -99},
    ],
)
def test_ubicacion_invalida(cliente, ubicacion):
    c, _, _ = cliente
    peticion = _peticion()
    peticion["origen"] = ubicacion
    assert c.post("/rutas/plan", json=peticion).status_code == 422


def test_estacion_desconocida_es_404(cliente):
    c, _, _ = cliente
    peticion = _peticion()
    peticion["origen"] = {"clave_estacion": "METRO-NO_EXISTE"}
    assert c.post("/rutas/plan", json=peticion).status_code == 404


def test_tipo_de_movilidad_invalido(cliente):
    c, _, _ = cliente
    assert (
        c.post("/rutas/plan", json=_peticion() | {"perfil": {"tipo_movilidad": "x"}}).status_code
        == 422
    )


def test_el_perfil_no_aparece_en_los_logs(cliente, caplog):
    """Regla de seguridad 6: el perfil de accesibilidad no aparece en logs."""
    c, _, _ = cliente
    caplog.set_level(logging.DEBUG)
    c.post("/rutas/plan", json=_peticion(escalones_max=3, peso_seguridad_vs_tiempo=0.77))
    texto = "\n".join(r.getMessage() for r in caplog.records)
    for sensible in ("silla_manual", "escalones_max", "peso_seguridad_vs_tiempo", "0.77"):
        assert sensible not in texto


def test_repr_del_perfil_oculta_sus_datos():
    from app.dominio.red import Perfil

    p = Perfil("silla_manual", 0, 6, False, 800, 0.9)
    assert "silla" not in repr(p) and "800" not in repr(p)
