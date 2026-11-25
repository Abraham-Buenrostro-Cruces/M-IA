"""Consulta por voz (F5-2, F5-3, D-24): intérprete local, resolución con aclaraciones,
transcriptor simulado y POST /voz/consulta."""

import base64
import hashlib
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.adaptadores.local.geocodificador import GeocodificadorLocal
from app.adaptadores.local.interprete import InterpreteReglas
from app.adaptadores.local.transcriptor import TranscriptorSimulado
from app.dominio.estaciones import EstacionResumen, Lugar
from app.dominio.voz import Intencion, Parcial, Restricciones, resolver, separar_sistema
from app.main import app
from app.modulos.estaciones.endpoints import obtener_geocodificador
from app.modulos.voz.endpoints import obtener_interprete, obtener_transcriptor


def _est(clave, nombre, sistema, lat, lon, lineas=("1",)):
    return EstacionResumen(clave, nombre, sistema, lat, lon, lineas, 1)


ESTACIONES = [
    _est("METRO-BUENAVISTA", "Buenavista", "METRO", 19.4466, -99.1530, ("B",)),
    _est("METROBUS-BUENAVISTA", "Buenavista", "METROBUS", 19.4470, -99.1525, ("1", "4")),
    _est("TREN_SUBURBANO-BUENAVISTA", "Buenavista", "TREN_SUBURBANO", 19.4497, -99.1528),
    _est("METRO-TASQUENA", "Tasqueña", "METRO", 19.3438, -99.1395, ("2",)),
    _est("METRO-ZAPATA", "Zapata", "METRO", 19.3707, -99.1650, ("3", "12")),
    _est("METRO-ZOCALO", "Zócalo", "METRO", 19.4326, -99.1332, ("2",)),
    # Homónimos lejanos (3.3 km en la red real): son lugares distintos.
    _est("METRO-VIADUCTO", "Viaducto", "METRO", 19.4007, -99.1366, ("2",)),
    _est("METROBUS-VIADUCTO", "Viaducto", "METROBUS", 19.3893, -99.1648, ("2",)),
]
LUGARES = [
    (Lugar("lugar", "Museo de la Ciudad de México", 19.42965, -99.1323, "Centro"),
     ["Museo de la Ciudad"]),
]  # fmt: skip
GEO = GeocodificadorLocal(ESTACIONES, LUGARES)
INTERPRETE = InterpreteReglas()


def entender(texto, previo=None):
    return resolver(INTERPRETE.interpretar(texto), GEO.buscar, previo)


# --------------------------------------------------------------------------- intérprete


@pytest.mark.parametrize(
    ("frase", "origen", "destino", "transbordos", "poco", "ubicacion"),
    [
        ("Quiero ir de Tasqueña al Museo de la Ciudad sin transbordos",
         "tasquena", "museo de la ciudad", 0, False, False),
        ("llévame al Zócalo desde aquí", None, "zocalo", None, False, True),
        ("al zócalo desde Taxqueña, por favor", "tasquena", "zocalo", None, False, False),
        ("de la estación Zapata a Buenavista con un transbordo y caminando poco",
         "zapata", "buenavista", 1, True, False),
        ("quiero llegar a Buenavista", None, "buenavista", None, False, False),
    ],
)  # fmt: skip
def test_interprete_reglas(frase, origen, destino, transbordos, poco, ubicacion):
    i = INTERPRETE.interpretar(frase)
    assert (i.origen_texto, i.destino_texto) == (origen, destino)
    assert i.restricciones == Restricciones(transbordos, poco)
    assert i.usar_ubicacion_origen is ubicacion


def test_un_lugar_suelto_y_una_frase_vacia():
    assert INTERPRETE.interpretar("Buenavista").lugar_suelto == "buenavista"
    assert INTERPRETE.interpretar("hola").entendida is False


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Buenavista del Metrobús", ("buenavista", "METROBUS")),
        ("la del metrobús", ("", "METROBUS")),
        ("La Raza del Metrobús", ("la raza", "METROBUS")),
        ("el del Suburbano", ("", "TREN_SUBURBANO")),
        ("Zócalo", ("zocalo", None)),
    ],
)
def test_separar_sistema(texto, esperado):
    assert separar_sistema(texto) == esperado


# --------------------------------------------------------------------------- resolución


def test_frase_completa_queda_lista():
    r = entender("de Tasqueña al Museo de la Ciudad sin transbordos")
    assert r.estado == "listo"
    assert r.parcial.origen.clave_estacion == "METRO-TASQUENA"
    assert r.parcial.destino.nombre == "Museo de la Ciudad de México"
    assert (
        r.mensaje
        == "Busco rutas de Tasqueña del Metro a Museo de la Ciudad de México, sin transbordos."
    )


def test_homonimos_del_mismo_nodo_no_se_preguntan():
    # Buenavista del Metro, del Metrobús y del Suburbano están a < 600 m y unidas a pie.
    r = entender("de Zapata a Buenavista")
    assert r.estado == "listo" and r.parcial.destino.nombre == "Buenavista"


def test_un_sistema_nombrado_elige_esa_estacion():
    r = entender("de Zapata a Buenavista del Suburbano")
    assert r.parcial.destino.clave_estacion == "TREN_SUBURBANO-BUENAVISTA"


def test_homonimos_lejanos_se_aclaran_y_la_respuesta_puede_ser_el_sistema():
    r = entender("de Zapata a Viaducto")
    assert r.estado == "aclaracion" and r.aclaracion.campo == "destino"
    assert {o.clave_estacion for o in r.aclaracion.opciones} == {
        "METRO-VIADUCTO", "METROBUS-VIADUCTO",
    }  # fmt: skip
    assert "Viaducto del Metrobús" in r.aclaracion.pregunta
    assert r.parcial.origen.clave_estacion == "METRO-ZAPATA"  # lo ya resuelto se conserva

    r2 = entender("la del Metrobús", r.parcial)
    assert r2.estado == "listo"
    assert r2.parcial.destino.clave_estacion == "METROBUS-VIADUCTO"
    assert r2.parcial.origen.clave_estacion == "METRO-ZAPATA"


def test_sin_origen_se_pregunta_y_acepta_la_ubicacion():
    r = entender("quiero ir al Zócalo sin transbordos")
    assert r.estado == "aclaracion" and r.aclaracion.campo == "origen"
    assert r.aclaracion.permite_ubicacion
    r2 = entender("desde mi ubicación", r.parcial)
    assert r2.estado == "listo" and r2.parcial.usar_ubicacion_origen
    assert r2.parcial.restricciones.max_transbordos == 0  # se conserva lo dicho antes
    assert r2.mensaje.startswith("Busco rutas de tu ubicación a Zócalo")


def test_un_lugar_que_contiene_todas_las_palabras_se_elige():
    r = entender("de Zapata al museo ciudad mexico")
    assert r.estado == "listo" and r.parcial.destino.nombre == "Museo de la Ciudad de México"


def test_lugar_desconocido_pide_otra_forma():
    r = entender("de Tasqueña a Narnia")
    assert r.estado == "aclaracion" and "No encontré «narnia»" in r.aclaracion.pregunta


def test_no_entendido():
    r = resolver(Intencion(entendida=False), GEO.buscar, Parcial())
    assert r.estado == "no_entendido" and "de Tasqueña al Zócalo" in r.mensaje


# --------------------------------------------------------------------------- transcriptor


def test_transcriptor_simulado_reconoce_audios_de_demo_y_si_no_usa_la_frase(tmp_path):
    audio = b"audio-sintetico"
    catalogo = tmp_path / "transcripciones.json"
    catalogo.write_text(json.dumps({"audios": [
        {"archivo": "a.wav", "sha256": hashlib.sha256(audio).hexdigest(), "texto": "de A a B"},
    ]}), encoding="utf-8")  # fmt: skip
    t = TranscriptorSimulado(catalogo, "frase de respaldo")
    assert t.transcribir(audio, "wav").texto == "de A a B"
    otro = t.transcribir(b"mi voz real", "webm")
    assert otro.texto == "frase de respaldo" and otro.simulada


# --------------------------------------------------------------------------- endpoint


class Espia:
    """Registra qué recibe cada puerto de IA, para la regla 6."""

    def __init__(self):
        self.recibido = []

    def transcribir(self, audio, formato):
        from app.dominio.voz import Transcripcion

        self.recibido.append(("audio", audio, formato))
        return Transcripcion("de Tasqueña a Zapata", 0.9, simulada=True)

    def interpretar(self, texto):
        self.recibido.append(("texto", texto))
        return INTERPRETE.interpretar(texto)


@pytest.fixture
def cliente():
    espia = Espia()
    app.dependency_overrides[obtener_geocodificador] = lambda: GEO
    app.dependency_overrides[obtener_transcriptor] = lambda: espia
    app.dependency_overrides[obtener_interprete] = lambda: espia
    yield TestClient(app), espia
    app.dependency_overrides.clear()


def test_consulta_por_texto_y_luego_aclaracion(cliente):
    c, _ = cliente
    r = c.post("/voz/consulta", json={"texto": "de Zapata a Viaducto"}).json()
    assert r["estado"] == "aclaracion" and len(r["aclaracion"]["opciones"]) == 2
    assert r["transcripcion"] == "de Zapata a Viaducto" and not r["transcripcion_simulada"]
    r2 = c.post("/voz/consulta", json={"texto": "la del metro", "contexto": r["contexto"]})
    r2 = r2.json()
    assert r2["estado"] == "listo"
    assert r2["contexto"]["destino"]["clave_estacion"] == "METRO-VIADUCTO"
    assert r2["contexto"]["origen"]["clave_estacion"] == "METRO-ZAPATA"


def test_consulta_por_audio(cliente):
    c, espia = cliente
    audio = base64.b64encode(b"\x1aE\xdf\xa3 audio webm").decode()
    r = c.post("/voz/consulta", json={"audio_b64": audio, "formato": "webm"}).json()
    assert r["estado"] == "listo" and r["transcripcion_simulada"]
    assert espia.recibido[0][0] == "audio" and espia.recibido[0][2] == "webm"


@pytest.mark.parametrize(
    ("cuerpo", "codigo"),
    [
        ({"texto": "de A a B", "audio_b64": "AAAA", "formato": "webm"}, 422),  # los dos
        ({}, 422),  # ninguno
        ({"audio_b64": "AAAA"}, 422),  # audio sin formato
        ({"audio_b64": "no es base64!", "formato": "webm"}, 422),
        ({"audio_b64": base64.b64encode(b"x" * 1_000_001).decode(), "formato": "webm"}, 413),
    ],
)
def test_entradas_invalidas(cliente, cuerpo, codigo):
    c, _ = cliente
    assert c.post("/voz/consulta", json=cuerpo).status_code == codigo


def test_regla_6_el_perfil_no_llega_a_los_puertos_ni_el_texto_a_los_logs(cliente, caplog):
    c, espia = cliente
    caplog.set_level(logging.DEBUG)
    frase = "de Tasqueña a Zapata sin transbordos"
    perfil = {"tipo_movilidad": "silla_manual", "distancia_pie_max_m": 321}
    # Aunque una PWA mal hecha mande el perfil, el contrato no lo acepta ni lo reenvía.
    r = c.post("/voz/consulta", json={"texto": frase, "perfil": perfil})
    assert r.status_code == 200
    assert espia.recibido == [("texto", frase)]
    registros = " ".join(rec.getMessage() for rec in caplog.records)
    assert "Tasqueña" not in registros and "silla_manual" not in registros
