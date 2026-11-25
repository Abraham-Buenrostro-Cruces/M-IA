"""Tipos de dominio del motor de rutas (F2). Sin I/O: los llena el repositorio.

Unidades: tiempos en segundos, distancias en metros, probabilidades en [0, 1].
"""

import math
from dataclasses import dataclass, field
from datetime import datetime

from app.dominio.catalogos import ESTADOS_EQUIPO


@dataclass(frozen=True)
class Nivel:
    codigo: str
    clave_estacion: str
    nombre_estacion: str
    tipo: str  # CALLE | VESTIBULO | ANDEN | PASILLO
    lat: float
    lon: float
    referencia: str = ""
    route_id: str | None = None  # sólo andenes
    direccion: str | None = None  # sólo andenes


@dataclass(frozen=True)
class Conexion:
    desde: str  # código de nivel
    hasta: str
    tipo: str
    tiempo_s: float
    longitud_m: float = 0.0
    escalones: int = 0
    pendiente_pct: float = 0.0
    bidireccional: bool = True
    equipo: str | None = None  # código de equipo


@dataclass(frozen=True)
class Equipo:
    codigo: str
    clave_estacion: str
    tipo: str
    referencia: str


@dataclass(frozen=True)
class Linea:
    route_id: str
    sistema: str
    nombre: str  # "2", "3", "A"
    intervalo_s: float  # intervalo medio entre trenes


@dataclass(frozen=True)
class Secuencia:
    """Estaciones de una línea en una dirección, con el tiempo de viaje desde la anterior."""

    route_id: str
    direccion: str
    paradas: tuple[tuple[str, float], ...]  # (clave_estacion, tiempo_desde_anterior_s)


@dataclass(frozen=True)
class Red:
    niveles: dict[str, Nivel]
    conexiones: tuple[Conexion, ...]
    equipos: dict[str, Equipo]
    lineas: dict[str, Linea]
    secuencias: tuple[Secuencia, ...]
    estaciones_cerradas: frozenset[str] = frozenset()


@dataclass(frozen=True)
class EstadoEquipo:
    estado: str
    prob_operativo: float
    actualizado_en: datetime | None = None
    fuente: str = ""

    def __post_init__(self):
        if self.estado not in ESTADOS_EQUIPO:
            raise ValueError(f"Estado de equipo desconocido: {self.estado}")


# Un equipo sin fila de estado se trata como DESCONOCIDO (regla de seguridad 1).
ESTADO_SIN_DATO = EstadoEquipo("DESCONOCIDO", 0.5)

# Velocidad a pie por tipo de movilidad (m/s). Supuestos conservadores para el MVP:
# ~1.3 m/s es la marcha media de un peatón adulto; las ayudas técnicas la reducen.
VELOCIDAD_PIE_M_S = {
    "silla_manual": 0.8,
    "silla_electrica": 1.1,
    "andadera": 0.6,
    "adulto_mayor": 0.9,
    "carriola": 1.1,
}
VELOCIDAD_PIE_POR_DEFECTO = 0.8


@dataclass(frozen=True)
class Perfil:
    """Necesidades funcionales (D-16). Dato sensible: no se registra en logs (regla 6)."""

    tipo_movilidad: str
    escalones_max: int
    pendiente_max_pct: float
    puede_escalera_electrica: bool
    distancia_pie_max_m: float
    peso_seguridad_vs_tiempo: float
    max_transbordos: int | None = None

    @property
    def velocidad_pie_m_s(self) -> float:
        return VELOCIDAD_PIE_M_S.get(self.tipo_movilidad, VELOCIDAD_PIE_POR_DEFECTO)

    @property
    def lambda_seguridad(self) -> float:
        """λ en minutos equivalentes por unidad de -ln(1-p) (02 §4.2, D-20).

        λ = 60·w/(1-w): w es la razón de momios "seguridad contra tiempo". Se acota w
        a 0.99 para que λ sea finito.
        """
        w = min(max(self.peso_seguridad_vs_tiempo, 0.0), 0.99)
        return 60.0 * w / (1.0 - w)

    def __repr__(self) -> str:  # evita que el perfil completo aparezca en trazas y logs
        return "Perfil(<oculto>)"


@dataclass(frozen=True)
class Punto:
    lat: float
    lon: float


def distancia_m(a: Punto, b: Punto) -> float:
    """Haversine en metros."""
    r = 6_371_000.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


@dataclass(frozen=True)
class Tramo:
    """Resultado de CaminataProveedor: distancia a pie real (no en línea recta)."""

    distancia_m: float
    geometria: tuple[Punto, ...] = field(default_factory=tuple)
