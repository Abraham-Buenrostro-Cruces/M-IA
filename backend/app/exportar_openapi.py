"""Exporta el esquema OpenAPI de api-core para generar los tipos del frontend.

Uso: ``python -m app.exportar_openapi <ruta-de-salida.json>`` (lo invoca
``npm run api:tipos`` en frontend/).
"""

import json
import sys
from pathlib import Path

from app.main import app

if __name__ == "__main__":
    salida = Path(sys.argv[1])
    salida.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OpenAPI -> {salida}")
