# Rendimiento de POST /rutas/plan — 2026-11-24

- Pares origen–destino: 100 (semilla 20261124), en proceso con TestClient y PostGIS local.
- Red: 224 niveles, 248 conexiones, 750 aristas en la topología.
- Carga inicial de red y topología: 0.50 s (una vez por proceso).

| p50 | p95 | máximo | Criterio F2-5 |
|---:|---:|---:|---|
| 29 ms | 105 ms | 174 ms | p95 < 1 s: ✅ cumple |

## Pares con ruta segura por perfil

Con el escenario de demostración `flujo1` y el inventario que respeta el GTFS (D-19).

| Perfil | Pares | Con ruta segura |
|---|---:|---:|
| silla_manual | 20 | 1 (5 %) |
| silla_electrica | 20 | 11 (55 %) |
| andadera | 20 | 0 (0 %) |
| adulto_mayor | 20 | 20 (100 %) |
| carriola | 20 | 4 (20 %) |
