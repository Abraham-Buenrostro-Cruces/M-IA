"""Costo aditivo w(e) en minutos equivalentes (F2-3; docs/arquitectura/02 §4.2, D-20).

    w(e) = λ·Σ -ln(1 - p_k) + α·t_e + β·abordaje_e + γ·d_pie_e + δ·u_e

Por qué -ln(1-p): P_éxito(r) = Π(1 - p_k) es un producto; su logaritmo negativo es
una suma por arista, y minimizar esa suma con Dijkstra/Yen maximiza P_éxito.
"""

import math
from datetime import datetime

from app.dominio.red import EstadoEquipo, Perfil
from app.dominio.restricciones import estado_de

ALFA_POR_MIN = 1.0  # α: un minuto de tiempo cuesta un minuto
BETA_ABORDAJE_MIN = 3.0  # β: cada abordaje (incluye el primero; ver 02 §4.2)
GAMMA_POR_100M = 1.0  # γ: esfuerzo de caminar, además de su tiempo
DELTA_INCERTIDUMBRE_MIN = 10.0  # δ: dato con 24 h o más sin verificación
VIGENCIA_VERIFICACION_H = 24.0
P_MAX = 0.999  # evita -ln(0) = ∞ si un estimador devolviera p = 1
# Probabilidad de funcionamiento "típica" con la que se evalúa un equipo bloqueado al
# reconstruir la ruta que se habría recomendado si estuviera operativo (ruta descartada).
PROB_NOMINAL = 0.98


def prob_falla(estado: EstadoEquipo) -> float:
    return min(max(1.0 - estado.prob_operativo, 0.0), P_MAX)


def incertidumbre(estado: EstadoEquipo, ahora: datetime) -> float:
    """u_e ∈ [0, 1]: crece linealmente con las horas desde la última verificación."""
    if estado.actualizado_en is None:
        return 1.0
    horas = max((ahora - estado.actualizado_en).total_seconds() / 3600.0, 0.0)
    return min(horas / VIGENCIA_VERIFICACION_H, 1.0)


def costo_min(
    arista: dict, perfil: Perfil, estados: dict[str, EstadoEquipo], ahora: datetime
) -> float:
    clase = arista["clase"]
    costo = ALFA_POR_MIN * arista["tiempo_s"] / 60.0
    if clase == "ABORDAR":
        costo += BETA_ABORDAJE_MIN
    if clase == "CAMINAR" or (
        clase == "CONEXION" and arista["conexion"].tipo in ("PASILLO", "RAMPA")
    ):
        costo += GAMMA_POR_100M * arista["longitud_m"] / 100.0
    if clase == "CONEXION" and arista["conexion"].equipo:
        estado = estado_de(arista["conexion"].equipo, estados)
        costo += perfil.lambda_seguridad * -math.log(1.0 - prob_falla(estado))
        costo += DELTA_INCERTIDUMBRE_MIN * incertidumbre(estado, ahora)
    return costo
