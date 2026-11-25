"""Planificación de rutas accesibles (F2-3, F2-4, F2-6). Lógica pura.

Flujo de ``planear``:
1. Grafo filtrado por el perfil y los estados (restricciones duras).
2. Hasta 3 alternativas con Yen (``nx.shortest_simple_paths``), sin repetir "firma"
   (la misma secuencia de salidas, abordajes y bajadas con otra escalera interna no
   es una alternativa real para la persona).
3. Evaluación de cada alternativa: pasos legibles, equipos críticos, IAR, plan B.
4. Diagnóstico con restricciones relajadas (sólo para explicar, nunca para recomendar):
   la ruta que habría ganado sin los estados ("descartada") y, si no hay ruta, qué la
   bloquea.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from itertools import islice

import networkx as nx

from app.dominio.costo import prob_falla
from app.dominio.grafo import (
    DESTINO,
    ORIGEN,
    Caminata,
    Relajacion,
    exclusiones_en,
    grafo_para,
)
from app.dominio.red import EstadoEquipo, Perfil, Red
from app.dominio.restricciones import Exclusion, estado_de

K_ALTERNATIVAS = 3
CANDIDATOS_MAX = 40  # caminos de Yen a examinar para encontrar K firmas distintas
IAR_ACEPTABLE = 70.0


def categoria_iar(iar: float) -> str:
    return "alta" if iar >= 90 else "media" if iar >= 70 else "baja"


@dataclass(frozen=True)
class Paso:
    tipo: str  # caminar | equipo | pasillo | escalera | abordar | viajar | transbordo
    descripcion: str
    duracion_s: float
    estacion: str | None = None
    equipo: str | None = None


@dataclass(frozen=True)
class EquipoEnRuta:
    codigo: str
    tipo: str
    referencia: str
    estacion: str
    nombre_estacion: str
    estado: str
    prob_operativo: float
    actualizado_en: datetime | None
    horas_desde_verificacion: float | None


@dataclass(frozen=True)
class PlanB:
    equipo: str
    descripcion: str


@dataclass
class Alternativa:
    camino: list[str]
    costo: float
    pasos: list[Paso]
    equipos: list[EquipoEnRuta]
    iar: float
    tiempo_total_s: float
    distancia_pie_m: float
    abordajes: int
    resumen: str
    puntos: list[tuple[float, float]]
    planes_b: list[PlanB] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
    explicacion: str = ""

    @property
    def categoria(self) -> str:
        return categoria_iar(self.iar)

    @property
    def transbordos(self) -> int:
        return max(self.abordajes - 1, 0)


@dataclass(frozen=True)
class Descartada:
    resumen: str
    motivo: str
    tiempo_total_s: float


@dataclass(frozen=True)
class Obstaculo:
    estacion: str | None
    descripcion: str


@dataclass
class ResultadoPlan:
    hay_ruta_segura: bool
    alternativas: list[Alternativa]
    descartadas: list[Descartada]
    obstaculos: list[Obstaculo]
    aviso: str | None
    sugerencias: list[str]


# --------------------------------------------------------------------------- lectura de caminos


def _aristas(g: nx.DiGraph, camino: list[str]) -> list[tuple[str, str, dict]]:
    return [(u, v, g[u][v]["arista"]) for u, v in zip(camino, camino[1:], strict=False)]


def firma(g: nx.DiGraph, camino: list[str]) -> tuple:
    """Lo que distingue a dos rutas para la persona: por dónde entra, por dónde sale y
    qué líneas usa (sin repetir consecutivas).

    Con esta firma, "pasar de largo y regresar en la misma línea" no cuenta como otra
    alternativa, ni tampoco usar la escalera en vez del elevador dentro de una estación.
    """
    entrada = salida = None
    lineas: list[str] = []
    for u, v, a in _aristas(g, camino):
        if a["clase"] == "CAMINAR":
            if u == ORIGEN:
                entrada = v
            if v == DESTINO:
                salida = u
        elif a["clase"] == "ABORDAR" and (not lineas or lineas[-1] != a["route_id"]):
            lineas.append(a["route_id"])
    return (entrada, salida, tuple(lineas))


def _nombres(red: Red) -> dict[str, str]:
    return {n.clave_estacion: n.nombre_estacion for n in red.niveles.values()}


def construir_pasos(g: nx.DiGraph, red: Red, camino: list[str]) -> list[Paso]:
    """Pasos en lenguaje claro. Los tramos consecutivos en el mismo tren se agrupan."""
    nombres = _nombres(red)
    pasos: list[Paso] = []
    en_tren: dict | None = None  # {route_id, desde, n, t}
    for u, v, a in _aristas(g, camino):
        clase = a["clase"]
        if clase == "VIAJAR":
            en_tren["n"] += 1
            en_tren["t"] += a["tiempo_s"]
            continue
        if clase == "BAJAR" and en_tren is not None:
            linea = red.lineas[en_tren["route_id"]].nombre
            n = en_tren["n"]
            pasos.append(
                Paso(
                    "viajar",
                    f"Viaja {n} {'estación' if n == 1 else 'estaciones'} en la "
                    f"Línea {linea} y baja en {nombres.get(a['estacion'], a['estacion'])}",
                    en_tren["t"],
                    estacion=a["estacion"],
                )
            )
            en_tren = None
            continue
        if clase == "ABORDAR":
            linea = red.lineas[a["route_id"]].nombre
            tipo = "transbordo" if any(p.tipo == "viajar" for p in pasos) else "abordar"
            pasos.append(
                Paso(
                    tipo,
                    f"Aborda la Línea {linea} dirección {a['direccion']} en "
                    f"{nombres.get(a['estacion'], a['estacion'])}",
                    a["tiempo_s"],
                    estacion=a["estacion"],
                )
            )
            en_tren = {"route_id": a["route_id"], "n": 0, "t": 0.0}
            continue
        if clase == "CAMINAR":
            d = a["longitud_m"]
            if u == ORIGEN and v == DESTINO:
                texto = f"Camina {d:.0f} m hasta tu destino"
            elif u == ORIGEN:
                n = red.niveles[v]
                texto = f"Camina {d:.0f} m hasta la {n.referencia} de {n.nombre_estacion}"
            else:
                n = red.niveles[u]
                texto = f"Sal por la {n.referencia} y camina {d:.0f} m hasta tu destino"
            pasos.append(Paso("caminar", texto, a["tiempo_s"]))
            continue
        c = a["conexion"]
        destino = red.niveles[v]
        if c.equipo:
            eq = red.equipos[c.equipo]
            pasos.append(
                Paso(
                    "equipo",
                    f"Usa el {eq.referencia} hacia el {_lugar(destino)}",
                    c.tiempo_s,
                    estacion=destino.clave_estacion,
                    equipo=c.equipo,
                )
            )
        elif c.tipo == "PASILLO":
            pasos.append(
                Paso(
                    "pasillo",
                    f"Recorre el pasillo ({c.longitud_m:.0f} m) hacia el {_lugar(destino)}",
                    c.tiempo_s,
                    estacion=destino.clave_estacion,
                )
            )
        else:
            pasos.append(
                Paso(
                    "escalera",
                    f"Usa la escalera ({c.escalones} escalones) hacia el {_lugar(destino)}",
                    c.tiempo_s,
                    estacion=destino.clave_estacion,
                )
            )
    return pasos


def _lugar(n) -> str:
    if n.tipo == "ANDEN":
        return n.referencia
    if n.tipo == "CALLE":
        return f"exterior ({n.referencia})"
    return n.referencia


def resumen(g: nx.DiGraph, red: Red, camino: list[str]) -> str:
    """'Línea 2 de Tasqueña a Pino Suárez, salida José María Izazaga'."""
    nombres = _nombres(red)
    viajes, sube, salida = [], None, None
    for u, v, a in _aristas(g, camino):
        if a["clase"] == "ABORDAR":
            sube = (a["route_id"], a["estacion"])
        elif a["clase"] == "BAJAR" and sube:
            linea = red.lineas[sube[0]].nombre
            viajes.append(f"Línea {linea} de {nombres[sube[1]]} a {nombres[a['estacion']]}")
            sube = None
        elif a["clase"] == "CAMINAR" and v == DESTINO and u != ORIGEN:
            salida = red.niveles[u].referencia
    if not viajes:
        return "Trayecto a pie"
    texto = ", luego ".join(viajes)
    return f"{texto}, {salida}" if salida else texto


def equipos_de(
    g: nx.DiGraph, red: Red, camino: list[str], estados: dict[str, EstadoEquipo], ahora: datetime
) -> list[EquipoEnRuta]:
    """Equipos distintos del camino, en orden de uso (un elevador usado dos veces cuenta una)."""
    vistos: dict[str, EquipoEnRuta] = {}
    nombres = _nombres(red)
    for _, _, a in _aristas(g, camino):
        c = a.get("conexion")
        if c is None or not c.equipo or c.equipo in vistos:
            continue
        eq, est = red.equipos[c.equipo], estado_de(c.equipo, estados)
        horas = None
        if est.actualizado_en is not None:
            horas = round((ahora - est.actualizado_en).total_seconds() / 3600.0, 1)
        vistos[c.equipo] = EquipoEnRuta(
            codigo=eq.codigo,
            tipo=eq.tipo,
            referencia=eq.referencia,
            estacion=eq.clave_estacion,
            nombre_estacion=nombres.get(eq.clave_estacion, ""),
            estado=est.estado,
            prob_operativo=est.prob_operativo,
            actualizado_en=est.actualizado_en,
            horas_desde_verificacion=horas,
        )
    return list(vistos.values())


def iar(equipos: list[EquipoEnRuta]) -> float:
    """IAR = 100·Π(1 - p_k) sobre equipos distintos (02 §4.2)."""
    p_exito = math.prod(1.0 - prob_falla(EstadoEquipo(e.estado, e.prob_operativo)) for e in equipos)
    return round(100.0 * p_exito, 1)


def _puntos(red: Red, camino: list[str], origen, destino) -> list[tuple[float, float]]:
    """Polilínea aproximada para el mapa: origen, niveles y destino en orden."""
    puntos = [(origen.lat, origen.lon)]
    for nodo in camino:
        n = red.niveles.get(nodo)
        if n is not None and (not puntos or puntos[-1] != (n.lat, n.lon)):
            puntos.append((n.lat, n.lon))
    puntos.append((destino.lat, destino.lon))
    return puntos


# --------------------------------------------------------------------------- planificación


@dataclass(frozen=True)
class Peticion:
    perfil: Perfil
    origen: object  # Punto
    destino: object  # Punto
    caminatas: tuple[Caminata, ...]
    ahora: datetime


def _evaluar(g, red, camino, estados, pet: Peticion) -> Alternativa:
    aristas = _aristas(g, camino)
    equipos = equipos_de(g, red, camino, estados, pet.ahora)
    alt = Alternativa(
        camino=camino,
        costo=nx.path_weight(g, camino, "w"),
        pasos=construir_pasos(g, red, camino),
        equipos=equipos,
        iar=iar(equipos),
        tiempo_total_s=sum(a["tiempo_s"] for _, _, a in aristas),
        distancia_pie_m=sum(
            a["longitud_m"]
            for _, _, a in aristas
            if a["clase"] == "CAMINAR" or (a.get("conexion") and a["conexion"].tipo == "PASILLO")
        ),
        abordajes=sum(1 for _, _, a in aristas if a["clase"] == "ABORDAR"),
        resumen=resumen(g, red, camino),
        puntos=_puntos(red, camino, pet.origen, pet.destino),
    )
    for e in equipos:
        if e.estado == "FALLA_PROBABLE":
            alt.advertencias.append(
                f"Hay un reporte reciente de falla en el {e.referencia} de {e.nombre_estacion}."
            )
        elif e.horas_desde_verificacion is not None and e.horas_desde_verificacion >= 24:
            alt.advertencias.append(
                f"El {e.referencia} de {e.nombre_estacion} no se verifica desde hace "
                f"{e.horas_desde_verificacion:.0f} h."
            )
    if alt.iar < IAR_ACEPTABLE:
        alt.advertencias.insert(0, "Riesgo alto: es probable encontrar una barrera en esta ruta.")
    return alt


def alternativas(g: nx.DiGraph, max_transbordos: int | None, k: int = K_ALTERNATIVAS):
    """Hasta k caminos de menor costo con firmas distintas (Yen)."""
    if ORIGEN not in g or DESTINO not in g or not nx.has_path(g, ORIGEN, DESTINO):
        return []
    elegidos, firmas = [], set()
    for camino in islice(nx.shortest_simple_paths(g, ORIGEN, DESTINO, weight="w"), CANDIDATOS_MAX):
        if exclusiones_en(g, camino):
            break  # sólo en grafos relajados: desde aquí todo viola alguna restricción
        if max_transbordos is not None:
            abordajes = sum(
                1
                for u, v in zip(camino, camino[1:], strict=False)
                if g[u][v]["arista"]["clase"] == "ABORDAR"
            )
            if abordajes - 1 > max_transbordos:
                continue
        f = firma(g, camino)
        if f in firmas:
            continue
        firmas.add(f)
        elegidos.append(camino)
        if len(elegidos) == k:
            break
    return elegidos


def _plan_b(red, topologia, pet, estados, alt: Alternativa, g: nx.DiGraph) -> list[PlanB]:
    """Para cada equipo crítico: la mejor continuación si ese equipo no funciona.

    Se recalcula desde el punto donde se usaría el equipo. Si ese punto es la calle
    (el acceso de la estación de origen), se recalcula desde el ORIGEN: la persona
    puede caminar a otra entrada.
    """
    planes = []
    for e in alt.equipos:
        sin_equipo = grafo_para(
            topologia,
            pet.perfil,
            estados,
            pet.ahora,
            pet.caminatas,
            excluir_equipos=frozenset({e.codigo}),
        )
        idx = next(
            i
            for i, (u, v) in enumerate(zip(alt.camino, alt.camino[1:], strict=False))
            if (c := g[u][v]["arista"].get("conexion")) and c.equipo == e.codigo
        )
        inicio = alt.camino[idx]
        if red.niveles.get(inicio) is not None and red.niveles[inicio].tipo == "CALLE":
            inicio = ORIGEN
        try:
            resto = nx.shortest_path(sin_equipo, inicio, DESTINO, weight="w")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            planes.append(
                PlanB(
                    e.codigo,
                    f"Si el {e.referencia} de {e.nombre_estacion} no "
                    "funciona, no hay alternativa accesible desde ese punto: pide "
                    "apoyo al personal de la estación.",
                )
            )
            continue
        pasos = [
            p
            for p in construir_pasos(sin_equipo, red, resto)
            if p.tipo in ("equipo", "viajar", "abordar", "transbordo", "caminar")
        ]
        detalle = "; ".join(p.descripcion[0].lower() + p.descripcion[1:] for p in pasos[:3])
        planes.append(
            PlanB(e.codigo, f"Si el {e.referencia} de {e.nombre_estacion} no funciona: {detalle}.")
        )
    return planes


def _describir_exclusion(red: Red, exc: Exclusion, nombres: dict[str, str]) -> str:
    if exc.equipo:
        eq = red.equipos[exc.equipo]
        return f"el {eq.referencia} de {nombres.get(eq.clave_estacion, '')} tiene {exc.motivo}"
    return exc.motivo


def _obstaculos(g_relajado, red, camino) -> list[Obstaculo]:
    nombres = _nombres(red)
    vistos, obst = set(), []
    for u, v in zip(camino, camino[1:], strict=False):
        exc = g_relajado[u][v]["exclusion"]
        if exc is None:
            continue
        estacion = g_relajado[u][v]["arista"].get("estacion")
        texto = _describir_exclusion(red, exc, nombres)
        if estacion and not exc.equipo:
            texto = f"{nombres.get(estacion, estacion)}: {texto}"
        if texto not in vistos:
            vistos.add(texto)
            obst.append(Obstaculo(estacion, texto))
    return obst


def planear(
    red: Red,
    topologia: nx.MultiDiGraph,
    estados: dict[str, EstadoEquipo],
    pet: Peticion,
) -> ResultadoPlan:
    """``topologia`` = ``construir_topologia(red)``; se recibe ya construida porque es
    estática y el servicio la reutiliza entre peticiones."""
    g = grafo_para(topologia, pet.perfil, estados, pet.ahora, pet.caminatas)
    caminos = alternativas(g, pet.perfil.max_transbordos)
    alts = [_evaluar(g, red, c, estados, pet) for c in caminos]
    # Orden final: primero por IAR aceptable, luego por costo. El ranking sólo reordena
    # rutas que ya pasaron las restricciones duras (regla de seguridad 3).
    alts.sort(key=lambda a: (a.iar < IAR_ACEPTABLE, a.costo))

    nombres = _nombres(red)
    descartadas: list[Descartada] = []
    g_estados = grafo_para(
        topologia,
        pet.perfil,
        estados,
        pet.ahora,
        pet.caminatas,
        relajar=Relajacion(estados=True, penalizar=False),
    )
    if nx.has_path(g_estados, ORIGEN, DESTINO):
        mejor = nx.shortest_path(g_estados, ORIGEN, DESTINO, weight="w")
        bloqueos = exclusiones_en(g_estados, mejor)
        firmas = {firma(g, a.camino) for a in alts}
        if bloqueos and firma(g_estados, mejor) not in firmas:
            motivo = "; ".join(_describir_exclusion(red, b, nombres) for b in bloqueos)
            tiempo = sum(
                g_estados[u][v]["arista"]["tiempo_s"]
                for u, v in zip(mejor, mejor[1:], strict=False)
            )
            descartadas.append(Descartada(resumen(g_estados, red, mejor), motivo, tiempo))

    for a in alts:
        a.planes_b = _plan_b(red, topologia, pet, estados, a, g)
        a.explicacion = _explicar(a, alts[0], descartadas)

    if alts and alts[0].iar >= IAR_ACEPTABLE:
        return ResultadoPlan(True, alts, descartadas, [], None, [])

    # Sin ruta segura (F2-6, regla de seguridad 5): se dice explícitamente.
    obstaculos: list[Obstaculo] = []
    sugerencias: list[str] = []
    if not alts:
        g_bloqueos = grafo_para(
            topologia,
            pet.perfil,
            estados,
            pet.ahora,
            pet.caminatas,
            relajar=Relajacion(estados=True),
        )
        if nx.has_path(g_bloqueos, ORIGEN, DESTINO):
            camino = nx.shortest_path(g_bloqueos, ORIGEN, DESTINO, weight="w")
            obstaculos = _obstaculos(g_bloqueos, red, camino)
            sugerencias.append(
                "El estado de los equipos cambia con los reportes: vuelve a "
                "consultar más tarde o reporta si el equipo ya funciona."
            )
        else:
            g_todo = grafo_para(
                topologia,
                pet.perfil,
                estados,
                pet.ahora,
                pet.caminatas,
                relajar=Relajacion(estados=True, fisicas=True),
            )
            if nx.has_path(g_todo, ORIGEN, DESTINO):
                camino = nx.shortest_path(g_todo, ORIGEN, DESTINO, weight="w")
                obstaculos = _obstaculos(g_todo, red, camino)
                sugerencias.append(
                    "El trayecto exige pasar por tramos que tu perfil no puede "
                    "recorrer. Considera un destino cercano en la misma línea o "
                    "pedir asistencia al personal del Metro."
                )
            else:
                sugerencias.append(
                    "No hay estaciones del corredor piloto al alcance a pie del "
                    "origen o del destino con tu perfil."
                )
        aviso = "No encontramos una ruta segura para tu perfil."
    else:
        aviso = (
            f"La mejor ruta disponible tiene un IAR de {alts[0].iar:.0f}: hay riesgo alto "
            "de encontrar una barrera."
        )
        sugerencias.append("Revisa los equipos críticos y su plan B antes de salir.")
    return ResultadoPlan(False, alts, descartadas, obstaculos, aviso, sugerencias)


def _explicar(alt: Alternativa, mejor: Alternativa, descartadas: list[Descartada]) -> str:
    partes = [f"IAR {alt.iar:.0f} ({alt.categoria})."]
    if alt.equipos:
        menos = min(alt.equipos, key=lambda e: e.prob_operativo)
        partes.append(
            f"Usa {len(alt.equipos)} {'equipo' if len(alt.equipos) == 1 else 'equipos'}; el de "
            f"menor confianza es el {menos.referencia} de {menos.nombre_estacion} "
            f"({100 * menos.prob_operativo:.0f} % de probabilidad de que funcione)."
        )
    else:
        partes.append("No depende de ningún equipo.")
    if alt is mejor:
        if descartadas:
            d = descartadas[0]
            extra = (alt.tiempo_total_s - d.tiempo_total_s) / 60
            partes.append(f"Evita la ruta {d.resumen} porque {d.motivo}.")
            if extra >= 1:
                partes.append(f"Toma unos {extra:.0f} min más que esa ruta.")
    else:
        dif = (alt.tiempo_total_s - mejor.tiempo_total_s) / 60
        if abs(dif) >= 1:
            partes.append(f"{abs(dif):.0f} min {'más' if dif > 0 else 'menos'} que la recomendada.")
    return " ".join(partes)
