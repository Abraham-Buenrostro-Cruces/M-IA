"""Escenario SINTÉTICO de estados para toda la red (F4B-4, D-25).

**Todo lo que produce este módulo son datos sintéticos de demostración.** Sin evidencia,
el estimador deja cada equipo en ``DESCONOCIDO`` y, por la regla de seguridad 1, ninguna
ruta en silla de ruedas sería posible. Este módulo reparte estados plausibles para que la
red completa se pueda simular con fallas, mantenimientos y datos faltantes.

No escribe estados (D-21): produce la *evidencia* que el estimador convierte en estado.

| Estado buscado    | Evidencia que se genera                               | Proporción |
|-------------------|-------------------------------------------------------|-----------:|
| OPERATIVO         | aviso DEMO de operación (hace 1–12 h)                 |      85 %  |
| FALLA_PROBABLE    | un reporte SINTÉTICO de falla sin foto, s = 0.6       |       7 %  |
| FALLA_CONFIRMADA  | aviso DEMO de falla (hace 2–48 h)                     |       4 %  |
| MANTENIMIENTO     | aviso DEMO de mantenimiento (hace 1–72 h)             |       2 %  |
| DESCONOCIDO       | ninguna                                               |       2 %  |

Las proporciones son un supuesto de demostración, no una medición; se cambian en
``REPARTO``. Cada equipo recibe su estado con un hash de ``semilla + código``: el
resultado no depende del orden del inventario y un equipo nuevo no cambia a los demás.

Los equipos de las estaciones ``protegidas`` (el corredor de los flujos documentados)
quedan operativos: sus estados los fija el escenario ``flujo1``, del que dependen las
pruebas e2e y la demostración.
"""

import zlib
from collections.abc import Iterable

import pandas as pd

SEMILLA = 20261125

# (estado, proporción acumulada, rango de horas desde la evidencia)
REPARTO: tuple[tuple[str, float, str], ...] = (
    ("OPERATIVO", 0.85, "1-12"),
    ("FALLA_PROBABLE", 0.92, "1-10"),
    ("FALLA_CONFIRMADA", 0.96, "2-48"),
    ("MANTENIMIENTO", 0.98, "1-72"),
    ("DESCONOCIDO", 1.00, ""),
)

NOTA = {
    "OPERATIVO": "SINTÉTICO: operación verificada",
    "FALLA_PROBABLE": "SINTÉTICO: un reporte de falla sin confirmar",
    "FALLA_CONFIRMADA": "SINTÉTICO: falla confirmada",
    "MANTENIMIENTO": "SINTÉTICO: en mantenimiento",
    "DESCONOCIDO": "SINTÉTICO: sin información reciente",
}

COLUMNAS = ["codigo_equipo", "estado", "horas_desde_verificacion", "nota"]


def uniforme(codigo: str, semilla: int = SEMILLA) -> float:
    """Número en [0, 1) fijo para cada código (CRC32: estable entre ejecuciones y equipos)."""
    return zlib.crc32(f"{semilla}|{codigo}".encode()) / 2**32


def estado_para(codigo: str, semilla: int = SEMILLA) -> tuple[str, str]:
    u = uniforme(codigo, semilla)
    for estado, hasta, horas in REPARTO:
        if u < hasta:
            return estado, horas
    return REPARTO[-1][0], REPARTO[-1][2]  # pragma: no cover (u < 1 siempre)


def generar(
    equipos: pd.DataFrame, protegidas: Iterable[str], semilla: int = SEMILLA
) -> pd.DataFrame:
    """Una fila por equipo con el estado sintético y las horas desde su evidencia.

    ``equipos`` necesita las columnas ``codigo`` y ``clave_estacion`` (equipos.csv).
    """
    protegidas = set(protegidas)
    filas = []
    for e in equipos.sort_values("codigo").itertuples():
        if e.clave_estacion in protegidas:
            estado, horas, nota = "OPERATIVO", "1-6", "Corredor de los flujos: lo fija flujo1"
        else:
            estado, horas = estado_para(e.codigo, semilla)
            nota = NOTA[estado]
        filas.append(
            {"codigo_equipo": e.codigo, "estado": estado, "horas_desde_verificacion": horas,
             "nota": nota}
        )  # fmt: skip
    return pd.DataFrame(filas, columns=COLUMNAS)
