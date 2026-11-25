"""worker-validacion (F4-3, F4-5): de reporte-creado a reporte-validado.

Pasos: análisis de la imagen, EXIF, duplicados (SHA-256 y pHash), geocerca y reputación
-> puntaje s (dominio/validacion.py). Guarda la versión saneada de la foto. Si el
analizador falla, el reporte no se pierde: queda en corroboración/moderación (doc. 07).
"""

import logging
import uuid
from datetime import timedelta

from sqlalchemy import func, select

from app.bd.modelos import (
    Estacion,
    EvidenciaFotografica,
    ReporteComunitario,
    Usuario,
    ValidacionComunitaria,
)
from app.dominio.red import Punto, distancia_m
from app.dominio.validacion import Desglose, puntaje
from app.modulos.reportes import imagenes
from app.workers.contexto import REPORTE_VALIDADO, Contexto

log = logging.getLogger("ra.worker.validacion")

UMBRAL_DUPLICADO_PHASH = 6  # bits
ANTIGUEDAD_MAXIMA_FOTO = timedelta(hours=48)
REVALIDABLES = ("PENDIENTE", "VERIFICADO_AUTO", "PENDIENTE_CORROBORACION", "BAJA_CONFIANZA")


def _punto(sesion, geom) -> Punto | None:
    if geom is None:
        return None
    lat, lon = sesion.execute(select(func.ST_Y(geom), func.ST_X(geom))).one()
    return Punto(lat, lon)


def _votos(sesion, id_reporte) -> tuple[int, int]:
    filas = sesion.execute(
        select(ValidacionComunitaria.voto, func.count())
        .where(ValidacionComunitaria.id_reporte == id_reporte)
        .group_by(ValidacionComunitaria.voto)
    ).all()
    conteo = dict(filas)
    return conteo.get("CONFIRMA", 0), conteo.get("NIEGA", 0)


def procesar_reporte(ctx: Contexto, id_reporte: uuid.UUID) -> Desglose | None:
    with ctx.sesiones.begin() as s:
        rep = s.get(ReporteComunitario, id_reporte)
        if rep is None or rep.estado_validacion not in REVALIDABLES:
            return None
        estacion = s.get(Estacion, rep.id_estacion)
        usuario = s.get(Usuario, rep.id_usuario) if rep.id_usuario else None
        evidencia = s.scalar(
            select(EvidenciaFotografica).where(EvidenciaFotografica.id_reporte == rep.id_reporte)
        )

        analisis = None
        duplicada = foto_vieja = False
        fallo_analisis = False
        gps = None
        if evidencia is not None:
            contenido = ctx.almacen.leer_original(evidencia.uri_original.removeprefix("local://"))
            img = imagenes.abrir_imagen(contenido)
            exif = imagenes.metadatos_exif(img)
            sha, phash = imagenes.huellas(contenido, img)
            otras = s.execute(
                select(EvidenciaFotografica.sha256, EvidenciaFotografica.phash).where(
                    EvidenciaFotografica.id_evidencia != evidencia.id_evidencia
                )
            ).all()
            duplicada = any(
                o.sha256 == sha
                or (o.phash and imagenes.distancia_phash(o.phash, phash) <= UMBRAL_DUPLICADO_PHASH)
                for o in otras
            )
            if exif.capturada_en is not None:
                creado = rep.creado_en.replace(tzinfo=None)
                foto_vieja = creado - exif.capturada_en > ANTIGUEDAD_MAXIMA_FOTO
            if exif.lat is not None:
                gps = Punto(exif.lat, exif.lon)
            try:
                analisis = ctx.analizador.analizar(contenido, rep.tipo_problema)
            except Exception:
                log.exception("Falló el análisis de la imagen del reporte %s", id_reporte)
                fallo_analisis = True
            evidencia.sha256, evidencia.phash = sha, phash
            if analisis is not None:
                id_obj = evidencia.uri_original.removeprefix("local://")
                ctx.almacen.guardar_redactada(id_obj, imagenes.sanear(img, analisis.rostros))
                evidencia.uri_redactada = f"local://{id_obj}"
                evidencia.etiqueta_ia = analisis.problema_visible
                evidencia.confianza_ia = analisis.confianza
                evidencia.resultado_gemini = {
                    "tipo_equipo_visible": analisis.tipo_equipo_visible,
                    "problema_visible": analisis.problema_visible,
                    "senales_textuales": list(analisis.senales_textuales),
                    "confianza": analisis.confianza,
                    "rostros_difuminados": len(analisis.rostros),
                }

        centro = Punto(
            *s.execute(select(func.ST_Y(estacion.ubicacion), func.ST_X(estacion.ubicacion))).one()
        )
        ubicacion = _punto(s, rep.ubicacion) or gps
        distancia = distancia_m(ubicacion, centro) if ubicacion else None
        if evidencia is not None and gps is not None:
            evidencia.gps_coincide = distancia_m(gps, centro) <= 150
        confirma, niega = _votos(s, rep.id_reporte)

        desglose = puntaje(
            rep.tipo_problema,
            analisis,
            distancia,
            usuario.reputacion if usuario else 0.5,
            confirma,
            niega,
            duplicada,
            foto_vieja,
        )
        estado = desglose.estado_validacion
        motivos = list(desglose.motivos)
        if fallo_analisis:
            # Sin análisis, ni verificación automática ni rechazo: lo decide una persona.
            estado = "PENDIENTE_CORROBORACION"
            motivos.append("análisis de imagen no disponible: pasa a moderación")
        rep.puntaje_confianza = desglose.s
        rep.estado_validacion = estado
        rep.desglose_puntaje = {
            **desglose.como_dict(),
            "estado_validacion": estado,
            "motivos": motivos,
        }
        rep.validado_en = ctx.reloj()
        id_equipo = rep.id_equipo

    ctx.bus.publicar(
        REPORTE_VALIDADO,
        {"id": str(id_reporte), "id_equipo": str(id_equipo) if id_equipo else None},
    )
    return desglose
