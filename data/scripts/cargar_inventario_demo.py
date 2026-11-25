"""Carga en PostGIS el inventario de DEMOSTRACIÓN y los perfiles semilla (F1-4, F1-5).

Requisitos: haber corrido ``cargar_gtfs.py`` (las estaciones deben existir) y
``generar_inventario_demo.py`` (los CSV de data/demo/).

Uso (desde la raíz del repositorio):
    backend/.venv/Scripts/python data/scripts/cargar_inventario_demo.py
"""

from pathlib import Path

import pandas as pd

from app.bd.sesion import fabrica_sesiones
from app.ingesta.carga import cargar_inventario
from app.ingesta.perfiles import cargar_perfiles

DEMO = Path(__file__).resolve().parents[2] / "data" / "demo"


def main() -> None:
    leer = lambda nombre: pd.read_csv(DEMO / nombre, dtype={"route_id_gtfs": str})  # noqa: E731
    with fabrica_sesiones().begin() as sesion:
        conteos = cargar_inventario(
            sesion, leer("niveles.csv"), leer("equipos.csv"), leer("conexiones.csv")
        )
        perfiles = cargar_perfiles(sesion)
    print(f"Inventario de DEMOSTRACIÓN cargado: {conteos}")
    print(f"Perfiles predefinidos: {perfiles}")


if __name__ == "__main__":
    main()
