"""Integración de la Fase 4 con PostGIS: reporte -> validación -> estimador -> estado.

Usa el feed de juguete, un inventario accesible en todas sus estaciones, el escenario
"todo operativo" como avisos DEMO, un bus síncrono y las fotos sintéticas de demostración.
"""

import io
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageChops, ImageStat
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.adaptadores.local.almacen import AlmacenLocal
from app.adaptadores.local.analizador import AnalizadorSimulado
from app.adaptadores.local.bus import BusEnProceso
from app.bd.modelos import EstadoEquipo, HistorialEstado, InfraestructuraAccesible, Usuario
from app.config import obtener_configuracion
from app.ingesta import gtfs
from app.ingesta import inventario as inv
from app.ingesta.carga import aplicar_escenario, cargar_inventario, cargar_red
from app.main import app
from app.modulos.reportes import endpoints as ep
from app.modulos.reportes import imagenes
from app.workers.contexto import Contexto
from app.workers.estado import recalcular_todos
from app.workers.registro import obtener_contexto, registrar
from tests.feed_juguete import escribir_feed

pytestmark = pytest.mark.bd

FOTOS = Path(__file__).resolve().parents[2] / "data" / "demo" / "fotos"
ALLENDE = {"lat": 19.43566, "lon": -99.13715, "precision_m": 15}
ELEVADOR = "METRO-ALLENDE/SAL-A/ELV"


def foto(nombre: str) -> bytes:
    return (FOTOS / nombre).read_bytes()


@pytest.fixture
def entorno(url_bd_pruebas, tmp_path):
    """Base de pruebas en una transacción que se revierte; app con contexto de prueba."""
    motor = create_engine(url_bd_pruebas)
    conexion = motor.connect()
    transaccion = conexion.begin()
    sesiones = sessionmaker(bind=conexion, join_transaction_mode="create_savepoint",
                            expire_on_commit=False)  # fmt: skip
    secreto = obtener_configuracion().jwt_secreto or "secreto-de-prueba-" * 3
    ctx = Contexto(
        sesiones=sesiones,
        almacen=AlmacenLocal(tmp_path, secreto),
        analizador=AnalizadorSimulado(FOTOS / "analisis.json"),
        bus=BusEnProceso(sincrono=True),
        reloj=lambda: datetime.now(UTC),
    )
    registrar(ctx)

    with sesiones.begin() as s:
        feed = gtfs.filtrar_sistemas(gtfs.leer_feed(escribir_feed(tmp_path / "gtfs.zip")))
        estaciones, p2c = gtfs.agrupar_estaciones(feed)
        secuencias = gtfs.secuencias(feed, p2c)
        cargar_red(s, feed.routes, estaciones, secuencias)
        lineas = inv.lineas_por_estacion(secuencias, feed.routes, feed.stops, {"M2", "M3"})
        catalogo = [inv.EntradaCatalogo(c, accesibilidad="COMPLETA") for c in sorted(lineas)]
        wb = dict(zip(estaciones.clave, estaciones.wheelchair_boarding_gtfs, strict=True))
        cargar_inventario(s, *inv.generar_inventario(catalogo, lineas, wb).como_dataframes())
        escenario = pd.DataFrame([{"codigo_equipo": "*", "estado": "OPERATIVO",
                                   "horas_desde_verificacion": "2"}])  # fmt: skip
        aplicar_escenario(s, escenario, ctx.reloj())
    recalcular_todos(ctx)

    original = obtener_configuracion().jwt_secreto
    obtener_configuracion().jwt_secreto = secreto
    app.dependency_overrides[obtener_contexto] = lambda: ctx
    try:
        yield TestClient(app), ctx
    finally:
        app.dependency_overrides.clear()
        obtener_configuracion().jwt_secreto = original
        transaccion.rollback()
        conexion.close()
        motor.dispose()


def nuevo_usuario(cliente, ctx, reputacion: float | None = None, rol: str | None = None) -> dict:
    datos = cliente.post("/usuarios/anonimo").json()
    if reputacion is not None or rol is not None:
        with ctx.sesiones.begin() as s:
            u = s.get(Usuario, __import__("uuid").UUID(datos["id_usuario"]))
            if reputacion is not None:
                u.reputacion = reputacion
            if rol is not None:
                u.rol = rol
        if rol is not None:
            from app.modulos.usuarios.identidad import emitir_token

            datos["token"] = emitir_token(__import__("uuid").UUID(datos["id_usuario"]), rol)
    return {"Authorization": f"Bearer {datos['token']}"}


def subir(cliente, cabeceras, contenido: bytes, tipo="image/jpeg") -> str:
    subida = cliente.post("/reportes/subidas", headers=cabeceras).json()
    url = subida["url_subida"].removeprefix("/api")
    r = cliente.put(url, content=contenido, headers={"Content-Type": tipo})
    assert r.status_code == 204, r.text
    return subida["id_subida"]


def reportar(cliente, cabeceras, archivo: str | None = "elevador-fuera-de-servicio.jpg",
             tipo="fuera_de_servicio", ubicacion=ALLENDE, contenido=None):  # fmt: skip
    cuerpo = {"clave_estacion": "METRO-ALLENDE", "codigo_equipo": ELEVADOR,
              "tipo_problema": tipo, "ubicacion": ubicacion}  # fmt: skip
    if archivo or contenido:
        cuerpo["id_subida"] = subir(cliente, cabeceras, contenido or foto(archivo))
    r = cliente.post("/reportes", json=cuerpo, headers=cabeceras)
    assert r.status_code == 202, r.text
    return cliente.get(f"/reportes/{r.json()['id_reporte']}", headers=cabeceras).json()


def estado_equipo(ctx) -> str:
    with ctx.sesiones() as s:
        return s.scalar(
            select(EstadoEquipo.estado)
            .join(InfraestructuraAccesible)
            .where(InfraestructuraAccesible.codigo == ELEVADOR)
        )


# ------------------------------------------------------------- flujo completo


def test_escenario_demo_deja_equipos_operativos_via_estimador(entorno):
    _, ctx = entorno
    assert estado_equipo(ctx) == "OPERATIVO"


def test_flujo_2_reporte_verificado_y_corroboracion_confirman_la_falla(entorno):
    cliente, ctx = entorno
    luis = nuevo_usuario(cliente, ctx, reputacion=0.9)
    rep = reportar(cliente, luis)
    assert rep["estado_validacion"] == "VERIFICADO_AUTO"
    assert rep["puntaje_confianza"] >= 0.75
    assert rep["estado_equipo"] == "FALLA_PROBABLE"  # un reporte basta para salir de OPERATIVO

    ana = nuevo_usuario(cliente, ctx)
    r = cliente.post(f"/equipos/{ELEVADOR}/corroboraciones", json={"voto": "CONFIRMA"},
                     headers=ana)  # fmt: skip
    assert r.status_code == 201
    assert estado_equipo(ctx) == "FALLA_CONFIRMADA"
    with ctx.sesiones() as s:
        causas = [
            h.causa
            for h in s.scalars(select(HistorialEstado).order_by(HistorialEstado.ocurrido_en))
        ]
    assert causas[-2:] == ["reporte", "voto"]

    # Un segundo voto de la misma persona no cuenta dos veces.
    r = cliente.post(f"/equipos/{ELEVADOR}/corroboraciones", json={"voto": "CONFIRMA"},
                     headers=ana)  # fmt: skip
    assert r.status_code == 409


def test_quien_reporta_no_puede_corroborarse(entorno):
    cliente, ctx = entorno
    luis = nuevo_usuario(cliente, ctx, reputacion=0.9)
    reportar(cliente, luis)
    r = cliente.post(f"/equipos/{ELEVADOR}/corroboraciones", json={"voto": "CONFIRMA"},
                     headers=luis)  # fmt: skip
    assert r.status_code == 404


def test_persona_nueva_queda_en_zona_gris(entorno):
    cliente, ctx = entorno
    rep = reportar(cliente, nuevo_usuario(cliente, ctx))
    assert rep["estado_validacion"] == "PENDIENTE_CORROBORACION"
    assert rep["estado_equipo"] == "FALLA_PROBABLE"  # s >= 0.40 ya cuenta como evidencia


def test_reporte_sin_foto_y_lejos_es_baja_confianza(entorno):
    cliente, ctx = entorno
    lejos = {"lat": 19.40, "lon": -99.10, "precision_m": 20}
    rep = reportar(cliente, nuevo_usuario(cliente, ctx), archivo=None, ubicacion=lejos)
    assert rep["estado_validacion"] == "BAJA_CONFIANZA"
    assert "sin foto" in rep["motivos"]
    assert rep["estado_equipo"] == "OPERATIVO"


def test_foto_duplicada_se_penaliza(entorno):
    cliente, ctx = entorno
    reportar(cliente, nuevo_usuario(cliente, ctx, reputacion=0.9))
    rep = reportar(cliente, nuevo_usuario(cliente, ctx, reputacion=0.9))
    assert "foto ya usada en otro reporte" in rep["motivos"]
    assert rep["estado_validacion"] == "BAJA_CONFIANZA"


def test_si_falla_el_analizador_el_reporte_va_a_moderacion(entorno, monkeypatch):
    cliente, ctx = entorno

    def fallar(*_):
        raise RuntimeError("Vision API no disponible")

    monkeypatch.setattr(ctx.analizador, "analizar", fallar)
    rep = reportar(cliente, nuevo_usuario(cliente, ctx, reputacion=1.0))
    assert rep["estado_validacion"] == "PENDIENTE_CORROBORACION"
    assert any("no disponible" in m for m in rep["motivos"])


# ------------------------------------------------------------- evidencias (F4-2, F4-5)


def test_version_saneada_sin_exif_y_con_rostros_difuminados(entorno):
    cliente, ctx = entorno
    luis = nuevo_usuario(cliente, ctx, reputacion=0.9)
    rep = reportar(cliente, luis)
    r = cliente.get(f"/evidencias/{rep['id_evidencia']}", headers=luis)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    saneada = Image.open(io.BytesIO(r.content))
    original = Image.open(FOTOS / "elevador-fuera-de-servicio.jpg")
    assert original.getexif().get_ifd(0x8825)  # la original trae GPS
    assert len(saneada.getexif()) == 0  # la saneada no trae ningún EXIF
    # Rostro de la izquierda (caja 60,360,90,115): sus píxeles cambian al difuminarse.
    assert diferencia_media(original, saneada, (75, 390, 135, 450)) > 10
    # Fuera de los rostros la imagen casi no cambia (sólo recompresión JPEG).
    assert diferencia_media(original, saneada, (400, 600, 460, 660)) < 3


def diferencia_media(a: Image.Image, b: Image.Image, caja) -> float:
    """Diferencia absoluta media por canal (0–255) entre dos recortes."""
    dif = ImageChops.difference(a.convert("RGB").crop(caja), b.convert("RGB").crop(caja))
    return sum(ImageStat.Stat(dif).mean) / 3


def test_evidencia_solo_para_su_autor_o_moderacion(entorno):
    cliente, ctx = entorno
    luis = nuevo_usuario(cliente, ctx, reputacion=0.9)
    rep = reportar(cliente, luis)
    otra = nuevo_usuario(cliente, ctx)
    mod = nuevo_usuario(cliente, ctx, rol="moderador")
    assert cliente.get(f"/evidencias/{rep['id_evidencia']}", headers=otra).status_code == 403
    assert cliente.get(f"/evidencias/{rep['id_evidencia']}", headers=mod).status_code == 200


def test_subida_rechaza_lo_que_no_es_imagen(entorno):
    cliente, ctx = entorno
    yo = nuevo_usuario(cliente, ctx)
    url = cliente.post("/reportes/subidas", headers=yo).json()["url_subida"].removeprefix("/api")
    assert (
        cliente.put(url, content=b"<script>", headers={"Content-Type": "image/jpeg"}).status_code
        == 422
    )
    assert cliente.put(url, content=foto("rampa-libre.jpg"),
                       headers={"Content-Type": "text/html"}).status_code == 415  # fmt: skip


def test_url_de_subida_es_de_un_solo_uso_y_firmada(entorno):
    cliente, ctx = entorno
    yo = nuevo_usuario(cliente, ctx)
    url = cliente.post("/reportes/subidas", headers=yo).json()["url_subida"].removeprefix("/api")
    jpeg = {"Content-Type": "image/jpeg"}
    assert cliente.put(url, content=foto("rampa-libre.jpg"), headers=jpeg).status_code == 204
    assert cliente.put(url, content=foto("rampa-libre.jpg"), headers=jpeg).status_code == 403
    alterada = url[:-3] + "abc"
    assert cliente.put(alterada, content=foto("rampa-libre.jpg"), headers=jpeg).status_code == 403


def test_imagen_demasiado_grande(monkeypatch):
    monkeypatch.setattr(imagenes, "TAMANO_MAXIMO_BYTES", 10)
    with pytest.raises(imagenes.ImagenInvalidaError, match="10 MB"):
        imagenes.abrir_imagen(foto("rampa-libre.jpg"))


# ------------------------------------------------------------- identidad y abuso


def test_sin_token_no_se_puede_reportar(entorno):
    cliente, _ = entorno
    assert cliente.post("/reportes/subidas").status_code == 401
    assert (
        cliente.post("/reportes/subidas", headers={"Authorization": "Bearer x"}).status_code == 401
    )


def test_limite_de_reportes_por_hora(entorno, monkeypatch):
    cliente, ctx = entorno
    monkeypatch.setattr(ep, "MAX_REPORTES_POR_HORA", 1)
    yo = nuevo_usuario(cliente, ctx)
    reportar(cliente, yo, archivo=None)
    cuerpo = {"clave_estacion": "METRO-ALLENDE", "tipo_problema": "bloqueado"}
    assert cliente.post("/reportes", json=cuerpo, headers=yo).status_code == 429


# ------------------------------------------------------------- moderación (F4-6)


def test_moderacion_requiere_rol(entorno):
    cliente, ctx = entorno
    assert (
        cliente.get("/moderacion/reportes", headers=nuevo_usuario(cliente, ctx)).status_code == 403
    )


def test_moderador_confirma_y_sube_la_reputacion(entorno):
    cliente, ctx = entorno
    autor = nuevo_usuario(cliente, ctx)
    rep = reportar(cliente, autor)
    mod = nuevo_usuario(cliente, ctx, rol="moderador")
    cola = cliente.get("/moderacion/reportes", headers=mod).json()
    assert [r["id_reporte"] for r in cola] == [rep["id_reporte"]]
    assert cola[0]["desglose"]["s"] == rep["puntaje_confianza"]
    r = cliente.post(f"/moderacion/reportes/{rep['id_reporte']}/decision",
                     json={"decision": "CONFIRMAR"}, headers=mod).json()  # fmt: skip
    assert r["estado_validacion"] == "CONFIRMADO_MODERADOR"
    assert cliente.get("/usuarios/yo", headers=autor).json()["reputacion"] == pytest.approx(2 / 3)
    assert cliente.get("/moderacion/reportes", headers=mod).json() == []


def test_rechazar_el_unico_reporte_regresa_a_operativo(entorno):
    """D-22: rechazar se resuelve reproduciendo la evidencia sin el reporte."""
    cliente, ctx = entorno
    rep = reportar(cliente, nuevo_usuario(cliente, ctx))
    assert rep["estado_equipo"] == "FALLA_PROBABLE"
    mod = nuevo_usuario(cliente, ctx, rol="moderador")
    cliente.post(f"/moderacion/reportes/{rep['id_reporte']}/decision",
                 json={"decision": "RECHAZAR"}, headers=mod)  # fmt: skip
    assert estado_equipo(ctx) == "OPERATIVO"


def test_aviso_de_moderador_fija_el_estado(entorno):
    cliente, ctx = entorno
    mod = nuevo_usuario(cliente, ctx, rol="moderador")
    r = cliente.post("/moderacion/avisos", headers=mod,
                     json={"codigo_equipo": ELEVADOR, "estado": "MANTENIMIENTO"})  # fmt: skip
    assert r.status_code == 201
    assert estado_equipo(ctx) == "MANTENIMIENTO"


def test_recalcular_estados_requiere_rol_y_responde(entorno):
    cliente, ctx = entorno
    assert (
        cliente.post(
            "/operacion/recalcular-estados", headers=nuevo_usuario(cliente, ctx)
        ).status_code
        == 403
    )
    mod = nuevo_usuario(cliente, ctx, rol="moderador")
    r = cliente.post("/operacion/recalcular-estados", headers=mod)
    assert r.status_code == 200 and r.json() == {"equipos_con_cambio": 0}
