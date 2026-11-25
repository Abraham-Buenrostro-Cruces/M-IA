from fastapi.testclient import TestClient

from app.config import Configuracion, obtener_configuracion
from app.main import app


def test_salud_responde_ok_y_reporta_modo_local():
    cliente = TestClient(app)
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["modo"] in {"local", "gcp"}


def test_salud_refleja_el_modo_configurado():
    # La configuración se inyecta, así que puede sustituirse sin tocar variables de entorno.
    app.dependency_overrides[obtener_configuracion] = lambda: Configuracion(modo="gcp")
    try:
        assert TestClient(app).get("/salud").json()["modo"] == "gcp"
    finally:
        app.dependency_overrides.clear()
