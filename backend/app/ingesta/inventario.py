"""Generador del inventario de DEMOSTRACIÓN por plantillas (F1-4, D-18, D-25).

**Todo lo que produce este módulo son datos de demostración**, no el inventario
real de los operadores (que no es público). Cada fila sale con ``fuente = "DEMO"``.

Entrada: el catálogo de toda la red (una entrada por estación de los cinco sistemas,
D-25, con los ajustes a mano de ``data/demo/ajustes_red.csv``) y la red del GTFS (qué
líneas y direcciones pasan por cada estación). Salida: niveles, equipos y conexiones con
la estructura de las tablas ``nivel``, ``infraestructura_accesible`` y ``conexion``.

Plantilla de una estación (por cada línea que pasa por ella); el detalle depende del
sistema (``PLANTILLAS``):

    calle (salidas) ──escalera fija / elevador / rampa── vestíbulo de la línea
    vestíbulo ──escalera fija [+ elevador] [+ escalera eléctrica de subida]── andén por dirección
        (Metrobús y Tren Ligero: andén a nivel, unido por un pasillo)
    andén central: los andenes de ambas direcciones se unen con un pasillo a nivel
    transbordo: los vestíbulos de cada línea se unen con un pasillo

Además, ``transbordos_a_pie`` une por la calle las salidas de estaciones cercanas que no
comparten línea (p. ej. Buenavista: Suburbano, Metro B y Metrobús): es lo que permite
compensar con otros sistemas la falta de elevadores del Metro (D-19, D-25).

Las escaleras fijas se modelan aunque haya elevador: el grafo debe contener las
barreras para que las restricciones duras del perfil las eliminen (D-18).
"""

import math
from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import combinations

import pandas as pd

from app.bd.modelos import LONGITUD_CODIGO
from app.dominio import catalogos as cat
from app.ingesta.gtfs import distancia_m, normalizar_nombre

FUENTE = "DEMO"

# Parámetros físicos de la plantilla. Son supuestos de demostración razonables para
# el Metro de la CDMX (estaciones subterráneas o elevadas de un nivel de vestíbulo).
ESCALONES_CALLE_VESTIBULO = 20
ESCALONES_VESTIBULO_ANDEN = 24
TIEMPO_ESCALERA_S = 45
TIEMPO_ELEVADOR_S = 90  # incluye la espera: es el dato que más pesa para quien depende de él
TIEMPO_ESCALERA_ELECTRICA_S = 30
PENDIENTE_RAMPA_PCT = 6.0  # máximo recomendado por la NOM-034-SCT2 / NMX-R-050 para rampas largas
LONGITUD_RAMPA_M = 25.0
VELOCIDAD_PASILLO_M_S = 0.8  # paso lento: silla de ruedas manual o andadera
FACTOR_RODEO_TRANSBORDO = 1.3
LONGITUD_MIN_TRANSBORDO_M = 60.0
# Desplazamiento de cada salida respecto del centro de la estación (~60 m).
DESPLAZAMIENTO_SALIDA_GRADOS = 0.00055

ACCESOS_VALIDOS = ("ELEVADOR", "RAMPA", "ESCALERA_FIJA")

# Transbordo a pie entre estaciones distintas. Medido en el GTFS 2026-08-28: con 300 m en
# línea recta quedaban fuera transbordos que la gente sí hace y que llevan el mismo nombre
# (Buenavista Suburbano–Metro, 377–422 m; Misterios, Martín Carrera, Chapultepec, La
# Villa, 316–432 m). 450 m los incluye; con el rodeo son hasta ~590 m, y la distancia
# máxima a pie de cada perfil (500 m con andadera) se aplica después, en el motor.
RADIO_TRANSBORDO_A_PIE_M = 450.0
LONGITUD_MIN_A_PIE_M = 20.0


@dataclass(frozen=True)
class PlantillaSistema:
    """Supuestos de demostración de cómo es una estación típica de cada sistema.

    - ``acceso_accesible``: equipo de las salidas en una estación accesible. En el Metro y
      los trenes suburbanos el andén está bajo o sobre la calle (elevador en una salida);
      en el Metrobús y el Tren Ligero el andén está casi a nivel de calle (rampa en todas).
    - ``escalera_siempre``: la salida tiene escalera fija aunque tenga elevador o rampa.
    - ``escalones_calle``: escalones de la escalera fija calle–vestíbulo (en el Metrobús,
      las estaciones no accesibles suelen tener puente peatonal).
    - ``anden_a_nivel``: vestíbulo y andén se unen con un pasillo, sin escalera.
    - ``escaleras_electricas``: escalera eléctrica de subida en terminales y transbordos.
    """

    acceso_accesible: str
    escalera_siempre: bool
    escalones_calle: int
    anden_a_nivel: bool
    escaleras_electricas: bool


_ELEVADO_O_SUBTERRANEO = PlantillaSistema("ELEVADOR", True, ESCALONES_CALLE_VESTIBULO, False, True)
PLANTILLAS = {
    "METRO": _ELEVADO_O_SUBTERRANEO,
    "TREN_SUBURBANO": _ELEVADO_O_SUBTERRANEO,
    "TREN_INTERURBANO": _ELEVADO_O_SUBTERRANEO,
    "METROBUS": PlantillaSistema("RAMPA", False, 30, True, False),
    "TREN_LIGERO": PlantillaSistema("RAMPA", False, ESCALONES_CALLE_VESTIBULO, True, False),
}


def sistema_de(clave: str) -> str:
    """'TREN_LIGERO-TASQUENA' -> 'TREN_LIGERO' (la clave es SISTEMA-NOMBRE, ver gtfs.py)."""
    return clave.split("-", 1)[0]


CARDINALES = {
    "norte": (1, 0), "sur": (-1, 0), "oriente": (0, 1), "poniente": (0, -1),
    "nororiente": (1, 1), "norponiente": (1, -1), "suroriente": (-1, 1), "surponiente": (-1, -1),
}  # fmt: skip


@dataclass(frozen=True)
class EntradaCatalogo:
    """Una estación del catálogo de la red (fila de ajustes_red.csv o plantilla por omisión)."""

    clave: str
    plantilla: str = "AUTO"  # AUTO | LATERAL | CENTRAL
    accesibilidad: str = "AUTO"  # AUTO | COMPLETA | NINGUNA
    salidas: tuple[str, ...] = ("A", "B")
    accesos: dict[str, str] = field(default_factory=dict)  # salida -> ELEVADOR|RAMPA|ESCALERA_FIJA
    nota: str = ""


@dataclass(frozen=True)
class LineaEnEstacion:
    route_id: str
    linea: str  # nombre corto: "2", "3", "A"
    direcciones: tuple[str, ...]
    lat: float
    lon: float
    terminal: bool


@dataclass
class Inventario:
    niveles: list[dict] = field(default_factory=list)
    equipos: list[dict] = field(default_factory=list)
    conexiones: list[dict] = field(default_factory=list)

    def como_dataframes(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        return (
            pd.DataFrame(self.niveles, columns=COLUMNAS_NIVEL),
            pd.DataFrame(self.equipos, columns=COLUMNAS_EQUIPO),
            pd.DataFrame(self.conexiones, columns=COLUMNAS_CONEXION),
        )


COLUMNAS_NIVEL = [
    "codigo", "clave_estacion", "tipo", "route_id_gtfs", "direccion", "referencia",
    "lat", "lon", "fuente",
]  # fmt: skip
COLUMNAS_EQUIPO = ["codigo", "clave_estacion", "tipo", "referencia", "lat", "lon", "fuente"]
COLUMNAS_CONEXION = [
    "nivel_desde", "nivel_hasta", "tipo", "codigo_equipo", "bidireccional", "escalones",
    "pendiente_pct", "longitud_m", "tiempo_s", "fuente",
]  # fmt: skip


# --------------------------------------------------------------------------- catálogo


def leer_catalogo(df: pd.DataFrame) -> list[EntradaCatalogo]:
    """Convierte el CSV del catálogo en entradas validadas.

    ``accesos`` usa el formato ``poniente=ELEVADOR;oriente=RAMPA``.
    """
    entradas = []
    for f in df.fillna("").itertuples():
        salidas = tuple(s.strip() for s in str(f.salidas).split(";") if s.strip()) or ("A", "B")
        accesos = {}
        for par in filter(None, (p.strip() for p in str(f.accesos).split(";"))):
            salida, _, tipo = par.partition("=")
            accesos[salida.strip()] = tipo.strip().upper()
        e = EntradaCatalogo(
            clave=f.clave.strip(),
            plantilla=(f.plantilla or "AUTO").strip().upper(),
            accesibilidad=(f.accesibilidad or "AUTO").strip().upper(),
            salidas=salidas,
            accesos=accesos,
            nota=str(f.nota).strip(),
        )
        _validar_entrada(e)
        entradas.append(e)
    claves = [e.clave for e in entradas]
    if len(claves) != len(set(claves)):
        raise ValueError("Claves de estación repetidas en el catálogo")
    return entradas


def catalogo_red(claves: Iterable[str], ajustes: list[EntradaCatalogo]) -> list[EntradaCatalogo]:
    """Una entrada por estación de la red (D-25): la de ``ajustes`` si existe, si no la
    plantilla por omisión (salidas A y B, accesibilidad según el GTFS)."""
    claves = sorted(set(claves))
    por_clave = {e.clave: e for e in ajustes}
    ajenas = sorted(set(por_clave) - set(claves))
    if ajenas:
        raise ValueError(f"Ajustes de estaciones que no están en la red: {ajenas}")
    return [por_clave.get(c, EntradaCatalogo(c)) for c in claves]


def _validar_entrada(e: EntradaCatalogo) -> None:
    if e.plantilla not in ("AUTO", "LATERAL", "CENTRAL"):
        raise ValueError(f"{e.clave}: plantilla desconocida {e.plantilla!r}")
    if e.accesibilidad not in ("AUTO", "COMPLETA", "NINGUNA"):
        raise ValueError(f"{e.clave}: accesibilidad desconocida {e.accesibilidad!r}")
    for salida, tipo in e.accesos.items():
        if salida not in e.salidas:
            raise ValueError(f"{e.clave}: el acceso {salida!r} no está en las salidas {e.salidas}")
        if tipo not in ACCESOS_VALIDOS:
            raise ValueError(f"{e.clave}: tipo de acceso {tipo!r} no válido")


# --------------------------------------------------------------------------- red


def lineas_por_estacion(
    secuencias: pd.DataFrame, rutas: pd.DataFrame, paradas: pd.DataFrame, route_ids: set[str]
) -> dict[str, list[LineaEnEstacion]]:
    """Para cada estación, las líneas del alcance (D-25) que la recorren, con sus direcciones."""
    nombre_linea = dict(zip(rutas["route_id"], rutas["route_short_name"], strict=True))
    coords = {p.stop_id: (float(p.stop_lat), float(p.stop_lon)) for p in paradas.itertuples()}
    s = secuencias[secuencias["route_id"].isin(route_ids)]
    ultima = s.groupby(["route_id", "direccion"])["secuencia"].transform("max")
    s = s.assign(terminal=(s["secuencia"] == 1) | (s["secuencia"] == ultima))

    resultado: dict[str, list[LineaEnEstacion]] = defaultdict(list)
    for (clave, route_id), b in s.groupby(["clave_estacion", "route_id"], sort=True):
        lat, lon = coords[b["stop_id"].iloc[0]]
        resultado[clave].append(
            LineaEnEstacion(
                route_id=route_id,
                linea=nombre_linea[route_id],
                direcciones=tuple(sorted(b["direccion"].unique())),
                lat=lat,
                lon=lon,
                terminal=bool(b["terminal"].any()),
            )
        )
    return dict(resultado)


# --------------------------------------------------------------------------- generación


def resolver_accesibilidad(entrada: EntradaCatalogo, wheelchair_gtfs: int) -> str:
    """AUTO sigue al GTFS: sólo ``wheelchair_boarding = 1`` se considera accesible.

    Sin dato (0) se trata como NINGUNA, por la regla de seguridad 1.
    """
    if entrada.accesibilidad != "AUTO":
        return entrada.accesibilidad
    return "COMPLETA" if wheelchair_gtfs == 1 else "NINGUNA"


def _accesos_resueltos(
    entrada: EntradaCatalogo, accesibilidad: str, plantilla: PlantillaSistema
) -> dict[str, str]:
    if entrada.accesos:
        return {s: entrada.accesos.get(s, "ESCALERA_FIJA") for s in entrada.salidas}
    if accesibilidad != "COMPLETA":
        return dict.fromkeys(entrada.salidas, "ESCALERA_FIJA")
    if plantilla.acceso_accesible == "RAMPA":
        return dict.fromkeys(entrada.salidas, "RAMPA")
    # Elevador en la primera salida; el resto, escaleras.
    return {s: ("ELEVADOR" if i == 0 else "ESCALERA_FIJA") for i, s in enumerate(entrada.salidas)}


def _desplazamiento(salida: str, i: int) -> tuple[float, float]:
    dlat, dlon = CARDINALES.get(salida.lower(), (0, 1 if i % 2 == 0 else -1))
    return dlat * DESPLAZAMIENTO_SALIDA_GRADOS, dlon * DESPLAZAMIENTO_SALIDA_GRADOS


def generar_estacion(
    inv: Inventario,
    entrada: EntradaCatalogo,
    lineas: list[LineaEnEstacion],
    wheelchair_gtfs: int,
) -> None:
    """Agrega al inventario los niveles, equipos y conexiones de una estación."""
    c = entrada.clave
    plantilla = PLANTILLAS[sistema_de(c)]
    accesible = resolver_accesibilidad(entrada, wheelchair_gtfs) == "COMPLETA"
    transbordo = len(lineas) > 1

    def nivel(codigo, tipo, referencia, lat, lon, route_id=None, direccion=None):
        inv.niveles.append(
            dict(codigo=codigo, clave_estacion=c, tipo=tipo, route_id_gtfs=route_id,
                 direccion=direccion, referencia=referencia, lat=round(lat, 6),
                 lon=round(lon, 6), fuente=FUENTE)
        )  # fmt: skip
        return codigo

    def equipo(codigo, tipo, referencia, lat, lon):
        inv.equipos.append(
            dict(codigo=codigo, clave_estacion=c, tipo=tipo, referencia=referencia,
                 lat=round(lat, 6), lon=round(lon, 6), fuente=FUENTE)
        )  # fmt: skip
        return codigo

    def conexion(desde, hasta, tipo, longitud, tiempo, equipo_=None, escalones=0,
                 pendiente=0.0, bidireccional=True):  # fmt: skip
        inv.conexiones.append(
            dict(nivel_desde=desde, nivel_hasta=hasta, tipo=tipo, codigo_equipo=equipo_,
                 bidireccional=bidireccional, escalones=escalones, pendiente_pct=pendiente,
                 longitud_m=round(longitud, 1), tiempo_s=int(tiempo), fuente=FUENTE)
        )  # fmt: skip

    vestibulos = {}
    for ln in lineas:
        central = entrada.plantilla == "CENTRAL" or (entrada.plantilla == "AUTO" and ln.terminal)
        ves = nivel(f"{c}/VES-L{ln.linea}", "VESTIBULO", f"vestíbulo Línea {ln.linea}",
                    ln.lat, ln.lon)  # fmt: skip
        vestibulos[ln.linea] = (ves, ln)
        andenes = []
        for d in ln.direcciones:
            andenes.append(
                nivel(f"{c}/AND-L{ln.linea}-{normalizar_nombre(d)}", "ANDEN",
                      f"andén Línea {ln.linea} dirección {d}", ln.lat, ln.lon,
                      route_id=ln.route_id, direccion=d)
            )  # fmt: skip
        if plantilla.anden_a_nivel:
            # Andén a nivel (Metrobús, Tren Ligero): la barrera, si la hay, está en la salida.
            for a in andenes:
                conexion(ves, a, "PASILLO", 10, 15)
            continue
        for d, a in zip(ln.direcciones, andenes, strict=True):
            conexion(ves, a, "ESCALERA_FIJA", 12, TIEMPO_ESCALERA_S,
                     escalones=ESCALONES_VESTIBULO_ANDEN)  # fmt: skip
            if plantilla.escaleras_electricas and (transbordo or ln.terminal):
                # Escalera eléctrica de subida (andén -> vestíbulo): sólo en un sentido.
                eq = equipo(f"{a}/ESC", "ESCALERA_ELECTRICA",
                            f"escalera eléctrica del andén Línea {ln.linea} dirección {d}",
                            ln.lat, ln.lon)  # fmt: skip
                conexion(a, ves, "ESCALERA_ELECTRICA", 12, TIEMPO_ESCALERA_ELECTRICA_S,
                         equipo_=eq, bidireccional=False)  # fmt: skip
        if central and len(andenes) > 1:
            for a, b in zip(andenes, andenes[1:], strict=False):
                conexion(a, b, "PASILLO", 10, 15)
        if accesible:
            if central:
                # Un elevador al andén central sirve a ambas direcciones: 1 equipo, N conexiones.
                eq = equipo(f"{c}/ELV-L{ln.linea}", "ELEVADOR",
                            f"elevador vestíbulo–andén central Línea {ln.linea}",
                            ln.lat, ln.lon)  # fmt: skip
                for a in andenes:
                    conexion(ves, a, "ELEVADOR", 5, TIEMPO_ELEVADOR_S, equipo_=eq)
            else:
                for d, a in zip(ln.direcciones, andenes, strict=True):
                    eq = equipo(f"{c}/ELV-L{ln.linea}-{normalizar_nombre(d)}", "ELEVADOR",
                                f"elevador al andén Línea {ln.linea} dirección {d}",
                                ln.lat, ln.lon)  # fmt: skip
                    conexion(ves, a, "ELEVADOR", 5, TIEMPO_ELEVADOR_S, equipo_=eq)

    # Salidas a la calle: se conectan al vestíbulo de la primera línea (orden alfanumérico).
    ves_salidas, ln0 = vestibulos[sorted(vestibulos)[0]]
    accesos = _accesos_resueltos(entrada, "COMPLETA" if accesible else "NINGUNA", plantilla)
    for i, (salida, acceso) in enumerate(accesos.items()):
        dlat, dlon = _desplazamiento(salida, i)
        lat, lon = ln0.lat + dlat, ln0.lon + dlon
        cal = nivel(f"{c}/SAL-{normalizar_nombre(salida)}", "CALLE", f"salida {salida}", lat, lon)
        if plantilla.escalera_siempre or acceso == "ESCALERA_FIJA":
            conexion(cal, ves_salidas, "ESCALERA_FIJA", 15, TIEMPO_ESCALERA_S,
                     escalones=plantilla.escalones_calle)  # fmt: skip
        if acceso == "ELEVADOR":
            eq = equipo(f"{cal}/ELV", "ELEVADOR", f"elevador salida {salida}", lat, lon)
            conexion(cal, ves_salidas, "ELEVADOR", 5, TIEMPO_ELEVADOR_S, equipo_=eq)
        elif acceso == "RAMPA":
            eq = equipo(f"{cal}/RMP", "RAMPA", f"rampa salida {salida}", lat, lon)
            conexion(cal, ves_salidas, "RAMPA", LONGITUD_RAMPA_M,
                     LONGITUD_RAMPA_M / VELOCIDAD_PASILLO_M_S, equipo_=eq,
                     pendiente=PENDIENTE_RAMPA_PCT)  # fmt: skip

    # Transbordo: pasillo entre vestíbulos de cada par de líneas.
    for (va, la), (vb, lb) in combinations([vestibulos[k] for k in sorted(vestibulos)], 2):
        longitud = max(
            LONGITUD_MIN_TRANSBORDO_M,
            FACTOR_RODEO_TRANSBORDO * distancia_m(la.lat, la.lon, lb.lat, lb.lon),
        )
        conexion(va, vb, "PASILLO", longitud, math.ceil(longitud / VELOCIDAD_PASILLO_M_S),
                 escalones=0 if accesible else ESCALONES_CALLE_VESTIBULO)  # fmt: skip


def generar_inventario(
    catalogo: list[EntradaCatalogo],
    lineas: dict[str, list[LineaEnEstacion]],
    wheelchair_gtfs: dict[str, int],
) -> Inventario:
    inv = Inventario()
    for entrada in catalogo:
        if entrada.clave not in lineas:
            raise ValueError(f"{entrada.clave}: ninguna línea del alcance pasa por esta estación")
        generar_estacion(inv, entrada, lineas[entrada.clave], wheelchair_gtfs.get(entrada.clave, 0))
    rutas = {clave: {ln.route_id for ln in lns} for clave, lns in lineas.items()}
    inv.conexiones.extend(transbordos_a_pie(inv.niveles, rutas))
    return inv


def transbordos_a_pie(niveles: list[dict], rutas_por_estacion: dict[str, set[str]]) -> list[dict]:
    """Conexiones por la calle entre salidas de estaciones cercanas que no comparten línea.

    Se unen todas las salidas de una estación con todas las de la otra que estén a menos de
    ``RADIO_TRANSBORDO_A_PIE_M``: así la persona puede salir por la que tenga elevador o
    rampa. Son tramos de banqueta (``PASILLO`` sin escalones); quien no puede caminar esa
    distancia los pierde por la restricción de distancia del perfil, no aquí.

    Dos estaciones que comparten una línea no se unen: entre ellas ya está el tren, y unir
    paradas consecutivas del Metrobús (a veces a menos de 300 m) sólo crearía atajos.
    """
    calles = sorted((n for n in niveles if n["tipo"] == "CALLE"), key=lambda n: n["lat"])
    # Barrido por latitud: sólo se comparan las salidas dentro de la franja del radio.
    franja = RADIO_TRANSBORDO_A_PIE_M / 111_000.0
    conexiones = []
    for i, a in enumerate(calles):
        for b in calles[i + 1 :]:
            if b["lat"] - a["lat"] > franja:
                break
            ea, eb = a["clave_estacion"], b["clave_estacion"]
            if ea == eb or rutas_por_estacion.get(ea, set()) & rutas_por_estacion.get(eb, set()):
                continue
            d = distancia_m(a["lat"], a["lon"], b["lat"], b["lon"])
            if d > RADIO_TRANSBORDO_A_PIE_M:
                continue
            longitud = max(LONGITUD_MIN_A_PIE_M, FACTOR_RODEO_TRANSBORDO * d)
            desde, hasta = sorted((a["codigo"], b["codigo"]))
            conexiones.append(
                dict(nivel_desde=desde, nivel_hasta=hasta, tipo="PASILLO", codigo_equipo=None,
                     bidireccional=True, escalones=0, pendiente_pct=0.0,
                     longitud_m=round(longitud, 1),
                     tiempo_s=math.ceil(longitud / VELOCIDAD_PASILLO_M_S), fuente=FUENTE)
            )  # fmt: skip
    conexiones.sort(key=lambda c: (c["nivel_desde"], c["nivel_hasta"]))
    return conexiones


# --------------------------------------------------------------------------- validación


def _sin_barreras(con: dict) -> bool:
    """Conexión transitable en silla de ruedas: sin escalones ni escaleras de ningún tipo."""
    return con["escalones"] == 0 and con["tipo"] not in ("ESCALERA_FIJA", "ESCALERA_ELECTRICA")


def alcanzables(
    niveles: pd.DataFrame, conexiones: pd.DataFrame, origenes: set[str], solo_sin_barreras: bool
) -> set[str]:
    """Niveles alcanzables desde ``origenes`` (BFS), respetando el sentido de cada conexión."""
    ady = defaultdict(set)
    for con in conexiones.to_dict("records"):
        if solo_sin_barreras and not _sin_barreras(con):
            continue
        ady[con["nivel_desde"]].add(con["nivel_hasta"])
        if con["bidireccional"]:
            ady[con["nivel_hasta"]].add(con["nivel_desde"])
    vistos, cola = set(origenes), deque(origenes)
    while cola:
        for v in ady[cola.popleft()] - vistos:
            vistos.add(v)
            cola.append(v)
    return vistos


def validar_inventario(
    niveles: pd.DataFrame, equipos: pd.DataFrame, conexiones: pd.DataFrame
) -> list[str]:
    """Errores de consistencia del inventario; lista vacía si todo está bien."""
    errores = []
    for nombre, df in (("niveles", niveles), ("equipos", equipos)):
        rep = df["codigo"][df["codigo"].duplicated()]
        errores += [f"{nombre}: código repetido {x}" for x in rep]
    for nombre, df in (("niveles", niveles), ("equipos", equipos)):
        largos = df["codigo"][df["codigo"].str.len() > LONGITUD_CODIGO]
        errores += [f"{nombre}: código de más de {LONGITUD_CODIGO} caracteres {x}" for x in largos]
    codigos_nivel, codigos_equipo = set(niveles["codigo"]), set(equipos["codigo"])
    errores += [f"nivel con tipo inválido: {x}" for x in
                niveles.loc[~niveles["tipo"].isin(cat.TIPOS_NIVEL), "codigo"]]  # fmt: skip
    errores += [f"equipo con tipo inválido: {x}" for x in
                equipos.loc[~equipos["tipo"].isin(cat.TIPOS_EQUIPO), "codigo"]]  # fmt: skip
    if not (niveles["fuente"] == FUENTE).all() or not (equipos["fuente"] == FUENTE).all():
        errores.append("todo el inventario generado debe tener fuente = DEMO")
    for con in conexiones.to_dict("records"):
        ref = f"{con['nivel_desde']} -> {con['nivel_hasta']}"
        for extremo in (con["nivel_desde"], con["nivel_hasta"]):
            if extremo not in codigos_nivel:
                errores.append(f"conexión {ref}: nivel inexistente {extremo}")
        sin_equipo = con["tipo"] in cat.TIPOS_CONEXION_SIN_EQUIPO
        tiene_equipo = isinstance(con["codigo_equipo"], str) and con["codigo_equipo"] != ""
        if sin_equipo == tiene_equipo:
            errores.append(f"conexión {ref}: tipo {con['tipo']} incompatible con su equipo")
        if tiene_equipo and con["codigo_equipo"] not in codigos_equipo:
            errores.append(f"conexión {ref}: equipo inexistente {con['codigo_equipo']}")

    # Topología: desde la calle se llega a cada andén y desde cada andén se vuelve a la calle.
    for clave, b in niveles.groupby("clave_estacion"):
        cods = set(b["codigo"])
        cx = conexiones[conexiones["nivel_desde"].isin(cods)]
        calles = set(b.loc[b["tipo"] == "CALLE", "codigo"])
        andenes = set(b.loc[b["tipo"] == "ANDEN", "codigo"])
        if not calles:
            errores.append(f"{clave}: sin salida a la calle")
            continue
        for a in andenes - alcanzables(b, cx, calles, solo_sin_barreras=False):
            errores.append(f"{clave}: andén {a} inalcanzable desde la calle")
        for a in andenes:
            if not calles & alcanzables(b, cx, {a}, solo_sin_barreras=False):
                errores.append(f"{clave}: desde {a} no se puede salir a la calle")
    return errores


def estaciones_sin_barreras(niveles: pd.DataFrame, conexiones: pd.DataFrame) -> dict[str, bool]:
    """Para cada estación: ¿todos sus andenes se alcanzan desde la calle sin escalones?"""
    resultado = {}
    for clave, b in niveles.groupby("clave_estacion"):
        cods = set(b["codigo"])
        cx = conexiones[conexiones["nivel_desde"].isin(cods)]
        calles = set(b.loc[b["tipo"] == "CALLE", "codigo"])
        andenes = set(b.loc[b["tipo"] == "ANDEN", "codigo"])
        resultado[clave] = andenes <= alcanzables(b, cx, calles, solo_sin_barreras=True)
    return resultado
