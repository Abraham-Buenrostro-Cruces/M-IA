"""Consulta por voz (F5-2, F5-3, D-24). Lógica pura: tipos y resolución de lugares.

Flujo: audio -> ``TranscriptorVoz`` -> texto -> ``InterpreteLenguaje`` -> ``Intencion``
(textos de origen y destino, restricciones) -> ``resolver`` -> lugares concretos o una
pregunta de aclaración. El módulo de voz **no calcula la ruta** (D-24): devuelve origen,
destino y restricciones, y la PWA llama a ``POST /rutas/plan`` con el perfil guardado en el
dispositivo. Así el perfil nunca entra al módulo de voz ni a las APIs de IA (regla 6).

La conversación no guarda estado en el servidor: cuando hace falta aclarar algo, la
respuesta trae lo ya resuelto (``Parcial``) y la PWA lo reenvía con la siguiente frase.
"""

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from app.dominio.estaciones import Lugar
from app.dominio.red import Punto, distancia_m

NOMBRE_SISTEMA_CORTO = {
    "METRO": "del Metro",
    "METROBUS": "del Metrobús",
    "TREN_LIGERO": "del Tren Ligero",
    "TREN_SUBURBANO": "del Tren Suburbano",
    "TREN_INTERURBANO": "del Tren El Insurgente",
}
OPCIONES_MAX = 4  # en voz, más de 4 opciones no se pueden recordar
# Estaciones con el mismo nombre en distintos sistemas a menos de esta distancia son el mismo
# nodo de transbordo (Buenavista, Tasqueña, El Rosario: 42 casos en el GTFS 2026-08-28): no
# se pregunta cuál, porque el motor considera todas las salidas cercanas a pie. Más lejos
# son lugares distintos y sí se pregunta (Viaducto: 3.3 km; Eje Central: 7.7 km; 13 casos).
MISMO_NODO_M = 600.0

# Palabras que nombran un sistema dentro de lo que se dijo ("Buenavista del Metrobús").
# El orden importa: "metrobus" antes que "metro".
PISTAS_SISTEMA = (
    ("tren ligero", "TREN_LIGERO"),
    ("suburbano", "TREN_SUBURBANO"),
    ("insurgente", "TREN_INTERURBANO"),
    ("interurbano", "TREN_INTERURBANO"),
    ("metrobus", "METROBUS"),
    ("metro", "METRO"),
)
_CONECTOR = r"(?:la|el|de|del|en|estacion|linea|tren)"
_CONECTORES_FINAL = re.compile(rf"(?:^|\s+)(?:{_CONECTOR}\s*)+$")
_CONECTORES_INICIO = re.compile(rf"^(?:{_CONECTOR}\s+)+|^{_CONECTOR}$")


@dataclass(frozen=True)
class Transcripcion:
    texto: str
    confianza: float
    simulada: bool = False  # True en RA_MODO=local: no se reconoció la voz de verdad


@dataclass(frozen=True)
class Restricciones:
    max_transbordos: int | None = None
    caminar_poco: bool = False


@dataclass(frozen=True)
class Intencion:
    """Lo que el intérprete entendió, todavía como texto (sin geocodificar)."""

    origen_texto: str | None = None
    destino_texto: str | None = None
    lugar_suelto: str | None = None  # un lugar sin "de"/"a": responde a una aclaración
    usar_ubicacion_origen: bool = False
    restricciones: Restricciones = field(default_factory=Restricciones)
    entendida: bool = True


@dataclass(frozen=True)
class Parcial:
    """Lo resuelto hasta ahora en la conversación (la PWA lo reenvía)."""

    origen: Lugar | None = None
    destino: Lugar | None = None
    usar_ubicacion_origen: bool = False
    restricciones: Restricciones = field(default_factory=Restricciones)
    campo: str | None = None  # qué se preguntó la última vez: "origen" | "destino"
    # El nombre que resultó ambiguo, para entender respuestas como "la del Metrobús".
    pendiente: str | None = None


@dataclass(frozen=True)
class Aclaracion:
    campo: str  # "origen" | "destino"
    pregunta: str
    opciones: list[Lugar] = field(default_factory=list)
    permite_ubicacion: bool = False  # para el origen: "desde mi ubicación"


@dataclass(frozen=True)
class ResultadoVoz:
    estado: str  # listo | aclaracion | no_entendido
    parcial: Parcial
    mensaje: str  # lo que la PWA lee en voz alta
    aclaracion: Aclaracion | None = None


def normalizar(texto: str) -> str:
    """'Taxqueña' -> 'tasquena'; minúsculas, sin acentos ni signos, espacios simples."""
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpio = re.sub(r"[^a-z0-9 ]+", " ", sin_acentos.lower())
    return " ".join("tasquena" if p == "taxquena" else p for p in limpio.split())


def _nombre_para_decir(lugar: Lugar) -> str:
    if lugar.tipo == "estacion" and lugar.clave_estacion:
        sistema = lugar.clave_estacion.split("-", 1)[0]
        return f"{lugar.nombre} {NOMBRE_SISTEMA_CORTO.get(sistema, '')}".strip()
    return lugar.nombre


def separar_sistema(texto: str) -> tuple[str, str | None]:
    """'Buenavista del Metrobús' -> ('buenavista', 'METROBUS'); sin pista -> (texto, None)."""
    t = normalizar(texto)
    for palabra, sistema in PISTAS_SISTEMA:
        if re.search(rf"\b{palabra}\b", t):
            antes, _, despues = t.partition(palabra)
            # Se quitan los conectores pegados a la pista ("la del", "estación de"), pero no
            # los que son parte del nombre: "La Raza del Metrobús" -> "la raza".
            antes = _CONECTORES_FINAL.sub("", antes.strip())
            despues = _CONECTORES_INICIO.sub("", despues.strip())
            return " ".join(f"{antes} {despues}".split()), sistema
    return t, None


def _resolver_lugar(
    texto: str, buscar: Callable[[str], list[Lugar]], pendiente: str | None = None
) -> tuple[Lugar | None, list[Lugar], str]:
    """(lugar elegido, opciones si hay que preguntar, nombre buscado).

    - Si se nombra un sistema ("del Metrobús"), sólo cuentan sus estaciones. Si después de
      quitar la pista no queda nombre, se usa ``pendiente`` (lo que se preguntó antes).
    - Si el nombre coincide exactamente con un solo candidato, se elige.
    - Si coincide con varios (Buenavista del Metro, del Metrobús y del Suburbano), se pregunta.
    - Si no coincide exactamente con ninguno: con un solo candidato se elige; con varios,
      se pregunta entre los primeros.
    """
    nombre, sistema = separar_sistema(texto)
    if sistema and not nombre and pendiente:
        nombre = pendiente
    nombre = nombre or normalizar(texto)
    candidatos = buscar(nombre)
    if sistema:
        del_sistema = [c for c in candidatos if (c.clave_estacion or "").startswith(sistema + "-")]
        candidatos = del_sistema or candidatos
    if not candidatos:
        return None, [], nombre
    consulta = normalizar(nombre)
    exactos = [c for c in candidatos if normalizar(c.nombre) == consulta]
    # Si ninguno coincide exacto, cuentan los que contienen todas las palabras dichas:
    # "centro médico siglo xxi" -> "Centro Médico Nacional Siglo XXI".
    palabras = set(consulta.split())
    contienen = [c for c in candidatos if palabras <= set(normalizar(c.nombre).split())]
    for grupo in (exactos, contienen):
        if len(grupo) == 1 or (grupo and _mismo_nodo(grupo)):
            return grupo[0], [], nombre
        if grupo:
            return None, grupo[:OPCIONES_MAX], nombre
    if len(candidatos) == 1:
        return candidatos[0], [], nombre
    return None, candidatos[:OPCIONES_MAX], nombre


def _mismo_nodo(lugares: list[Lugar]) -> bool:
    p0 = Punto(lugares[0].lat, lugares[0].lon)
    return all(distancia_m(p0, Punto(x.lat, x.lon)) <= MISMO_NODO_M for x in lugares[1:])


def _lista_hablada(opciones: list[Lugar]) -> str:
    nombres = [_nombre_para_decir(o) for o in opciones]
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " o " + nombres[-1]


def resolver(
    intencion: Intencion, buscar: Callable[[str], list[Lugar]], previo: Parcial | None = None
) -> ResultadoVoz:
    """Combina lo que se acaba de decir con lo ya resuelto y decide si falta algo.

    ``buscar`` es ``Geocodificador.buscar``: recibe sólo el texto del lugar, nunca el perfil.
    """
    previo = previo or Parcial()
    r = intencion.restricciones
    restricciones = Restricciones(
        r.max_transbordos
        if r.max_transbordos is not None
        else previo.restricciones.max_transbordos,
        r.caminar_poco or previo.restricciones.caminar_poco,
    )
    parcial = replace(previo, restricciones=restricciones, campo=None, pendiente=None)
    if intencion.usar_ubicacion_origen:
        parcial = replace(parcial, origen=None, usar_ubicacion_origen=True)

    # Un lugar suelto responde a lo último que se preguntó; sin pregunta previa, es el destino.
    origen_txt, destino_txt = intencion.origen_texto, intencion.destino_texto
    if intencion.lugar_suelto:
        if previo.campo == "origen":
            origen_txt = intencion.lugar_suelto
        else:
            destino_txt = intencion.lugar_suelto

    if not (intencion.entendida or origen_txt or destino_txt or intencion.usar_ubicacion_origen):
        return ResultadoVoz(
            "no_entendido", previo,
            "No entendí a dónde quieres ir. Puedes decir, por ejemplo: de Tasqueña al Zócalo.",
        )  # fmt: skip

    # Se resuelve todo lo que se dijo y luego se pregunta por lo primero que falló (destino
    # antes que origen): así no se pierde lo que sí quedó claro en la misma frase.
    duda: Aclaracion | None = None
    for campo, texto in (("destino", destino_txt), ("origen", origen_txt)):
        if not texto:
            continue
        pendiente = previo.pendiente if previo.campo == campo else None
        lugar, opciones, nombre = _resolver_lugar(texto, buscar, pendiente)
        if lugar is not None:
            parcial = replace(parcial, **{campo: lugar})
            if campo == "origen":
                parcial = replace(parcial, usar_ubicacion_origen=False)
            continue
        parcial = replace(parcial, **{campo: None})
        if duda is None:
            parcial = replace(parcial, campo=campo, pendiente=nombre)
            if not opciones:
                pregunta = f"No encontré «{texto}». ¿Puedes decir el nombre de otra forma?"
            else:
                pregunta = f"¿Te refieres a {_lista_hablada(opciones)}?"
            duda = Aclaracion(campo, pregunta, opciones, permite_ubicacion=campo == "origen")
    if duda is not None:
        return ResultadoVoz("aclaracion", parcial, duda.pregunta, duda)

    # Se pregunta primero el destino: es lo que la persona más necesita decir.
    if parcial.destino is None:
        pregunta = "¿A dónde quieres ir?"
        return ResultadoVoz(
            "aclaracion", replace(parcial, campo="destino"), pregunta,
            Aclaracion("destino", pregunta),
        )  # fmt: skip
    if parcial.origen is None and not parcial.usar_ubicacion_origen:
        pregunta = "¿Desde dónde sales? Puedes decir una estación o «desde mi ubicación»."
        return ResultadoVoz(
            "aclaracion", replace(parcial, campo="origen"), pregunta,
            Aclaracion("origen", pregunta, permite_ubicacion=True),
        )  # fmt: skip

    desde = "tu ubicación" if parcial.usar_ubicacion_origen else _nombre_para_decir(parcial.origen)
    extras = []
    if restricciones.max_transbordos == 0:
        extras.append("sin transbordos")
    elif restricciones.max_transbordos == 1:
        extras.append("con máximo un transbordo")
    elif restricciones.max_transbordos is not None:
        extras.append(f"con máximo {restricciones.max_transbordos} transbordos")
    if restricciones.caminar_poco:
        extras.append("caminando poco")
    cola = (", " + " y ".join(extras)) if extras else ""
    mensaje = f"Busco rutas de {desde} a {_nombre_para_decir(parcial.destino)}{cola}."
    return ResultadoVoz("listo", parcial, mensaje)
