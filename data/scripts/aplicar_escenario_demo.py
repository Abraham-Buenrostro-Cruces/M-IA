"""Aplica un escenario de estados de DEMOSTRACIÓN a los equipos (D-20).

Uso (desde la raíz del repositorio):
    backend/.venv/Scripts/python data/scripts/aplicar_escenario_demo.py [flujo1]

Los escenarios están en data/demo/escenarios/<nombre>.csv. Sin argumento se usa ``flujo1``.
El servicio de rutas relee los estados cada 60 s, así que no hace falta reiniciarlo.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from app.bd.sesion import fabrica_sesiones
from app.ingesta.carga import aplicar_escenario

ESCENARIOS = Path(__file__).resolve().parents[2] / "data" / "demo" / "escenarios"


def main() -> None:
    nombre = sys.argv[1] if len(sys.argv) > 1 else "flujo1"
    escenario = pd.read_csv(ESCENARIOS / f"{nombre}.csv", comment="#", dtype=str)
    with fabrica_sesiones().begin() as sesion:
        n = aplicar_escenario(sesion, escenario, datetime.now(UTC))
    print(f"Escenario de DEMOSTRACIÓN '{nombre}' aplicado a {n} equipos.")


if __name__ == "__main__":
    main()
