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


def test_intervalos_medios_por_ruta(tmp_path):
    frecuencias = (
        "trip_id,start_time,end_time,headway_secs,exact_times\n"
        "m2a,06:00:00,12:00:00,120,0\n"
        "m2b,12:00:00,24:00:00,240,0\n"
        "r1a,06:00:00,24:00:00,600,0\n"  # RTP: se filtra
    )
    ruta = escribir_feed(tmp_path / "gtfs.zip", frequencies=frecuencias)
    feed = gtfs.filtrar_sistemas(gtfs.leer_feed(ruta))
    assert gtfs.intervalos_medios(feed) == {"M2": 180}


def test_feed_sin_frecuencias(feed):
    assert gtfs.intervalos_medios(feed) == {}


# ------------------------------------------------------------- trazos (mapa de la red)

TRIPS_CON_TRAZO = (
    "route_id,service_id,trip_id,trip_headsign,direction_id,shape_id\n"
    "M2,LV,m2a,Tasqueña,0,S-IDA\n"
    "M2,SAB,m2b,Tasqueña,0,S-VUELTA\n"
    "M3,LV,m3a,Universidad,0,S-CORTO\n"
    "MB1,LV,mb1a,El Caminero,0,S-RAMAL\n"
    "R1,LV,r1a,Destino,0,S-RTP\n"
)


def _trazo(sid: str, puntos: list[tuple[float, float]]) -> str:
    return "".join(f"{sid},{lat},{lon},{i}\n" for i, (lat, lon) in enumerate(puntos, start=1))


# Recta norte-sur sobre un meridiano, con un punto cada ~110 m (como el GTFS de la CDMX).
VIA = [(19.42 + i * 0.001, -99.14) for i in range(20)]


def test_trazos_descarta_la_direccion_contraria_y_conserva_ramales(tmp_path):
    vuelta = [(lat, lon + 0.0002) for lat, lon in reversed(VIA)]  # ~20 m al lado
    corto = VIA[5:12]  # servicio parcial contenido en la vía
    ramal = [(19.42 + i * 0.001, -99.14 + i * 0.001) for i in range(20)]  # se aleja km
    shapes = "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n" + "".join(
        [_trazo("S-IDA", VIA), _trazo("S-VUELTA", vuelta), _trazo("S-CORTO", corto),
         _trazo("S-RAMAL", ramal), _trazo("S-RTP", VIA)]
    )  # fmt: skip
    ruta = escribir_feed(tmp_path / "gtfs.zip", trips=TRIPS_CON_TRAZO, shapes=shapes)
    feed = gtfs.filtrar_sistemas(gtfs.leer_feed(ruta))
    assert "S-RTP" not in set(feed.shapes["shape_id"])  # RTP filtrado
    trazos = gtfs.trazos_por_ruta(feed)
    assert len(trazos["M2"]) == 1 and len(trazos["M2"][0]) == 20  # ida y vuelta = una vía
    assert len(trazos["M3"]) == 1  # único trazo, aunque sea corto
    assert len(trazos["MB1"]) == 1


def test_trazos_sin_shapes():
    assert gtfs.trazos_por_ruta(gtfs.FeedGTFS(*[pd.DataFrame()] * 5)) == {}


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("F94F8E", "#F94F8E"), ("#0071c1", "#0071C1"), ("", None), (None, None), ("�", None),
     ("12345", None)],
)  # fmt: skip
def test_color_valido(valor, esperado):
    assert gtfs.color_valido(valor) == esperado
