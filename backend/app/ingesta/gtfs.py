"""Lectura y normalización del GTFS estático de la CDMX (F1-1, F1-3).

Funciones puras sobre DataFrames: no tocan la base de datos, así que se prueban
con un feed de juguete (tests/test_ingesta_gtfs.py).

Particularidades del feed de la CDMX que este módulo resuelve:
- No usa ``parent_station``: una estación de transbordo (p. ej. Hidalgo) aparece
  como una parada distinta por línea (``B_0200L2-HIDALGO``, ``B_0200L3-HIDALGO``).
  Se agrupan por sistema + nombre normalizado + cercanía (ver ``agrupar_estaciones``).
- Trae muchos sistemas (RTP, trolebús, corredores concesionados…); el MVP usa
  Metro, Metrobús y Tren Ligero (``catalogos.AGENCIA_A_SISTEMA``).
- Hay viajes repetidos por ``service_id`` con la misma secuencia; para la
  topología basta un viaje representativo por ruta y dirección.
"""

import math
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.dominio.catalogos import AGENCIA_A_SISTEMA

ARCHIVOS = ("agency", "routes", "trips", "stops", "stop_times")

# Dos paradas del mismo sistema y nombre se consideran la misma estación si están
# a menos de esta distancia. Medido en el GTFS 2026-08-28: el transbordo más largo es
# Atlalilco (L8–L12, 636 m entre paradas), y no hay estaciones homónimas distintas
# dentro de un mismo sistema. 800 m une todos los transbordos con margen.
RADIO_AGRUPACION_M = 800.0


@dataclass(frozen=True)
class FeedGTFS:
    agency: pd.DataFrame
    routes: pd.DataFrame
    trips: pd.DataFrame
    stops: pd.DataFrame
    stop_times: pd.DataFrame
    frequencies: pd.DataFrame | None = None  # opcional en GTFS


def leer_feed(ruta_zip: Path) -> FeedGTFS:
    """Lee las tablas necesarias del ZIP. Todo como texto: los ids del GTFS no son números."""
    with zipfile.ZipFile(ruta_zip) as z:
        nombres = set(z.namelist())
        tablas = {
            n: pd.read_csv(
                z.open(f"{n}.txt"), dtype=str, keep_default_na=False, encoding="utf-8-sig"
            )
            for n in ARCHIVOS
        }
        if "frequencies.txt" in nombres:
            tablas["frequencies"] = pd.read_csv(
                z.open("frequencies.txt"), dtype=str, keep_default_na=False, encoding="utf-8-sig"
            )
    return FeedGTFS(**tablas)


def filtrar_sistemas(feed: FeedGTFS) -> FeedGTFS:
    """Conserva sólo las rutas de Metro, Metrobús y Tren Ligero y lo que de ellas depende."""
    rutas = feed.routes[feed.routes["agency_id"].isin(AGENCIA_A_SISTEMA)].copy()
    rutas["sistema"] = rutas["agency_id"].map(AGENCIA_A_SISTEMA)
    viajes = feed.trips[feed.trips["route_id"].isin(rutas["route_id"])]
    horarios = feed.stop_times[feed.stop_times["trip_id"].isin(viajes["trip_id"])]
    paradas = feed.stops[feed.stops["stop_id"].isin(horarios["stop_id"])]
    frecuencias = (
        None
        if feed.frequencies is None
        else feed.frequencies[feed.frequencies["trip_id"].isin(viajes["trip_id"])]
    )
    return FeedGTFS(feed.agency, rutas, viajes, paradas, horarios, frecuencias)


def intervalos_medios(feed: FeedGTFS) -> dict[str, int]:
    """Intervalo medio entre trenes (s) por ruta, a partir de ``frequencies.txt``.

    Es un promedio simple de ``headway_secs`` sobre las franjas publicadas; el feed de la
    CDMX publica un solo intervalo por franja amplia (p. ej. 180 s en el Metro L2).
    Las rutas sin frecuencias no aparecen: el motor usará un valor por defecto del sistema.
    """
    if feed.frequencies is None or feed.frequencies.empty:
        return {}
    f = feed.frequencies.merge(feed.trips[["trip_id", "route_id"]], on="trip_id")
    medias = f.assign(h=f["headway_secs"].astype(int)).groupby("route_id")["h"].mean()
    return {r: int(round(h)) for r, h in medias.items()}


def normalizar_nombre(nombre: str) -> str:
    """'Tasqueña' -> 'TASQUENA'; 'Deportivo 18 de Marzo' -> 'DEPORTIVO_18_DE_MARZO'."""
    sin_acentos = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", "_", sin_acentos.upper()).strip("_")


def distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia de gran círculo (haversine). Suficiente para agrupar a escala de cuadras."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _sistema_por_parada(feed: FeedGTFS) -> pd.Series:
    """Sistema de cada parada, a partir de las rutas que pasan por ella."""
    t = feed.stop_times[["trip_id", "stop_id"]].drop_duplicates()
    t = t.merge(feed.trips[["trip_id", "route_id"]], on="trip_id")
    t = t.merge(feed.routes[["route_id", "sistema"]], on="route_id")
    sistemas = t.groupby("stop_id")["sistema"].unique()
    ambiguas = sistemas[sistemas.map(len) > 1]
    if not ambiguas.empty:
        raise ValueError(f"Paradas compartidas por varios sistemas: {list(ambiguas.index)[:5]}")
    return sistemas.map(lambda s: s[0])


def _wheelchair_agregado(valores: pd.Series) -> int:
    """Combina el ``wheelchair_boarding`` de las paradas de una estación.

    Gana el valor menos favorable: si alguna parada es no accesible (2) la estación
    también; si alguna no tiene dato (0) la estación queda sin dato. Coincide con la
    regla de seguridad 1: la falta de información no se presume accesible.
    """
    v = {int(x) if str(x).strip() else 0 for x in valores}
    if 2 in v:
        return 2
    if 0 in v:
        return 0
    return 1


def agrupar_estaciones(feed: FeedGTFS) -> tuple[pd.DataFrame, dict[str, str]]:
    """Agrupa paradas en estaciones físicas.

    Devuelve ``(estaciones, parada_a_clave)``. ``estaciones`` tiene columnas
    clave, nombre, sistema, lat, lon, wheelchair_boarding_gtfs, paradas.
    La clave es ``SISTEMA-NOMBRE_NORMALIZADO`` (p. ej. ``METRO-HIDALGO``); si dos
    estaciones homónimas del mismo sistema están lejos, la segunda recibe ``-2``.
    """
    paradas = feed.stops.copy()
    paradas["sistema"] = paradas["stop_id"].map(_sistema_por_parada(feed))
    paradas["lat"] = paradas["stop_lat"].astype(float)
    paradas["lon"] = paradas["stop_lon"].astype(float)
    paradas["nombre_norm"] = paradas["stop_name"].map(normalizar_nombre)

    grupos: list[dict] = []
    for (sistema, nombre_norm), bloque in paradas.sort_values("stop_id").groupby(
        ["sistema", "nombre_norm"], sort=True
    ):
        propios: list[dict] = []
        for p in bloque.itertuples():
            destino = next(
                (
                    g
                    for g in propios
                    if distancia_m(p.lat, p.lon, g["lat0"], g["lon0"]) <= RADIO_AGRUPACION_M
                ),
                None,
            )
            if destino is None:
                sufijo = "" if not propios else f"-{len(propios) + 1}"
                destino = {
                    "clave": f"{sistema}-{nombre_norm}{sufijo}",
                    "sistema": sistema,
                    "lat0": p.lat,
                    "lon0": p.lon,
                    "filas": [],
                }
                propios.append(destino)
            destino["filas"].append(p)
        grupos.extend(propios)

    estaciones, parada_a_clave = [], {}
    for g in grupos:
        filas = g["filas"]
        # El nombre más frecuente conserva acentos y mayúsculas tal como los publica el GTFS.
        nombre = pd.Series([f.stop_name for f in filas]).mode().iloc[0]
        estaciones.append(
            {
                "clave": g["clave"],
                "nombre": nombre,
                "sistema": g["sistema"],
                "lat": sum(f.lat for f in filas) / len(filas),
                "lon": sum(f.lon for f in filas) / len(filas),
                "wheelchair_boarding_gtfs": _wheelchair_agregado(
                    pd.Series([f.wheelchair_boarding for f in filas])
                ),
                "paradas": sorted(f.stop_id for f in filas),
            }
        )
        for f in filas:
            parada_a_clave[f.stop_id] = g["clave"]
    return pd.DataFrame(estaciones), parada_a_clave


def _segundos(hhmmss: str) -> int | None:
    """'25:10:00' -> 90600. El GTFS permite horas > 24 para viajes que cruzan la medianoche."""
    if not hhmmss:
        return None
    h, m, s = (int(x) for x in hhmmss.strip().split(":"))
    return h * 3600 + m * 60 + s


def secuencias(feed: FeedGTFS, parada_a_clave: dict[str, str]) -> pd.DataFrame:
    """Secuencia de estaciones por ruta y dirección, con el tiempo desde la anterior.

    Para cada (route_id, direction_id) toma como representativo el viaje con más
    paradas (los demás repiten la secuencia con otro ``service_id``). La dirección se
    nombra con el ``trip_headsign``, que es la terminal señalizada en el andén.
    """
    horarios = feed.stop_times.copy()
    horarios["stop_sequence"] = horarios["stop_sequence"].astype(int)
    conteo = horarios.groupby("trip_id").size().rename("n_paradas")
    viajes = feed.trips.merge(conteo, left_on="trip_id", right_index=True)
    viajes = viajes.sort_values(
        ["route_id", "direction_id", "n_paradas", "trip_id"], ascending=[True, True, False, True]
    )
    representativos = viajes.drop_duplicates(["route_id", "direction_id"])

    filas = []
    for v in representativos.itertuples():
        h = horarios[horarios["trip_id"] == v.trip_id].sort_values("stop_sequence")
        anterior = None
        for i, x in enumerate(h.itertuples(), start=1):
            t = _segundos(x.arrival_time) or _segundos(x.departure_time)
            filas.append(
                {
                    "route_id": v.route_id,
                    "direccion": v.trip_headsign or f"dirección {v.direction_id}",
                    "secuencia": i,
                    "clave_estacion": parada_a_clave[x.stop_id],
                    "stop_id": x.stop_id,
                    "tiempo_desde_anterior_s": (
                        t - anterior if t is not None and anterior is not None else None
                    ),
                }
            )
            anterior = t
    return pd.DataFrame(filas)


def reporte(feed: FeedGTFS, estaciones: pd.DataFrame) -> dict:
    """Resumen para F1-1: rutas, paradas y estaciones por sistema, y cobertura de accesibilidad."""
    por_sistema = {}
    for sistema, bloque in estaciones.groupby("sistema"):
        wb = bloque["wheelchair_boarding_gtfs"].value_counts().to_dict()
        por_sistema[sistema] = {
            "rutas": int((feed.routes["sistema"] == sistema).sum()),
            "paradas_gtfs": int(bloque["paradas"].map(len).sum()),
            "estaciones": len(bloque),
            "accesibles_gtfs": int(wb.get(1, 0)),
            "no_accesibles_gtfs": int(wb.get(2, 0)),
            "sin_dato_gtfs": int(wb.get(0, 0)),
        }
    return por_sistema
