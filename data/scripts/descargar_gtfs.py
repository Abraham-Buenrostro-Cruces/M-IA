"""Descarga el GTFS estático de la CDMX desde el Portal de Datos Abiertos (F1-1).

La URL del ZIP se resuelve con la API CKAN del portal en cada ejecución, porque
cambia con cada publicación. Junto al ZIP se guarda ``metadatos.json`` con la
fecha de publicación y el SHA-256: así cada carga en PostGIS es reproducible y
se puede decir en la presentación exactamente qué versión del GTFS se usó.

Uso (desde la raíz del repositorio):
    backend/.venv/Scripts/python data/scripts/descargar_gtfs.py
"""

import hashlib
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

API_CKAN = "https://datos.cdmx.gob.mx/api/3/action/package_show?id=gtfs"
DESTINO = Path(__file__).resolve().parents[1] / "raw" / "gtfs"
# Identificador genérico: no se envían datos del proyecto ni de la persona usuaria.
CABECERAS = {"User-Agent": "rutaaccesible-ingesta/0.1"}


def _leer(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=CABECERAS), timeout=120) as r:
        return r.read()


def resolver_recurso() -> dict:
    paquete = json.loads(_leer(API_CKAN))["result"]
    zips = [r for r in paquete["resources"] if (r.get("format") or "").upper() == "ZIP"]
    if not zips:
        sys.exit("El conjunto 'gtfs' del portal no tiene ningún recurso ZIP.")
    return max(zips, key=lambda r: r.get("last_modified") or r.get("created") or "")


def main() -> None:
    recurso = resolver_recurso()
    publicado = (recurso.get("last_modified") or recurso.get("created") or "")[:10]
    carpeta = DESTINO / publicado
    archivo = carpeta / "gtfs.zip"
    if archivo.exists():
        print(f"Ya existe {archivo}; no se descarga de nuevo.")
        return

    print(f"Descargando GTFS publicado el {publicado}…")
    contenido = _leer(recurso["url"])
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo.write_bytes(contenido)
    metadatos = {
        "url": recurso["url"],
        "publicado_en": recurso.get("last_modified") or recurso.get("created"),
        "descargado_en": datetime.now(UTC).isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(contenido).hexdigest(),
        "bytes": len(contenido),
    }
    (carpeta / "metadatos.json").write_text(json.dumps(metadatos, indent=2), encoding="utf-8")
    print(f"Guardado en {archivo} ({len(contenido) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
