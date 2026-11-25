"""Lugares y estado de accesibilidad de cada estación (F3-1, F3-3). Lógica pura."""

from collections import defaultdict, deque
from dataclasses import dataclass

from app.dominio.red import EstadoEquipo, Red
from app.dominio.restricciones import ESTADOS_BLOQUEANTES, estado_de


@dataclass(frozen=True)
class Lugar:
    """Resultado del Geocodificador: una estación del catálogo o un lugar."""

    tipo: str  # "estacion" | "lugar"
    nombre: str
    lat: float
    lon: float
    detalle: str = ""
    clave_estacion: str | None = None


@dataclass(frozen=True)
class EstacionResumen:
    clave: str
    nombre: str
    sistema: str
    lat: float
    lon: float
    lineas: tuple[str, ...]
    wheelchair_boarding_gtfs: int


# Estados para el mapa (F3-3). Se comunican con color + forma + texto en la UI.
ACCESIBLE = "ACCESIBLE"  # camino sin escalones calle↔todos los andenes, equipos operativos
CON_FALLAS = "CON_FALLAS"  # accesible por inventario, pero hoy algún equipo necesario bloqueado
NO_ACCESIBLE = "NO_ACCESIBLE"  # el inventario sólo tiene escalones o escaleras
SIN_DATOS = "SIN_DATOS"  # fuera del corredor: sin inventario


def _sin_escalones(tipo: str, escalones: int) -> bool:
    return escalones == 0 and tipo not in ("ESCALERA_FIJA", "ESCALERA_ELECTRICA")


def estado_accesibilidad(red: Red, estados: dict[str, EstadoEquipo]) -> dict[str, str]:
    """Estado de cada estación con inventario para quien no puede usar escalones.

    Se exige ir y volver: de alguna salida a cada andén y de cada andén a alguna salida.
    Primero sólo con la topología (¿existe el camino?) y después con los estados
    vigentes (¿se puede usar hoy?). Estaciones sin inventario no aparecen: son SIN_DATOS.
    """
    por_estacion: dict[str, list] = defaultdict(list)
    for c in red.conexiones:
        por_estacion[red.niveles[c.desde].clave_estacion].append(c)

    resultado = {}
    for clave, conexiones in por_estacion.items():
        niveles = [n for n in red.niveles.values() if n.clave_estacion == clave]
        calles = {n.codigo for n in niveles if n.tipo == "CALLE"}
        andenes = {n.codigo for n in niveles if n.tipo == "ANDEN"}

        def conectados(usar_estados: bool, conexiones=conexiones, calles=calles, andenes=andenes):
            ady = defaultdict(set)
            for c in conexiones:
                if not _sin_escalones(c.tipo, c.escalones):
                    continue
                if (
                    usar_estados
                    and c.equipo
                    and estado_de(c.equipo, estados).estado in ESTADOS_BLOQUEANTES
                ):
                    continue
                ady[c.desde].add(c.hasta)
                if c.bidireccional:
                    ady[c.hasta].add(c.desde)
            ida = _alcanzables(ady, calles)
            return andenes <= ida and all(calles & _alcanzables(ady, {a}) for a in andenes)

        if clave in red.estaciones_cerradas or not conectados(False):
            resultado[clave] = NO_ACCESIBLE
        else:
            resultado[clave] = ACCESIBLE if conectados(True) else CON_FALLAS
    return resultado


def _alcanzables(ady: dict[str, set[str]], origenes: set[str]) -> set[str]:
    vistos, cola = set(origenes), deque(origenes)
    while cola:
        for v in ady[cola.popleft()] - vistos:
            vistos.add(v)
            cola.append(v)
    return vistos
