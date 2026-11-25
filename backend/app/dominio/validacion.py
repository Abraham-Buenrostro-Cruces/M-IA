"""Puntaje de confianza s de un reporte (F4-3; documento 04 §7.3). Lógica pura.

    s = 0.45·visual + 0.25·geo + 0.15·reputación + 0.15·corroboración − penalizaciones

Los pesos se fijan a mano en el MVP; cuando haya reportes revisados por moderadores se
aprenden con una regresión logística (IA-2). El desglose se guarda con el reporte para
explicar la decisión y para entrenar ese modelo después.
"""

from dataclasses import asdict, dataclass

W_VISUAL, W_GEO, W_REPUTACION, W_CORROBORACION = 0.45, 0.25, 0.15, 0.15
PENALIZACION_DUPLICADO = 0.5  # foto ya usada (hash exacto o perceptual)
PENALIZACION_FOTO_VIEJA = 0.2  # EXIF con fecha de captura muy anterior al reporte
RADIO_GEOCERCA_M = 150.0  # a esta distancia o menos, geo = 1
RADIO_MAXIMO_M = 500.0  # a partir de aquí, geo = 0 (lineal entre ambos)

UMBRAL_VERIFICADO = 0.75
UMBRAL_CORROBORACION = 0.40


@dataclass(frozen=True)
class AnalisisImagen:
    """Salida del puerto AnalizadorImagen: Vision API + Gemini (04 §7.3) o el simulado."""

    tipo_equipo_visible: str  # elevador | rampa | escaleras | otro | ninguno
    problema_visible: str  # fuera_de_servicio | bloqueado | danado | sin_problema | indeterminado
    senales_textuales: tuple[str, ...]
    confianza: float
    contenido_apropiado: bool = True  # SafeSearch
    rostros: tuple[tuple[int, int, int, int], ...] = ()  # cajas (x, y, ancho, alto) en píxeles


@dataclass(frozen=True)
class Desglose:
    visual: float
    geo: float
    reputacion: float
    corroboracion: float
    penalizaciones: float
    s: float
    estado_validacion: str
    motivos: tuple[str, ...]

    def como_dict(self) -> dict:
        return asdict(self)


def coincide(tipo_problema: str, analisis: AnalisisImagen) -> bool:
    """¿La foto respalda lo que la persona reporta?"""
    if analisis.problema_visible == "indeterminado":
        return False
    if tipo_problema == "funciona":
        return analisis.problema_visible == "sin_problema"
    return analisis.problema_visible != "sin_problema"


def termino_visual(tipo_problema: str, analisis: AnalisisImagen | None) -> float:
    if analisis is None:
        return 0.0
    if analisis.problema_visible == "indeterminado":
        # Foto que el análisis no puede interpretar: aporta algo (alguien estuvo ahí y tomó
        # una foto), pero nunca basta por sí sola para verificar.
        return 0.5 * analisis.confianza
    return analisis.confianza if coincide(tipo_problema, analisis) else 0.0


def termino_geo(distancia_m: float | None) -> float:
    if distancia_m is None:
        return 0.0
    if distancia_m <= RADIO_GEOCERCA_M:
        return 1.0
    if distancia_m >= RADIO_MAXIMO_M:
        return 0.0
    return 1.0 - (distancia_m - RADIO_GEOCERCA_M) / (RADIO_MAXIMO_M - RADIO_GEOCERCA_M)


def termino_corroboracion(confirma: int, niega: int) -> float:
    """Fracción de votos que confirman, atenuada si hay pocos votos (1 voto vale la mitad)."""
    total = confirma + niega
    if total == 0:
        return 0.0
    return (confirma / total) * min(1.0, total / 2)


def clasificar(s: float) -> str:
    if s >= UMBRAL_VERIFICADO:
        return "VERIFICADO_AUTO"
    if s >= UMBRAL_CORROBORACION:
        return "PENDIENTE_CORROBORACION"
    return "BAJA_CONFIANZA"


def puntaje(
    tipo_problema: str,
    analisis: AnalisisImagen | None,
    distancia_m: float | None,
    reputacion: float,
    votos_confirma: int = 0,
    votos_niega: int = 0,
    duplicada: bool = False,
    foto_vieja: bool = False,
) -> Desglose:
    motivos = []
    if analisis is not None and not analisis.contenido_apropiado:
        return Desglose(0, 0, 0, 0, 0, 0.0, "RECHAZADO", ("contenido inapropiado en la foto",))

    visual = termino_visual(tipo_problema, analisis)
    geo = termino_geo(distancia_m)
    corro = termino_corroboracion(votos_confirma, votos_niega)
    penal = (PENALIZACION_DUPLICADO if duplicada else 0) + (
        PENALIZACION_FOTO_VIEJA if foto_vieja else 0
    )
    if analisis is None:
        motivos.append("sin foto")
    elif visual == 0:
        motivos.append("la foto no respalda el reporte")
    if distancia_m is None:
        motivos.append("sin ubicación")
    elif geo < 1:
        motivos.append(f"reportado a {distancia_m:.0f} m de la estación")
    if duplicada:
        motivos.append("foto ya usada en otro reporte")
    if foto_vieja:
        motivos.append("la foto no es reciente")

    s = W_VISUAL * visual + W_GEO * geo + W_REPUTACION * reputacion + W_CORROBORACION * corro
    s = round(min(max(s - penal, 0.0), 1.0), 3)
    return Desglose(
        round(visual, 3), round(geo, 3), round(reputacion, 3), round(corro, 3), penal, s,
        clasificar(s), tuple(motivos),
    )  # fmt: skip


def reputacion(confirmados: int, rechazados: int) -> float:
    """Media de una Beta(1, 1) actualizada con las decisiones de moderación."""
    return (confirmados + 1) / (confirmados + rechazados + 2)
