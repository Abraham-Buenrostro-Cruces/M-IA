"""Servicio de planificación: une el dominio con los datos y los adaptadores (F2-5).

- La topología se construye una vez (es estática).
- Los estados se leen con una caché de 60 s (06-flujos.md: "lectura con caché de 60 s"):
  una ruta refleja un cambio de estado a lo más un minuto después.
- Las caminatas de primera y última milla se piden a ``CaminataProveedor`` sólo para
  las salidas que, en línea recta, ya están dentro de la distancia máxima del perfil.
"""

import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime

from app.adaptadores.puertos import CaminataProveedor
from app.dominio.grafo import DESTINO, ORIGEN, Caminata, construir_topologia
from app.dominio.planificador import Peticion, ResultadoPlan, planear
from app.dominio.red import EstadoEquipo, Perfil, Punto, Red, distancia_m

VIGENCIA_CACHE_ESTADOS_S = 60.0


class EstacionDesconocidaError(LookupError):
    pass


class ServicioRutas:
    def __init__(
        self,
        red: Red,
        cargar_estados: Callable[[], dict[str, EstadoEquipo]],
        caminata: CaminataProveedor,
        *,
        datos_demostracion: bool = True,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.red = red
        self.topologia = construir_topologia(red)
        self.caminata = caminata
        self.datos_demostracion = datos_demostracion
        self._cargar_estados = cargar_estados
        self._reloj = reloj
        self._estados: dict[str, EstadoEquipo] = {}
        self._leido_en = float("-inf")
        self._candado = threading.Lock()
        self._calles = [n for n in red.niveles.values() if n.tipo == "CALLE"]

    def estados(self) -> dict[str, EstadoEquipo]:
        with self._candado:
            if time.monotonic() - self._leido_en > VIGENCIA_CACHE_ESTADOS_S:
                self._estados = self._cargar_estados()
                self._leido_en = time.monotonic()
            return self._estados

    def invalidar_estados(self) -> None:
        """Fuerza a releer los estados en la próxima petición (tras un estado-cambiado)."""
        with self._candado:
            self._leido_en = float("-inf")

    def punto_de_estacion(self, clave: str) -> Punto:
        """Centro de las salidas de la estación (para origen/destino dados por estación)."""
        salidas = [n for n in self._calles if n.clave_estacion == clave]
        if not salidas:
            raise EstacionDesconocidaError(clave)
        return Punto(
            sum(n.lat for n in salidas) / len(salidas), sum(n.lon for n in salidas) / len(salidas)
        )

    def _caminatas(self, origen: Punto, destino: Punto, perfil: Perfil) -> tuple[Caminata, ...]:
        maximo = perfil.distancia_pie_max_m
        res = []
        for n in self._calles:
            p = Punto(n.lat, n.lon)
            # La línea recta es cota inferior de la distancia a pie: si ya excede el
            # máximo, no hace falta consultar al proveedor.
            if distancia_m(origen, p) <= maximo:
                res.append(Caminata(ORIGEN, n.codigo, self.caminata.tramo(origen, p)))
            if distancia_m(p, destino) <= maximo:
                res.append(Caminata(n.codigo, DESTINO, self.caminata.tramo(p, destino)))
        if distancia_m(origen, destino) <= maximo:
            res.append(Caminata(ORIGEN, DESTINO, self.caminata.tramo(origen, destino)))
        return tuple(res)

    def planear(self, origen: Punto, destino: Punto, perfil: Perfil) -> ResultadoPlan:
        pet = Peticion(perfil, origen, destino, self._caminatas(origen, destino, perfil),
                       self._reloj())  # fmt: skip
        return planear(self.red, self.topologia, self.estados(), pet)
