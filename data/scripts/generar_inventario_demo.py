"""Genera el inventario de DEMOSTRACIÓN del corredor piloto (F1-4).

Lee el catálogo editable ``data/demo/estaciones_corredor.csv`` y el GTFS más
reciente, y escribe ``niveles.csv``, ``equipos.csv`` y ``conexiones.csv`` en
``data/demo/``. Valida el resultado y falla si hay inconsistencias.

Para ampliar el corredor (Fase 9) basta agregar líneas a ``LINEAS_CORREDOR`` y sus
estaciones al catálogo; las estaciones de transbordo se regeneran con todas sus líneas.

Uso (desde la raíz del repositorio):
    backend/.venv/Scripts/python data/scripts/generar_inventario_demo.py
"""

import sys
from pathlib import Path

import pandas as pd

from app.ingesta import gtfs
from app.ingesta import inventario as inv

RAIZ = Path(__file__).resolve().parents[2]
DEMO = RAIZ / "data" / "demo"

# Corredor piloto (D-17): Metro Líneas 2 y 3. Se identifican por agencia y nombre corto.
LINEAS_CORREDOR = {("METRO", "2"), ("METRO", "3")}


def main() -> None:
    carpeta = sorted(p for p in (RAIZ / "data" / "raw" / "gtfs").iterdir() if p.is_dir())[-1]
    feed = gtfs.filtrar_sistemas(gtfs.leer_feed(carpeta / "gtfs.zip"))
    estaciones, parada_a_clave = gtfs.agrupar_estaciones(feed)
    secuencias = gtfs.secuencias(feed, parada_a_clave)

    rutas = feed.routes
    route_ids = set(
        rutas.loc[
            [
                (a, n) in LINEAS_CORREDOR
                for a, n in zip(rutas.agency_id, rutas.route_short_name, strict=True)
            ],
            "route_id",
        ]
    )
    lineas = inv.lineas_por_estacion(secuencias, rutas, feed.stops, route_ids)

    catalogo = inv.leer_catalogo(pd.read_csv(DEMO / "estaciones_corredor.csv", dtype=str))
    faltantes = set(lineas) - {e.clave for e in catalogo}
    if faltantes:
        sys.exit(f"Estaciones del corredor sin fila en el catálogo: {sorted(faltantes)}")

    wheelchair = dict(zip(estaciones.clave, estaciones.wheelchair_boarding_gtfs, strict=True))
    niveles, equipos, conexiones = inv.generar_inventario(
        catalogo, lineas, wheelchair
    ).como_dataframes()

    errores = inv.validar_inventario(niveles, equipos, conexiones)
    if errores:
        sys.exit("Inventario inválido:\n  " + "\n  ".join(errores))

    niveles.to_csv(DEMO / "niveles.csv", index=False, lineterminator="\n")
    equipos.to_csv(DEMO / "equipos.csv", index=False, lineterminator="\n")
    conexiones.to_csv(DEMO / "conexiones.csv", index=False, lineterminator="\n")

    sin_barreras = inv.estaciones_sin_barreras(niveles, conexiones)
    print(f"GTFS {carpeta.name} · corredor {sorted(n for _, n in LINEAS_CORREDOR)}")
    print(f"  estaciones: {len(catalogo)} ({sum(sin_barreras.values())} accesibles sin escalones)")
    print(f"  niveles: {len(niveles)} · equipos: {len(equipos)} · conexiones: {len(conexiones)}")
    print(f"  equipos por tipo: {equipos['tipo'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
