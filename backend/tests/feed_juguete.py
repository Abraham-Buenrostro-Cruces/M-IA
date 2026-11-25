"""Feed GTFS de juguete compartido por las pruebas.

Red (coordenadas reales aproximadas del centro de la CDMX):
- Metro L2: Allende → Bellas Artes → Hidalgo (viajes repetidos con otro service_id).
- Metro L3: Juárez → Hidalgo (parada propia, a ~50 m de la de L2: transbordo).
- Metrobús L1: Hidalgo (misma denominación que el Metro, pero otro sistema).
- RTP: una ruta que debe quedar fuera.
"""

import zipfile
from pathlib import Path

AGENCY = "agency_id,agency_name\nMETRO,Metro\nMB,Metrobús\nRTP,RTP\n"
ROUTES = (
    "route_id,agency_id,route_short_name,route_long_name,route_type\n"
    "M2,METRO,2,Cuatro Caminos - Tasqueña,1\n"
    "M3,METRO,3,Indios Verdes - Universidad,1\n"
    "MB1,MB,1,Indios Verdes - El Caminero,3\n"
    "R1,RTP,1,Ruta RTP,3\n"
)
TRIPS = (
    "route_id,service_id,trip_id,trip_headsign,direction_id\n"
    "M2,LV,m2a,Tasqueña,0\n"
    "M2,SAB,m2b,Tasqueña,0\n"  # mismo recorrido, otro servicio: no debe duplicar la secuencia
    "M3,LV,m3a,Universidad,0\n"
    "MB1,LV,mb1a,El Caminero,0\n"
    "R1,LV,r1a,Destino,0\n"
)
STOPS = (
    "stop_id,stop_name,stop_lat,stop_lon,wheelchair_boarding\n"
    "L2-ALLENDE,Allende,19.43566,-99.13715,1\n"
    "L2-BELLAS,Bellas Artes,19.43638,-99.14161,2\n"
    "L2-HIDALGO,Hidalgo,19.43755,-99.14722,1\n"
    "L3-JUAREZ,Juárez,19.43290,-99.14760,\n"
    "L3-HIDALGO,Hidalgo,19.43738,-99.14678,2\n"
    "MB-HIDALGO,Hidalgo,19.43700,-99.14600,1\n"
    "RTP-X,Parada RTP,19.40000,-99.10000,0\n"
)
STOP_TIMES = (
    "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
    "m2a,06:00:00,06:00:00,L2-ALLENDE,1\n"
    "m2a,06:01:30,06:01:30,L2-BELLAS,2\n"
    "m2a,06:03:00,06:03:00,L2-HIDALGO,3\n"
    "m2b,07:00:00,07:00:00,L2-ALLENDE,1\n"
    "m2b,07:01:30,07:01:30,L2-BELLAS,2\n"
    "m2b,07:03:00,07:03:00,L2-HIDALGO,3\n"
    "m3a,23:59:00,23:59:00,L3-JUAREZ,1\n"
    "m3a,24:01:00,24:01:00,L3-HIDALGO,2\n"  # cruza la medianoche: hora > 24 válida en GTFS
    "mb1a,06:00:00,06:00:00,MB-HIDALGO,1\n"
    "r1a,06:00:00,06:00:00,RTP-X,1\n"
)


def escribir_feed(ruta: Path, **reemplazos: str) -> Path:
    """Escribe el feed de juguete como ZIP; ``reemplazos`` sustituye tablas completas."""
    tablas = {
        "agency": AGENCY,
        "routes": ROUTES,
        "trips": TRIPS,
        "stops": STOPS,
        "stop_times": STOP_TIMES,
        **reemplazos,
    }
    with zipfile.ZipFile(ruta, "w") as z:
        for nombre, contenido in tablas.items():
            z.writestr(f"{nombre}.txt", contenido)
    return ruta
