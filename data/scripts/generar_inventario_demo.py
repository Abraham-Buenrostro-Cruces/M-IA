"""Genera el inventario de DEMOSTRACIÓN de toda la red (F1-4, F4B-2, D-25).

Toma del GTFS más reciente todas las estaciones de Metro, Metrobús, Tren Ligero, Tren
Suburbano y Tren El Insurgente, les aplica la plantilla de su sistema y los ajustes a mano
de ``data/demo/ajustes_red.csv``, y escribe en ``data/demo/``:

- ``estaciones_red.csv``: el catálogo resuelto (una fila por estación), para revisarlo;
- ``niveles.csv``, ``equipos.csv`` y ``conexiones.csv``: el inventario que se carga.

Valida el resultado y falla si hay inconsistencias.

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


def main() -> None:
    carpeta = sorted(p for p in (RAIZ / "data" / "raw" / "gtfs").iterdir() if p.is_dir())[-1]
    feed = gtfs.filtrar_sistemas(gtfs.leer_feed(carpeta / "gtfs.zip"))
    estaciones, parada_a_clave = gtfs.agrupar_estaciones(feed)
    secuencias = gtfs.secuencias(feed, parada_a_clave)
    lineas = inv.lineas_por_estacion(
        secuencias, feed.routes, feed.stops, set(feed.routes["route_id"])
    )

    ajustes = inv.leer_catalogo(pd.read_csv(DEMO / "ajustes_red.csv", dtype=str))
    try:
        catalogo = inv.catalogo_red(lineas, ajustes)
    except ValueError as e:
        sys.exit(str(e))

    wheelchair = dict(zip(estaciones.clave, estaciones.wheelchair_boarding_gtfs, strict=True))
    niveles, equipos, conexiones = inv.generar_inventario(
        catalogo, lineas, wheelchair
    ).como_dataframes()

    errores = inv.validar_inventario(niveles, equipos, conexiones)
    if errores:
        sys.exit("Inventario inválido:\n  " + "\n  ".join(errores[:50]))

    sin_barreras = inv.estaciones_sin_barreras(niveles, conexiones)
    nombre = dict(zip(estaciones.clave, estaciones.nombre, strict=True))
    resumen = pd.DataFrame(
        [
            {
                "clave": e.clave,
                "nombre": nombre[e.clave],
                "sistema": inv.sistema_de(e.clave),
                "lineas": ";".join(sorted(ln.linea for ln in lineas[e.clave])),
                "wheelchair_gtfs": wheelchair.get(e.clave, 0),
                "accesibilidad": inv.resolver_accesibilidad(e, wheelchair.get(e.clave, 0)),
                "sin_barreras": sin_barreras[e.clave],
                "ajustada": e in ajustes,
            }
            for e in catalogo
        ]
    )

    resumen.to_csv(DEMO / "estaciones_red.csv", index=False, lineterminator="\n")
    niveles.to_csv(DEMO / "niveles.csv", index=False, lineterminator="\n")
    equipos.to_csv(DEMO / "equipos.csv", index=False, lineterminator="\n")
    conexiones.to_csv(DEMO / "conexiones.csv", index=False, lineterminator="\n")

    a_pie = (
        conexiones["nivel_desde"].str.split("/").str[0]
        != conexiones["nivel_hasta"].str.split("/").str[0]
    )
    print(f"GTFS {carpeta.name} · red completa (D-25)")
    for sistema, b in resumen.groupby("sistema"):
        print(f"  {sistema}: {len(b)} estaciones, {int(b['sin_barreras'].sum())} sin escalones")
    print(f"  niveles: {len(niveles)} · equipos: {len(equipos)} · conexiones: {len(conexiones)}")
    print(f"  transbordos a pie entre estaciones: {int(a_pie.sum())}")
    print(f"  equipos por tipo: {equipos['tipo'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
