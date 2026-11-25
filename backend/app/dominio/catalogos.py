"""Catálogos cerrados del dominio (docs/arquitectura/03-datos.md, D-18).

Son la única fuente de estos valores: las restricciones CHECK de la base, la
validación del inventario de demostración y, después, el motor de rutas los
importan de aquí. Así un tipo nuevo no puede existir en un lugar y no en otro.
"""

SISTEMAS = ("METRO", "METROBUS", "TREN_LIGERO", "TREN_SUBURBANO", "TREN_INTERURBANO")

# Agencia GTFS -> sistema (D-25). El feed de la CDMX trae también RTP, trolebús,
# Cablebús, corredores concesionados, etc., que quedan fuera del alcance.
AGENCIA_A_SISTEMA = {
    "METRO": "METRO",
    "MB": "METROBUS",
    "TL": "TREN_LIGERO",
    "SUB": "TREN_SUBURBANO",
    "INTERURBANO": "TREN_INTERURBANO",
}

# Nombre para la persona. El Interurbano México–Toluca opera como "Tren El Insurgente".
NOMBRE_SISTEMA = {
    "METRO": "Metro",
    "METROBUS": "Metrobús",
    "TREN_LIGERO": "Tren Ligero",
    "TREN_SUBURBANO": "Tren Suburbano",
    "TREN_INTERURBANO": "Tren El Insurgente",
}

ESTADOS_EQUIPO = (
    "OPERATIVO",
    "FALLA_PROBABLE",
    "FALLA_CONFIRMADA",
    "DESCONOCIDO",
    "MANTENIMIENTO",
)

TIPOS_NIVEL = ("CALLE", "VESTIBULO", "ANDEN", "PASILLO")

# Tipos de equipo: tienen estado dinámico porque pueden fallar o bloquearse.
TIPOS_EQUIPO = ("ELEVADOR", "RAMPA", "SALVAESCALERAS", "ESCALERA_ELECTRICA", "ACCESO_A_NIVEL")

# Tipos de conexión entre niveles. PASILLO y ESCALERA_FIJA no tienen equipo ni estado,
# pero se modelan porque son las barreras que filtran las restricciones duras (D-18).
TIPOS_CONEXION = (*TIPOS_EQUIPO, "PASILLO", "ESCALERA_FIJA")
TIPOS_CONEXION_SIN_EQUIPO = ("PASILLO", "ESCALERA_FIJA")

TIPOS_MOVILIDAD = ("silla_manual", "silla_electrica", "andadera", "adulto_mayor", "carriola")

ROLES = ("usuario", "moderador", "operador", "admin")
CANALES = ("texto", "voz")
# Estados de validación de un reporte (documento 04 §7.3, D-23).
ESTADOS_VALIDACION = (
    "PENDIENTE",  # recibido, aún sin validar
    "VERIFICADO_AUTO",  # s >= 0.75
    "PENDIENTE_CORROBORACION",  # 0.40 <= s < 0.75: zona gris, a moderación y corroboración
    "BAJA_CONFIANZA",  # s < 0.40
    "CONFIRMADO_MODERADOR",
    "RECHAZADO",
)
# Lo que la persona reporta. "funciona" es evidencia a favor del equipo.
TIPOS_PROBLEMA = ("fuera_de_servicio", "bloqueado", "danado", "funciona")
# Avisos: evidencia con autoridad que fija el estado (D-21).
FUENTES_AVISO = ("OFICIAL", "MODERADOR", "DEMO")
ESTADOS_AVISO = ("OPERATIVO", "FALLA_CONFIRMADA", "MANTENIMIENTO")
VOTOS = ("CONFIRMA", "NIEGA")
CAUSAS_CAMBIO_ESTADO = ("reporte", "oficial", "decaimiento", "moderador", "voto", "demo")
RESULTADOS_VIAJE = ("completado", "barrera_encontrada", "sin_dato")
ESTADOS_OPERACION = ("abierta", "cerrada_obra")

# Origen de cada dato del inventario. DEMO = datos de demostración (CLAUDE.md, regla 4).
FUENTES_INVENTARIO = ("DEMO", "GTFS", "OFICIAL", "COMUNIDAD")
