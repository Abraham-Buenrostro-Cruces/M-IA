import pytest

from app.adaptadores import fabrica
from app.adaptadores.local.caminata import FACTOR_RODEO, CaminataLineaRecta
from app.config import Configuracion
from app.dominio.red import Punto, distancia_m


def test_caminata_local_aplica_factor_de_rodeo():
    a, b = Punto(19.43, -99.13), Punto(19.435, -99.13)
    assert CaminataLineaRecta().tramo(a, b).distancia_m == pytest.approx(
        distancia_m(a, b) * FACTOR_RODEO
    )


def test_modo_gcp_sin_adaptador_falla_explicitamente(monkeypatch):
    fabrica.caminata.cache_clear()
    monkeypatch.setattr(fabrica, "obtener_configuracion", lambda: Configuracion(modo="gcp"))
    with pytest.raises(fabrica.AdaptadorNoDisponibleError):
        fabrica.caminata()
    fabrica.caminata.cache_clear()
