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

from typing import Protocol

from app.dominio.estaciones import Lugar
from app.dominio.red import Punto, Tramo


class CaminataProveedor(Protocol):
    """Distancia a pie real entre dos puntos (F2-5).

    Sólo recibe coordenadas: la velocidad y los límites del perfil los aplica el
    motor, así el perfil nunca sale hacia una API externa (regla de seguridad 6).
    """

    def tramo(self, origen: Punto, destino: Punto) -> Tramo: ...


class Geocodificador(Protocol):
    """Texto -> lugares candidatos (F3-1). Sólo recibe el texto que la persona escribió."""

    def buscar(self, texto: str, limite: int = 8) -> list[Lugar]: ...
