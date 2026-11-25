"""Dependencias de los trabajadores (worker-validacion y worker-estado).

En local corren dentro de api-core suscritos al BusEnProceso; en la nube cada uno será un
servicio de Cloud Run con suscripción push de Pub/Sub, con el mismo código de manejador.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import sessionmaker

from app.adaptadores.puertos import AlmacenEvidencias, AnalizadorImagen, BusEventos

# Temas de eventos (nombres de los tópicos de Pub/Sub, documento 02).
REPORTE_CREADO = "reporte-creado"
REPORTE_VALIDADO = "reporte-validado"
AVISO_CREADO = "aviso-creado"
VOTO_REGISTRADO = "voto-registrado"
ESTADO_CAMBIADO = "estado-cambiado"


@dataclass
class Contexto:
    sesiones: sessionmaker
    almacen: AlmacenEvidencias
    analizador: AnalizadorImagen
    bus: BusEventos
    reloj: Callable[[], datetime]
