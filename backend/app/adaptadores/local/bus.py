"""BusEventos local: cola en proceso (emula Pub/Sub con suscripción push a Cloud Run).

- ``sincrono=True`` (pruebas): cada manejador corre en el momento de publicar, así las
  pruebas son deterministas.
- ``sincrono=False`` (servidor): un solo hilo de trabajo procesa los eventos en orden
  FIFO, sin bloquear la respuesta HTTP (POST /reportes responde 202 de inmediato).

Un error en un manejador se registra y no detiene a los demás: como en Pub/Sub, un
mensaje que falla no debe tumbar al publicador.
"""

import logging
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("ra.bus")


class BusEnProceso:
    def __init__(self, sincrono: bool = False):
        self._manejadores: dict[str, list[Callable[[dict], None]]] = defaultdict(list)
        self._ejecutor = None if sincrono else ThreadPoolExecutor(1, thread_name_prefix="bus")

    def suscribir(self, tema: str, manejador: Callable[[dict], None]) -> None:
        self._manejadores[tema].append(manejador)

    def publicar(self, tema: str, datos: dict) -> None:
        for manejador in list(self._manejadores[tema]):
            if self._ejecutor is None:
                self._ejecutar(tema, manejador, datos)
            else:
                self._ejecutor.submit(self._ejecutar, tema, manejador, datos)

    @staticmethod
    def _ejecutar(tema: str, manejador: Callable[[dict], None], datos: dict) -> None:
        try:
            manejador(datos)
        except Exception:
            # Sólo el tema y el identificador: nunca el contenido (puede traer ubicación).
            log.exception("Falló un manejador de %s (id=%s)", tema, datos.get("id"))

    def esperar(self) -> None:
        """Espera a que se vacíe la cola (útil en scripts y pruebas de integración)."""
        if self._ejecutor is not None:
            self._ejecutor.submit(lambda: None).result()
