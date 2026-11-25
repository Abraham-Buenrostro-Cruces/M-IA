"""Geocodificador local: catálogo de estaciones + lugares de prueba (08 §11.5).

Coincidencia aproximada con RapidFuzz sobre nombres normalizados (sin acentos ni
mayúsculas), para que "taxqueña", "zocalo" o "CU" encuentren lo que la persona busca.
"""

import csv
import re
import unicodedata

from rapidfuzz import fuzz, process

from app.dominio.catalogos import NOMBRE_SISTEMA
from app.dominio.estaciones import EstacionResumen, Lugar

# Por debajo de este puntaje (0–100) un candidato se considera ruido.
PUNTAJE_MINIMO = 70


# Grafías equivalentes de uso común en la CDMX ("Taxqueña" y "Tasqueña" son la misma).
EQUIVALENCIAS = {"taxquena": "tasquena"}


def normalizar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    limpio = re.sub(r"[^a-z0-9 ]+", " ", sin_acentos.lower()).strip()
    return " ".join(EQUIVALENCIAS.get(p, p) for p in limpio.split())


def _puntaje(consulta: str, candidato: str, **_) -> float:
    """Mezcla de dos medidas de RapidFuzz.

    - ``token_set_ratio`` vale 100 si todas las palabras de la consulta están en el
      candidato ("museo ciudad" ⊂ "museo de la ciudad de mexico").
    - ``WRatio`` tolera errores de escritura ("tasquna").

    El peso mayor del primero evita que una coincidencia parcial larga ("arena ciudad de
    mexico") gane a la que contiene todas las palabras buscadas.
    """
    return 0.6 * fuzz.token_set_ratio(consulta, candidato) + 0.4 * fuzz.WRatio(consulta, candidato)


class GeocodificadorLocal:
    def __init__(self, estaciones: list[EstacionResumen], lugares: list[tuple[Lugar, list[str]]]):
        # Cada entrada: (texto normalizado con el que se compara, Lugar). Un lugar con alias
        # aparece varias veces; al final se deduplica por lugar.
        self._entradas: list[tuple[str, Lugar]] = []
        for e in estaciones:
            lineas = ", ".join(e.lineas)
            lugar = Lugar("estacion", e.nombre, e.lat, e.lon,
                          f"{NOMBRE_SISTEMA[e.sistema]} · Línea {lineas}" if lineas
                          else NOMBRE_SISTEMA[e.sistema], e.clave)  # fmt: skip
            self._entradas.append((normalizar(e.nombre), lugar))
        for lugar, alias in lugares:
            for nombre in [lugar.nombre, *alias]:
                self._entradas.append((normalizar(nombre), lugar))
        self._textos = [t for t, _ in self._entradas]

    def buscar(self, texto: str, limite: int = 8) -> list[Lugar]:
        consulta = normalizar(texto)
        if not consulta:
            return []
        # Los candidatos que empiezan con la consulta se ordenan primero.
        candidatos = process.extract(
            consulta, self._textos, scorer=_puntaje, limit=limite * 4,
            score_cutoff=PUNTAJE_MINIMO,
        )  # fmt: skip
        ordenados = sorted(
            candidatos,
            key=lambda c: (not self._textos[c[2]].startswith(consulta), -c[1], c[2]),
        )
        vistos, resultado = set(), []
        for _, _, i in ordenados:
            lugar = self._entradas[i][1]
            if id(lugar) in vistos:
                continue
            vistos.add(id(lugar))
            resultado.append(lugar)
            if len(resultado) == limite:
                break
        return resultado


def leer_lugares(ruta) -> list[tuple[Lugar, list[str]]]:
    """Lee data/demo/lugares.csv (las líneas que empiezan con # son comentarios)."""
    with open(ruta, encoding="utf-8") as f:
        filas = csv.DictReader(line for line in f if not line.startswith("#"))
        return [
            (
                Lugar("lugar", r["nombre"], float(r["lat"]), float(r["lon"]), r["detalle"]),
                [a.strip() for a in r["alias"].split(";") if a.strip()],
            )
            for r in filas
        ]
