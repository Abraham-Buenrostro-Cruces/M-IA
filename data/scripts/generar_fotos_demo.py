"""Genera las FOTOS SINTÉTICAS de demostración y su análisis simulado (F4-3).

Son dibujos hechos con Pillow, no fotografías reales: sirven para mostrar el flujo de
reportes sin depender de Vision API ni de fotos con personas reales. El
AnalizadorSimulado las reconoce por su hash perceptual (data/demo/fotos/analisis.json).

Uso (desde la raíz del repositorio):
    backend/.venv/Scripts/python data/scripts/generar_fotos_demo.py
"""

import json
from fractions import Fraction
from pathlib import Path

import imagehash
from PIL import Image, ImageDraw, ImageFont

SALIDA = Path(__file__).resolve().parents[2] / "data" / "demo" / "fotos"
ANCHO, ALTO = 960, 720
PINO_SUAREZ = (19.42438, -99.13294)  # coordenadas para el GPS EXIF de una foto


def _fuente(tam: int):
    for nombre in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(nombre, tam)
        except OSError:
            continue
    return ImageFont.load_default(tam)


def _base(color_muro=(205, 200, 190)) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (ANCHO, ALTO), color_muro)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 560, ANCHO, ALTO], fill=(120, 115, 110))  # piso
    return img, d


def _elevador(d: ImageDraw.ImageDraw, abierto: bool):
    d.rectangle([300, 120, 660, 560], fill=(150, 155, 160), outline=(60, 60, 60), width=6)
    if abierto:
        d.rectangle([330, 150, 630, 560], fill=(235, 230, 200))  # cabina iluminada
        d.ellipse([680, 300, 720, 340], fill=(30, 160, 60))  # botón verde encendido
    else:
        d.line([480, 150, 480, 560], fill=(60, 60, 60), width=6)  # puertas cerradas
        d.ellipse([680, 300, 720, 340], fill=(70, 70, 70))


def _rostro(d: ImageDraw.ImageDraw, x: int, y: int) -> list[int]:
    d.ellipse([x, y, x + 90, y + 115], fill=(214, 170, 130), outline=(120, 80, 50), width=3)
    d.ellipse([x + 22, y + 40, x + 34, y + 52], fill=(30, 30, 30))
    d.ellipse([x + 56, y + 40, x + 68, y + 52], fill=(30, 30, 30))
    d.arc([x + 25, y + 65, x + 65, y + 95], 20, 160, fill=(120, 40, 40), width=4)
    return [x, y, 90, 115]


def elevador_fuera_de_servicio():
    img, d = _base()
    _elevador(d, abierto=False)
    for i in range(0, ANCHO, 80):  # cinta de restricción
        d.polygon([(i, 330), (i + 40, 330), (i + 80, 370), (i + 40, 370)], fill=(240, 200, 0))
    d.rectangle([330, 200, 630, 300], fill=(200, 20, 20))
    d.text((480, 250), "FUERA DE\nSERVICIO", fill="white", font=_fuente(40), anchor="mm",
           align="center")  # fmt: skip
    rostros = [_rostro(d, 60, 360), _rostro(d, 800, 380)]
    return img, {"tipo_equipo_visible": "elevador", "problema_visible": "fuera_de_servicio",
                 "senales_textuales": ["FUERA DE SERVICIO"], "confianza": 0.88,
                 "rostros": rostros}  # fmt: skip


def elevador_funcionando():
    img, d = _base((215, 215, 225))
    _elevador(d, abierto=True)
    return img, {"tipo_equipo_visible": "elevador", "problema_visible": "sin_problema",
                 "senales_textuales": [], "confianza": 0.85}  # fmt: skip


def _rampa(d: ImageDraw.ImageDraw):
    d.polygon([(100, 560), (860, 330), (860, 560)], fill=(170, 170, 175), outline=(70, 70, 70))
    d.line([(100, 470), (860, 240)], fill=(40, 40, 40), width=8)  # pasamanos


def rampa_bloqueada():
    img, d = _base((190, 205, 215))
    _rampa(d)
    for x in (420, 520, 470):  # cajas que bloquean el paso
        d.rectangle([x, 330, x + 110, 450], fill=(150, 100, 50), outline=(80, 50, 20), width=4)
    return img, {"tipo_equipo_visible": "rampa", "problema_visible": "bloqueado",
                 "senales_textuales": [], "confianza": 0.8}  # fmt: skip


def rampa_libre():
    img, d = _base((190, 205, 215))
    _rampa(d)
    return img, {"tipo_equipo_visible": "rampa", "problema_visible": "sin_problema",
                 "senales_textuales": [], "confianza": 0.9}  # fmt: skip


def _exif_gps(img: Image.Image, lat: float, lon: float) -> bytes:
    def dms(v: float):
        v = abs(v)
        g, m = int(v), int((v % 1) * 60)
        return (Fraction(g), Fraction(m), Fraction(round(((v * 60) % 1) * 60 * 100), 100))

    exif = img.getexif()
    exif[0x8825] = {1: "N" if lat >= 0 else "S", 2: dms(lat), 3: "E" if lon >= 0 else "W",
                    4: dms(lon)}  # fmt: skip
    return exif.tobytes()


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    fotos = []
    for nombre, fabrica, con_gps in [
        ("elevador-fuera-de-servicio.jpg", elevador_fuera_de_servicio, True),
        ("elevador-funcionando.jpg", elevador_funcionando, False),
        ("rampa-bloqueada.jpg", rampa_bloqueada, False),
        ("rampa-libre.jpg", rampa_libre, False),
    ]:
        img, analisis = fabrica()
        ruta = SALIDA / nombre
        extra = {"exif": _exif_gps(img, *PINO_SUAREZ)} if con_gps else {}
        img.save(ruta, "JPEG", quality=90, **extra)
        analisis["phash"] = str(imagehash.phash(Image.open(ruta).convert("RGB")))
        fotos.append({"archivo": nombre, **analisis})
        print(f"{nombre}: {analisis['problema_visible']} ({analisis['phash']})")
    hashes = [imagehash.hex_to_hash(f["phash"]) for f in fotos]
    minima = min(a - b for i, a in enumerate(hashes) for b in hashes[i + 1 :])
    (SALIDA / "analisis.json").write_text(
        json.dumps({"_nota": "FOTOS SINTÉTICAS DE DEMOSTRACIÓN y análisis simulado.",
                    "fotos": fotos}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )  # fmt: skip
    print(f"Distancia mínima de pHash entre fotos: {minima} bits (deben ser > 6)")


if __name__ == "__main__":
    main()
