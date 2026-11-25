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

from collections.abc import Iterable
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
    (``arista``) y, si se relajó alguna restricción, la ``exclusion`` que se ignoró."""
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
        actual = g.get_edge_data(u, v)
        if actual is None or w < actual["w"]:
            g.add_edge(u, v, w=w, arista=datos, exclusion=exc)

    for u, v, datos in topologia.edges(data=True):
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
