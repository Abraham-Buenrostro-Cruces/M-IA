"""Construcción del grafo de la red (F2-1).

Dos capas:

1. **Topología** (``construir_topologia``): un ``MultiDiGraph`` que se arma una vez al
   arrancar. Es multigrafo porque entre dos niveles puede haber varias conexiones
   paralelas (la escalera fija y el elevador unen la misma salida con el mismo vestíbulo).

2. **Grafo por petición** (``grafo_para``): aplica las restricciones duras del perfil
   y los estados vigentes, agrega origen y destino, calcula w(e) y colapsa las aristas
   paralelas en la más barata. El resultado es un ``DiGraph`` simple, que es lo que
   requiere el algoritmo de Yen (``nx.shortest_simple_paths``).

Nodos:
- niveles del inventario (código del nivel);
- ``TREN|route_id|direccion|clave``: "a bordo" de un tren de esa línea y dirección
  detenido en esa estación. Separar el andén del "a bordo" permite cobrar la espera
  sólo al abordar y contar los abordajes (transbordos);
- ``ORIGEN`` y ``DESTINO``: puntos de la persona.
"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

import networkx as nx

from app.dominio.costo import PROB_NOMINAL, costo_min
from app.dominio.red import EstadoEquipo, Perfil, Red, Tramo
from app.dominio.restricciones import Exclusion, exclusion

ORIGEN, DESTINO = "ORIGEN", "DESTINO"


def nodo_tren(route_id: str, direccion: str, clave: str) -> str:
    return f"TREN|{route_id}|{direccion}|{clave}"


def construir_topologia(red: Red) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for n in red.niveles.values():
        g.add_node(n.codigo, nivel=n)

    for c in red.conexiones:
        est_desde = red.niveles[c.desde].clave_estacion
        est_hasta = red.niveles[c.hasta].clave_estacion
        if {est_desde, est_hasta} & red.estaciones_cerradas:
            continue
        datos = {
            "clase": "CONEXION",
            "conexion": c,
            "tiempo_s": c.tiempo_s,
            "longitud_m": c.longitud_m,
            "estacion": est_desde,
            # Transbordo por la calle entre dos estaciones (D-25): cuenta como caminata.
            "entre_estaciones": est_desde != est_hasta,
        }
        g.add_edge(c.desde, c.hasta, **datos)
        if c.bidireccional:
            g.add_edge(c.hasta, c.desde, **datos)

    andenes = {
        (n.clave_estacion, n.route_id, n.direccion): n.codigo
        for n in red.niveles.values()
        if n.tipo == "ANDEN"
    }
    for s in red.secuencias:
        linea = red.lineas[s.route_id]
        anterior = None
        for clave, tiempo in s.paradas:
            tren = nodo_tren(s.route_id, s.direccion, clave)
            g.add_node(tren, tren=(s.route_id, s.direccion, clave))
            if anterior is not None:
                g.add_edge(
                    anterior,
                    tren,
                    clase="VIAJAR",
                    tiempo_s=tiempo,
                    longitud_m=0.0,
                    route_id=s.route_id,
                    estacion=clave,
                )
            anden = andenes.get((clave, s.route_id, s.direccion))
            if anden and clave not in red.estaciones_cerradas:
                # Espera esperada H/2 con llegadas aleatorias de pasajeros (02 §4.2).
                g.add_edge(
                    anden,
                    tren,
                    clase="ABORDAR",
                    tiempo_s=linea.intervalo_s / 2,
                    longitud_m=0.0,
                    route_id=s.route_id,
                    direccion=s.direccion,
                    estacion=clave,
                )
                g.add_edge(
                    tren,
                    anden,
                    clase="BAJAR",
                    tiempo_s=0.0,
                    longitud_m=0.0,
                    route_id=s.route_id,
                    estacion=clave,
                )
            anterior = tren
    return g


@dataclass(frozen=True)
class Caminata:
    """Tramo a pie candidato entre ORIGEN/DESTINO y un nivel de calle (o entre ambos)."""

    desde: str
    hasta: str
    tramo: Tramo


@dataclass(frozen=True)
class Relajacion:
    """Qué restricciones se ignoran, sólo para diagnosticar (nunca para recomendar).

    - ``penalizar=True`` (obstáculos): cada arista relajada cuesta 10 000 min, así el
      camino usa el menor número posible de tramos prohibidos.
    - ``penalizar=False`` (ruta descartada): un equipo bloqueado por su estado cuesta como
      si funcionara; así se obtiene la ruta que *habría* ganado y se puede explicar por qué
      no se recomienda.
    """

    estados: bool = False
    fisicas: bool = False
    penalizar: bool = True


def grafo_para(
    topologia: nx.MultiDiGraph,
    perfil: Perfil,
    estados: dict[str, EstadoEquipo],
    ahora: datetime,
    caminatas: Iterable[Caminata],
    *,
    excluir_equipos: frozenset[str] = frozenset(),
    relajar: Relajacion = Relajacion(),
) -> nx.DiGraph:
    """DiGraph ponderado para un perfil. Cada arista guarda la arista original elegida
    (``arista``), si se relajó alguna restricción, la ``exclusion`` que se ignoró, y las
    ``opciones`` paralelas que cumplían las restricciones (para ``sin_equipos``)."""
    g = nx.DiGraph()
    g.add_nodes_from(topologia.nodes(data=True))
    g.add_node(ORIGEN)
    g.add_node(DESTINO)

    def considerar(u: str, v: str, datos: dict) -> None:
        conexion = datos.get("conexion")
        if conexion is not None and conexion.equipo in excluir_equipos:
            return
        exc = exclusion(datos, perfil, estados)
        if exc is not None and not (
            (exc.clase == "estado" and relajar.estados)
            or (exc.clase == "fisica" and relajar.fisicas)
        ):
            return
        if exc is not None and not relajar.penalizar and exc.equipo:
            nominal = {exc.equipo: EstadoEquipo("OPERATIVO", PROB_NOMINAL, ahora)}
            w = costo_min(datos, perfil, nominal, ahora)
        else:
            w = costo_min(datos, perfil, estados, ahora)
        if exc is not None and relajar.penalizar:
            w += 10_000.0  # una arista relajada sólo se usa si no hay otra opción
        if conexion is not None and conexion.equipo:
            # Índice equipo -> aristas, para que ``sin_equipos`` no recorra todo el grafo.
            g.graph.setdefault("por_equipo", {}).setdefault(conexion.equipo, set()).add((u, v))
        actual = g.get_edge_data(u, v)
        if actual is None:
            g.add_edge(u, v, w=w, arista=datos, exclusion=exc, opciones=[(w, datos, exc)])
        else:
            # Se guardan también las paralelas descartadas (p. ej. la escalera junto al
            # elevador): ``sin_equipos`` las usa para el plan B sin reconstruir el grafo.
            actual["opciones"].append((w, datos, exc))
            if w < actual["w"]:
                actual.update(w=w, arista=datos, exclusion=exc)

    estaticas, con_equipo = _partes_por_perfil(topologia, perfil, relajar)
    g.add_edges_from(
        (u, v, {"w": o[0][0], "arista": o[0][1], "exclusion": o[0][2], "opciones": list(o)})
        for (u, v), o in estaticas.items()
    )
    for u, v, datos in con_equipo:
        considerar(u, v, datos)
    for c in caminatas:
        datos = {
            "clase": "CAMINAR",
            "tiempo_s": c.tramo.distancia_m / perfil.velocidad_pie_m_s,
            "longitud_m": c.tramo.distancia_m,
            "tramo": c.tramo,
        }
        considerar(c.desde, c.hasta, datos)
    _podar_caminatas_dominadas(g)
    return g


# Parte del grafo que sólo depende del perfil (aristas sin equipo: escaleras, pasillos,
# viajes, abordajes). Es ~85 % de las aristas de la red completa y no cambia entre
# peticiones con el mismo perfil, así que se calcula una vez. Pocas entradas: los perfiles
# predefinidos son 5 y los personalizados suelen repetirse en una sesión.
_CACHE_PERFIL: dict[tuple, tuple] = {}
_CACHE_MAX = 16


def _partes_por_perfil(
    topologia: nx.MultiDiGraph, perfil: Perfil, relajar: Relajacion
) -> tuple[dict[tuple[str, str], list], list[tuple[str, str, dict]]]:
    """(aristas sin equipo ya filtradas y con peso, agrupadas por par y ordenadas por peso;
    aristas con equipo, que dependen del estado y se evalúan en cada petición)."""
    clave = (id(topologia), perfil, relajar)
    guardado = _CACHE_PERFIL.get(clave)
    if guardado is not None and guardado[0] is topologia:
        return guardado[1], guardado[2]
    estaticas: dict[tuple[str, str], list] = {}
    con_equipo = []
    for u, v, datos in topologia.edges(data=True):
        c = datos.get("conexion")
        if c is not None and c.equipo:
            con_equipo.append((u, v, datos))
            continue
        # Sin equipo, la exclusión y el costo no dependen de estados ni de la hora.
        exc = exclusion(datos, perfil, {})
        if exc is not None and not relajar.fisicas:
            continue
        w = costo_min(datos, perfil, {}, datetime.min)
        if exc is not None and relajar.penalizar:
            w += 10_000.0
        estaticas.setdefault((u, v), []).append((w, datos, exc))
    for opciones in estaticas.values():
        opciones.sort(key=lambda o: o[0])
    if len(_CACHE_PERFIL) >= _CACHE_MAX:
        _CACHE_PERFIL.pop(next(iter(_CACHE_PERFIL)))
    _CACHE_PERFIL[clave] = (topologia, estaticas, con_equipo)
    return estaticas, con_equipo


@contextmanager
def sin_equipos(g: nx.DiGraph, codigos: frozenset[str]) -> Iterator[nx.DiGraph]:
    """El mismo grafo, mientras dura el ``with``, como si ``codigos`` no existieran.

    Equivale a ``grafo_para(..., excluir_equipos=codigos)`` pero sin reconstruir las
    ~11 000 aristas de la red completa: sólo cambian las que usan esos equipos, que pasan a
    su mejor paralela (la escalera, si el perfil puede usarla) o desaparecen. Al salir se
    restauran. Es lo que hace barato el plan B de cada equipo crítico (F2-4).
    """
    cambios: list[tuple[str, str, dict]] = []
    indice = g.graph.get("por_equipo", {})
    pares = {e for cod in codigos for e in indice.get(cod, ())}
    for u, v in pares:
        if not g.has_edge(u, v):
            continue  # podada
        a = g[u][v]
        c = a["arista"].get("conexion")
        if c is None or c.equipo not in codigos:
            continue
        cambios.append((u, v, dict(a)))
        resto = [
            o for o in a["opciones"]
            if not ((oc := o[1].get("conexion")) and oc.equipo in codigos)
        ]  # fmt: skip
        if resto:
            w, datos, exc = min(resto, key=lambda o: o[0])
            a.update(w=w, arista=datos, exclusion=exc)
        else:
            g.remove_edge(u, v)
    try:
        yield g
    finally:
        for u, v, original in cambios:
            if g.has_edge(u, v):
                g[u][v].update(original)
            else:
                g.add_edge(u, v, **original)


def _podar_caminatas_dominadas(g: nx.DiGraph) -> None:
    """Quita los transbordos por la calle entre dos salidas a las que el origen (o desde
    las que el destino) ya llega caminando directo.

    "Origen → salida a → banqueta → salida b" nunca es mejor que "origen → salida b": las
    caminatas cumplen la desigualdad del triángulo (línea recta × el mismo factor de rodeo).
    Pero Yen sí enumera esas variantes, y con la red completa (D-25) agotaban los
    candidatos antes de llegar a una alternativa realmente distinta (99 caminos para 5
    firmas en Tasqueña → Museo de la Ciudad; 17 tras la poda).
    """
    cerca_origen = set(g.successors(ORIGEN))
    cerca_destino = set(g.predecessors(DESTINO))
    dominadas = [
        (u, v)
        for u, v, a in g.edges(data=True)
        if a["arista"].get("entre_estaciones")
        and ({u, v} <= cerca_origen or {u, v} <= cerca_destino)
    ]
    g.remove_edges_from(dominadas)


def exclusiones_en(g: nx.DiGraph, camino: list[str]) -> list[Exclusion]:
    """Restricciones relajadas que usa un camino (vacío si es un camino válido)."""
    return [
        g[u][v]["exclusion"]
        for u, v in zip(camino, camino[1:], strict=False)
        if g[u][v]["exclusion"] is not None
    ]
