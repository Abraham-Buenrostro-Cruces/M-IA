"""Pruebas de app/ingesta/gtfs.py con el feed de juguete (tests/feed_juguete.py)."""

import pandas as pd
import pytest

from app.ingesta import gtfs
from tests.feed_juguete import STOPS, escribir_feed


@pytest.fixture
def feed(tmp_path):
    return gtfs.filtrar_sistemas(gtfs.leer_feed(escribir_feed(tmp_path / "gtfs.zip")))


def test_filtra_solo_metro_metrobus_y_tren_ligero(feed):
    assert set(feed.routes["route_id"]) == {"M2", "M3", "MB1"}
    assert "RTP-X" not in set(feed.stops["stop_id"])


def test_transbordo_se_agrupa_en_una_estacion(feed):
    estaciones, parada_a_clave = gtfs.agrupar_estaciones(feed)
    assert parada_a_clave["L2-HIDALGO"] == parada_a_clave["L3-HIDALGO"] == "METRO-HIDALGO"
    hidalgo = estaciones.set_index("clave").loc["METRO-HIDALGO"]
    assert hidalgo["paradas"] == ["L2-HIDALGO", "L3-HIDALGO"]


def test_mismo_nombre_en_otro_sistema_es_otra_estacion(feed):
    _, parada_a_clave = gtfs.agrupar_estaciones(feed)
    assert parada_a_clave["MB-HIDALGO"] == "METROBUS-HIDALGO"


def test_homonimas_lejanas_no_se_agrupan(tmp_path):
    # Dos "Hidalgo" de Metro a ~5 km: deben ser estaciones distintas.
    stops = STOPS.replace(
        "L3-HIDALGO,Hidalgo,19.43738,-99.14678", "L3-HIDALGO,Hidalgo,19.39000,-99.14678"
    )
    ruta = escribir_feed(tmp_path / "gtfs.zip", stops=stops)
    _, parada_a_clave = gtfs.agrupar_estaciones(gtfs.filtrar_sistemas(gtfs.leer_feed(ruta)))
    assert parada_a_clave["L2-HIDALGO"] != parada_a_clave["L3-HIDALGO"]
    assert parada_a_clave["L3-HIDALGO"] == "METRO-HIDALGO-2"


@pytest.mark.parametrize(
    ("valores", "esperado"),
    [(["1", "1"], 1), (["1", "2"], 2), (["1", ""], 0), (["0", "2"], 2), (["1", "0"], 0)],
)
def test_wheelchair_agregado_toma_el_valor_menos_favorable(valores, esperado):
    assert gtfs._wheelchair_agregado(pd.Series(valores)) == esperado


def test_wheelchair_de_hidalgo_es_no_accesible_si_una_parada_lo_es(feed):
    estaciones, _ = gtfs.agrupar_estaciones(feed)
    assert estaciones.set_index("clave").loc["METRO-HIDALGO", "wheelchair_boarding_gtfs"] == 2


def test_secuencias_un_viaje_por_ruta_y_direccion_con_tiempos(feed):
    _, parada_a_clave = gtfs.agrupar_estaciones(feed)
    s = gtfs.secuencias(feed, parada_a_clave)
    l2 = s[s["route_id"] == "M2"]
    assert list(l2["clave_estacion"]) == ["METRO-ALLENDE", "METRO-BELLAS_ARTES", "METRO-HIDALGO"]
    assert list(l2["direccion"]) == ["Tasqueña"] * 3
    assert l2["tiempo_desde_anterior_s"].tolist()[1:] == [90, 90]


def test_secuencias_cruzan_medianoche(feed):
    _, parada_a_clave = gtfs.agrupar_estaciones(feed)
    s = gtfs.secuencias(feed, parada_a_clave)
    assert s[s["route_id"] == "M3"]["tiempo_desde_anterior_s"].tolist()[1] == 120


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("Tasqueña", "TASQUENA"),
        ("Deportivo 18 de Marzo", "DEPORTIVO_18_DE_MARZO"),
        ("Garibaldi / Lagunilla", "GARIBALDI_LAGUNILLA"),
    ],
)
def test_normalizar_nombre(nombre, esperado):
    assert gtfs.normalizar_nombre(nombre) == esperado


def test_reporte_cuenta_por_sistema(feed):
    estaciones, _ = gtfs.agrupar_estaciones(feed)
    r = gtfs.reporte(feed, estaciones)
    assert r["METRO"]["estaciones"] == 4  # Allende, Bellas Artes, Hidalgo, Juárez
    assert r["METRO"]["paradas_gtfs"] == 5
    assert r["METRO"]["sin_dato_gtfs"] == 1  # Juárez
    assert r["METROBUS"]["estaciones"] == 1
