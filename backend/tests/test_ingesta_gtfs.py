"""Pruebas de app/ingesta/gtfs.py con un feed GTFS de juguete.

Red de juguete (coordenadas reales aproximadas del centro de la CDMX):
- Metro L2: Allende → Bellas Artes → Hidalgo (viajes repetidos con otro service_id).
- Metro L3: Juárez → Hidalgo (parada propia, a ~50 m de la de L2: transbordo).
- Metrobús L1: Hidalgo (misma denominación que el Metro, pero otro sistema).
- RTP: una ruta que debe quedar fuera.
"""

import zipfile

import pytest

from app.ingesta import gtfs

AGENCY = "agency_id,agency_name\nMETRO,Metro\nMB,Metrobús\nRTP,RTP\n"
ROUTES = (
    "route_id,agency_id,route_short_name,route_long_name,route_type\n"
    "M2,METRO,2,Cuatro Caminos - Tasqueña,1\n"
    "M3,METRO,3,Indios Verdes - Universidad,1\n"
    "MB1,MB,1,Indios Verdes - El Caminero,3\n"
    "R1,RTP,1,Ruta RTP,3\n"
)
TRIPS = (
    "route_id,service_id,trip_id,trip_headsign,direction_id\n"
    "M2,LV,m2a,Tasqueña,0\n"
    "M2,SAB,m2b,Tasqueña,0\n"  # mismo recorrido, otro servicio: no debe duplicar la secuencia
    "M3,LV,m3a,Universidad,0\n"
    "MB1,LV,mb1a,El Caminero,0\n"
    "R1,LV,r1a,Destino,0\n"
)
STOPS = (
    "stop_id,stop_name,stop_lat,stop_lon,wheelchair_boarding\n"
    "L2-ALLENDE,Allende,19.43566,-99.13715,1\n"
    "L2-BELLAS,Bellas Artes,19.43638,-99.14161,2\n"
    "L2-HIDALGO,Hidalgo,19.43755,-99.14722,1\n"
    "L3-JUAREZ,Juárez,19.43290,-99.14760,\n"
    "L3-HIDALGO,Hidalgo,19.43738,-99.14678,2\n"
    "MB-HIDALGO,Hidalgo,19.43700,-99.14600,1\n"
    "RTP-X,Parada RTP,19.40000,-99.10000,0\n"
)
STOP_TIMES = (
    "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
    "m2a,06:00:00,06:00:00,L2-ALLENDE,1\n"
    "m2a,06:01:30,06:01:30,L2-BELLAS,2\n"
    "m2a,06:03:00,06:03:00,L2-HIDALGO,3\n"
    "m2b,07:00:00,07:00:00,L2-ALLENDE,1\n"
    "m2b,07:01:30,07:01:30,L2-BELLAS,2\n"
    "m2b,07:03:00,07:03:00,L2-HIDALGO,3\n"
    "m3a,23:59:00,23:59:00,L3-JUAREZ,1\n"
    "m3a,24:01:00,24:01:00,L3-HIDALGO,2\n"  # cruza la medianoche: hora > 24 válida en GTFS
    "mb1a,06:00:00,06:00:00,MB-HIDALGO,1\n"
    "r1a,06:00:00,06:00:00,RTP-X,1\n"
)


@pytest.fixture
def feed(tmp_path):
    ruta = tmp_path / "gtfs.zip"
    with zipfile.ZipFile(ruta, "w") as z:
        for nombre, contenido in {
            "agency": AGENCY,
            "routes": ROUTES,
            "trips": TRIPS,
            "stops": STOPS,
            "stop_times": STOP_TIMES,
        }.items():
            z.writestr(f"{nombre}.txt", contenido)
    return gtfs.filtrar_sistemas(gtfs.leer_feed(ruta))


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
    ruta = tmp_path / "gtfs.zip"
    with zipfile.ZipFile(ruta, "w") as z:
        for n, c in {
            "agency": AGENCY,
            "routes": ROUTES,
            "trips": TRIPS,
            "stops": stops,
            "stop_times": STOP_TIMES,
        }.items():
            z.writestr(f"{n}.txt", c)
    _, parada_a_clave = gtfs.agrupar_estaciones(gtfs.filtrar_sistemas(gtfs.leer_feed(ruta)))
    assert parada_a_clave["L2-HIDALGO"] != parada_a_clave["L3-HIDALGO"]
    assert parada_a_clave["L3-HIDALGO"] == "METRO-HIDALGO-2"


@pytest.mark.parametrize(
    ("valores", "esperado"),
    [(["1", "1"], 1), (["1", "2"], 2), (["1", ""], 0), (["0", "2"], 2), (["1", "0"], 0)],
)
def test_wheelchair_agregado_toma_el_valor_menos_favorable(valores, esperado):
    import pandas as pd

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
