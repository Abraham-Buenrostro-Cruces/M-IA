# ⚠️ Datos de demostración — no son el inventario real del Metro

Esta carpeta contiene el **inventario de demostración** de toda la red que cubre M-IA
(Metro, Metrobús, Tren Ligero, Tren Suburbano y Tren El Insurgente, decisión D-25). No existe un
inventario público de elevadores, rampas y escaleras de estos sistemas, así que estos datos se
**generan con plantillas** para que el sistema pueda funcionar y demostrarse. Toda fila lleva
`fuente = DEMO`.

Lo que **sí** es real:
- Las estaciones, líneas, direcciones, coordenadas de andén y tiempos entre estaciones (GTFS de la CDMX).
- Qué estaciones tienen accesibilidad: se respeta el `wheelchair_boarding` del GTFS (D-19).

Lo que es **supuesto de demostración**:
- Los nombres de salidas, la cantidad y ubicación de elevadores, rampas y escaleras eléctricas,
  los escalones, longitudes y tiempos dentro de cada estación.
- La forma de cada estación según su sistema: Metro, Suburbano y El Insurgente con elevador en
  una salida y escaleras; Metrobús y Tren Ligero con andén a nivel y rampas (o un puente con
  escalones si el GTFS dice que no es accesible).
- Los transbordos a pie entre estaciones de sistemas distintos a menos de 450 m.

## Archivos

| Archivo | Edición | Contenido |
|---|---|---|
| `ajustes_red.csv` | **A mano** | Sólo las estaciones que no siguen la plantilla de su sistema: salidas con nombre y tipo de acceso de cada salida (flujos de `06-flujos.md`). |
| `estaciones_red.csv` | Generado | Catálogo resuelto de toda la red, para revisarlo: sistema, líneas, accesibilidad del GTFS y si queda sin escalones. |
| `niveles.csv` | Generado | Nodos del grafo: salidas, vestíbulos y andenes por línea y dirección (tabla `nivel`). |
| `equipos.csv` | Generado | Elevadores, rampas y escaleras eléctricas (tabla `infraestructura_accesible`). |
| `conexiones.csv` | Generado | Aristas internas de cada estación, incluidas las escaleras fijas, y los transbordos a pie entre estaciones (tabla `conexion`). |

No edites los archivos generados: cambia el catálogo y vuelve a ejecutar
`data/scripts/generar_inventario_demo.py`.

## Columnas de `ajustes_red.csv`

- `plantilla`: `AUTO` (terminal → andén central; de paso → andenes laterales), `LATERAL` o `CENTRAL`.
- `accesibilidad`: `AUTO` (sigue al GTFS: sólo `wheelchair_boarding = 1` es accesible), `COMPLETA` o `NINGUNA`.
- `salidas`: nombres separados por `;`.
- `accesos`: `salida=ELEVADOR|RAMPA|ESCALERA_FIJA` separados por `;`. Vacío: lo decide la plantilla del sistema
  (Metro y trenes: elevador en la primera salida; Metrobús y Tren Ligero: rampa en todas; sin accesibilidad: escaleras).
- `nota`: para qué se usa la estación en los flujos de `docs/arquitectura/06-flujos.md`.
