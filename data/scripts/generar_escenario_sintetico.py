"""Genera el escenario SINTÉTICO de estados de toda la red (F4B-4).

Lee ``data/demo/equipos.csv`` y escribe ``data/synthetic/escenario_red.csv``: una fila por
equipo con el estado que debe producir su evidencia sintética. Es reproducible (semilla
fija); hay que volver a generarlo cuando cambia el inventario.

Las estaciones de las líneas 2 y 3 del Metro (el corredor de los flujos de
``06-flujos.md``) quedan operativas: sus estados los fija ``data/demo/escenarios/flujo1.csv``,
que ``aplicar_escenario_demo.py`` aplica encima de este archivo.

Uso (desde la raíz del repositorio):
    backend/.venv/Scripts/python data/scripts/generar_escenario_sintetico.py
"""

from pathlib import Path

import pandas as pd

from app.ingesta import escenario_sintetico as es

RAIZ = Path(__file__).resolve().parents[2]
DEMO = RAIZ / "data" / "demo"
SALIDA = RAIZ / "data" / "synthetic" / "escenario_red.csv"

ENCABEZADO = """\
# DATOS SINTÉTICOS de demostración: no describen el estado real de ningún equipo.
# Generado por data/scripts/generar_escenario_sintetico.py (semilla {semilla}); no se edita a mano.
# aplicar_escenario_demo.py lo carga como base y aplica encima el escenario elegido (flujo1).
"""


def main() -> None:
    equipos = pd.read_csv(DEMO / "equipos.csv", dtype=str)
    red = pd.read_csv(DEMO / "estaciones_red.csv", dtype=str)
    protegidas = red.loc[
        (red["sistema"] == "METRO")
        & red["lineas"].str.split(";").map(lambda ls: bool({"2", "3"} & set(ls))),
        "clave",
    ]
    escenario = es.generar(equipos, protegidas)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", encoding="utf-8", newline="\n") as f:
        f.write(ENCABEZADO.format(semilla=es.SEMILLA))
        escenario.to_csv(f, index=False, lineterminator="\n")

    print(f"Escenario SINTÉTICO de la red -> {SALIDA.relative_to(RAIZ)}")
    print(f"  equipos: {len(escenario)} ({len(protegidas)} estaciones protegidas por flujo1)")
    conteo = escenario["estado"].value_counts()
    for estado, n in conteo.items():
        print(f"  {estado}: {n} ({100 * n / len(escenario):.1f} %)")


if __name__ == "__main__":
    main()
