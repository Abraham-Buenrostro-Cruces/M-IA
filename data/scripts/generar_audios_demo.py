"""Genera los audios SINTÉTICOS de demostración de la consulta por voz (F5, D-24).

Usa la voz es-MX de Windows (Microsoft Sabina, System.Speech) para decir cada frase de
``FRASES`` y escribe en ``data/demo/audios/``:

- un WAV por frase (PCM 16 bits, 48 kHz, mono: el formato que acepta el micrófono simulado
  de Chromium en las pruebas e2e);
- ``transcripciones.json``: archivo, sha256 y texto de cada audio. El transcriptor simulado
  (RA_MODO=local) reconoce los audios por su sha256 y devuelve ese texto.

Son voces sintéticas, no grabaciones de personas. Sólo funciona en Windows; los audios ya
generados están versionados, así que no hace falta volver a correrlo para usarlos.

Uso (desde la raíz del repositorio):
    backend/.venv/Scripts/python data/scripts/generar_audios_demo.py
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "demo" / "audios"
VOZ = "Microsoft Sabina Desktop"

# (archivo, frase, para qué sirve en la demostración)
FRASES = [
    ("flujo1.wav", "Quiero ir de Tasqueña al Museo de la Ciudad de México sin transbordos",
     "Flujo 1 dicho: ruta con alternativas y descartada"),
    ("cuautitlan-rosario.wav", "Llévame de Cuautitlán a El Rosario",
     "Red completa: Suburbano y Metrobús"),
    ("popotla-zapata.wav", "Quiero ir de Popotla a Zapata",
     "Sin ruta segura: otras opciones y ruta con asistencia"),
    ("zapata-viaducto.wav", "De Zapata a Viaducto",
     "Aclaración: Viaducto del Metro o del Metrobús (a 3.3 km)"),
    ("la-del-metrobus.wav", "La del Metrobús", "Respuesta a la aclaración anterior"),
    ("al-zocalo.wav", "Quiero ir al Zócalo", "Aclaración: falta el origen"),
    ("desde-mi-ubicacion.wav", "Desde mi ubicación", "Respuesta: usar la ubicación del teléfono"),
]  # fmt: skip

POWERSHELL = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice($env:RA_VOZ)
$s.Rate = -1
$af = 'System.Speech.AudioFormat'
$bits = [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen
$canal = [System.Speech.AudioFormat.AudioChannel]::Mono
$formato = New-Object "$af.SpeechAudioFormatInfo" 48000, $bits, $canal
$s.SetOutputToWaveFile($env:RA_ARCHIVO, $formato)
$s.Speak($env:RA_FRASE)
$s.Dispose()
"""


def main() -> None:
    if sys.platform != "win32":
        sys.exit("Este script usa la síntesis de voz de Windows (System.Speech).")
    SALIDA.mkdir(parents=True, exist_ok=True)
    catalogo = []
    for archivo, frase, uso in FRASES:
        destino = SALIDA / archivo
        # Las frases van por variables de entorno, no dentro del comando: así no hay que
        # escapar comillas ni acentos.
        entorno = {"RA_VOZ": VOZ, "RA_ARCHIVO": str(destino), "RA_FRASE": frase}
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", POWERSHELL],
            check=True, env={**__import__("os").environ, **entorno},
        )  # fmt: skip
        datos = destino.read_bytes()
        catalogo.append({
            "archivo": archivo, "sha256": hashlib.sha256(datos).hexdigest(), "texto": frase,
            "uso": uso, "bytes": len(datos),
        })  # fmt: skip
        print(f"  {archivo}: {len(datos) / 1024:.0f} KB · «{frase}»")
    (SALIDA / "transcripciones.json").write_text(
        json.dumps(
            {"nota": "AUDIOS SINTÉTICOS (voz de Windows es-MX), no son grabaciones de personas.",
             "voz": VOZ, "audios": catalogo},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
        newline="\n",  # LF también en Windows, como el resto de los datos versionados
    )  # fmt: skip
    print(f"{len(catalogo)} audios SINTÉTICOS -> {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
