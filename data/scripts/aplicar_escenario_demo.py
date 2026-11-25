"""Aplica un escenario de DEMOSTRACIÓN: avisos DEMO + recálculo con el estimador (D-21).

Uso (desde la raíz del repositorio):
    backend/.venv/Scripts/python data/scripts/aplicar_escenario_demo.py [flujo1] [--reiniciar]

Base: el escenario SINTÉTICO de toda la red, ``data/synthetic/escenario_red.csv`` (F4B-4).
Encima se aplica el escenario elegido, ``data/demo/escenarios/<nombre>.csv``: sus filas
explícitas reemplazan a las de la base. ``--sin-red`` omite la base (sólo el escenario).

``--reiniciar`` borra además los reportes, votos e historial de la comunidad, para que la
demo (o las pruebas e2e) partan siempre del mismo estado. El servicio de rutas relee los
estados cada 60 s.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from app.adaptadores.local.bus import BusEnProceso
from app.bd.sesion import fabrica_sesiones
from app.ingesta.carga import aplicar_escenario, reiniciar_comunidad
from app.workers.contexto import Contexto
from app.workers.estado import recalcular_todos

RAIZ = Path(__file__).resolve().parents[2]
ESCENARIOS = RAIZ / "data" / "demo" / "escenarios"
BASE_RED = RAIZ / "data" / "synthetic" / "escenario_red.csv"


def main() -> None:
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    nombre = argumentos[0] if argumentos else "flujo1"
    escenario = pd.read_csv(ESCENARIOS / f"{nombre}.csv", comment="#", dtype=str)
    if "--sin-red" not in sys.argv and BASE_RED.exists():
        base = pd.read_csv(BASE_RED, comment="#", dtype=str)
        escenario = pd.concat([base, escenario]).drop_duplicates("codigo_equipo", keep="last")
    ahora = datetime.now(UTC)
    sesiones = fabrica_sesiones()
    with sesiones.begin() as sesion:
        if "--reiniciar" in sys.argv:
            reiniciar_comunidad(sesion)
        n = aplicar_escenario(sesion, escenario, ahora)
    # Sólo el estimador escribe estados. Bus síncrono y sin suscriptores: aquí no hace
    # falta avisar a nadie (el servicio de rutas relee los estados por su cuenta).
    ctx = Contexto(sesiones, None, None, BusEnProceso(sincrono=True), lambda: ahora)
    cambios = recalcular_todos(ctx)
    print(
        f"Escenario de DEMOSTRACIÓN '{nombre}' sobre la red SINTÉTICA: evidencia para {n} "
        f"equipos; {cambios} cambiaron de estado."
    )


if __name__ == "__main__":
    main()
