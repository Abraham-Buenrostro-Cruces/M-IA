"""Puertos (interfaces) entre el dominio y el mundo exterior — patrón de adaptadores, D-10.

Cada puerto es un ``typing.Protocol`` con dos implementaciones:
``adaptadores/local`` (simulada, determinista, sin red) y ``adaptadores/gcp`` (real).
``RA_MODO`` decide cuál se inyecta. El dominio y los módulos dependen *sólo* de estos
protocolos; las bibliotecas ``google-cloud-*`` y ``google-genai`` se importan únicamente
dentro de ``adaptadores/gcp``.

Puertos previstos (docs/arquitectura/08-mvp-y-tecnologias.md §11.5); se definen
en la fase que los usa:

- ``CaminataProveedor``  (F2) — tramos a pie
- ``Geocodificador``     (F3) — texto/lugar → coordenadas
- ``AlmacenEvidencias``  (F4) — fotos de reportes
- ``BusEventos``         (F4) — reporte-recibido, reporte-validado, estado-cambiado
- ``AnalizadorImagen``   (F4) — Vision API + Gemini
- ``TranscriptorVoz``    (F5) — Speech-to-Text v2
- ``InterpreteLenguaje`` (F5) — intención y entidades con Gemini
- ``ProveedorIdentidad`` (F6) — Identity Platform

Regla de seguridad 6: el perfil de accesibilidad nunca forma parte de los argumentos
de un puerto que llame a una API de IA.
"""

from collections.abc import Callable
from typing import Protocol

from app.dominio.estaciones import Lugar
from app.dominio.red import Punto, Tramo
from app.dominio.validacion import AnalisisImagen


class CaminataProveedor(Protocol):
    """Distancia a pie real entre dos puntos (F2-5).

    Sólo recibe coordenadas: la velocidad y los límites del perfil los aplica el
    motor, así el perfil nunca sale hacia una API externa (regla de seguridad 6).
    """

    def tramo(self, origen: Punto, destino: Punto) -> Tramo: ...


class Geocodificador(Protocol):
    """Texto -> lugares candidatos (F3-1). Sólo recibe el texto que la persona escribió."""

    def buscar(self, texto: str, limite: int = 8) -> list[Lugar]: ...


class AlmacenEvidencias(Protocol):
    """Fotos de reportes (F4-2). Original privada; sólo la versión saneada se muestra.

    En la nube la PWA sube directo a Cloud Storage con una URL firmada: el backend nunca
    recibe el archivo (06-flujos). En local se emula con un token de un solo propósito.
    """

    def url_subida(self, id_objeto: str, segundos: int) -> str: ...

    def leer_original(self, id_objeto: str) -> bytes | None: ...

    def guardar_redactada(self, id_objeto: str, contenido: bytes) -> None: ...

    def leer_redactada(self, id_objeto: str) -> bytes | None: ...


class BusEventos(Protocol):
    """Eventos reporte-creado, reporte-validado, estado-cambiado (Pub/Sub en la nube)."""

    def publicar(self, tema: str, datos: dict) -> None: ...

    def suscribir(self, tema: str, manejador: Callable[[dict], None]) -> None: ...


class AnalizadorImagen(Protocol):
    """Vision API + Gemini en la nube (04 §7.3); simulado y determinista en local.

    Sólo recibe la imagen y el tipo de problema reportado: nunca datos de la persona.
    """

    def analizar(self, contenido: bytes, tipo_problema: str) -> AnalisisImagen: ...
