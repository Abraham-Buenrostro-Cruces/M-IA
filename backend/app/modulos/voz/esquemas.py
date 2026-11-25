"""Contrato de POST /voz/consulta (F5-2, F5-3, D-24)."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.modulos.estaciones.endpoints import LugarSalida

# Un minuto de voz en webm/opus pesa ~250 KB; 1 MB deja margen. En base64 crece 4/3.
AUDIO_MAX_BYTES = 1_000_000
AUDIO_B64_MAX = AUDIO_MAX_BYTES * 4 // 3 + 4
FORMATOS = Literal["webm", "ogg", "mp4", "wav"]


class RestriccionesVoz(BaseModel):
    max_transbordos: int | None = Field(None, ge=0, le=5)
    caminar_poco: bool = False


class ContextoVoz(BaseModel):
    """Lo ya resuelto en la conversación; la PWA lo reenvía tal cual lo recibió."""

    origen: LugarSalida | None = None
    destino: LugarSalida | None = None
    usar_ubicacion_origen: bool = False
    restricciones: RestriccionesVoz = Field(default_factory=RestriccionesVoz)
    campo: Literal["origen", "destino"] | None = None
    pendiente: str | None = Field(None, max_length=80)


class ConsultaVoz(BaseModel):
    """Audio grabado **o** texto (para quien prefiere escribir, y para las pruebas), **o**
    sólo el contexto: cuando la persona elige una opción de la aclaración en pantalla o
    "desde mi ubicación", la PWA lo pone en el contexto y pregunta qué falta.

    No lleva el perfil de movilidad (D-24, regla 6): la ruta se pide después a /rutas/plan.
    """

    audio_b64: str | None = Field(None, max_length=AUDIO_B64_MAX)
    formato: FORMATOS | None = None
    texto: str | None = Field(None, min_length=1, max_length=300)
    contexto: ContextoVoz | None = None

    @model_validator(mode="after")
    def _una_entrada(self) -> Self:
        if self.audio_b64 is not None and self.texto is not None:
            raise ValueError("Envía audio_b64 o texto, no los dos.")
        if self.audio_b64 is None and self.texto is None and self.contexto is None:
            raise ValueError("Envía audio_b64, texto o el contexto de la conversación.")
        if self.audio_b64 is not None and self.formato is None:
            raise ValueError("Con audio_b64 indica su formato.")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [{"texto": "Quiero ir de Tasqueña al Museo de la Ciudad sin transbordos"}]
        }
    }


class AclaracionSalida(BaseModel):
    campo: Literal["origen", "destino"]
    pregunta: str
    opciones: list[LugarSalida]
    permite_ubicacion: bool


class RespuestaVoz(BaseModel):
    estado: Literal["listo", "aclaracion", "no_entendido"]
    transcripcion: str = Field(description="Lo que se entendió que dijo la persona.")
    transcripcion_simulada: bool = Field(
        description="RA_MODO=local: el audio no se reconoció de verdad (no hay Speech-to-Text)."
    )
    mensaje: str = Field(description="Texto para mostrar y leer en voz alta.")
    contexto: ContextoVoz = Field(description="Reenviar en la siguiente consulta.")
    aclaracion: AclaracionSalida | None = None
