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


def evidencias_de(sesion, id_equipo: uuid.UUID) -> list[Evidencia]:
    ev: list[Evidencia] = []
    for a in sesion.scalars(select(Aviso).where(Aviso.id_equipo == id_equipo)):
        ev.append(
            Evidencia(AVISO, a.emitido_en, estado_aviso=a.estado, causa=CAUSA_AVISO[a.fuente])
        )

    reportes = sesion.scalars(
        select(ReporteComunitario).where(
            ReporteComunitario.id_equipo == id_equipo,
            ReporteComunitario.estado_validacion.in_(CON_EVIDENCIA),
        )
    ).all()
    con_foto = set(
        sesion.scalars(
            select(EvidenciaFotografica.id_reporte).where(
                EvidenciaFotografica.id_reporte.in_([r.id_reporte for r in reportes])
            )
        )
    )
    for r in reportes:
        tipo = FUNCIONA if r.tipo_problema == "funciona" else FALLA
        moderado = r.estado_validacion == "CONFIRMADO_MODERADOR"
        s = max(r.puntaje_confianza or 0.0, UMBRAL_FOTO_VERIFICADA if moderado else 0.0)
        # "Foto verificada": con foto y s alto, o confirmado por una persona moderadora.
        verificada = moderado or (r.id_reporte in con_foto and s >= UMBRAL_FOTO_VERIFICADA)
        ev.append(
            Evidencia(
                tipo,
                r.creado_en,
                s,
                str(r.id_usuario),
                verificada,
                causa="moderador" if moderado else "reporte",
            )
        )
        for v in sesion.scalars(
            select(ValidacionComunitaria).where(ValidacionComunitaria.id_reporte == r.id_reporte)
        ):
            # Confirmar un reporte de falla es evidencia de falla; negarlo, de que funciona.
            mismo = v.voto == "CONFIRMA"
            tipo_voto = tipo if mismo else (FALLA if tipo == FUNCIONA else FUNCIONA)
            ev.append(Evidencia(tipo_voto, v.creado_en, 0.5, str(v.id_usuario), causa="voto"))
    return ev


def recalcular_equipo(ctx: Contexto, id_equipo: uuid.UUID) -> str | None:
    """Recalcula y guarda el estado. Devuelve el estado nuevo si cambió."""
    ahora = ctx.reloj()
    with ctx.sesiones.begin() as s:
        r = estimar(evidencias_de(s, id_equipo), ahora)
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
    if anterior != r.estado:
        ctx.bus.publicar(ESTADO_CAMBIADO, {"id": str(id_equipo), "estado": r.estado})
        return r.estado
    return None


def recalcular_todos(ctx: Contexto) -> int:
    with ctx.sesiones() as s:
        ids = list(s.scalars(select(InfraestructuraAccesible.id_equipo)))
    return sum(recalcular_equipo(ctx, i) is not None for i in ids)
