"""Procesamiento de fotos de evidencia con Pillow (F4-2, F4-3, F4-5).

- ``abrir_imagen``: valida que el contenido sea realmente una imagen de un tipo permitido
  (no se confía en la extensión ni en el Content-Type que manda el cliente).
- ``metadatos_exif``: fecha de captura y GPS, para las validaciones temporal y geográfica.
- ``huellas``: SHA-256 (duplicado exacto) y hash perceptual (foto reciclada o recortada).
- ``sanear``: **vuelve a codificar** la imagen (descarta cargas ocultas), **elimina el EXIF**
  (que puede contener la ubicación de la casa de quien toma la foto) y **difumina rostros**.
  Sólo la versión saneada se muestra a otras personas (documento 07).
"""

import hashlib
import io
from dataclasses import dataclass
from datetime import datetime

import imagehash
from PIL import ExifTags, Image, ImageFilter, UnidentifiedImageError

TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024  # 10 MB (06-flujos, flujo 2)
FORMATOS_PERMITIDOS = {"JPEG", "PNG", "WEBP"}
LADO_MAXIMO_PX = 1600  # la versión saneada se reduce: basta para verificar y pesa menos
MAX_PIXELES = 40_000_000  # defensa contra "bombas" de descompresión

Image.MAX_IMAGE_PIXELS = MAX_PIXELES


class ImagenInvalidaError(ValueError):
    pass


@dataclass(frozen=True)
class Exif:
    capturada_en: datetime | None
    lat: float | None
    lon: float | None


def abrir_imagen(contenido: bytes) -> Image.Image:
    if len(contenido) > TAMANO_MAXIMO_BYTES:
        raise ImagenInvalidaError("La foto supera 10 MB.")
    try:
        img = Image.open(io.BytesIO(contenido))
        img.verify()  # detecta archivos truncados o manipulados
        img = Image.open(io.BytesIO(contenido))  # verify() deja la imagen inutilizable
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise ImagenInvalidaError("El archivo no es una imagen válida.") from e
    if img.format not in FORMATOS_PERMITIDOS:
        raise ImagenInvalidaError("Formato no permitido: usa JPEG, PNG o WEBP.")
    return img


def _grados(valor, referencia: str) -> float:
    g, m, s = (float(x) for x in valor)
    decimal = g + m / 60 + s / 3600
    return -decimal if referencia in ("S", "W") else decimal


def metadatos_exif(img: Image.Image) -> Exif:
    exif = img.getexif()
    fecha = None
    texto = exif.get_ifd(ExifTags.IFD.Exif).get(ExifTags.Base.DateTimeOriginal) or exif.get(
        ExifTags.Base.DateTime
    )
    if texto:
        try:
            fecha = datetime.strptime(str(texto), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            fecha = None
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    lat = lon = None
    try:
        if gps.get(2) and gps.get(4):
            lat = _grados(gps[2], gps.get(1, "N"))
            lon = _grados(gps[4], gps.get(3, "E"))
    except (TypeError, ValueError, ZeroDivisionError):
        lat = lon = None
    return Exif(fecha, lat, lon)


def huellas(contenido: bytes, img: Image.Image) -> tuple[str, str]:
    return hashlib.sha256(contenido).hexdigest(), str(imagehash.phash(img.convert("RGB")))


def distancia_phash(a: str, b: str) -> int:
    """Distancia de Hamming entre dos hashes perceptuales (0 = idénticos, 64 = opuestos)."""
    return imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b)


def sanear(img: Image.Image, rostros: tuple[tuple[int, int, int, int], ...] = ()) -> bytes:
    """JPEG nuevo, sin EXIF, con los rostros difuminados y el lado mayor ≤ 1600 px."""
    limpia = img.convert("RGB")  # descarta perfil, canal alfa y metadatos
    for x, y, ancho, alto in rostros:
        caja = (max(x, 0), max(y, 0), min(x + ancho, limpia.width), min(y + alto, limpia.height))
        if caja[2] > caja[0] and caja[3] > caja[1]:
            radio = max(8, (caja[2] - caja[0]) // 4)
            limpia.paste(limpia.crop(caja).filter(ImageFilter.GaussianBlur(radio)), caja)
    limpia.thumbnail((LADO_MAXIMO_PX, LADO_MAXIMO_PX))
    salida = io.BytesIO()
    limpia.save(salida, "JPEG", quality=85)  # sin exif=: Pillow no copia metadatos
    return salida.getvalue()
