"""Estimador del estado de un equipo (F4-4; documento 04 §7.4, D-21, D-22). Lógica pura.

Dos salidas complementarias:

1. **Estado discreto** (OPERATIVO, FALLA_PROBABLE, ...): se obtiene *reproduciendo* la
   evidencia en orden cronológico sobre una máquina de estados con **umbrales
   asimétricos**. Así el resultado no depende del orden en que llegaron los mensajes al
   sistema, y quitar una evidencia (p. ej. un reporte que el moderador rechaza) se
   resuelve volviendo a reproducir sin ella.

2. **Probabilidad de que funcione** p = E[θ] con θ ~ Beta(α, β): *prior* débil más la
   evidencia ponderada por su confianza y **olvidada** con vidas medias distintas: la
   evidencia de "funciona" se olvida más rápido que la de falla, porque un equipo puede
   descomponerse en cualquier momento y una reparación suele tardar días.

Transiciones (D-22 completa la tabla de 04 §7.4):

- cualquiera -> lo que diga un **aviso** (OFICIAL, MODERADOR o DEMO).
- OPERATIVO o DESCONOCIDO -> FALLA_PROBABLE: un reporte de falla con s >= 0.40.
- FALLA_PROBABLE -> FALLA_CONFIRMADA: 2 personas distintas en 24 h, una con foto verificada.
- FALLA_PROBABLE -> OPERATIVO: un "funciona" con foto verificada (o rechazo del reporte,
  que se resuelve reproduciendo sin él).
- FALLA_CONFIRMADA -> OPERATIVO: 2 personas distintas en 24 h con "funciona" y foto verificada.
- DESCONOCIDO -> OPERATIVO: un "funciona" con foto verificada.
- MANTENIMIENTO: sólo un aviso lo cambia.
- cualquiera -> DESCONOCIDO: 7 días sin evidencia.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

# --- Parámetros (D-22) ---------------------------------------------------------------
P_FALLA_PRIOR = 0.05  # sin predicción de ML todavía (llega en F7 como prior por franja)
FUERZA_PRIOR = 4.0  # m: el prior "vale" como 4 observaciones
PESO_FALLA = 3.0  # un reporte de falla con confianza s suma 3·s a β
PESO_OK = 2.0  # un reporte de "funciona" suma 2·s a α
PESO_AVISO = 20.0
VIDA_MEDIA_FALLA_H = 72.0
VIDA_MEDIA_OK_H = 24.0
VIGENCIA = timedelta(days=7)
VENTANA_CORROBORACION = timedelta(hours=24)
UMBRAL_REPORTE = 0.40  # s mínimo para que un reporte cuente como evidencia
UMBRAL_FOTO_VERIFICADA = 0.75  # s mínimo (con foto) para "foto verificada"
CONFIANZA_VOTO = 0.5  # un voto de corroboración es evidencia sin foto de confianza media

# Tipos de evidencia.
FALLA, FUNCIONA, AVISO = "falla", "funciona", "aviso"


@dataclass(frozen=True)
class Evidencia:
    tipo: str  # FALLA | FUNCIONA | AVISO
    momento: datetime
    confianza: float = 1.0  # s del reporte (avisos: 1)
    persona: str | None = None  # id de quien reporta o vota
    con_foto_verificada: bool = False
    estado_aviso: str | None = None  # sólo avisos
    causa: str = "reporte"  # para historial_estado: reporte | voto | oficial | moderador | demo

    @property
    def cuenta(self) -> bool:
        """Los avisos siempre cuentan; los reportes, sólo con s suficiente."""
        return self.tipo == AVISO or self.confianza >= UMBRAL_REPORTE


@dataclass(frozen=True)
class EstadoCalculado:
    estado: str
    prob_operativo: float
    alfa: float
    beta: float
    masa_evidencia: float  # α + β - m: cuánta evidencia (olvidada) respalda la estimación
    ultima_evidencia: datetime | None
    causa: str  # qué produjo el último cambio de estado


def _decaimiento(horas: float, vida_media_h: float) -> float:
    return 0.5 ** (max(horas, 0.0) / vida_media_h)


def _personas_distintas(ventana: list[Evidencia], tipo: str, exigir_foto: bool) -> tuple[int, bool]:
    """(nº de personas distintas con evidencia de `tipo`, ¿alguna con foto verificada?)."""
    relevantes = [e for e in ventana if e.tipo == tipo and e.cuenta]
    personas = {e.persona for e in relevantes if e.persona is not None}
    hay_foto = any(e.con_foto_verificada for e in relevantes)
    return len(personas), (hay_foto if exigir_foto else True)


def _transicion(estado: str, e: Evidencia, previas: list[Evidencia]) -> str:
    if e.tipo == AVISO:
        return e.estado_aviso
    if not e.cuenta or estado == "MANTENIMIENTO":
        return estado
    ventana = [x for x in previas if e.momento - x.momento <= VENTANA_CORROBORACION] + [e]

    if e.tipo == FALLA:
        if estado in ("OPERATIVO", "DESCONOCIDO"):
            return "FALLA_PROBABLE"
        if estado == "FALLA_PROBABLE":
            personas, hay_foto = _personas_distintas(ventana, FALLA, exigir_foto=True)
            return "FALLA_CONFIRMADA" if personas >= 2 and hay_foto else estado
        return estado

    # FUNCIONA: volver a OPERATIVO exige más evidencia que salir de él (asimetría).
    if estado in ("FALLA_PROBABLE", "DESCONOCIDO"):
        return "OPERATIVO" if e.con_foto_verificada else estado
    if estado == "FALLA_CONFIRMADA":
        verificadas = [x for x in ventana if x.tipo == FUNCIONA and x.con_foto_verificada]
        personas = {x.persona for x in verificadas if x.persona is not None}
        return "OPERATIVO" if len(personas) >= 2 else estado
    return estado


def estimar(evidencias: list[Evidencia], ahora: datetime) -> EstadoCalculado:
    """Estado y probabilidad de un equipo a partir de toda su evidencia vigente."""
    ordenadas = sorted((e for e in evidencias if e.momento <= ahora), key=lambda e: e.momento)

    estado, causa, ultima = "DESCONOCIDO", "decaimiento", None
    previas: list[Evidencia] = []
    for e in ordenadas:
        if ultima is not None and e.momento - ultima > VIGENCIA:
            estado, causa = "DESCONOCIDO", "decaimiento"
        nuevo = _transicion(estado, e, previas)
        if nuevo != estado:
            estado, causa = nuevo, e.causa
        if e.cuenta:
            ultima = e.momento
        previas.append(e)
    if ultima is None or ahora - ultima > VIGENCIA:
        if estado != "DESCONOCIDO":
            causa = "decaimiento"
        estado = "DESCONOCIDO"

    alfa = FUERZA_PRIOR * (1 - P_FALLA_PRIOR)
    beta = FUERZA_PRIOR * P_FALLA_PRIOR
    for e in ordenadas:
        if not e.cuenta:
            continue
        horas = (ahora - e.momento).total_seconds() / 3600
        if e.tipo == FALLA:
            beta += PESO_FALLA * e.confianza * _decaimiento(horas, VIDA_MEDIA_FALLA_H)
        elif e.tipo == FUNCIONA:
            alfa += PESO_OK * e.confianza * _decaimiento(horas, VIDA_MEDIA_OK_H)
        elif e.estado_aviso == "OPERATIVO":
            alfa += PESO_AVISO * _decaimiento(horas, VIDA_MEDIA_OK_H)
        else:  # aviso de falla o mantenimiento
            beta += PESO_AVISO * _decaimiento(horas, VIDA_MEDIA_FALLA_H)

    return EstadoCalculado(
        estado=estado,
        prob_operativo=round(alfa / (alfa + beta), 4),
        alfa=round(alfa, 4),
        beta=round(beta, 4),
        masa_evidencia=round(alfa + beta - FUERZA_PRIOR, 4),
        ultima_evidencia=ultima,
        causa=causa,
    )
