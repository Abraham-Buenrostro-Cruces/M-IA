"""Contrato de ``POST /rutas/plan`` (F2-5)."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.dominio import catalogos as cat

TipoMovilidad = Literal[cat.TIPOS_MOVILIDAD]  # type: ignore[valid-type]


class Ubicacion(BaseModel):
    """Coordenadas **o** clave de estación (p. ej. ``METRO-TASQUENA``), no ambas."""

    lat: float | None = Field(None, ge=19.0, le=19.8, description="Latitud (zona metropolitana)")
    lon: float | None = Field(None, ge=-99.5, le=-98.8)
    clave_estacion: str | None = Field(None, examples=["METRO-TASQUENA"])

    @model_validator(mode="after")
    def _exactamente_una_forma(self) -> Self:
        con_coordenadas = self.lat is not None and self.lon is not None
        if con_coordenadas == (self.clave_estacion is not None):
            raise ValueError("Indica lat y lon, o clave_estacion (exactamente una de las dos).")
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat y lon van juntas.")
        return self


class PerfilEntrada(BaseModel):
    """Perfil de movilidad. Basta ``tipo_movilidad`` para usar el predefinido; los demás
    campos lo ajustan (el perfil anónimo de la PWA viaja completo).

    Dato sensible (D-16, regla 6): se usa sólo para calcular y nunca se registra.
    """

    tipo_movilidad: TipoMovilidad
    escalones_max: int | None = Field(None, ge=0)
    pendiente_max_pct: float | None = Field(None, ge=0, le=30)
    puede_escalera_electrica: bool | None = None
    distancia_pie_max_m: int | None = Field(None, ge=50, le=5000)
    peso_seguridad_vs_tiempo: float | None = Field(None, ge=0, le=1)


class PeticionPlan(BaseModel):
    origen: Ubicacion
    destino: Ubicacion
    perfil: PerfilEntrada
    max_transbordos: int | None = Field(None, ge=0, le=5)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "origen": {"clave_estacion": "METRO-TASQUENA"},
                    "destino": {"lat": 19.42965, "lon": -99.1323},
                    "perfil": {"tipo_movilidad": "silla_manual"},
                }
            ]
        }
    }


class PasoSalida(BaseModel):
    tipo: str
    descripcion: str
    duracion_s: int
    estacion: str | None
    equipo: str | None


class EquipoCritico(BaseModel):
    codigo: str
    tipo: str
    referencia: str
    estacion: str
    nombre_estacion: str
    estado: str
    prob_operativo: float
    ultima_verificacion: datetime | None
    horas_desde_verificacion: float | None


class PlanBSalida(BaseModel):
    equipo: str
    descripcion: str


class AlternativaSalida(BaseModel):
    orden: int
    recomendada: bool
    resumen: str
    iar: float
    categoria_iar: Literal["alta", "media", "baja"]
    tiempo_total_min: float
    distancia_pie_m: int
    transbordos: int
    pasos: list[PasoSalida]
    equipos_criticos: list[EquipoCritico]
    planes_b: list[PlanBSalida]
    explicacion: str
    advertencias: list[str]
    trazo: list[tuple[float, float]] = Field(description="Puntos (lat, lon) para el mapa")


class DescartadaSalida(BaseModel):
    resumen: str
    motivo: str


class ObstaculoSalida(BaseModel):
    estacion: str | None
    descripcion: str


class RespuestaPlan(BaseModel):
    hay_ruta_segura: bool
    aviso: str | None
    alternativas: list[AlternativaSalida]
    descartadas: list[DescartadaSalida]
    obstaculos: list[ObstaculoSalida]
    sugerencias: list[str]
    datos_demostracion: bool = Field(
        description="El inventario y/o los estados de equipos son de demostración (regla 4)."
    )
    calculado_en: datetime
