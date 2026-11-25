# Backlog del MVP — RutaAccesible

Orden de construcción recomendado. Cada historia tiene criterios de aceptación verificables. Antes de iniciar cada fase, Claude Code presenta el plan de la fase y espera aprobación.

Convención de estado: `[ ]` pendiente · `[~]` en curso · `[x]` terminada.

---

## Fase 0 — Entorno y esqueleto

- [x] **F0-1 Verificar herramientas locales.** Node.js LTS, Python 3.12, Docker Desktop y Git instalados y en el PATH.
  *Aceptación*: `node -v`, `python --version`, `docker --version`, `git --version` responden.
- [x] **F0-2 Inicializar repositorio** con la estructura de `CLAUDE.md`, `.gitignore` (incluye `.env`, credenciales, `data/raw/`), `README.md`.
- [x] **F0-3 docker compose con PostGIS.** Un servicio `db` (imagen PostGIS) con volumen persistente y límite de memoria modesto.
  *Aceptación*: `SELECT PostGIS_Version();` responde.
- [x] **F0-4 Esqueleto de backend** FastAPI con `/salud`, configuración por variables de entorno (`RA_MODO=local|gcp`) y pytest funcionando.
- [x] **F0-5 Esqueleto de frontend** React + TypeScript + Vite con PWA, React Router y una pantalla de inicio accesible.

## Fase 1 — Datos base

- [x] **F1-1 Descargar y validar el GTFS de la CDMX** (script en `data/scripts/`), filtrando Metro, Metrobús y Tren Ligero.
  *Aceptación*: reporte con número de estaciones, rutas y paradas con `wheelchair_boarding` informado.
- [x] **F1-2 Migraciones** (Alembic) con las tablas del modelo de datos (`docs/arquitectura/03-datos.md`).
- [x] **F1-3 Cargar estaciones, rutas y estación-ruta** a PostGIS.
  *Aceptación*: consulta "estaciones a menos de 600 m de un punto" devuelve resultados correctos para 3 puntos de prueba.
- [x] **F1-4 Inventario de demostración** del corredor piloto (CSV en `data/demo/`), marcado como datos de demostración, con equipos y niveles que conectan.
  *Hecho*: generado por plantillas desde `data/demo/estaciones_corredor.csv` (D-18, D-19); 44 estaciones, 224 niveles, 61 equipos, 248 conexiones.
- [x] **F1-5 Perfiles de movilidad** predefinidos (silla manual, silla eléctrica, andadera, adulto mayor, carriola) como datos semilla.

## Fase 2 — Motor de rutas

- [x] **F2-1 Construir el grafo** (estación → niveles; aristas de viaje, transbordo y verticales ligadas a equipos).
  *Aceptación*: prueba unitaria con una red pequeña de juguete.
- [x] **F2-2 Restricciones duras por perfil.**
  *Aceptación*: con un elevador en `FALLA_CONFIRMADA`, ninguna ruta para silla de ruedas usa esa arista.
- [x] **F2-3 Costo $w(e)$ y alternativas con Yen (k = 3).** *Sustituido por el método de penalización en la Fase 4B (D-27).*
  *Aceptación*: con $p_k$ alto en un equipo, la ruta recomendada cambia aunque sea más lenta; con $p_k$ bajo, gana la más rápida.
- [x] **F2-4 IAR, equipos críticos, plan B y explicación** en lenguaje claro.
- [x] **F2-5 Endpoint `POST /rutas/plan`** con tramos a pie mediante el adaptador `CaminataProveedor`.
  *Aceptación*: p95 local < 1 s en el corredor piloto.
- [x] **F2-6 Caso "sin ruta segura"**: respuesta explícita con riesgos y sugerencias.

*Hecho (F2)*: p95 de 105 ms en 100 pares (`data/reportes/rendimiento-rutas.md`). Hallazgo: con el inventario que respeta el GTFS, sólo el 5 % de pares aleatorios del corredor tiene ruta segura en silla manual (55 % en silla eléctrica, 100 % adulto mayor), por las 27 estaciones no accesibles y la falta de transbordo accesible L2↔L3 (D-19).

## Fase 3 — PWA

- [x] **F3-1 Búsqueda de origen y destino** (catálogo de estaciones + adaptador de geocodificación) y "mi ubicación".
- [x] **F3-2 Selección de perfil** guardado localmente (uso anónimo).
- [x] **F3-3 Mapa** con estaciones por estado (color + forma + texto) y trazo de la ruta; respaldo Leaflet sin llave de Maps.
- [x] **F3-4 Resultados**: tarjetas de alternativas con IAR, tiempo, transbordos, equipos críticos con última verificación; **vista en lista** equivalente al mapa.
- [x] **F3-5 Accesibilidad**: navegación por teclado, etiquetas ARIA, contraste; prueba automática con axe-core sin violaciones graves.
- [x] **F3-6 Caché de la ruta activa** para consulta sin señal.

*Hecho (F3)*: PWA con 6 pantallas; 27 pruebas Vitest (MSW con respuestas reales del backend) y 24 de Playwright en escritorio y celular: flujo 1 sólo con teclado, axe-core WCAG 2.1 AA sin violaciones graves (incluido contraste y mapas) y ruta activa sin red con el service worker.

## Fase 4 — Reportes y estado

- [x] **F4-1 Flujo de reporte** en la PWA: elegir equipo de la estación cercana, tomar foto, enviar.
- [x] **F4-2 Subida de evidencia** por el adaptador `AlmacenEvidencias` (carpeta local / URL firmada).
- [x] **F4-3 Trabajador de validación** con el adaptador `AnalizadorImagen` (simulado / Vision + Gemini), geocerca, hash y puntaje $s$.
- [x] **F4-4 Estimador bayesiano** con decaimiento y umbrales asimétricos.
  *Aceptación*: pruebas para cada transición de la tabla de la sección 7.4.
- [x] **F4-5 Saneamiento de imagen**: reescritura, borrado de EXIF, difuminado de rostros (cuando el adaptador real los detecte).
- [x] **F4-6 Consola de moderación** mínima (lista de reportes en zona gris, confirmar/rechazar).
- [x] **F4-7 Pregunta de corroboración** a quien consulta una ruta que pasa por un equipo en `FALLA_PROBABLE`.

*Bloque 1 (backend) hecho*: estimador (D-21, D-22), puntaje s, trabajadores de validación y estado en un bus local, almacén con URL de subida firmada, saneamiento de fotos, identidad local (D-23) y endpoints de reportes, corroboración y moderación; 233 pruebas. *Bloque 2 (PWA) hecho*: pantallas Reportar, seguimiento y Mis reportes, consola de Moderación y pregunta de corroboración en el detalle de la ruta; 40 pruebas Vitest y 28 Playwright, incluido el flujo 2 de punta a punta (reporte con foto → corroboración de otra persona → falla confirmada) y la moderación.

## Fase 4B — Red completa y opciones sin ruta segura (D-25, D-26)

Adelanta la Fase 9 y la extiende a otros sistemas: sin transbordos accesibles entre sistemas no se pueden simular viajes reales.

- [x] **F4B-1 Sistemas en la ingesta**: Tren Suburbano y Tren El Insurgente se suman a Metro, Metrobús y Tren Ligero.
- [x] **F4B-2 Catálogo de toda la red generado desde el GTFS** con plantillas por sistema y un archivo pequeño de ajustes manuales; todo con `fuente = DEMO`. Respeta D-19.
  *Aceptación*: todas las estaciones de los cinco sistemas tienen niveles y equipos; ninguna queda sin conexión entre andén y salida.
- [x] **F4B-3 Transbordos entre sistemas** (conexiones a pie entre salidas cercanas, p. ej. Buenavista: Suburbano ↔ Metro B ↔ Metrobús).
  *Hecho (commit 1)*: 456 estaciones (163 Metro, 263 Metrobús, 18 Tren Ligero, 7 Suburbano, 5 El Insurgente); los ramales del Metrobús entran como direcciones propias (sin ellos faltaban 28 estaciones); transbordos a pie a menos de 450 m. El Insurgente del GTFS 2026-08-28 termina en Santa Fe y no conecta con la red.
- [x] **F4B-4 Escenario sintético de estados** para toda la red, determinista, en `data/synthetic/`, aplicado como avisos DEMO a través del estimador.
  *Hecho (commit 2)*: `data/synthetic/escenario_red.csv` (semilla fija): 86 % operativo, 7 % falla probable (reporte SINTÉTICO sin foto), 3 % falla confirmada, 2 % desconocido, 1 % mantenimiento; las líneas 2 y 3 las fija `flujo1`.
- [ ] **F4B-5 Otras opciones sin ruta segura** (D-26): sistemas alternos, estación accesible más cercana al destino, ruta si se repara un equipo y, al final, ruta con asistencia marcada en rojo.
  *Aceptación*: toda búsqueda con origen y destino válidos devuelve al menos una opción; la ruta con asistencia nunca aparece en `alternativas` (prueba de propiedad).
  *Motor y API hechos (commit 3)*: `otras_opciones` en `POST /rutas/plan` con `estacion_cercana`, `si_se_repara` y `con_asistencia` (siempre al final); los pasos que necesitan ayuda llevan `asistencia` con el motivo. "Sistemas alternos" no es una opción aparte: con la red completa ya son alternativas normales. Si no hay ninguna estación al alcance a pie, se repite con caminatas de hasta 2 km, que aparecen como punto de asistencia ("caminata de 927 m"). Sólo queda sin opciones un punto a más de 2 km de toda estación. Falta la PWA (F4B-7).
- [x] **F4B-6 Rendimiento con la red completa.** *Aceptación*: `POST /rutas/plan` mantiene p95 local < 1 s.
  *Hecho (commit 2)*: p95 450–510 ms (p50 ≈ 340 ms) en tres corridas de 100 pares; antes, p95 ≈ 4 s. Yen sustituido por el método de penalización (D-27), plan B sin reconstruir el grafo y caché de la parte del grafo que sólo depende del perfil.
- [ ] **F4B-7 PWA, pruebas y documentación**: capa de accesibilidad de toda la red, nuevo caso de demostración de "sin ruta segura", capturas del MSW, escenarios E1–E7 en `06-flujos.md` y alcance en `08` y `09`.
- [ ] **F4B-8 (opcional) Capa de Voronoi** de estaciones accesibles (`ST_VoronoiPolygons`), recalculada al cambiar un estado.

## Fase 5 — Voz

- [ ] **F5-1 Captura de audio** en la PWA con botón accesible.
- [ ] **F5-2 Endpoint `POST /voz/consulta`** con adaptadores `TranscriptorVoz` e `InterpreteLenguaje`.
- [ ] **F5-3 Diálogo de aclaración** cuando falta origen/destino o hay ambigüedad.
- [ ] **F5-4 Respuesta hablada** con la síntesis de voz del navegador.

## Fase 6 — Google Cloud

- [ ] **F6-1 Abrir la prueba gratuita**, crear proyecto, presupuesto y alertas; habilitar APIs.
- [ ] **F6-2 Secretos** en Secret Manager; cuentas de servicio por componente.
- [ ] **F6-3 Adaptadores reales**: Cloud Storage, Vision API, Gemini, Speech-to-Text v2, Places/Routes, Pub/Sub.
- [ ] **F6-4 Cloud SQL** con PostGIS y migraciones aplicadas.
- [ ] **F6-5 Despliegue** de `api-core` y `worker-validacion` en Cloud Run; PWA publicada.
  *Aceptación*: los cuatro flujos funcionan en la URL pública.
- [ ] **F6-6 Logging y Monitoring**: logs estructurados, panel básico y una alerta de latencia.

## Fase 7 — Datos y ML

- [ ] **F7-1 Generador de historial sintético** (claramente identificado) de fallas por equipo, día y franja con patrones plausibles (afluencia, lluvias, recurrencia).
- [ ] **F7-2 Datasets de BigQuery** `ra_bronze`, `ra_silver`, `ra_gold`, `ra_ml`; suscripción de Pub/Sub a BigQuery.
- [ ] **F7-3 Modelo BigQuery ML** (regresión logística base + boosted trees), división temporal, PR-AUC, Brier y calibración.
- [ ] **F7-4 Predicción por lotes** y copia a Cloud SQL; el motor la usa como *prior*.
- [ ] **F7-5 Dashboard en Looker Studio**: fallas por estación, mapa de zonas críticas, disponibilidad por franja, ranking de riesgo.
- [ ] **F7-6 (Podría)** Registro del modelo en Vertex AI Model Registry.

## Fase 8 — Cierre

- [ ] **F8-1 Guion de demostración** de 5–7 minutos que recorre los cuatro flujos.
- [ ] **F8-2 Capturas y video corto** de respaldo por si falla la red.
- [ ] **F8-3 Actualizar la documentación** con lo que cambió durante la construcción.
- [ ] **F8-4 Entregable final** para el profesor (formato por decidir: P-01).

## Fase 9 — Ampliación a toda la red del Metro (post-MVP, D-17)

> **Absorbida por la Fase 4B (D-25)**, salvo F9-3, que se hará en la Fase 7 con los equipos de toda la red.

Primera ampliación una vez terminado el MVP. No requiere cambios de código ni de esquema; es trabajo de datos y de verificación.

- [ ] **F9-1 Inventario de demostración de las 10 líneas restantes** (1, 4, 5, 6, 7, 8, 9, A, B y 12), marcado como datos de demostración.
  *Aceptación*: todas las estaciones del Metro tienen niveles y equipos; ninguna queda sin conexión entre andén y salida en el grafo.
- [ ] **F9-2 Revisar las estaciones de transbordo** (p. ej. Hidalgo, Pino Suárez, Balderas, Pantitlán). El generador ya agrega solo los andenes y pasillos de las líneas nuevas; falta ajustar a mano salidas y accesos en el catálogo.
- [ ] **F9-3 Regenerar el historial sintético y reentrenar** el modelo de BigQuery ML con los equipos nuevos.
- [ ] **F9-4 Rendimiento con la red completa.**
  *Aceptación*: `POST /rutas/plan` mantiene p95 local < 1 s.
- [ ] **F9-5 Actualizar documentación**: alcance en `08-mvp-y-tecnologias.md` y limitaciones en `09-riesgos-y-evolucion.md`.
