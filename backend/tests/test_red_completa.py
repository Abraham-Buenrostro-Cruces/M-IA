"""Pruebas de la red completa (F4B-1 a F4B-3, D-25): sistemas nuevos, ramales del
Metrobús, plantillas por sistema y transbordos a pie entre estaciones."""

import dataclasses

import pandas as pd
import pytest

from app.dominio.grafo import construir_topologia
from app.dominio.planificador import nombre_linea
from app.dominio.red import Conexion, Linea
from app.dominio.restricciones import exclusion
from app.ingesta import gtfs
from app.ingesta import inventario as inv
from tests.feed_juguete import ROUTES, STOP_TIMES, STOPS, TRIPS, escribir_feed
from tests.red_motor_juguete import construir_red, estados_ok, perfil

# --------------------------------------------------------------------------- ingesta GTFS


def _feed(tmp_path, **reemplazos):
    return gtfs.filtrar_sistemas(gtfs.leer_feed(escribir_feed(tmp_path / "g.zip", **reemplazos)))


def test_suburbano_e_insurgente_entran_y_la_l12_pierde_la_l(tmp_path):
    rutas = ROUTES + "S1,SUB,1,Buenavista - Cuautitlán,2\nM12,METRO,L12,Tláhuac - Mixcoac,1\n"
    trips = TRIPS + "S1,LV,s1a,Cuautitlán,0\nM12,LV,m12a,Mixcoac,0\n"
    stops = STOPS + "S-BV,Buenavista,19.4497,-99.1528,1\nL12-ZAP,Zapata,19.3707,-99.1650,1\n"
    tiempos = STOP_TIMES + "s1a,06:00:00,06:00:00,S-BV,1\nm12a,06:00:00,06:00:00,L12-ZAP,1\n"
    feed = _feed(tmp_path, routes=rutas, trips=trips, stops=stops, stop_times=tiempos)
    sistemas = dict(zip(feed.routes["route_id"], feed.routes["sistema"], strict=True))
    assert sistemas["S1"] == "TREN_SUBURBANO"
    assert "R1" not in sistemas  # RTP sigue fuera del alcance
    nombres = dict(zip(feed.routes["route_id"], feed.routes["route_short_name"], strict=True))
    assert nombres["M12"] == "12"


def test_ramal_con_paradas_propias_se_agrega_como_otra_direccion(tmp_path):
    # El Metrobús L1 tiene un recorrido largo (Hidalgo → Juárez) y un ramal que termina en
    # Bellas Artes. Un tercer viaje repite el recorrido largo: no debe duplicarse.
    trips = TRIPS + "MB1,LV,mb1b,El Caminero,0\nMB1,LV,mb1c,Bellas Artes,0\n"
    tiempos = STOP_TIMES + (
        "mb1b,06:00:00,06:00:00,MB-HIDALGO,1\nmb1b,06:05:00,06:05:00,L3-JUAREZ,2\n"
        "mb1c,06:00:00,06:00:00,MB-HIDALGO,1\nmb1c,06:04:00,06:04:00,L2-BELLAS,2\n"
    )
    feed = _feed(tmp_path, trips=trips, stop_times=tiempos)
    # Las paradas de Metro las usa sólo el Metrobús aquí: se reasignan a su sistema.
    feed = dataclasses.replace(
        feed, trips=feed.trips[feed.trips["route_id"] == "MB1"],
        stop_times=feed.stop_times[feed.stop_times["trip_id"].str.startswith("mb1")],
    )  # fmt: skip
    _, parada_a_clave = gtfs.agrupar_estaciones(feed)
    s = gtfs.secuencias(feed, parada_a_clave)
    assert sorted(s["direccion"].unique()) == ["Bellas Artes", "El Caminero"]
    assert len(s[s["direccion"] == "El Caminero"]) == 2  # el viaje de una sola parada sobra


def test_ramal_con_el_mismo_headsign_recibe_nombre_distinto(tmp_path):
    trips = TRIPS + "MB1,LV,mb1b,El Caminero,0\n"
    tiempos = STOP_TIMES + "mb1b,06:00:00,06:00:00,L3-JUAREZ,1\n"
    feed = _feed(tmp_path, trips=trips, stop_times=tiempos)
    feed = dataclasses.replace(
        feed, trips=feed.trips[feed.trips["route_id"] == "MB1"],
        stop_times=feed.stop_times[feed.stop_times["trip_id"].str.startswith("mb1")],
    )  # fmt: skip
    _, parada_a_clave = gtfs.agrupar_estaciones(feed)
    direcciones = set(gtfs.secuencias(feed, parada_a_clave)["direccion"])
    assert direcciones == {"El Caminero", "El Caminero (ramal 2)"}


# --------------------------------------------------------------------------- plantillas


def _linea(route_id="MB1", linea="1", terminal=False, direcciones=("Norte", "Sur")):
    return inv.LineaEnEstacion(route_id, linea, direcciones, 19.43, -99.14, terminal)


def _generar(clave, wheelchair, lineas=None):
    entrada = inv.EntradaCatalogo(clave)
    return inv.generar_inventario(
        [entrada], {clave: lineas or [_linea()]}, {clave: wheelchair}
    ).como_dataframes()


def test_metrobus_accesible_tiene_rampas_y_anden_a_nivel():
    niveles, equipos, conexiones = _generar("METROBUS-X", 1)
    assert set(equipos["tipo"]) == {"RAMPA"} and len(equipos) == 2  # una por salida
    assert "ESCALERA_FIJA" not in set(conexiones["tipo"])
    assert inv.estaciones_sin_barreras(niveles, conexiones) == {"METROBUS-X": True}


def test_metrobus_no_accesible_tiene_puente_con_escalones():
    niveles, equipos, conexiones = _generar("METROBUS-X", 2)
    assert equipos.empty
    escaleras = conexiones[conexiones["tipo"] == "ESCALERA_FIJA"]
    assert (escaleras["escalones"] == 30).all() and len(escaleras) == 2
    assert inv.estaciones_sin_barreras(niveles, conexiones) == {"METROBUS-X": False}


def test_suburbano_usa_la_plantilla_de_elevador_del_metro():
    _, equipos, conexiones = _generar("TREN_SUBURBANO-X", 1, [_linea("S1", terminal=True)])
    assert "ELEVADOR" in set(equipos["tipo"])
    assert "ESCALERA_ELECTRICA" in set(equipos["tipo"])  # terminal
    assert "ESCALERA_FIJA" in set(conexiones["tipo"])  # la barrera sigue en el grafo


def test_catalogo_red_usa_ajustes_y_rechaza_estaciones_ajenas():
    ajuste = inv.EntradaCatalogo("METRO-B", salidas=("Norte",))
    cat = inv.catalogo_red({"METRO-A", "METRO-B"}, [ajuste])
    assert [e.clave for e in cat] == ["METRO-A", "METRO-B"]
    assert cat[1] is ajuste and cat[0].salidas == ("A", "B")
    with pytest.raises(ValueError, match="no están en la red"):
        inv.catalogo_red({"METRO-A"}, [ajuste])


# --------------------------------------------------------------------------- transbordos a pie


def _calle(codigo, clave, lat, lon=-99.14):
    return {"codigo": codigo, "clave_estacion": clave, "tipo": "CALLE", "lat": lat, "lon": lon}


def test_transbordo_a_pie_une_estaciones_cercanas_sin_linea_comun():
    niveles = [
        _calle("METRO-H/SAL-A", "METRO-H", 19.4370),
        _calle("METROBUS-H/SAL-A", "METROBUS-H", 19.4380),  # ~111 m
        _calle("METROBUS-L/SAL-A", "METROBUS-L", 19.4500),  # ~1.4 km: demasiado lejos
        {**_calle("METRO-H/VES", "METRO-H", 19.4370), "tipo": "VESTIBULO"},  # sólo calles
    ]
    rutas = {"METRO-H": {"M2"}, "METROBUS-H": {"MB1"}, "METROBUS-L": {"MB1"}}
    (c,) = inv.transbordos_a_pie(niveles, rutas)
    assert (c["nivel_desde"], c["nivel_hasta"]) == ("METRO-H/SAL-A", "METROBUS-H/SAL-A")
    assert c["tipo"] == "PASILLO" and c["escalones"] == 0 and c["bidireccional"]
    assert c["longitud_m"] == pytest.approx(1.3 * 111.2, abs=1) and c["fuente"] == "DEMO"


def test_no_hay_transbordo_a_pie_entre_estaciones_de_la_misma_linea():
    niveles = [_calle("MB-A/SAL-A", "MB-A", 19.4370), _calle("MB-B/SAL-A", "MB-B", 19.4380)]
    assert inv.transbordos_a_pie(niveles, {"MB-A": {"MB1"}, "MB-B": {"MB1", "MB2"}}) == []


def test_inventario_con_transbordo_entre_sistemas_es_valido(tmp_path):
    feed = _feed(tmp_path)
    estaciones, parada_a_clave = gtfs.agrupar_estaciones(feed)
    secuencias = gtfs.secuencias(feed, parada_a_clave)
    lineas = inv.lineas_por_estacion(secuencias, feed.routes, feed.stops, set(feed.routes.route_id))
    wheelchair = dict(zip(estaciones["clave"], estaciones["wheelchair_boarding_gtfs"], strict=True))
    niveles, equipos, conexiones = inv.generar_inventario(
        inv.catalogo_red(lineas, []), lineas, wheelchair
    ).como_dataframes()
    assert inv.validar_inventario(niveles, equipos, conexiones) == []
    estacion = conexiones["nivel_desde"].str.split("/").str[0]
    otra = conexiones["nivel_hasta"].str.split("/").str[0]
    pares = set(zip(estacion[estacion != otra], otra[estacion != otra], strict=True))
    assert ("METRO-HIDALGO", "METROBUS-HIDALGO") in pares


# --------------------------------------------------------------------------- motor


def test_transbordo_por_la_calle_cuenta_como_caminata_del_perfil():
    red = construir_red()
    calle = Conexion("C/SAL-C1", "Z/SAL-Z1", "PASILLO", 700, 560.0)
    red = dataclasses.replace(red, conexiones=(*red.conexiones, calle))
    topologia = construir_topologia(red)
    datos = next(d for _, _, d in topologia.edges("C/SAL-C1", data=True) if d["conexion"] is calle)
    assert datos["entre_estaciones"] is True
    exc = exclusion(datos, perfil(distancia_pie_max_m=500), estados_ok())
    assert exc is not None and exc.clase == "fisica" and "caminata de 560 m" in exc.motivo
    assert exclusion(datos, perfil(distancia_pie_max_m=800), estados_ok()) is None
    # Un pasillo dentro de una estación no es caminata: no lo limita la distancia a pie.
    interno = next(d for _, _, d in topologia.edges("B/VES-2", data=True)
                   if d["conexion"].tipo == "PASILLO")  # fmt: skip
    assert interno["entre_estaciones"] is False


@pytest.mark.parametrize(
    ("sistema", "nombre", "sin", "con"),
    [
        ("METRO", "2", "Línea 2", "la Línea 2"),
        ("METROBUS", "1", "Metrobús Línea 1", "el Metrobús Línea 1"),
        ("TREN_LIGERO", "1", "Tren Ligero", "el Tren Ligero"),
        ("TREN_SUBURBANO", "1", "Tren Suburbano", "el Tren Suburbano"),
        ("TREN_INTERURBANO", "1", "Tren El Insurgente", "el Tren El Insurgente"),
    ],
)
def test_nombre_de_linea_distingue_el_sistema(sistema, nombre, sin, con):
    linea = Linea("R", sistema, nombre, 300)
    assert nombre_linea(linea) == sin
    assert nombre_linea(linea, articulo=True) == con


def test_catalogo_de_ajustes_del_repositorio_es_valido():
    """El archivo a mano de data/demo se lee sin errores (las claves se validan al generar)."""
    from pathlib import Path

    ruta = Path(__file__).resolve().parents[2] / "data" / "demo" / "ajustes_red.csv"
    entradas = inv.leer_catalogo(pd.read_csv(ruta, dtype=str))
    assert {"METRO-PINO_SUAREZ", "METRO-ZOCALO", "METRO-TASQUENA"} <= {e.clave for e in entradas}


# --------------------------------------------------------------------------- D-27


def _grafo_juguete(perf=None, destino=None):
    from app.dominio.grafo import grafo_para
    from tests.red_motor_juguete import AHORA, DESTINO_PUNTO, ORIGEN_PUNTO, caminatas

    red = construir_red()
    destino = destino or DESTINO_PUNTO
    return grafo_para(
        construir_topologia(red), perf or perfil(), estados_ok(), AHORA,
        caminatas(red, ORIGEN_PUNTO, destino),
    )  # fmt: skip


def test_penalizacion_la_primera_alternativa_es_el_camino_minimo():
    import networkx as nx

    from app.dominio.grafo import DESTINO, ORIGEN
    from app.dominio.planificador import alternativas, firma

    g = _grafo_juguete(perfil("adulto_mayor"))
    caminos = alternativas(g, None)
    minimo = nx.shortest_path(g, ORIGEN, DESTINO, weight="w")
    costo = lambda c: sum(g[u][v]["w"] for u, v in zip(c, c[1:], strict=False))  # noqa: E731
    assert costo(caminos[0]) == pytest.approx(costo(minimo))
    assert len({firma(g, c) for c in caminos}) == len(caminos)  # todas distintas


def test_penalizacion_respeta_exactamente_el_limite_de_transbordos():
    from app.dominio.planificador import alternativas
    from tests.red_motor_juguete import DESTINO_EN_Z

    g = _grafo_juguete(perfil("adulto_mayor"), DESTINO_EN_Z)
    for limite in (0, 1):
        for c in alternativas(g, limite):
            abordajes = sum(
                g[u][v]["arista"]["clase"] == "ABORDAR" for u, v in zip(c, c[1:], strict=False)
            )
            assert abordajes - 1 <= limite
