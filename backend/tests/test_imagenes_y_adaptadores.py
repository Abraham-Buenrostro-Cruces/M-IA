"""Pruebas sin base de datos: imágenes (F4-2, F4-5), analizador simulado y bus local."""

import io
import json
from pathlib import Path

import pytest
from PIL import Image

from app.adaptadores.local.almacen import AlmacenLocal, TokenSubidaInvalidoError
from app.adaptadores.local.analizador import DESCONOCIDA, AnalizadorSimulado
from app.adaptadores.local.bus import BusEnProceso
from app.modulos.reportes import imagenes

FOTOS = Path(__file__).resolve().parents[2] / "data" / "demo" / "fotos"
SECRETO = "s" * 40  # HS256 exige llaves de al menos 32 bytes
CATALOGO = json.loads((FOTOS / "analisis.json").read_text(encoding="utf-8"))["fotos"]


def leer(nombre: str) -> bytes:
    return (FOTOS / nombre).read_bytes()


def png(ancho=50, alto=40, color=(10, 120, 200)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (ancho, alto), color).save(b, "PNG")
    return b.getvalue()


# --------------------------------------------------------------------------- imágenes


def test_abrir_imagen_acepta_jpeg_y_png():
    assert imagenes.abrir_imagen(leer("rampa-libre.jpg")).format == "JPEG"
    assert imagenes.abrir_imagen(png()).format == "PNG"


@pytest.mark.parametrize("contenido", [b"", b"no soy una imagen", b"\xff\xd8\xff\xe0truncado"])
def test_abrir_imagen_rechaza_contenido_invalido(contenido):
    with pytest.raises(imagenes.ImagenInvalidaError):
        imagenes.abrir_imagen(contenido)


def test_abrir_imagen_rechaza_formatos_no_permitidos():
    b = io.BytesIO()
    Image.new("RGB", (10, 10)).save(b, "GIF")
    with pytest.raises(imagenes.ImagenInvalidaError, match="Formato"):
        imagenes.abrir_imagen(b.getvalue())


def test_exif_gps_de_la_foto_de_demostracion():
    exif = imagenes.metadatos_exif(imagenes.abrir_imagen(leer("elevador-fuera-de-servicio.jpg")))
    assert exif.lat == pytest.approx(19.42438, abs=1e-4)
    assert exif.lon == pytest.approx(-99.13294, abs=1e-4)


def test_huellas_y_distancia_phash():
    a, b = leer("rampa-libre.jpg"), leer("rampa-bloqueada.jpg")
    sha_a, ph_a = imagenes.huellas(a, imagenes.abrir_imagen(a))
    sha_b, ph_b = imagenes.huellas(b, imagenes.abrir_imagen(b))
    assert sha_a != sha_b and len(sha_a) == 64
    assert imagenes.distancia_phash(ph_a, ph_a) == 0
    assert imagenes.distancia_phash(ph_a, ph_b) > 6


def test_phash_reconoce_la_misma_foto_recomprimida():
    original = imagenes.abrir_imagen(leer("rampa-bloqueada.jpg"))
    recomprimida = io.BytesIO()
    original.convert("RGB").resize((480, 360)).save(recomprimida, "JPEG", quality=40)
    _, ph_o = imagenes.huellas(b"", original)
    _, ph_r = imagenes.huellas(b"", Image.open(recomprimida))
    assert imagenes.distancia_phash(ph_o, ph_r) <= 6  # foto "reciclada" detectable


def test_sanear_quita_exif_y_reduce_tamano():
    grande = Image.new("RGB", (4000, 3000), (200, 200, 200))
    saneada = Image.open(io.BytesIO(imagenes.sanear(grande)))
    assert max(saneada.size) == imagenes.LADO_MAXIMO_PX
    con_gps = imagenes.abrir_imagen(leer("elevador-fuera-de-servicio.jpg"))
    assert len(Image.open(io.BytesIO(imagenes.sanear(con_gps))).getexif()) == 0


def test_sanear_ignora_cajas_fuera_de_la_imagen():
    img = Image.new("RGB", (100, 100))
    imagenes.sanear(img, ((90, 90, 50, 50), (-20, -20, 10, 10), (200, 200, 10, 10)))


# --------------------------------------------------------------------------- analizador simulado


@pytest.mark.parametrize("foto", CATALOGO, ids=lambda f: f["archivo"])
def test_analizador_reconoce_las_fotos_de_demostracion(foto):
    r = AnalizadorSimulado(FOTOS / "analisis.json").analizar(leer(foto["archivo"]), "x")
    assert r.problema_visible == foto["problema_visible"]
    assert r.confianza == foto["confianza"]


def test_analizador_no_verifica_fotos_desconocidas():
    """Una foto real cualquiera nunca se verifica sola en modo local."""
    assert AnalizadorSimulado(FOTOS / "analisis.json").analizar(png(), "x") == DESCONOCIDA


def test_analizador_devuelve_las_cajas_de_rostros():
    r = AnalizadorSimulado(FOTOS / "analisis.json").analizar(
        leer("elevador-fuera-de-servicio.jpg"), "fuera_de_servicio"
    )
    assert len(r.rostros) == 2


# --------------------------------------------------------------------------- almacén y bus


def test_almacen_local_url_firmada_de_un_solo_uso(tmp_path):
    a = AlmacenLocal(tmp_path, SECRETO)
    token = a.url_subida("obj-1", 60).rsplit("/", 1)[1]
    assert a.objeto_de_token(token) == "obj-1"
    a.guardar_original("obj-1", b"x")
    with pytest.raises(TokenSubidaInvalidoError):
        a.guardar_original("obj-1", b"y")
    with pytest.raises(TokenSubidaInvalidoError):
        AlmacenLocal(tmp_path, "o" * 40).objeto_de_token(token)


def test_almacen_local_token_vencido(tmp_path):
    a = AlmacenLocal(tmp_path, SECRETO)
    token = a.url_subida("obj-2", -1).rsplit("/", 1)[1]
    with pytest.raises(TokenSubidaInvalidoError, match="venció"):
        a.objeto_de_token(token)


def test_almacen_local_rechaza_rutas_ajenas(tmp_path):
    with pytest.raises(ValueError):
        AlmacenLocal(tmp_path, SECRETO).leer_original("../../.env")


@pytest.mark.parametrize("sincrono", [True, False])
def test_bus_entrega_en_orden_y_aisla_errores(sincrono):
    bus = BusEnProceso(sincrono=sincrono)
    recibidos = []
    bus.suscribir("t", lambda d: (_ for _ in ()).throw(RuntimeError("falla")))  # no detiene
    bus.suscribir("t", lambda d: recibidos.append(d["id"]))
    for i in range(5):
        bus.publicar("t", {"id": i})
    bus.esperar()
    assert recibidos == [0, 1, 2, 3, 4]
