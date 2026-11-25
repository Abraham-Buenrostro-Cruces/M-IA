"""worker-estado (F4-4): reúne la evidencia de un equipo y aplica el estimador (D-21).

Se dispara con reporte-validado, aviso-creado y voto-registrado, y también de forma
periódica (``recalcular_todos``) para que el olvido y la vigencia surtan efecto aunque no
llegue evidencia nueva (Cloud Scheduler en la nube).
"""

import uuid

from sqlalchemy import select

from app.bd.modelos import (
    Aviso,
    EstadoEquipo,
    EvidenciaFotografica,
    HistorialEstado,
    InfraestructuraAccesible,
    ReporteComunitario,
    ValidacionComunitaria,
)
from app.dominio.estimador import AVISO, FALLA, FUNCIONA, UMBRAL_FOTO_VERIFICADA, Evidencia, estimar
from app.workers.contexto import ESTADO_CAMBIADO, Contexto

CAUSA_AVISO = {"OFICIAL": "oficial", "MODERADOR": "moderador", "DEMO": "demo"}
CON_EVIDENCIA = (
    "VERIFICADO_AUTO",
    "PENDIENTE_CORROBORACION",
    "BAJA_CONFIANZA",
    "CONFIRMADO_MODERADOR",
)


def evidencias_por_equipo(
    sesion, ids: list[uuid.UUID] | None = None
) -> dict[uuid.UUID, list[Evidencia]]:
    """Evidencia de varios equipos (todos si ``ids`` es None) en cuatro consultas.

    Con la red completa (899 equipos), leer equipo por equipo hacía miles de viajes a la
    base y recalcular todo tardaba ~47 s; en lote, unos segundos. El orden dentro de cada
    equipo es el mismo de siempre (avisos, y cada reporte seguido de sus votos); de todos
    modos el estimador ordena por fecha.
    """

    def filtro(columna):
        return [] if ids is None else [columna.in_(ids)]

    ev: dict[uuid.UUID, list[Evidencia]] = {}
    for a in sesion.scalars(select(Aviso).where(*filtro(Aviso.id_equipo))):
        ev.setdefault(a.id_equipo, []).append(
            Evidencia(AVISO, a.emitido_en, estado_aviso=a.estado, causa=CAUSA_AVISO[a.fuente])
        )

    reportes = sesion.scalars(
        select(ReporteComunitario).where(
            ReporteComunitario.id_equipo.is_not(None),
            ReporteComunitario.estado_validacion.in_(CON_EVIDENCIA),
            *filtro(ReporteComunitario.id_equipo),
        )
    ).all()
    id_reportes = [r.id_reporte for r in reportes]
    con_foto = set(
        sesion.scalars(
            select(EvidenciaFotografica.id_reporte).where(
                EvidenciaFotografica.id_reporte.in_(id_reportes)
            )
        )
    )
    votos: dict[uuid.UUID, list] = {}
    for v in sesion.scalars(
        select(ValidacionComunitaria).where(ValidacionComunitaria.id_reporte.in_(id_reportes))
    ):
        votos.setdefault(v.id_reporte, []).append(v)

    for r in reportes:
        tipo = FUNCIONA if r.tipo_problema == "funciona" else FALLA
        moderado = r.estado_validacion == "CONFIRMADO_MODERADOR"
        s = max(r.puntaje_confianza or 0.0, UMBRAL_FOTO_VERIFICADA if moderado else 0.0)
        # "Foto verificada": con foto y s alto, o confirmado por una persona moderadora.
        verificada = moderado or (r.id_reporte in con_foto and s >= UMBRAL_FOTO_VERIFICADA)
        lista = ev.setdefault(r.id_equipo, [])
        lista.append(
            Evidencia(
                tipo,
                r.creado_en,
                s,
                str(r.id_usuario),
                verificada,
                causa="moderador" if moderado else "reporte",
            )
        )
        for v in votos.get(r.id_reporte, []):
            # Confirmar un reporte de falla es evidencia de falla; negarlo, de que funciona.
            mismo = v.voto == "CONFIRMA"
            tipo_voto = tipo if mismo else (FALLA if tipo == FUNCIONA else FUNCIONA)
            lista.append(Evidencia(tipo_voto, v.creado_en, 0.5, str(v.id_usuario), causa="voto"))
    return ev


def evidencias_de(sesion, id_equipo: uuid.UUID) -> list[Evidencia]:
    return evidencias_por_equipo(sesion, [id_equipo]).get(id_equipo, [])


def recalcular_equipo(ctx: Contexto, id_equipo: uuid.UUID) -> str | None:
    """Recalcula y guarda el estado. Devuelve el estado nuevo si cambió."""
    ahora = ctx.reloj()
    with ctx.sesiones.begin() as s:
        anterior, nuevo = _guardar(s, id_equipo, evidencias_de(s, id_equipo), ahora)
    if anterior != nuevo:
        ctx.bus.publicar(ESTADO_CAMBIADO, {"id": str(id_equipo), "estado": nuevo})
        return nuevo
    return None


def _guardar(s, id_equipo: uuid.UUID, evidencias: list[Evidencia], ahora, actual=None):
    """Aplica el estimador y escribe el estado (y su historial si cambió). Sólo aquí se
    escribe ``estado_equipo`` (D-21). Devuelve (estado anterior, estado nuevo)."""
    r = estimar(evidencias, ahora)
    if actual is None:
        actual = s.get(EstadoEquipo, id_equipo)
    anterior = actual.estado if actual else None
    valores = dict(
        estado=r.estado,
        prob_operativo=r.prob_operativo,
        alfa=max(r.alfa, 1e-3),
        beta=max(r.beta, 1e-3),
        confianza=r.masa_evidencia,
        fuente_ultima=r.causa,
        actualizado_en=r.ultima_evidencia or ahora,
    )
    if actual is None:
        s.add(EstadoEquipo(id_equipo=id_equipo, **valores))
    else:
        for k, v in valores.items():
            setattr(actual, k, v)
    if anterior != r.estado:
        s.add(
            HistorialEstado(
                id_equipo=id_equipo,
                estado_anterior=anterior,
                estado_nuevo=r.estado,
                causa=r.causa,
                ocurrido_en=ahora,
            )
        )
    return anterior, r.estado


def recalcular_todos(ctx: Contexto) -> int:
    """Recalcula todos los equipos en una sola transacción, con la evidencia leída en lote.

    Los eventos estado-cambiado se publican al final, ya confirmada la transacción, igual
    que ``recalcular_equipo`` los publica después de la suya.
    """
    ahora = ctx.reloj()
    cambios: list[tuple[uuid.UUID, str]] = []
    with ctx.sesiones.begin() as s:
        ids = list(s.scalars(select(InfraestructuraAccesible.id_equipo)))
        evidencias = evidencias_por_equipo(s)
        estados = {e.id_equipo: e for e in s.scalars(select(EstadoEquipo))}
        for i in ids:
            anterior, nuevo = _guardar(s, i, evidencias.get(i, []), ahora, estados.get(i))
            if anterior != nuevo:
                cambios.append((i, nuevo))
    for i, nuevo in cambios:
        ctx.bus.publicar(ESTADO_CAMBIADO, {"id": str(i), "estado": nuevo})
    return len(cambios)
