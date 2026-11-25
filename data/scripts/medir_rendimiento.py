"""Mide la latencia de POST /rutas/plan sobre el corredor piloto (F2-5: p95 local < 1 s).

Genera N pares origen–destino reproducibles (semilla fija): puntos a menos de ~400 m
de estaciones del corredor, elegidas al azar, y alterna los 5 perfiles predefinidos.
Usa la aplicación real en proceso (TestClient) contra PostGIS, así se mide el
endpoint completo: validación, planificación y serialización.

Uso (desde la raíz del repositorio):
    backend/.venv/Scripts/python data/scripts/medir_rendimiento.py [N]
"""

import random
import statistics
import sys
import time
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app.ingesta.perfiles import PERFILES_SEMILLA
from app.main import app
from app.modulos.rutas.endpoints import obtener_servicio_rutas

SALIDA = Path(__file__).resolve().parents[2] / "data" / "reportes" / "rendimiento-rutas.md"
SEMILLA = 20261124
DESPLAZAMIENTO_GRADOS = 0.0035  # ~±390 m


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    rnd = random.Random(SEMILLA)
    cliente = TestClient(app)

    t0 = time.perf_counter()
    servicio = obtener_servicio_rutas()  # carga red y topología (una vez por proceso)
    carga_s = time.perf_counter() - t0
    estaciones = sorted({nv.clave_estacion for nv in servicio.red.niveles.values()})
    centros = {c: servicio.punto_de_estacion(c) for c in estaciones}

    def punto_cerca(clave):
        p = centros[clave]
        return {"lat": p.lat + rnd.uniform(-1, 1) * DESPLAZAMIENTO_GRADOS,
                "lon": p.lon + rnd.uniform(-1, 1) * DESPLAZAMIENTO_GRADOS}  # fmt: skip

    cliente.post("/rutas/plan", json={  # calentamiento: primera lectura de estados
        "origen": {"clave_estacion": estaciones[0]}, "destino": {"clave_estacion": estaciones[1]},
        "perfil": {"tipo_movilidad": "silla_manual"}})  # fmt: skip

    tiempos, seguras, por_perfil = [], 0, {}
    for i in range(n):
        a, b = rnd.sample(estaciones, 2)
        perfil = PERFILES_SEMILLA[i % len(PERFILES_SEMILLA)]["tipo_movilidad"]
        cuerpo = {"origen": punto_cerca(a), "destino": punto_cerca(b),
                  "perfil": {"tipo_movilidad": perfil}}  # fmt: skip
        t = time.perf_counter()
        r = cliente.post("/rutas/plan", json=cuerpo)
        tiempos.append(time.perf_counter() - t)
        r.raise_for_status()
        segura = r.json()["hay_ruta_segura"]
        seguras += segura
        tot, ok = por_perfil.get(perfil, (0, 0))
        por_perfil[perfil] = (tot + 1, ok + segura)

    tiempos.sort()
    p50 = statistics.median(tiempos)
    p95 = tiempos[max(int(0.95 * n) - 1, 0)]
    lineas = [
        f"# Rendimiento de POST /rutas/plan — {date.today().isoformat()}",
        "",
        f"- Pares origen–destino: {n} (semilla {SEMILLA}), en proceso con TestClient y "
        "PostGIS local.",
        f"- Red: {len(servicio.red.niveles)} niveles, {len(servicio.red.conexiones)} conexiones, "
        f"{servicio.topologia.number_of_edges()} aristas en la topología.",
        f"- Carga inicial de red y topología: {carga_s:.2f} s (una vez por proceso).",
        "",
        "| p50 | p95 | máximo | Criterio F2-5 |",
        "|---:|---:|---:|---|",
        f"| {p50 * 1000:.0f} ms | {p95 * 1000:.0f} ms | {tiempos[-1] * 1000:.0f} ms | "
        f"p95 < 1 s: {'✅ cumple' if p95 < 1 else '❌ no cumple'} |",
        "",
        "## Pares con ruta segura por perfil",
        "",
        "Con el escenario de demostración `flujo1` y el inventario que respeta el GTFS (D-19).",
        "",
        "| Perfil | Pares | Con ruta segura |",
        "|---|---:|---:|",
    ] + [f"| {p} | {t} | {ok} ({100 * ok / t:.0f} %) |" for p, (t, ok) in por_perfil.items()]
    SALIDA.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
