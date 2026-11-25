# ⚠️ Datos de demostración — no son el inventario real del Metro

Esta carpeta contiene el **inventario de demostración** del corredor piloto de RutaAccesible
(Metro Líneas 2 y 3, decisión D-17). No existe un inventario público de elevadores, rampas y
escaleras del STC Metro, así que estos datos se **generan con plantillas** para que el
sistema pueda funcionar y demostrarse. Toda fila lleva `fuente = DEMO`.

Lo que **sí** es real:
- Las estaciones, líneas, direcciones, coordenadas de andén y tiempos entre estaciones (GTFS de la CDMX).
- Qué estaciones tienen accesibilidad: se respeta el `wheelchair_boarding` del GTFS (D-19).

Lo que es **supuesto de demostración**:
- Los nombres de salidas, la cantidad y ubicación de elevadores, rampas y escaleras eléctricas,
  los escalones, longitudes y tiempos dentro de cada estación.

## Archivos

| Archivo | Edición | Contenido |
|---|---|---|
| `estaciones_corredor.csv` | **A mano** | Una fila por estación: plantilla, accesibilidad, salidas y tipo de acceso de cada salida. |
| `niveles.csv` | Generado | Nodos del grafo: salidas, vestíbulos y andenes por línea y dirección (tabla `nivel`). |
| `equipos.csv` | Generado | Elevadores, rampas y escaleras eléctricas (tabla `infraestructura_accesible`). |
| `conexiones.csv` | Generado | Aristas internas de cada estación, incluidas las escaleras fijas (tabla `conexion`). |

No edites los archivos generados: cambia el catálogo y vuelve a ejecutar
`data/scripts/generar_inventario_demo.py`.

## Columnas del catálogo

- `plantilla`: `AUTO` (terminal → andén central; de paso → andenes laterales), `LATERAL` o `CENTRAL`.
- `accesibilidad`: `AUTO` (sigue al GTFS: sólo `wheelchair_boarding = 1` es accesible), `COMPLETA` o `NINGUNA`.
- `salidas`: nombres separados por `;`.
- `accesos`: `salida=ELEVADOR|RAMPA|ESCALERA_FIJA` separados por `;`. Vacío: en estaciones accesibles,
  elevador en la primera salida; en las demás, sólo escaleras.
- `nota`: para qué se usa la estación en los flujos de `docs/arquitectura/06-flujos.md`.
