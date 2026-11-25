"""TranscriptorVoz local (RA_MODO=local, F5-2): no reconoce voz de verdad.

Hasta la Fase 6 (Speech-to-Text v2 con Chirp 3) no hay reconocimiento real. Para que la
demostración funcione de punta a punta:

- Si el audio es uno de los audios SINTÉTICOS de ``data/demo/audios/`` (se reconoce por su
  huella sha256, igual que el analizador simulado reconoce las fotos de demostración), se
  devuelve su transcripción.
- Con cualquier otro audio (p. ej. la voz de la persona por el micrófono) se devuelve la
  frase de demostración ``RA_VOZ_FRASE_DEMO``, marcada como **simulada** para que la PWA
  lo diga ("Transcripción simulada en modo local").

El audio sólo se usa para calcular la huella: no se guarda ni se registra.
"""

import hashlib
import json
from pathlib import Path

from app.dominio.voz import Transcripcion


class TranscriptorSimulado:
    def __init__(self, catalogo: Path, frase_respaldo: str):
        self._conocidos: dict[str, str] = {}
        if catalogo.exists():
            datos = json.loads(catalogo.read_text(encoding="utf-8"))
            self._conocidos = {a["sha256"]: a["texto"] for a in datos.get("audios", [])}
        self._respaldo = frase_respaldo

    def transcribir(self, audio: bytes, formato: str) -> Transcripcion:
        texto = self._conocidos.get(hashlib.sha256(audio).hexdigest())
        if texto is not None:
            return Transcripcion(texto, confianza=0.95, simulada=True)
        return Transcripcion(self._respaldo, confianza=0.5, simulada=True)
