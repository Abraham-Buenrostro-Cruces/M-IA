"""Carga el GTFS más reciente de data/raw/gtfs/ en PostGIS y genera el reporte (F1-1, F1-3).

Requisitos: ``docker compose up -d`` y ``alembic upgrade head``.

Uso (desde la raíz del repositorio):
    backend/.venv/Scripts/python data/scripts/cargar_gtfs.py
"""

import json
from pathlib import Path

from app.bd.sesion import fabrica_sesiones
from app.ingesta import gtfs
from app.ingesta.carga import cargar_red
from app.modulos.rutas.consultas import estaciones_cercanas

RAIZ = Path(__file__).resolve().parents[2]
CARPETA_GTFS = RAIZ / "data" / "raw" / "gtfs"
CARPETA_REPORTES = RAIZ / "data" / "reportes"

# Puntos de verificación de la consulta de cercanía (criterio de aceptación de F1-3).
PUNTOS_PRUEBA = {
    "Palacio de Bellas Artes": (19.43520, -99.14120),
    "Zócalo (Plaza de la Constitución)": (19.43260, -99.13320),
    "Ciudad Universitaria, Facultad de Ciencias": (19.32420, -99.17940),
}

NOMBRES = {"METRO": "Metro", "METROBUS": "Metrobús", "TREN_LIGERO": "Tren Ligero"}


def main() -> None:
    carpeta = sorted(p for p in CARPETA_GTFS.iterdir() if (p / "gtfs.zip").exists())[-1]
    metadatos = json.loads((carpeta / "metadatos.json").read_text(encoding="utf-8"))
    print(f"GTFS publicado el {carpeta.name} (sha256 {metadatos['sha256'][:12]}…)")

    feed = gtfs.filtrar_sistemas(gtfs.leer_feed(carpeta / "gtfs.zip"))
    estaciones, parada_a_clave = gtfs.agrupar_estaciones(feed)
    secuencias = gtfs.secuencias(feed, parada_a_clave)

    with fabrica_sesiones().begin() as sesion:
        conteos = cargar_red(sesion, feed.routes, estaciones, secuencias)
        cercanas = {
            nombre: estaciones_cercanas(sesion, lat, lon)
            for nombre, (lat, lon) in PUNTOS_PRUEBA.items()
        }
    print(f"Cargado: {conteos}")

    resumen = gtfs.reporte(feed, estaciones)
    lineas = [
        f"# Reporte de carga del GTFS — publicado el {carpeta.name}",
        "",
        f"- Fuente: Portal de Datos Abiertos de la CDMX (`{metadatos['url']}`)",
        f"- SHA-256: `{metadatos['sha256']}`",
        f"- Descargado: {metadatos['descargado_en']}",
        "- Generado por `data/scripts/cargar_gtfs.py`.",
        "",
        "## Red cargada",
        "",
        "`wheelchair_boarding` es el indicador estático del GTFS (1 = accesible, 2 = no accesible,"
        " 0 = sin dato). Para estaciones con varias paradas se toma el valor menos favorable.",
        "",
        "| Sistema | Rutas | Paradas GTFS | Estaciones físicas | Accesibles | No accesibles"
        " | Sin dato |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s, r in resumen.items():
        lineas.append(
            f"| {NOMBRES[s]} | {r['rutas']} | {r['paradas_gtfs']} | {r['estaciones']} |"
            f" {r['accesibles_gtfs']} | {r['no_accesibles_gtfs']} | {r['sin_dato_gtfs']} |"
        )
    lineas += [
        "",
        f"Filas de `estacion_ruta`: {conteos['estacion_ruta']}.",
        "",
        "## Verificación: estaciones a menos de 600 m",
        "",
    ]
    for nombre, resultado in cercanas.items():
        lat, lon = PUNTOS_PRUEBA[nombre]
        lineas.append(f"**{nombre}** ({lat}, {lon})")
        lineas.append("")
        lineas += [
            f"- {e.nombre} ({NOMBRES[e.sistema]}) — {e.distancia_m:.0f} m" for e in resultado
        ]
        lineas.append("")

    CARPETA_REPORTES.mkdir(parents=True, exist_ok=True)
    salida = CARPETA_REPORTES / f"gtfs-{carpeta.name}.md"
    salida.write_text("\n".join(lineas), encoding="utf-8")
    print(f"Reporte: {salida}")


if __name__ == "__main__":
    main()
