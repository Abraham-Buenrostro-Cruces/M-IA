"""Modelo relacional de api-core (docs/arquitectura/03-datos.md, con D-18).

Notas de diseño:
- Los catálogos se aplican con CHECK sobre VARCHAR, no con ENUM de Postgres:
  agregar un valor a un ENUM requiere migraciones especiales y no se puede
  hacer dentro de una transacción; un CHECK se reemplaza en una migración normal.
- Las geometrías son POINT en EPSG:4326 (lat/lon del GTFS). Las distancias se
  calculan casteando a ``geography`` para obtener metros sobre el elipsoide.
- ``estado_equipo`` es 1–1 con el equipo y guarda los parámetros Beta (alfa, beta)
  del estimador; ``historial_estado`` es la bitácora de transiciones.
"""

import uuid
from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.dominio import catalogos as cat

# Longitud de los códigos legibles de niveles y equipos ("<clave estación>/<parte>").
# Los nombres oficiales largos (p. ej. "Etiopía y Plaza de la Transparencia") los llevan a ~70.
LONGITUD_CODIGO = 120

# Nombres de restricciones deterministas: Alembic los necesita para poder
# borrarlas o modificarlas en migraciones futuras.
CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _en(columna: str, valores: tuple[str, ...]) -> str:
    """Expresión SQL ``columna IN ('a', 'b', ...)`` para un CHECK de catálogo."""
    lista = ", ".join(f"'{v}'" for v in valores)
    return f"{columna} IN ({lista})"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _punto(nullable: bool = True):
    return mapped_column(Geometry("POINT", srid=4326, spatial_index=True), nullable=nullable)


def _ahora() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


# --------------------------------------------------------------------------- personas


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (CheckConstraint(_en("rol", cat.ROLES), name="rol"),)

    id_usuario: Mapped[uuid.UUID] = _uuid_pk()
    # El uid de Identity Platform no es un UUID (cadena de ~28 caracteres), por eso
    # va en su propia columna en lugar de usarse como llave primaria.
    uid_identidad: Mapped[str | None] = mapped_column(String(128), unique=True)
    alias: Mapped[str | None] = mapped_column(String(80))
    rol: Mapped[str] = mapped_column(String(20), default="usuario")
    reputacion: Mapped[float] = mapped_column(Float, default=0.5)
    consentimiento_sensibles_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = _ahora()


class PerfilAccesibilidad(Base):
    """Necesidades funcionales, nunca diagnósticos (D-16). Dato sensible: regla de seguridad 6.

    ``id_usuario`` nulo = perfil predefinido (semilla de F1-5) que la persona puede
    tomar como punto de partida.
    """

    __tablename__ = "perfil_accesibilidad"
    __table_args__ = (
        CheckConstraint(_en("tipo_movilidad", cat.TIPOS_MOVILIDAD), name="tipo_movilidad"),
        CheckConstraint("pendiente_max_pct >= 0", name="pendiente_no_negativa"),
        CheckConstraint("escalones_max >= 0", name="escalones_no_negativos"),
        CheckConstraint("peso_seguridad_vs_tiempo BETWEEN 0 AND 1", name="peso_seguridad_en_rango"),
    )

    id_perfil: Mapped[uuid.UUID] = _uuid_pk()
    id_usuario: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="CASCADE")
    )
    nombre: Mapped[str] = mapped_column(String(80))
    tipo_movilidad: Mapped[str] = mapped_column(String(20))
    requiere_elevador: Mapped[bool] = mapped_column(Boolean)
    pendiente_max_pct: Mapped[float] = mapped_column(Float)
    escalones_max: Mapped[int] = mapped_column(Integer)
    puede_escalera_electrica: Mapped[bool] = mapped_column(Boolean)
    distancia_pie_max_m: Mapped[int] = mapped_column(Integer)
    peso_seguridad_vs_tiempo: Mapped[float] = mapped_column(Float)
    prefiere_voz: Mapped[bool] = mapped_column(Boolean, default=False)


# --------------------------------------------------------------------------- red de transporte


class Estacion(Base):
    __tablename__ = "estacion"
    __table_args__ = (
        CheckConstraint(_en("sistema", cat.SISTEMAS), name="sistema"),
        CheckConstraint(_en("estado_operacion", cat.ESTADOS_OPERACION), name="estado_operacion"),
        UniqueConstraint("clave", name="uq_estacion_clave"),
    )

    id_estacion: Mapped[uuid.UUID] = _uuid_pk()
    # Clave estable y legible (p. ej. METRO-HIDALGO): la usa el inventario de demostración
    # para referirse a la estación sin depender de los UUID generados en cada carga.
    clave: Mapped[str] = mapped_column(String(60))
    nombre: Mapped[str] = mapped_column(String(120))
    sistema: Mapped[str] = mapped_column(String(12))
    ubicacion = _punto(nullable=False)
    alcaldia: Mapped[str | None] = mapped_column(String(60))
    # Peor valor entre las paradas GTFS agrupadas (0 = sin dato, 1 = accesible, 2 = no).
    wheelchair_boarding_gtfs: Mapped[int] = mapped_column(Integer, default=0)
    estado_operacion: Mapped[str] = mapped_column(String(15), default="abierta")


class RutaTransporte(Base):
    __tablename__ = "ruta_transporte"
    __table_args__ = (
        CheckConstraint(_en("sistema", cat.SISTEMAS), name="sistema"),
        UniqueConstraint("route_id_gtfs", name="uq_ruta_transporte_route_id_gtfs"),
    )

    id_ruta: Mapped[uuid.UUID] = _uuid_pk()
    route_id_gtfs: Mapped[str] = mapped_column(String(40))
    sistema: Mapped[str] = mapped_column(String(12))
    nombre_linea: Mapped[str] = mapped_column(String(20))  # "2", "A", "L12"
    nombre_largo: Mapped[str | None] = mapped_column(String(120))
    color: Mapped[str | None] = mapped_column(String(7))
    # Intervalo medio entre trenes (frequencies.txt). La espera esperada al abordar es la
    # mitad: con llegadas aleatorias de pasajeros, E[espera] = intervalo / 2.
    intervalo_medio_s: Mapped[int | None] = mapped_column(Integer)


class EstacionRuta(Base):
    """Secuencia de estaciones de una ruta en cada dirección.

    Una fila por (ruta, dirección, secuencia). ``direccion`` es la terminal hacia la
    que se viaja (el ``trip_headsign`` del GTFS), que es como se señaliza en los andenes.
    ``tiempo_desde_anterior_s`` sale de ``stop_times`` y será el costo t_e de las
    aristas de viaje en tren (F2).
    """

    __tablename__ = "estacion_ruta"

    id_ruta: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ruta_transporte.id_ruta", ondelete="CASCADE"), primary_key=True
    )
    direccion: Mapped[str] = mapped_column(String(120), primary_key=True)
    secuencia: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_estacion: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("estacion.id_estacion", ondelete="CASCADE"), index=True
    )
    stop_id_gtfs: Mapped[str] = mapped_column(String(60))
    tiempo_desde_anterior_s: Mapped[int | None] = mapped_column(Integer)


class UnidadTransporte(Base):
    __tablename__ = "unidad_transporte"

    id_unidad: Mapped[uuid.UUID] = _uuid_pk()
    id_ruta: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ruta_transporte.id_ruta", ondelete="CASCADE")
    )
    tipo_unidad: Mapped[str] = mapped_column(String(40))
    abordaje_a_nivel: Mapped[bool] = mapped_column(Boolean)
    espacio_silla: Mapped[bool] = mapped_column(Boolean)
    rampa_abordaje: Mapped[bool] = mapped_column(Boolean)


# ------------------------------------------------------------- interior de estaciones (D-18)


class Nivel(Base):
    """Nodo del grafo: salida a la calle, vestíbulo, pasillo o andén (uno por línea y dirección)."""

    __tablename__ = "nivel"
    __table_args__ = (
        CheckConstraint(_en("tipo", cat.TIPOS_NIVEL), name="tipo"),
        # Un andén siempre pertenece a una línea y una dirección; los demás niveles no.
        CheckConstraint(
            "(tipo = 'ANDEN') = (id_ruta IS NOT NULL AND direccion IS NOT NULL)",
            name="anden_con_ruta_y_direccion",
        ),
        CheckConstraint(_en("fuente", cat.FUENTES_INVENTARIO), name="fuente"),
        UniqueConstraint("codigo", name="uq_nivel_codigo"),
    )

    id_nivel: Mapped[uuid.UUID] = _uuid_pk()
    id_estacion: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("estacion.id_estacion", ondelete="CASCADE"), index=True
    )
    codigo: Mapped[str] = mapped_column(String(LONGITUD_CODIGO))
    tipo: Mapped[str] = mapped_column(String(10))
    id_ruta: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ruta_transporte.id_ruta"))
    direccion: Mapped[str | None] = mapped_column(String(120))
    referencia: Mapped[str | None] = mapped_column(String(160))
    ubicacion = _punto()
    fuente: Mapped[str] = mapped_column(String(10))


class InfraestructuraAccesible(Base):
    """Equipo con estado dinámico. Habilita 1–N conexiones (un elevador con tres paradas, dos)."""

    __tablename__ = "infraestructura_accesible"
    __table_args__ = (
        CheckConstraint(_en("tipo", cat.TIPOS_EQUIPO), name="tipo"),
        CheckConstraint(_en("fuente", cat.FUENTES_INVENTARIO), name="fuente"),
        UniqueConstraint("codigo", name="uq_infraestructura_accesible_codigo"),
    )

    id_equipo: Mapped[uuid.UUID] = _uuid_pk()
    id_estacion: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("estacion.id_estacion", ondelete="CASCADE"), index=True
    )
    codigo: Mapped[str] = mapped_column(String(LONGITUD_CODIGO))
    tipo: Mapped[str] = mapped_column(String(20))
    ubicacion = _punto()
    referencia: Mapped[str | None] = mapped_column(String(160))
    fuente: Mapped[str] = mapped_column(String(10))
    verificado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Conexion(Base):
    """Arista interna de una estación entre dos niveles (D-18)."""

    __tablename__ = "conexion"
    __table_args__ = (
        CheckConstraint(_en("tipo", cat.TIPOS_CONEXION), name="tipo"),
        CheckConstraint("id_nivel_desde <> id_nivel_hasta", name="niveles_distintos"),
        # Pasillos y escaleras fijas no dependen de un equipo; todo lo demás sí.
        CheckConstraint(
            f"({_en('tipo', cat.TIPOS_CONEXION_SIN_EQUIPO)}) = (id_equipo IS NULL)",
            name="equipo_segun_tipo",
        ),
        CheckConstraint("escalones >= 0", name="escalones_no_negativos"),
        CheckConstraint(_en("fuente", cat.FUENTES_INVENTARIO), name="fuente"),
    )

    id_conexion: Mapped[uuid.UUID] = _uuid_pk()
    id_nivel_desde: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nivel.id_nivel", ondelete="CASCADE"), index=True
    )
    id_nivel_hasta: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nivel.id_nivel", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(20))
    id_equipo: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("infraestructura_accesible.id_equipo", ondelete="CASCADE"), index=True
    )
    bidireccional: Mapped[bool] = mapped_column(Boolean, default=True)
    escalones: Mapped[int] = mapped_column(Integer, default=0)
    pendiente_pct: Mapped[float] = mapped_column(Float, default=0.0)
    longitud_m: Mapped[float] = mapped_column(Float)
    tiempo_s: Mapped[int] = mapped_column(Integer)
    fuente: Mapped[str] = mapped_column(String(10))


# --------------------------------------------------------------------------- estado de equipos


class EstadoEquipo(Base):
    __tablename__ = "estado_equipo"
    __table_args__ = (
        CheckConstraint(_en("estado", cat.ESTADOS_EQUIPO), name="estado"),
        CheckConstraint("alfa > 0 AND beta > 0", name="beta_valida"),
        CheckConstraint("prob_operativo BETWEEN 0 AND 1", name="prob_en_rango"),
    )

    id_equipo: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("infraestructura_accesible.id_equipo", ondelete="CASCADE"), primary_key=True
    )
    # Valor por defecto DESCONOCIDO: un equipo recién inventariado sin evidencia
    # nunca se presume accesible (regla de seguridad 1).
    estado: Mapped[str] = mapped_column(String(20), default="DESCONOCIDO")
    prob_operativo: Mapped[float] = mapped_column(Float)
    alfa: Mapped[float] = mapped_column(Float)
    beta: Mapped[float] = mapped_column(Float)
    confianza: Mapped[float] = mapped_column(Float, default=0.0)
    fuente_ultima: Mapped[str | None] = mapped_column(String(20))
    actualizado_en: Mapped[datetime] = _ahora()
    expira_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HistorialEstado(Base):
    __tablename__ = "historial_estado"
    __table_args__ = (
        CheckConstraint(_en("estado_nuevo", cat.ESTADOS_EQUIPO), name="estado_nuevo"),
        CheckConstraint(_en("causa", cat.CAUSAS_CAMBIO_ESTADO), name="causa"),
    )

    id_evento: Mapped[uuid.UUID] = _uuid_pk()
    id_equipo: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("infraestructura_accesible.id_equipo", ondelete="CASCADE"), index=True
    )
    estado_anterior: Mapped[str | None] = mapped_column(String(20))
    estado_nuevo: Mapped[str] = mapped_column(String(20))
    causa: Mapped[str] = mapped_column(String(15))
    id_reporte: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reporte_comunitario.id_reporte", ondelete="SET NULL")
    )
    ocurrido_en: Mapped[datetime] = _ahora()


# --------------------------------------------------------------------------- reportes


class ReporteComunitario(Base):
    __tablename__ = "reporte_comunitario"
    __table_args__ = (
        CheckConstraint(_en("canal", cat.CANALES), name="canal"),
        CheckConstraint(_en("estado_validacion", cat.ESTADOS_VALIDACION), name="estado_validacion"),
    )

    id_reporte: Mapped[uuid.UUID] = _uuid_pk()
    id_usuario: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="SET NULL")
    )
    id_estacion: Mapped[uuid.UUID] = mapped_column(ForeignKey("estacion.id_estacion"), index=True)
    id_equipo: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("infraestructura_accesible.id_equipo"), index=True
    )
    tipo_problema: Mapped[str] = mapped_column(String(40))
    descripcion: Mapped[str | None] = mapped_column(Text)
    canal: Mapped[str] = mapped_column(String(5), default="texto")
    ubicacion = _punto()
    precision_m: Mapped[int | None] = mapped_column(Integer)
    estado_validacion: Mapped[str] = mapped_column(String(12), default="RECIBIDO")
    puntaje_confianza: Mapped[float | None] = mapped_column(Float)
    id_reporte_padre: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reporte_comunitario.id_reporte", ondelete="SET NULL")
    )
    creado_en: Mapped[datetime] = _ahora()


class EvidenciaFotografica(Base):
    __tablename__ = "evidencia_fotografica"

    id_evidencia: Mapped[uuid.UUID] = _uuid_pk()
    id_reporte: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reporte_comunitario.id_reporte", ondelete="CASCADE"), index=True
    )
    uri_original: Mapped[str] = mapped_column(String(400))
    uri_redactada: Mapped[str | None] = mapped_column(String(400))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    phash: Mapped[str | None] = mapped_column(String(32))
    gps_coincide: Mapped[bool | None] = mapped_column(Boolean)
    resultado_vision: Mapped[dict | None] = mapped_column(JSONB)
    resultado_gemini: Mapped[dict | None] = mapped_column(JSONB)
    etiqueta_ia: Mapped[str | None] = mapped_column(String(40))
    confianza_ia: Mapped[float | None] = mapped_column(Float)
    creado_en: Mapped[datetime] = _ahora()


class ValidacionComunitaria(Base):
    __tablename__ = "validacion_comunitaria"
    __table_args__ = (
        CheckConstraint(_en("voto", cat.VOTOS), name="voto"),
        # Una persona vota una sola vez por reporte (evita inflar la corroboración).
        UniqueConstraint("id_reporte", "id_usuario", name="uq_validacion_un_voto_por_persona"),
    )

    id_validacion: Mapped[uuid.UUID] = _uuid_pk()
    id_reporte: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reporte_comunitario.id_reporte", ondelete="CASCADE")
    )
    id_usuario: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="CASCADE")
    )
    voto: Mapped[str] = mapped_column(String(8))
    creado_en: Mapped[datetime] = _ahora()


# --------------------------------------------------------------------------- ML y recomendaciones


class PrediccionFalla(Base):
    __tablename__ = "prediccion_falla"
    __table_args__ = (
        CheckConstraint("prob_falla BETWEEN 0 AND 1", name="prob_en_rango"),
        UniqueConstraint(
            "id_equipo",
            "fecha_objetivo",
            "franja_horaria",
            "version_modelo",
            name="uq_prediccion_por_franja",
        ),
    )

    id_prediccion: Mapped[uuid.UUID] = _uuid_pk()
    id_equipo: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("infraestructura_accesible.id_equipo", ondelete="CASCADE")
    )
    fecha_objetivo: Mapped[date] = mapped_column(Date)
    franja_horaria: Mapped[str] = mapped_column(String(20))
    prob_falla: Mapped[float] = mapped_column(Float)
    version_modelo: Mapped[str] = mapped_column(String(40))
    factores_principales: Mapped[dict | None] = mapped_column(JSONB)
    generado_en: Mapped[datetime] = _ahora()


class RecomendacionRuta(Base):
    __tablename__ = "recomendacion_ruta"
    __table_args__ = (
        CheckConstraint(_en("canal", cat.CANALES), name="canal"),
        CheckConstraint(
            f"resultado_viaje IS NULL OR {_en('resultado_viaje', cat.RESULTADOS_VIAJE)}",
            name="resultado_viaje",
        ),
        CheckConstraint("iar IS NULL OR iar BETWEEN 0 AND 100", name="iar_en_rango"),
    )

    id_recomendacion: Mapped[uuid.UUID] = _uuid_pk()
    id_usuario: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="SET NULL")
    )
    id_perfil: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("perfil_accesibilidad.id_perfil", ondelete="SET NULL")
    )
    origen = _punto(nullable=False)
    destino = _punto(nullable=False)
    canal: Mapped[str] = mapped_column(String(5), default="texto")
    alternativas: Mapped[dict] = mapped_column(JSONB)
    alternativa_elegida: Mapped[int | None] = mapped_column(Integer)
    iar: Mapped[float | None] = mapped_column(Float)
    resultado_viaje: Mapped[str | None] = mapped_column(String(20))
    version_motor: Mapped[str] = mapped_column(String(20))
    solicitada_en: Mapped[datetime] = _ahora()
