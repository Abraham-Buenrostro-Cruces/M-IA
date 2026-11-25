"""Catálogos cerrados del dominio (docs/arquitectura/03-datos.md, D-18).

Son la única fuente de estos valores: las restricciones CHECK de la base, la
validación del inventario de demostración y, después, el motor de rutas los
importan de aquí. Así un tipo nuevo no puede existir en un lugar y no en otro.
"""

SISTEMAS = ("METRO", "METROBUS", "TREN_LIGERO")

# Agencia GTFS -> sistema. El feed de la CDMX trae también RTP, trolebús, corredores
# concesionados, etc., que quedan fuera del alcance del MVP.
AGENCIA_A_SISTEMA = {"METRO": "METRO", "MB": "METROBUS", "TL": "TREN_LIGERO"}

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
ESTADOS_VALIDACION = ("RECIBIDO", "VALIDADO", "ZONA_GRIS", "RECHAZADO")
VOTOS = ("CONFIRMA", "NIEGA")
CAUSAS_CAMBIO_ESTADO = ("reporte", "oficial", "decaimiento", "moderador")
RESULTADOS_VIAJE = ("completado", "barrera_encontrada", "sin_dato")
ESTADOS_OPERACION = ("abierta", "cerrada_obra")

# Origen de cada dato del inventario. DEMO = datos de demostración (CLAUDE.md, regla 4).
FUENTES_INVENTARIO = ("DEMO", "GTFS", "OFICIAL", "COMUNIDAD")
