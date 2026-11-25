"""Reportes comunitarios, evidencias, corroboración y moderación (F4-1, F4-2, F4-6, F4-7).

Las respuestas nunca incluyen la ubicación exacta de quien reporta ni la foto original:
sólo la versión saneada y sólo para su autor o para moderación.
"""

import uuid
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.adaptadores.local.almacen import AlmacenLocal, TokenSubidaInvalidoError
from app.bd.modelos import (
    Aviso,
    Estacion,
    EvidenciaFotografica,
    InfraestructuraAccesible,
    ReporteComunitario,
    Usuario,
    ValidacionComunitaria,
)
from app.dominio.validacion import reputacion
from app.modulos.reportes import imagenes
from app.modulos.usuarios.identidad import moderador_actual, usuario_actual
from app.workers.contexto import (
    AVISO_CREADO,
    REPORTE_CREADO,
    REPORTE_VALIDADO,
    VOTO_REGISTRADO,
    Contexto,
)
from app.workers.registro import obtener_contexto, obtener_sesion

router = APIRouter(tags=["reportes"])

VIGENCIA_SUBIDA_S = 300  # 5 minutos (06-flujos, flujo 2)
MAX_REPORTES_POR_HORA = 10  # freno básico contra el abuso (documento 07)
VENTANA_CORROBORACION = timedelta(hours=24)

Sesion = Annotated[object, Depends(obtener_sesion)]
Ctx = Annotated[Contexto, Depends(obtener_contexto)]
Yo = Annotated[Usuario, Depends(usuario_actual)]
Moderador = Annotated[Usuario, Depends(moderador_actual)]
TipoProblema = Literal["fuera_de_servicio", "bloqueado", "danado", "funciona"]


class SubidaSalida(BaseModel):
    id_subida: str
    url_subida: str
    metodo: Literal["PUT"] = "PUT"
    tipos_permitidos: list[str] = ["image/jpeg", "image/png", "image/webp"]
    tamano_maximo_bytes: int = imagenes.TAMANO_MAXIMO_BYTES
    vence_en_s: int = VIGENCIA_SUBIDA_S


class UbicacionReporte(BaseModel):
    lat: float = Field(ge=19.0, le=19.8)
    lon: float = Field(ge=-99.5, le=-98.8)
    precision_m: int | None = Field(None, ge=0, le=5000)


class ReporteEntrada(BaseModel):
    clave_estacion: str
    codigo_equipo: str | None = None
    tipo_problema: TipoProblema
    descripcion: str | None = Field(None, max_length=500)
    ubicacion: UbicacionReporte | None = None
    id_subida: str | None = None


class ReporteSalida(BaseModel):
    id_reporte: str
    estado_validacion: str
    puntaje_confianza: float | None
    motivos: list[str]
    tipo_problema: str
    clave_estacion: str
    codigo_equipo: str | None
    con_foto: bool
    id_evidencia: str | None
    creado_en: datetime
    estado_equipo: str | None = None


class VotoEntrada(BaseModel):
    voto: Literal["CONFIRMA", "NIEGA"]


class DecisionEntrada(BaseModel):
    decision: Literal["CONFIRMAR", "RECHAZAR"]
    nota: str | None = Field(None, max_length=500)


class AvisoEntrada(BaseModel):
    codigo_equipo: str
    estado: Literal["OPERATIVO", "FALLA_CONFIRMADA", "MANTENIMIENTO"]
    nota: str | None = Field(None, max_length=500)


def _salida(s, rep: ReporteComunitario) -> ReporteSalida:
    from app.bd.modelos import EstadoEquipo

    clave = s.scalar(select(Estacion.clave).where(Estacion.id_estacion == rep.id_estacion))
    codigo = estado = None
    if rep.id_equipo:
        codigo = s.scalar(
            select(InfraestructuraAccesible.codigo).where(
                InfraestructuraAccesible.id_equipo == rep.id_equipo
            )
        )
        estado = s.scalar(
            select(EstadoEquipo.estado).where(EstadoEquipo.id_equipo == rep.id_equipo)
        )
    id_ev = s.scalar(
        select(EvidenciaFotografica.id_evidencia).where(
            EvidenciaFotografica.id_reporte == rep.id_reporte
        )
    )
    return ReporteSalida(
        id_reporte=str(rep.id_reporte),
        estado_validacion=rep.estado_validacion,
        puntaje_confianza=rep.puntaje_confianza,
        motivos=(rep.desglose_puntaje or {}).get("motivos", []),
        tipo_problema=rep.tipo_problema,
        clave_estacion=clave,
        codigo_equipo=codigo,
        con_foto=id_ev is not None,
        id_evidencia=str(id_ev) if id_ev else None,
        creado_en=rep.creado_en,
        estado_equipo=estado,
    )


# --------------------------------------------------------------------------- evidencias (F4-2)


@router.post("/reportes/subidas", response_model=SubidaSalida, status_code=201)
def crear_subida(ctx: Ctx, _yo: Yo) -> SubidaSalida:
    """URL de un solo uso para subir la foto (en la nube: URL firmada de Cloud Storage)."""
    id_objeto = str(uuid.uuid4())  # el nombre lo genera el servidor, nunca la persona
    return SubidaSalida(
        id_subida=id_objeto, url_subida=ctx.almacen.url_subida(id_objeto, VIGENCIA_SUBIDA_S)
    )


@router.put("/evidencias/subidas/{token}", status_code=204, include_in_schema=False)
async def recibir_subida(token: str, request: Request, ctx: Ctx) -> Response:
    """Sólo en RA_MODO=local: emula la subida directa a Cloud Storage."""
    if not isinstance(ctx.almacen, AlmacenLocal):
        raise HTTPException(404)
    if (
        request.headers.get("content-type")
        not in SubidaSalida.model_fields["tipos_permitidos"].default
    ):
        raise HTTPException(415, "Sólo se aceptan imágenes JPEG, PNG o WEBP.")
    contenido = await request.body()
    try:
        id_objeto = ctx.almacen.objeto_de_token(token)
        imagenes.abrir_imagen(contenido)  # valida antes de guardar
        ctx.almacen.guardar_original(id_objeto, contenido)
    except TokenSubidaInvalidoError as e:
        raise HTTPException(403, str(e)) from None
    except imagenes.ImagenInvalidaError as e:
        raise HTTPException(422, str(e)) from None
    return Response(status_code=204)


@router.get("/evidencias/{id_evidencia}")
def ver_evidencia(id_evidencia: uuid.UUID, s: Sesion, ctx: Ctx, yo: Yo) -> Response:
    """Versión **saneada** (sin EXIF, rostros difuminados), sólo para su autor o moderación."""
    ev = s.get(EvidenciaFotografica, id_evidencia)
    if ev is None or ev.uri_redactada is None:
        raise HTTPException(404, "Evidencia no disponible (puede seguir en validación).")
    rep = s.get(ReporteComunitario, ev.id_reporte)
    if yo.rol not in ("moderador", "admin") and rep.id_usuario != yo.id_usuario:
        raise HTTPException(403, "Sin permiso para ver esta evidencia.")
    contenido = ctx.almacen.leer_redactada(ev.uri_redactada.removeprefix("local://"))
    return Response(
        contenido, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"}
    )


# --------------------------------------------------------------------------- reportes (F4-1)


@router.post("/reportes", response_model=ReporteSalida, status_code=202)
def crear_reporte(entrada: ReporteEntrada, s: Sesion, ctx: Ctx, yo: Yo) -> ReporteSalida:
    """Registra el reporte y lo manda a validación (202: el resultado llega después)."""
    hace_una_hora = ctx.reloj() - timedelta(hours=1)
    recientes = s.scalar(
        select(func.count())
        .select_from(ReporteComunitario)
        .where(
            ReporteComunitario.id_usuario == yo.id_usuario,
            ReporteComunitario.creado_en >= hace_una_hora,
        )
    )
    if recientes >= MAX_REPORTES_POR_HORA:
        raise HTTPException(429, "Demasiados reportes en una hora. Intenta más tarde.")

    estacion = s.scalar(select(Estacion).where(Estacion.clave == entrada.clave_estacion))
    if estacion is None:
        raise HTTPException(404, "Estación no encontrada.")
    id_equipo = None
    if entrada.codigo_equipo:
        equipo = s.scalar(
            select(InfraestructuraAccesible).where(
                InfraestructuraAccesible.codigo == entrada.codigo_equipo
            )
        )
        if equipo is None or equipo.id_estacion != estacion.id_estacion:
            raise HTTPException(422, "El equipo no pertenece a esa estación.")
        id_equipo = equipo.id_equipo

    contenido = None
    if entrada.id_subida:
        contenido = ctx.almacen.leer_original(entrada.id_subida)
        if contenido is None:
            raise HTTPException(422, "No se encontró la foto: súbela antes de enviar el reporte.")
        ya_usada = s.scalar(
            select(func.count())
            .select_from(EvidenciaFotografica)
            .where(EvidenciaFotografica.uri_original == f"local://{entrada.id_subida}")
        )
        if ya_usada:
            raise HTTPException(409, "Esa foto ya está asociada a otro reporte.")

    u = entrada.ubicacion
    rep = ReporteComunitario(
        id_usuario=yo.id_usuario,
        id_estacion=estacion.id_estacion,
        id_equipo=id_equipo,
        tipo_problema=entrada.tipo_problema,
        descripcion=entrada.descripcion,
        canal="texto",
        ubicacion=f"SRID=4326;POINT({u.lon} {u.lat})" if u else None,
        precision_m=u.precision_m if u else None,
        estado_validacion="PENDIENTE",
        creado_en=ctx.reloj(),
    )
    s.add(rep)
    s.flush()
    if contenido is not None:
        sha, phash = imagenes.huellas(contenido, imagenes.abrir_imagen(contenido))
        s.add(
            EvidenciaFotografica(
                id_reporte=rep.id_reporte,
                sha256=sha,
                phash=phash,
                uri_original=f"local://{entrada.id_subida}",
            )
        )
    s.commit()
    ctx.bus.publicar(REPORTE_CREADO, {"id": str(rep.id_reporte)})
    s.refresh(rep)
    return _salida(s, rep)


@router.get("/reportes/mios", response_model=list[ReporteSalida])
def mis_reportes(s: Sesion, yo: Yo) -> list[ReporteSalida]:
    reps = s.scalars(
        select(ReporteComunitario)
        .where(ReporteComunitario.id_usuario == yo.id_usuario)
        .order_by(ReporteComunitario.creado_en.desc())
        .limit(20)
    ).all()
    return [_salida(s, r) for r in reps]


@router.get("/reportes/{id_reporte}", response_model=ReporteSalida)
def ver_reporte(id_reporte: uuid.UUID, s: Sesion, yo: Yo) -> ReporteSalida:
    rep = s.get(ReporteComunitario, id_reporte)
    if rep is None or (rep.id_usuario != yo.id_usuario and yo.rol not in ("moderador", "admin")):
        raise HTTPException(404, "Reporte no encontrado.")
    return _salida(s, rep)


# --------------------------------------------------------------------------- corroboración (F4-7)


@router.post("/equipos/{codigo:path}/corroboraciones", status_code=201)
def corroborar(codigo: str, entrada: VotoEntrada, s: Sesion, ctx: Ctx, yo: Yo) -> dict:
    # {codigo:path}: los códigos de equipo llevan "/" (METRO-ZOCALO/SAL-.../ELV).
    """ "¿Sigue fuera de servicio?" Se vota sobre el reporte de falla más reciente (24 h) de
    otra persona. Un voto por persona y reporte (la base lo garantiza)."""
    equipo = s.scalar(
        select(InfraestructuraAccesible).where(InfraestructuraAccesible.codigo == codigo)
    )
    if equipo is None:
        raise HTTPException(404, "Equipo no encontrado.")
    rep = s.scalar(
        select(ReporteComunitario)
        .where(
            ReporteComunitario.id_equipo == equipo.id_equipo,
            ReporteComunitario.tipo_problema != "funciona",
            ReporteComunitario.estado_validacion.not_in(("PENDIENTE", "RECHAZADO")),
            ReporteComunitario.creado_en >= ctx.reloj() - VENTANA_CORROBORACION,
            ReporteComunitario.id_usuario != yo.id_usuario,
        )
        .order_by(ReporteComunitario.creado_en.desc())
    )
    if rep is None:
        raise HTTPException(404, "No hay un reporte reciente de otra persona que corroborar.")
    s.add(
        ValidacionComunitaria(
            id_reporte=rep.id_reporte,
            id_usuario=yo.id_usuario,
            voto=entrada.voto,
            creado_en=ctx.reloj(),
        )
    )
    try:
        s.commit()
    except IntegrityError:
        s.rollback()
        raise HTTPException(409, "Ya respondiste sobre este equipo.") from None
    ctx.bus.publicar(VOTO_REGISTRADO, {"id": str(rep.id_reporte)})
    return {"id_reporte": str(rep.id_reporte), "voto": entrada.voto}


# --------------------------------------------------------------------------- moderación (F4-6)


class ReporteModeracion(ReporteSalida):
    descripcion: str | None
    desglose: dict | None
    votos_confirma: int
    votos_niega: int
    nombre_estacion: str
    referencia_equipo: str | None


@router.get("/moderacion/reportes", response_model=list[ReporteModeracion], tags=["moderación"])
def cola_moderacion(s: Sesion, _mod: Moderador) -> list[ReporteModeracion]:
    """Reportes en zona gris (PENDIENTE_CORROBORACION), del más antiguo al más reciente."""
    reps = s.scalars(
        select(ReporteComunitario)
        .where(ReporteComunitario.estado_validacion == "PENDIENTE_CORROBORACION")
        .order_by(ReporteComunitario.creado_en)
        .limit(50)
    ).all()
    salida = []
    for r in reps:
        base = _salida(s, r)
        votos = dict(
            s.execute(
                select(ValidacionComunitaria.voto, func.count())
                .where(ValidacionComunitaria.id_reporte == r.id_reporte)
                .group_by(ValidacionComunitaria.voto)
            ).all()
        )
        nombre = s.scalar(select(Estacion.nombre).where(Estacion.id_estacion == r.id_estacion))
        ref = None
        if r.id_equipo:
            ref = s.scalar(
                select(InfraestructuraAccesible.referencia).where(
                    InfraestructuraAccesible.id_equipo == r.id_equipo
                )
            )
        salida.append(
            ReporteModeracion(
                **base.model_dump(),
                descripcion=r.descripcion,
                desglose=r.desglose_puntaje,
                votos_confirma=votos.get("CONFIRMA", 0),
                votos_niega=votos.get("NIEGA", 0),
                nombre_estacion=nombre,
                referencia_equipo=ref,
            )
        )
    return salida


@router.post(
    "/moderacion/reportes/{id_reporte}/decision", response_model=ReporteSalida, tags=["moderación"]
)
def decidir(
    id_reporte: uuid.UUID, entrada: DecisionEntrada, s: Sesion, ctx: Ctx, mod: Moderador
) -> ReporteSalida:
    rep = s.get(ReporteComunitario, id_reporte)
    if rep is None:
        raise HTTPException(404, "Reporte no encontrado.")
    if rep.estado_validacion in ("CONFIRMADO_MODERADOR", "RECHAZADO"):
        raise HTTPException(409, "Este reporte ya fue moderado.")
    if rep.id_usuario == mod.id_usuario:
        raise HTTPException(403, "No puedes moderar tu propio reporte.")
    confirmar = entrada.decision == "CONFIRMAR"
    rep.estado_validacion = "CONFIRMADO_MODERADOR" if confirmar else "RECHAZADO"
    rep.desglose_puntaje = {
        **(rep.desglose_puntaje or {}),
        "moderacion": {
            "decision": entrada.decision,
            "nota": entrada.nota,
            "en": ctx.reloj().isoformat(),
        },
    }
    autor = s.get(Usuario, rep.id_usuario) if rep.id_usuario else None
    if autor is not None:
        if confirmar:
            autor.reportes_confirmados += 1
        else:
            autor.reportes_rechazados += 1
        autor.reputacion = reputacion(autor.reportes_confirmados, autor.reportes_rechazados)
    s.commit()
    ctx.bus.publicar(
        REPORTE_VALIDADO,
        {"id": str(rep.id_reporte), "id_equipo": str(rep.id_equipo) if rep.id_equipo else None},
    )
    s.refresh(rep)
    return _salida(s, rep)


@router.post("/moderacion/avisos", status_code=201, tags=["moderación"])
def crear_aviso(entrada: AvisoEntrada, s: Sesion, ctx: Ctx, mod: Moderador) -> dict:
    """Fija el estado de un equipo con autoridad (p. ej. tras verificar una reparación)."""
    equipo = s.scalar(
        select(InfraestructuraAccesible).where(
            InfraestructuraAccesible.codigo == entrada.codigo_equipo
        )
    )
    if equipo is None:
        raise HTTPException(404, "Equipo no encontrado.")
    aviso = Aviso(
        id_equipo=equipo.id_equipo,
        estado=entrada.estado,
        fuente="MODERADOR",
        id_usuario=mod.id_usuario,
        nota=entrada.nota,
        emitido_en=ctx.reloj(),
    )
    s.add(aviso)
    s.commit()
    ctx.bus.publicar(AVISO_CREADO, {"id": str(aviso.id_aviso), "id_equipo": str(equipo.id_equipo)})
    return {"id_aviso": str(aviso.id_aviso)}
