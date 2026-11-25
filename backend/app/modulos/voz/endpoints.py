"""POST /voz/consulta (F5-2, F5-3, D-24).

Sólo interpreta: devuelve origen, destino y restricciones resueltos, o una pregunta de
aclaración. No calcula la ruta ni recibe el perfil: la PWA llama después a /rutas/plan
con el perfil guardado en el dispositivo (regla de seguridad 6).

Ni el audio ni la transcripción se guardan ni se registran en logs: pueden contener datos
personales (a dónde va alguien, su voz).
"""

import base64
import binascii
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.adaptadores import fabrica
from app.adaptadores.puertos import Geocodificador, InterpreteLenguaje, TranscriptorVoz
from app.dominio.estaciones import Lugar
from app.dominio.voz import Parcial, Restricciones, Transcripcion, resolver
from app.modulos.estaciones.endpoints import LugarSalida, obtener_geocodificador
from app.modulos.voz.esquemas import (
    AUDIO_MAX_BYTES,
    AclaracionSalida,
    ConsultaVoz,
    ContextoVoz,
    RespuestaVoz,
    RestriccionesVoz,
)

router = APIRouter(prefix="/voz", tags=["voz"])


def obtener_transcriptor() -> TranscriptorVoz:
    return fabrica.transcriptor()


def obtener_interprete() -> InterpreteLenguaje:
    return fabrica.interprete()


def _a_lugar(x: LugarSalida | None) -> Lugar | None:
    if x is None:
        return None
    return Lugar(x.tipo, x.nombre, x.lat, x.lon, x.detalle, x.clave_estacion)


def _a_salida(x: Lugar | None) -> LugarSalida | None:
    if x is None:
        return None
    return LugarSalida(tipo=x.tipo, nombre=x.nombre, detalle=x.detalle, lat=x.lat, lon=x.lon,
                       clave_estacion=x.clave_estacion)  # fmt: skip


def _a_parcial(c: ContextoVoz | None) -> Parcial | None:
    if c is None:
        return None
    return Parcial(
        origen=_a_lugar(c.origen),
        destino=_a_lugar(c.destino),
        usar_ubicacion_origen=c.usar_ubicacion_origen,
        restricciones=Restricciones(c.restricciones.max_transbordos, c.restricciones.caminar_poco),
        campo=c.campo,
        pendiente=c.pendiente,
    )


def _a_contexto(p: Parcial) -> ContextoVoz:
    return ContextoVoz(
        origen=_a_salida(p.origen),
        destino=_a_salida(p.destino),
        usar_ubicacion_origen=p.usar_ubicacion_origen,
        restricciones=RestriccionesVoz(
            max_transbordos=p.restricciones.max_transbordos,
            caminar_poco=p.restricciones.caminar_poco,
        ),
        campo=p.campo,
        pendiente=p.pendiente,
    )


@router.post("/consulta", response_model=RespuestaVoz)
def consulta(
    entrada: ConsultaVoz,
    transcriptor: Annotated[TranscriptorVoz, Depends(obtener_transcriptor)],
    interprete: Annotated[InterpreteLenguaje, Depends(obtener_interprete)],
    geocodificador: Annotated[Geocodificador, Depends(obtener_geocodificador)],
) -> RespuestaVoz:
    """Interpreta una petición de ruta dicha (o escrita) y resuelve sus lugares."""
    if entrada.audio_b64 is not None:
        try:
            audio = base64.b64decode(entrada.audio_b64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(422, "audio_b64 no es base64 válido.") from None
        if len(audio) > AUDIO_MAX_BYTES:
            raise HTTPException(413, "El audio supera 1 MB (unos 60 segundos).")
        if not audio:
            raise HTTPException(422, "El audio está vacío.")
        transcripcion = transcriptor.transcribir(audio, entrada.formato)
    else:
        transcripcion = Transcripcion(entrada.texto, confianza=1.0)

    r = resolver(
        interprete.interpretar(transcripcion.texto),
        geocodificador.buscar,
        _a_parcial(entrada.contexto),
    )
    a = r.aclaracion
    return RespuestaVoz(
        estado=r.estado,
        transcripcion=transcripcion.texto,
        transcripcion_simulada=transcripcion.simulada,
        mensaje=r.mensaje,
        contexto=_a_contexto(r.parcial),
        aclaracion=None
        if a is None
        else AclaracionSalida(
            campo=a.campo,
            pregunta=a.pregunta,
            opciones=[_a_salida(o) for o in a.opciones],
            permite_ubicacion=a.permite_ubicacion,
        ),  # fmt: skip
    )
