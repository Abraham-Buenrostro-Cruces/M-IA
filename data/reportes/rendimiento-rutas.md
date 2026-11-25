# Rendimiento de POST /rutas/plan — 2026-11-25

- Pares origen–destino: 100 (semilla 20261124), en proceso con TestClient y PostGIS local.
- Red: 3027 niveles, 3557 conexiones, 11526 aristas en la topología.
- Carga inicial de red y topología: 0.43 s (una vez por proceso).

| p50 | p95 | máximo | Criterio F2-5 |
|---:|---:|---:|---|
| 339 ms | 460 ms | 703 ms | p95 < 1 s: ✅ cumple |

## Pares con ruta segura por perfil

Con el escenario SINTÉTICO de la red + `flujo1` (F4B-4) y el inventario que respeta el GTFS (D-19). Alternativas por penalización (D-27).

| Perfil | Pares | Con ruta segura |
|---|---:|---:|
| silla_manual | 20 | 16 (80 %) |
| silla_electrica | 20 | 19 (95 %) |
| andadera | 20 | 12 (60 %) |
| adulto_mayor | 20 | 20 (100 %) |
| carriola | 20 | 18 (90 %) |
