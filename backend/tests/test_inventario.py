"""Pruebas del generador de inventario de demostración (app/ingesta/inventario.py)."""

import pandas as pd
import pytest

from app.ingesta import gtfs
from app.ingesta import inventario as inv
from tests.feed_juguete import escribir_feed


@pytest.fixture
def red(tmp_path):
    """Líneas por estación del feed de juguete (Metro L2 y L3; Hidalgo es transbordo)."""
    feed = gtfs.filtrar_sistemas(gtfs.leer_feed(escribir_feed(tmp_path / "gtfs.zip")))
    estaciones, parada_a_clave = gtfs.agrupar_estaciones(feed)
    secuencias = gtfs.secuencias(feed, parada_a_clave)
    lineas = inv.lineas_por_estacion(secuencias, feed.routes, feed.stops, {"M2", "M3"})
    wheelchair = dict(zip(estaciones["clave"], estaciones["wheelchair_boarding_gtfs"], strict=True))
    return lineas, wheelchair


def _generar(red, *entradas):
    lineas, wheelchair = red
    return inv.generar_inventario(list(entradas), lineas, wheelchair).como_dataframes()


def test_lineas_por_estacion_detecta_transbordo_y_terminales(red):
    lineas, _ = red
    assert sorted(ln.linea for ln in lineas["METRO-HIDALGO"]) == ["2", "3"]
    assert all(ln.terminal for ln in lineas["METRO-HIDALGO"])  # fin de ambas líneas de juguete
    assert not lineas["METRO-BELLAS_ARTES"][0].terminal
    assert "METROBUS-HIDALGO" not in lineas  # la prueba sólo pide las rutas M2 y M3


def test_estacion_de_paso_lateral_sin_accesibilidad(red):
    niveles, equipos, conexiones = _generar(
        red, inv.EntradaCatalogo("METRO-BELLAS_ARTES", accesibilidad="NINGUNA")
    )
    assert sorted(niveles["tipo"]) == ["ANDEN", "CALLE", "CALLE", "VESTIBULO"]
    assert equipos.empty  # sin elevadores ni escaleras eléctricas
    assert (conexiones["tipo"] == "ESCALERA_FIJA").all()
    assert inv.estaciones_sin_barreras(niveles, conexiones) == {"METRO-BELLAS_ARTES": False}


def test_estacion_accesible_tiene_camino_sin_barreras(red):
    niveles, equipos, conexiones = _generar(
        red, inv.EntradaCatalogo("METRO-BELLAS_ARTES", accesibilidad="COMPLETA")
    )
    assert set(equipos["tipo"]) == {"ELEVADOR"}
    # Las escaleras fijas siguen en el grafo: son la barrera que filtra el perfil.
    assert (conexiones["tipo"] == "ESCALERA_FIJA").any()
    assert inv.estaciones_sin_barreras(niveles, conexiones) == {"METRO-BELLAS_ARTES": True}


def test_auto_sigue_al_gtfs_y_sin_dato_no_es_accesible(red):
    lineas, wheelchair = red
    # Juárez no tiene dato de wheelchair_boarding en el GTFS de juguete (0).
    assert wheelchair["METRO-JUAREZ"] == 0
    assert inv.resolver_accesibilidad(inv.EntradaCatalogo("METRO-JUAREZ"), 0) == "NINGUNA"
    assert inv.resolver_accesibilidad(inv.EntradaCatalogo("X"), 1) == "COMPLETA"
    assert inv.resolver_accesibilidad(inv.EntradaCatalogo("X"), 2) == "NINGUNA"


def test_andén_central_un_elevador_sirve_a_ambas_direcciones(red):
    niveles, equipos, conexiones = _generar(
        red,
        inv.EntradaCatalogo("METRO-BELLAS_ARTES", plantilla="CENTRAL", accesibilidad="COMPLETA"),
    )
    elevadores = equipos[equipos["codigo"] == "METRO-BELLAS_ARTES/ELV-L2"]
    assert len(elevadores) == 1
    usos = conexiones[conexiones["codigo_equipo"] == "METRO-BELLAS_ARTES/ELV-L2"]
    andenes = niveles[niveles["tipo"] == "ANDEN"]
    assert len(usos) == len(andenes)  # 1 equipo -> N conexiones (D-18)


def test_transbordo_une_vestibulos_y_lleva_escalera_electrica(red):
    niveles, equipos, conexiones = _generar(
        red, inv.EntradaCatalogo("METRO-HIDALGO", accesibilidad="COMPLETA")
    )
    pasillos = conexiones[conexiones["tipo"] == "PASILLO"]
    entre_vestibulos = pasillos[
        pasillos["nivel_desde"].str.contains("/VES-")
        & pasillos["nivel_hasta"].str.contains("/VES-")
    ]
    assert len(entre_vestibulos) == 1
    assert entre_vestibulos["longitud_m"].iloc[0] >= inv.LONGITUD_MIN_TRANSBORDO_M
    assert entre_vestibulos["escalones"].iloc[0] == 0
    esc = conexiones[conexiones["tipo"] == "ESCALERA_ELECTRICA"]
    assert not esc.empty and not esc["bidireccional"].any()  # sólo de subida
    assert inv.estaciones_sin_barreras(niveles, conexiones) == {"METRO-HIDALGO": True}


def test_acceso_por_rampa_en_salida_indicada(red):
    niveles, equipos, conexiones = _generar(
        red,
        inv.EntradaCatalogo(
            "METRO-BELLAS_ARTES",
            accesibilidad="COMPLETA",
            salidas=("oriente", "poniente"),
            accesos={"oriente": "RAMPA"},
        ),
    )
    rampa = conexiones[conexiones["tipo"] == "RAMPA"]
    assert rampa["nivel_desde"].tolist() == ["METRO-BELLAS_ARTES/SAL-ORIENTE"]
    assert rampa["pendiente_pct"].iloc[0] == inv.PENDIENTE_RAMPA_PCT
    # La salida poniente no tiene acceso accesible: sólo escalera.
    poniente = conexiones[conexiones["nivel_desde"] == "METRO-BELLAS_ARTES/SAL-PONIENTE"]
    assert poniente["tipo"].tolist() == ["ESCALERA_FIJA"]


def test_inventario_generado_es_valido_y_todo_es_demo(red):
    lineas, _ = red
    entradas = [inv.EntradaCatalogo(k) for k in sorted(lineas)]
    niveles, equipos, conexiones = _generar(red, *entradas)
    assert inv.validar_inventario(niveles, equipos, conexiones) == []
    assert set(niveles["fuente"]) == set(equipos["fuente"]) == set(conexiones["fuente"]) == {"DEMO"}


def test_validacion_detecta_anden_aislado(red):
    niveles, equipos, conexiones = _generar(
        red, inv.EntradaCatalogo("METRO-BELLAS_ARTES", accesibilidad="NINGUNA")
    )
    anden = niveles.loc[niveles["tipo"] == "ANDEN", "codigo"].iloc[0]
    sin_anden = conexiones[conexiones["nivel_hasta"] != anden]
    errores = inv.validar_inventario(niveles, equipos, sin_anden)
    assert any("inalcanzable desde la calle" in e for e in errores)


def test_validacion_detecta_equipo_inexistente(red):
    niveles, equipos, conexiones = _generar(
        red, inv.EntradaCatalogo("METRO-BELLAS_ARTES", accesibilidad="COMPLETA")
    )
    errores = inv.validar_inventario(niveles, equipos.iloc[0:0], conexiones)
    assert any("equipo inexistente" in e for e in errores)


@pytest.mark.parametrize(
    ("fila", "mensaje"),
    [
        ({"plantilla": "REDONDA"}, "plantilla desconocida"),
        ({"accesibilidad": "PARCIAL"}, "accesibilidad desconocida"),
        ({"accesos": "norte=ELEVADOR"}, "no está en las salidas"),
        ({"accesos": "A=TELEFERICO"}, "no válido"),
    ],
)
def test_catalogo_rechaza_entradas_invalidas(fila, mensaje):
    base = {"clave": "METRO-X", "plantilla": "", "accesibilidad": "", "salidas": "A;B",
            "accesos": "", "nota": ""}  # fmt: skip
    with pytest.raises(ValueError, match=mensaje):
        inv.leer_catalogo(pd.DataFrame([{**base, **fila}]))


def test_catalogo_lee_accesos():
    fila = {
        "clave": "METRO-COPILCO",
        "plantilla": "",
        "accesibilidad": "COMPLETA",
        "salidas": "oriente;poniente",
        "accesos": "oriente=RAMPA",
        "nota": "x",
    }
    df = pd.DataFrame([fila])
    (e,) = inv.leer_catalogo(df)
    assert e.salidas == ("oriente", "poniente")
    assert e.accesos == {"oriente": "RAMPA"}
    assert e.plantilla == "AUTO"
