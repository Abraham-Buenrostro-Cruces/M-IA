"""CaminataProveedor local: línea recta × factor de rodeo (08 §11.5)."""

from app.dominio.red import Punto, Tramo, distancia_m

# Cociente típico entre la distancia por calle y la distancia en línea recta en una
# traza urbana en retícula como la del centro de la CDMX (en una retícula perfecta es
# 4/π ≈ 1.27 en promedio). Es un supuesto del modo local; en modo gcp lo sustituye
# Routes API.
FACTOR_RODEO = 1.3


class CaminataLineaRecta:
    def __init__(self, factor_rodeo: float = FACTOR_RODEO):
        self.factor_rodeo = factor_rodeo

    def tramo(self, origen: Punto, destino: Punto) -> Tramo:
        return Tramo(distancia_m(origen, destino) * self.factor_rodeo, (origen, destino))
