"""Red de juguete para las pruebas del motor de rutas (F2).

    Línea 2 (R2):  A ──120 s── B ──120 s── C        Línea 3 (R3):  B ──150 s── Z

          O (origen, junto a A)          D (destino, entre B y C: 611 m de B, 500 m de C)

- A: salida A1 con elevador multinivel E-A1 (calle↔vestíbulo y vestíbulo↔andenes:
  un equipo, tres conexiones) y escaleras.
- B: salida B1 con elevador E-B1; elevador E-B2 a los andenes de L2, E-B3 al andén de
  L3; pasillo a nivel entre vestíbulos; escalera eléctrica de subida en L2 (ESC-B).
- C: salidas C1 (elevador E-C1) y C2 (elevador E-C3); elevador E-C2 al andén central,
  del que dependen ambas salidas.
- Z: sólo escaleras (no accesible).

Las coordenadas están sobre un meridiano: 0.001° de latitud ≈ 111 m.
"""

from datetime import datetime, timedelta

from app.dominio.grafo import DESTINO, ORIGEN, Caminata
from app.dominio.red import (
    Conexion,
    Equipo,
    EstadoEquipo,
    Linea,
    Nivel,
    Perfil,
    Punto,
    Red,
    Secuencia,
    Tramo,
    distancia_m,
)

AHORA = datetime(2026, 11, 24, 12, 0, 0)
LON = -99.10
COORD = {"A": 19.300, "B": 19.310, "C": 19.320, "Z": 19.310}
LON_Z = -99.09
NOMBRE = {"A": "Estación A", "B": "Estación B", "C": "Estación C", "Z": "Estación Z"}

ORIGEN_PUNTO = Punto(19.2995, LON)
DESTINO_PUNTO = Punto(19.3155, LON)
DESTINO_EN_Z = Punto(19.3100, -99.0895)


def _n(clave, sufijo, tipo, ref, route=None, direccion=None):
    lon = LON_Z if clave == "Z" else LON
    return Nivel(f"{clave}/{sufijo}", clave, NOMBRE[clave], tipo, COORD[clave], lon, ref,
                 route, direccion)  # fmt: skip


def _esc(desde, hasta, escalones=24):
    return Conexion(desde, hasta, "ESCALERA_FIJA", 45, 12, escalones=escalones)


def _elv(desde, hasta, equipo):
    return Conexion(desde, hasta, "ELEVADOR", 90, 5, equipo=equipo)


def construir_red() -> Red:
    n = [
        _n("A", "SAL-A1", "CALLE", "salida A1"), _n("A", "VES", "VESTIBULO", "vestíbulo"),
        _n("A", "AND-2-C", "ANDEN", "andén L2 dirección C", "R2", "C"),
        _n("A", "AND-2-A", "ANDEN", "andén L2 dirección A", "R2", "A"),
        _n("B", "SAL-B1", "CALLE", "salida B1"), _n("B", "VES-2", "VESTIBULO", "vestíbulo L2"),
        _n("B", "VES-3", "VESTIBULO", "vestíbulo L3"),
        _n("B", "AND-2-C", "ANDEN", "andén L2 dirección C", "R2", "C"),
        _n("B", "AND-2-A", "ANDEN", "andén L2 dirección A", "R2", "A"),
        _n("B", "AND-3-Z", "ANDEN", "andén L3 dirección Z", "R3", "Z"),
        _n("B", "AND-3-B", "ANDEN", "andén L3 dirección B", "R3", "B"),
        _n("C", "SAL-C1", "CALLE", "salida C1"), _n("C", "SAL-C2", "CALLE", "salida C2"),
        _n("C", "VES", "VESTIBULO", "vestíbulo"),
        _n("C", "AND-2-C", "ANDEN", "andén L2 dirección C", "R2", "C"),
        _n("C", "AND-2-A", "ANDEN", "andén L2 dirección A", "R2", "A"),
        _n("Z", "SAL-Z1", "CALLE", "salida Z1"), _n("Z", "VES", "VESTIBULO", "vestíbulo"),
        _n("Z", "AND-3-Z", "ANDEN", "andén L3 dirección Z", "R3", "Z"),
        _n("Z", "AND-3-B", "ANDEN", "andén L3 dirección B", "R3", "B"),
    ]  # fmt: skip
    niveles = {x.codigo: x for x in n}
    c = [
        _esc("A/SAL-A1", "A/VES", 20), _elv("A/SAL-A1", "A/VES", "E-A1"),
        _esc("A/VES", "A/AND-2-C"), _elv("A/VES", "A/AND-2-C", "E-A1"),
        _esc("A/VES", "A/AND-2-A"), _elv("A/VES", "A/AND-2-A", "E-A1"),
        Conexion("A/AND-2-C", "A/AND-2-A", "PASILLO", 15, 10),
        _esc("B/SAL-B1", "B/VES-2", 20), _elv("B/SAL-B1", "B/VES-2", "E-B1"),
        _esc("B/VES-2", "B/AND-2-C"), _elv("B/VES-2", "B/AND-2-C", "E-B2"),
        _esc("B/VES-2", "B/AND-2-A"), _elv("B/VES-2", "B/AND-2-A", "E-B2"),
        Conexion("B/AND-2-C", "B/VES-2", "ESCALERA_ELECTRICA", 30, 12, bidireccional=False,
                 equipo="ESC-B"),
        _esc("B/VES-3", "B/AND-3-Z"), _elv("B/VES-3", "B/AND-3-Z", "E-B3"),
        _esc("B/VES-3", "B/AND-3-B"), _elv("B/VES-3", "B/AND-3-B", "E-B3"),
        Conexion("B/VES-2", "B/VES-3", "PASILLO", 82, 65),
        _esc("C/SAL-C1", "C/VES", 20), _elv("C/SAL-C1", "C/VES", "E-C1"),
        _esc("C/SAL-C2", "C/VES", 20), _elv("C/SAL-C2", "C/VES", "E-C3"),
        _esc("C/VES", "C/AND-2-C"), _elv("C/VES", "C/AND-2-C", "E-C2"),
        _esc("C/VES", "C/AND-2-A"), _elv("C/VES", "C/AND-2-A", "E-C2"),
        Conexion("C/AND-2-C", "C/AND-2-A", "PASILLO", 15, 10),
        _esc("Z/SAL-Z1", "Z/VES", 20), _esc("Z/VES", "Z/AND-3-Z"), _esc("Z/VES", "Z/AND-3-B"),
    ]  # fmt: skip
    equipos = {
        cod: Equipo(cod, estacion, tipo, ref)
        for cod, estacion, tipo, ref in [
            ("E-A1", "A", "ELEVADOR", "elevador salida A1"),
            ("E-B1", "B", "ELEVADOR", "elevador salida B1"),
            ("E-B2", "B", "ELEVADOR", "elevador andenes L2"),
            ("E-B3", "B", "ELEVADOR", "elevador andenes L3"),
            ("ESC-B", "B", "ESCALERA_ELECTRICA", "escalera eléctrica L2"),
            ("E-C1", "C", "ELEVADOR", "elevador salida C1"),
            ("E-C2", "C", "ELEVADOR", "elevador andén central"),
            ("E-C3", "C", "ELEVADOR", "elevador salida C2"),
        ]
    }
    lineas = {"R2": Linea("R2", "METRO", "2", 180), "R3": Linea("R3", "METRO", "3", 240)}
    secuencias = (
        Secuencia("R2", "C", (("A", 0), ("B", 120), ("C", 120))),
        Secuencia("R2", "A", (("C", 0), ("B", 120), ("A", 120))),
        Secuencia("R3", "Z", (("B", 0), ("Z", 150))),
        Secuencia("R3", "B", (("Z", 0), ("B", 150))),
    )
    return Red(niveles, tuple(c), equipos, lineas, secuencias)


def estados_ok(horas: float = 2.0, prob: float = 0.98, **cambios: EstadoEquipo):
    """Todos los equipos operativos, verificados hace ``horas``; ``cambios`` sobrescribe."""
    base = {cod: EstadoEquipo("OPERATIVO", prob, AHORA - timedelta(hours=horas))
            for cod in construir_red().equipos}  # fmt: skip
    base.update({k.replace("_", "-"): v for k, v in cambios.items()})
    return base


def falla() -> EstadoEquipo:
    return EstadoEquipo("FALLA_CONFIRMADA", 0.05, AHORA - timedelta(hours=20))


def perfil(tipo="silla_manual", **cambios) -> Perfil:
    base = {
        "silla_manual": dict(escalones_max=0, pendiente_max_pct=6, puede_escalera_electrica=False,
                             distancia_pie_max_m=800, peso_seguridad_vs_tiempo=0.9),
        "adulto_mayor": dict(escalones_max=30, pendiente_max_pct=10, puede_escalera_electrica=True,
                             distancia_pie_max_m=1000, peso_seguridad_vs_tiempo=0.7),
    }[tipo]  # fmt: skip
    return Perfil(tipo_movilidad=tipo, **{**base, **cambios})


def linea_recta(a: Punto, b: Punto) -> Tramo:
    """CaminataProveedor de prueba: distancia en línea recta, sin factor de rodeo."""
    return Tramo(distancia_m(a, b))


def caminatas(red: Red, origen: Punto, destino: Punto, radio_m: float = 1000):
    """Caminatas del origen a cada salida y de cada salida al destino dentro del radio."""
    res = []
    for n in red.niveles.values():
        if n.tipo != "CALLE":
            continue
        p = Punto(n.lat, n.lon)
        if distancia_m(origen, p) <= radio_m:
            res.append(Caminata(ORIGEN, n.codigo, linea_recta(origen, p)))
        if distancia_m(p, destino) <= radio_m:
            res.append(Caminata(n.codigo, DESTINO, linea_recta(p, destino)))
    return tuple(res)
