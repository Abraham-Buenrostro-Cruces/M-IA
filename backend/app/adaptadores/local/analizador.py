"""AnalizadorImagen local SIMULADO y determinista (RA_MODO=local).

No intenta "adivinar" el contenido de una foto: reconoce las **fotos de demostración**
(data/demo/fotos/, imágenes sintéticas) por su hash perceptual y devuelve el análisis
predefinido para cada una, con el mismo formato que darán Vision API + Gemini. Cualquier
otra foto recibe "indeterminado" con confianza 0.5, lo que la manda a corroboración y
moderación: el modo local nunca verifica automáticamente una foto real.
"""

import io
import json
from pathlib import Path

import imagehash
from PIL import Image

from app.dominio.validacion import AnalisisImagen

DISTANCIA_MAXIMA = 6  # bits de diferencia de pHash para considerar "la misma foto"
DESCONOCIDA = AnalisisImagen("ninguno", "indeterminado", (), 0.5)


class AnalizadorSimulado:
    def __init__(self, catalogo: Path):
        datos = json.loads(catalogo.read_text(encoding="utf-8")) if catalogo.exists() else {}
        self._catalogo = [
            (imagehash.hex_to_hash(f["phash"]), AnalisisImagen(
                f["tipo_equipo_visible"], f["problema_visible"], tuple(f["senales_textuales"]),
                f["confianza"], f.get("contenido_apropiado", True),
                tuple(tuple(r) for r in f.get("rostros", [])),
            ))
            for f in datos.get("fotos", [])
        ]  # fmt: skip

    def analizar(self, contenido: bytes, tipo_problema: str) -> AnalisisImagen:
        h = imagehash.phash(Image.open(io.BytesIO(contenido)).convert("RGB"))
        mejor = min(self._catalogo, key=lambda c: c[0] - h, default=None)
        if mejor is not None and mejor[0] - h <= DISTANCIA_MAXIMA:
            return mejor[1]
        return DESCONOCIDA
