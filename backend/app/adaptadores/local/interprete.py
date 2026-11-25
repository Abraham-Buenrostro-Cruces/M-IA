"""InterpreteLenguaje local: reglas sobre el texto transcrito (RA_MODO=local, F5-2).

Determinista y sin red. En la nube lo sustituye Gemini con salida estructurada (04 §7.6);
ambos producen la misma ``Intencion``. Cubre las formas más comunes de pedir una ruta:

- "de X a Y", "desde X hasta Y", "del X al Y"
- "a Y desde X", "quiero ir a Y", "llévame al Y" (sin origen: se preguntará)
- "desde aquí / desde mi ubicación"
- "sin transbordos", "con un transbordo", "caminar poco"
- un lugar suelto ("Buenavista", "la del Metrobús"): responde a una aclaración
"""

import re

from app.dominio.voz import Intencion, Restricciones, normalizar

_A = r"(?:a|al|hasta|hacia|para)"
_DE = r"(?:de|del|desde)"
# Orden: primero la forma completa con origen y destino.
_DE_A = re.compile(rf"\b{_DE} (?P<o>.+?) {_A} (?P<d>.+)$")
_A_DESDE = re.compile(rf"\b{_A} (?P<d>.+?) desde (?P<o>.+)$")
_SOLO_A = re.compile(rf"\b{_A} (?P<d>.+)$")

_UBICACION = re.compile(r"\bdesde (?:aqui|aca|donde estoy|mi ubicacion|mi posicion)\b")
_SIN_TRANSBORDOS = re.compile(
    r"\bsin (?:hacer )?(?:transbordos?|cambiar de linea|cambios? de linea)\b"
)
_N_TRANSBORDOS = re.compile(
    r"\b(?:con )?(?:maximo |maximo de |a lo mas |solo )?(un|1|dos|2|tres|3) transbordos?\b"
)
_CAMINAR_POCO = re.compile(
    r"\b(?:caminar poco|caminando poco|poca caminata|sin caminar mucho|"
    r"no (?:quiero |puedo )?caminar mucho|caminar lo menos(?: posible)?)\b"
)
_NUMEROS = {"un": 1, "1": 1, "dos": 2, "2": 2, "tres": 3, "3": 3}

# Muletillas al inicio que no son parte de ningún lugar.
_INICIO = re.compile(
    r"^(?:(?:hola|oye|por favor|este)\s+)*"
    r"(?:(?:quiero|quisiera|necesito|me gustaria|voy|vamos)\s+)?"
    r"(?:(?:ir|llegar|viajar|moverme)\s+)?"
    r"(?:(?:llevame|como llego|como voy|como me voy|buscame una ruta|una ruta|ruta)\s+)?"
)
_RELLENO_FINAL = re.compile(r"\s+(?:por favor|pero|y|si se puede|gracias)\s*$")
_ESTACION = re.compile(r"^(?:(?:la|el)\s+)?(?:estacion|parada)\s+(?:de\s+)?")
# Frases que, solas, no piden nada: no se buscan como lugar.
_SIN_CONTENIDO = {"hola", "oye", "gracias", "por favor", "si", "no", "ok", "este", "bueno"}


def _limpiar_lugar(texto: str | None) -> str | None:
    if not texto:
        return None
    t = _ESTACION.sub("", texto)
    while True:
        nuevo = _RELLENO_FINAL.sub("", t).strip(" ,")
        if nuevo == t:
            break
        t = nuevo
    return t or None


class InterpreteReglas:
    def interpretar(self, texto: str) -> Intencion:
        t = normalizar(texto)
        ubicacion = bool(_UBICACION.search(t))
        t = _UBICACION.sub(" ", t)

        max_transbordos = None
        if _SIN_TRANSBORDOS.search(t):
            max_transbordos = 0
            t = _SIN_TRANSBORDOS.sub(" ", t)
        elif m := _N_TRANSBORDOS.search(t):
            max_transbordos = _NUMEROS[m.group(1)]
            t = _N_TRANSBORDOS.sub(" ", t)
        caminar_poco = bool(_CAMINAR_POCO.search(t))
        t = _CAMINAR_POCO.sub(" ", t)

        t = " ".join(t.split())
        t = _INICIO.sub("", t).strip()
        # Lo que queda tras quitar restricciones suele terminar en "pero", "y", "con"...
        t = re.sub(r"\s+(?:pero|y|con|sin)$", "", t).strip()
        restricciones = Restricciones(max_transbordos, caminar_poco)

        for patron in (_DE_A, _A_DESDE):
            if m := patron.search(t):
                return Intencion(
                    origen_texto=_limpiar_lugar(m.group("o")),
                    destino_texto=_limpiar_lugar(m.group("d")),
                    usar_ubicacion_origen=ubicacion,
                    restricciones=restricciones,
                )
        if m := _SOLO_A.search(t):
            return Intencion(
                destino_texto=_limpiar_lugar(m.group("d")),
                usar_ubicacion_origen=ubicacion,
                restricciones=restricciones,
            )
        suelto = _limpiar_lugar(t)
        if suelto in _SIN_CONTENIDO:
            suelto = None
        hay_algo = bool(suelto or ubicacion or max_transbordos is not None or caminar_poco)
        return Intencion(
            lugar_suelto=suelto,
            usar_ubicacion_origen=ubicacion,
            restricciones=restricciones,
            entendida=hay_algo,
        )
