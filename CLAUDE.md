# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Proyecto: M-IA.** Léelo completo antes de proponer o escribir código.

## Qué es este proyecto

**M-IA** es una PWA de planificación de viajes en transporte público de la CDMX (Metro, Metrobús, Tren Ligero, Tren Suburbano y Tren El Insurgente) para personas con movilidad reducida, especialmente usuarias de silla de ruedas. Optimiza la **probabilidad de completar el viaje sin barreras**; el tiempo es criterio secundario.

Es el proyecto de un **curso de cómputo en la nube** (especialización Data, ML e IA en Google Cloud). Se presentará ante el profesor con **tono académico de nivel maestría**. La carpeta local se llama `mapaUsuarios`; el producto y el repositorio público se llaman **M-IA** (antes RutaAccesible, D-28). Los identificadores técnicos `RA_`, `rutaaccesible`, `ra-db` y `ra.*` se conservan a propósito.

## Estado actual

- **2026-11-24**: Fases 0 a 3 terminadas. PostGIS con el GTFS de la CDMX, inventario DEMO del corredor L2–L3 (D-17, D-19), motor de rutas con `POST /rutas/plan` (D-20) y PWA usable en local (planear, perfil, resultados, detalle, ruta activa sin señal y estaciones).
- **2026-11-25**: Fase 4 terminada (reportes con foto, validación, estimador bayesiano, corroboración y moderación). El plan de la Fase 5 (voz) está aprobado, pero antes va la **Fase 4B**: red completa (D-25) y otras opciones cuando no hay ruta segura (D-26).
- **Fase 4B terminada** (salvo F4B-8, Voronoi, opcional). Siguiente paso: **Fase 5 — Voz** (plan ya aprobado).
- F4B-1 a F4B-3 hechas: inventario DEMO de **toda la red** (Metro, Metrobús, Tren Ligero, Suburbano y El Insurgente; 456 estaciones), ramales del Metrobús y transbordos a pie entre sistemas. Tasqueña → Copilco ya tiene ruta (L2–L12–L3); **Popotla → Zapata** es ahora el caso de "sin ruta segura" (Popotla no tiene elevador según el GTFS). El Insurgente del GTFS 2026-08-28 sólo llega a Santa Fe: no conecta con el resto de la red.
- Formato del entregable final para el profesor: **pendiente** (se decide al terminar; ver `docs/decisiones.md`, P-01).

## Dónde está cada cosa

| Ruta | Contenido |
|---|---|
| `docs/arquitectura/00-indice.md` | Índice de las 14 secciones del enunciado y resumen en una página |
| `docs/arquitectura/01…09-*.md` | Arquitectura completa (diagramas Mermaid incluidos) |
| `docs/decisiones.md` | Decisiones de arquitectura aceptadas y pendientes. **Respétalas**; si algo debe cambiar, propón una nueva decisión y espera aprobación |
| `docs/mvp-backlog.md` | Historias del MVP con criterios de aceptación, por fases |
| `docs/fuentes.md` | Fuentes consultadas |
| `docs/prompt-original.md` | Enunciado original del proyecto |

## Forma de trabajo (obligatoria)

1. **Planear antes de construir.** Al iniciar cada fase del backlog, presenta un plan breve (archivos, pasos, pruebas) y **espera aprobación** antes de escribir código.
2. Avanza **una fase a la vez** y marca en `docs/mvp-backlog.md` lo terminado.
3. Si una decisión de implementación contradice la arquitectura, **actualiza el documento correspondiente** en `docs/` o pregunta; la documentación es parte del entregable.
4. Todo dato inventado (inventario de equipos, historial de fallas) va en carpetas `demo/` o `synthetic/` y se etiqueta como **datos de demostración / sintéticos** en código, UI y dashboard.
5. Explica en los comentarios el *porqué* de las decisiones no obvias (el autor tiene formación en matemáticas aplicadas y presenta el trabajo).

## Entorno de desarrollo

- **Windows**, laptop con **8 GB de RAM**: evita servicios pesados (nada de OpenTripPlanner, Kafka, etc.). Un solo contenedor de PostGIS con límite de memoria.
- Node.js 26 LTS, Docker Desktop (motor WSL 2) y Git instalados. `~/.wslconfig` limita WSL a **2 GB de RAM**; no lo subas sin necesidad.
- Si en una terminal no se reconocen `node` o `docker` (PATH desactualizado tras instalar), agrega `C:\Program Files\nodejs` y `C:\Program Files\Docker\Docker\resources\bin` o abre una terminal nueva.
- **Sin cuenta de Google Cloud** todavía: todo se desarrolla en `RA_MODO=local` con adaptadores simulados; la cuenta de prueba (300 USD / 90 días) se abre en la Fase 6.
- Python 3.12. Usa un entorno virtual en `backend/.venv` (no lo subas a git).

## Stack decidido

- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 + GeoAlchemy2, Alembic, NetworkX, pandas, RapidFuzz, Pillow, imagehash, pytest. Bibliotecas `google-cloud-*` y `google-genai` sólo dentro de los adaptadores GCP.
- **Frontend**: React + TypeScript + Vite, PWA (`vite-plugin-pwa`), React Router, TanStack Query, React Aria + Tailwind, `@vis.gl/react-google-maps` (Leaflet + OSM como respaldo local), Vitest, Playwright, axe-core.
- **Datos/ML**: PostgreSQL + PostGIS; BigQuery + BigQuery ML; Looker Studio.
- **Nube**: Cloud Run, Cloud SQL, Cloud Storage, Pub/Sub, BigQuery, Vertex AI (Gemini Enterprise Agent Platform), Vision API, Speech-to-Text v2 (Chirp 3), Maps Platform, Identity Platform, IAM, Secret Manager, Cloud Logging/Monitoring, Cloud Scheduler.

## Estructura de repositorio propuesta

```
mapaUsuarios/
├── CLAUDE.md
├── README.md
├── docker-compose.yml          # PostGIS (y después backend)
├── .env.example                # variables sin secretos
├── docs/
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py           # RA_MODO=local|gcp
│   │   ├── dominio/            # reglas puras (sin I/O); catalogos.py = estados y tipos válidos
│   │   ├── bd/                 # modelos SQLAlchemy (modelos.py) y sesión
│   │   ├── ingesta/            # GTFS, inventario DEMO, perfiles (puro) + carga.py (escritura)
│   │   ├── modulos/
│   │   │   ├── usuarios/
│   │   │   ├── rutas/          # repositorio (BD→dominio), servicio (caché 60 s), esquemas, endpoints
│   │   │   ├── estado/         # estimador bayesiano
│   │   │   ├── reportes/
│   │   │   └── voz/
│   │   ├── adaptadores/
│   │   │   ├── puertos.py      # interfaces (Protocol)
│   │   │   ├── local/          # simulados
│   │   │   └── gcp/            # reales
│   │   └── workers/            # validación y estado
│   └── tests/
├── frontend/
│   ├── package.json
│   └── src/
├── data/
│   ├── raw/                    # GTFS descargado (no se versiona)
│   ├── demo/                   # inventario de demostración (sí se versiona)
│   ├── synthetic/              # historial sintético
│   └── scripts/
├── ml/
│   └── bigquery/               # SQL de features, modelo y predicción
└── infra/                      # scripts gcloud / despliegue
```

## Modelo del dominio (resumen; el detalle está repartido entre varios documentos)

- **Grafo** (`modulos/rutas`, NetworkX en memoria): nodos = niveles de estación; aristas de viaje, transbordo y **verticales ligadas a equipos** (elevador, rampa, salvaescaleras). Fuente: GTFS de la CDMX + inventario de `data/demo/`.
- **Ruteo en dos pasos** (D-08, `02-arquitectura-general.md` §B): primero se **eliminan** las aristas que violan restricciones duras del perfil; luego 3 alternativas por el **método de penalización** (D-27, sustituye a Yen) con costo aditivo
  $w(e) = \lambda_{\text{perfil}} \sum_{k \in \text{req}(e)} -\ln(1-p_k) + \alpha t_e + \beta\,\text{transbordo}_e + \gamma d^{\text{pie}}_e + \delta u_e$.
  Como $-\ln(1-p)$ es aditivo, minimizar el costo maximiza $P_{\text{éxito}}$; con $\lambda \gg \alpha$ el tiempo sólo desempata.
- **IAR** $= 100 \cdot P_{\text{éxito}}(r)$; categorías alta ≥ 90, media 70–89, baja < 70.
- **Estado de equipos** (`modulos/estado`, `04-data-ml-ia.md` §7.4): Beta($\alpha_k,\beta_k$) con *prior* de la predicción de BigQuery ML, evidencia ponderada por el puntaje de confianza $s$ del reporte, decaimiento temporal (la evidencia de "funciona" se olvida más rápido) y la tabla de **transiciones asimétricas**, que es la especificación de las pruebas de F4-4.
- **Puertos/adaptadores** (D-10, `08-mvp-y-tecnologias.md` §11.5): `AlmacenEvidencias`, `BusEventos`, `AnalizadorImagen`, `TranscriptorVoz`, `InterpreteLenguaje`, `Geocodificador`, `CaminataProveedor`, `ProveedorIdentidad`. `RA_MODO` elige la implementación `local` (simulada y determinista) o `gcp`. El código de dominio y de módulos depende sólo de los puertos.
- **ML fuera del camino caliente** (D-06): predicciones por lotes copiadas a Cloud SQL; ningún endpoint espera a un modelo.

## Motor de rutas: dónde está cada pieza

- `app/dominio/`: `red.py` (tipos y `Perfil`, cuyo `repr` oculta los datos), `restricciones.py` (restricciones duras físicas y de estado, D-20), `costo.py` (w(e) y sus pesos), `grafo.py` (topología + grafo por petición), `planificador.py` (alternativas por penalización D-27, firma de alternativas, IAR, plan B, descartadas, sin ruta segura). Todo puro; se prueba con `tests/red_motor_juguete.py`.
- Transbordos por la calle entre estaciones (D-25): conexiones `PASILLO` entre salidas de estaciones distintas (`entre_estaciones` en la arista); cuentan como caminata del perfil. `grafo_para` poda los que el origen o el destino ya alcanzan caminando directo: sin la poda, las búsquedas se gastan en variantes de banqueta.
- El grafo de diagnóstico con restricciones **relajadas** (`Relajacion`) sólo sirve para explicar descartadas y obstáculos: nunca alimenta las alternativas devueltas (regla 3; lo vigila la prueba de propiedad en `tests/test_motor.py`).
- Los textos para la persona (pasos, planes B, explicaciones) se generan en `planificador.py`; usa `con_articulo()` para la concordancia de género.
- Sin ruta segura (D-26), `planear` arma `otras_opciones` aparte de `alternativas`: `_opcion_estacion_cercana` (grafo seguro), `_opcion_si_se_repara` (estados relajados) y `_opcion_con_asistencia` (físicas relajadas; siempre la última, con `Paso.asistencia`). `ServicioRutas.planear` repite con caminatas de hasta 2 km si no salió ninguna opción.

## Reportes y estado: dónde está cada pieza

- Sólo el **estimador** (`app/dominio/estimador.py`) decide el estado de un equipo (D-21): reproduce en orden avisos, reportes validados y votos. Nunca escribas `estado_equipo` desde otro lugar; crea evidencia (un `aviso`, un reporte) y deja que `workers/estado.py` recalcule.
- Flujo de eventos en `app/workers/registro.py`: reporte-creado → `workers/validacion.py` (puntaje s de `dominio/validacion.py`) → reporte-validado → `workers/estado.py` → estado-cambiado → invalida la caché de rutas. En local el bus es una cola en proceso; en pruebas, síncrono.
- Las pruebas de integración sustituyen `obtener_contexto` (sesiones ligadas a la transacción de prueba, bus síncrono, almacén en `tmp_path`): ver `tests/test_bd_reportes.py`.
- Los códigos de equipo llevan `/`: en rutas de FastAPI usa `{codigo:path}`.
- `POST /operacion/recalcular-estados` (rol moderador) recalcula todo con el estimador **a través del bus**, así invalida la caché de rutas; úsalo tras escribir en la base desde un script (las pruebas e2e lo hacen al reiniciar la demo). En la nube lo llamará Cloud Scheduler.
- Requiere `RA_JWT_SECRETO` (≥ 32 caracteres) en `.env`. Las fotos subidas en local quedan en `backend/almacen_local/` (ignorado por git).

## Voz: dónde está cada pieza (Fase 5, D-24)

- `app/dominio/voz.py` (puro): `Intencion`, `Parcial` (lo resuelto en la conversación), `resolver()` y las reglas de aclaración (homónimos a > 600 m, lugar no encontrado, falta origen o destino; "la del Metrobús" responde con la pista de sistema y `pendiente`).
- `adaptadores/local/interprete.py` (reglas) y `adaptadores/local/transcriptor.py` (audios sintéticos por sha256 en `data/demo/audios/transcripciones.json`; si no, `RA_VOZ_FRASE_DEMO`, marcada como simulada). En la nube: Gemini y Speech-to-Text v2.
- `modulos/voz/`: `POST /voz/consulta` sólo interpreta; **no recibe el perfil ni calcula la ruta**. No registres ni guardes el audio ni la transcripción.

## PWA: dónde está cada pieza

- `src/api/cliente.ts`: única puerta a la API (`/api/*`, que el proxy de Vite reenvía a FastAPI). Los tipos vienen de `esquema.d.ts` (generado); no los escribas a mano.
- `src/estado/almacen.ts`: perfil y ruta activa en `localStorage` (sólo en el dispositivo; el perfil sale únicamente dentro de `POST /rutas/plan`). `estado/plan.ts` + `ProveedorPlan.tsx`: búsqueda en curso en `sessionStorage`.
- `src/componentes/simbologia.ts`: color + forma + texto de cada estado; la usan listas y mapas para que siempre coincidan. `SIMBOLO_ASISTENCIA` marca en rojo los puntos de la ruta con asistencia.
- Sin ruta segura (D-26): `componentes/OtraOpcion.tsx` pinta cada opción de `otras_opciones` en la sección "Otras opciones" de Resultados; `ListaPasos` (en `Alternativa.tsx`) marca los pasos con `asistencia`. `MapaDesplegable` es el botón "Ver mapa" de cada tarjeta; `MapaRuta` recibe `asistencia` para los marcadores rojos.
- Para nombres accesibles de botones y enlaces usa `aria-label` o deja el espacio **fuera** de un `span.sr-only`: el espacio inicial dentro del span se pierde ("plan Bde la opción 1").
- Los mapas (`componentes/Mapas.tsx`, Leaflet + OSM) se cargan con `React.lazy` y en Vitest se sustituyen por un doble; se prueban en Playwright. La vista de lista es siempre equivalente.
- Identidad (D-23): `api/cliente.ts` crea el usuario anónimo la primera vez (`ra.token` en localStorage) y lo renueva ante un 401. La moderación usa otro token (`ra.token-moderacion`).
- `BuscadorLugar`: `allowsCustomValue` e ignorar `onSelectionChange(null)` evitan que una respuesta tardía del autocompletado borre lo elegido; no los quites.
- Las pruebas e2e de reportes modifican la base: corren sólo en el proyecto "escritorio" y reinician la demo antes y después (`e2e/preparacion.ts`).
- Pruebas: `src/pruebas/api-simulada.ts` (MSW) responde con salidas reales del backend guardadas en `src/pruebas/datos/`; si cambia el contrato, vuelve a capturarlas (tras `aplicar_escenario_demo.py flujo1 --reiniciar` y 60 s, que es la caché de estados). `plan-sin-ruta.json` es Terminal Aérea → Lechería (trae los tres tipos de otra opción); `estaciones.json` es una muestra de los cinco sistemas.

## Convenciones

- **Idioma**: nombres del dominio en español sin acentos (`estacion`, `reporte`, `estado_equipo`, `prob_operativo`), igual que en `docs/arquitectura/03-datos.md`. Comentarios y mensajes de UI en español de México.
- Endpoints REST en español: `/rutas/plan`, `/estaciones/{id}/estado`, `/reportes`, `/voz/consulta`.
- Estados de equipo: `OPERATIVO`, `FALLA_PROBABLE`, `FALLA_CONFIRMADA`, `DESCONOCIDO`, `MANTENIMIENTO`.
- La lógica de dominio (grafo, costo, estimador) va en funciones puras con pruebas unitarias; el I/O vive en adaptadores.
- Secretos sólo en `.env` local (ignorado) o Secret Manager; nunca en el repositorio.
- Commits pequeños y descriptivos en español.

## Reglas de seguridad del dominio (no negociables)

Estas reglas vienen de `docs/arquitectura/07-seguridad-escalabilidad.md` §10.5 y deben tener pruebas:

1. `DESCONOCIDO` **nunca** se trata como accesible.
2. Umbrales **asimétricos**: volver a `OPERATIVO` exige más evidencia que pasar a falla.
3. Ningún modelo ni ranking puede devolver como **alternativa** una ruta que viole una restricción dura del perfil. La única excepción es la **ruta con asistencia** (D-26): va separada, siempre al final de las "otras opciones", sólo cuando no hay ruta segura y marcando en rojo dónde pedir ayuda y por qué.
4. Toda ruta muestra IAR, equipos críticos, última verificación y plan B.
5. Si no hay ruta segura, se dice explícitamente; no se muestra una ruta riesgosa como si fuera buena.
6. El perfil de accesibilidad es dato sensible: no se envía a APIs de IA ni aparece en logs.

## Comandos

Mantén esta sección al día cada vez que se agregue un comando. Desde la raíz, salvo que se indique otra carpeta.

**Base de datos** (requiere `.env`, copiado de `.env.example`):
```bash
docker compose up -d                     # PostGIS en 127.0.0.1:5432 (contenedor ra-db, 512 MB)
docker compose exec db psql -U ra -d rutaaccesible -c "SELECT PostGIS_Version();"
docker compose down                      # detiene; los datos persisten en el volumen ra-db-datos
```

**Backend** (`backend/`, venv en `backend/.venv`):
```bash
py -3.12 -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/uvicorn app.main:app --reload            # http://localhost:8000/salud · /docs
.venv/Scripts/python -m pytest                         # todas las pruebas
.venv/Scripts/python -m pytest tests/test_config.py::test_modo_invalido_detiene_el_arranque   # una sola
.venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .
```
En PowerShell usa `.venv\Scripts\...` o activa con `.venv\Scripts\Activate.ps1`.

Las pruebas marcadas `@pytest.mark.bd` usan la base `rutaaccesible_pruebas` (se crea y migra sola) y **se omiten** si PostGIS no está arriba. Sólo pruebas puras: `pytest -m "not bd"`.

**Migraciones** (`backend/`): `alembic upgrade head` · nueva: `alembic revision --autogenerate -m "..."` (revisa el archivo generado) · `alembic check` confirma que modelos y base coinciden. No edites migraciones ya versionadas; crea una nueva.

**Datos** (desde la raíz, en este orden; todos son idempotentes):
```bash
backend/.venv/Scripts/python data/scripts/descargar_gtfs.py            # GTFS -> data/raw/gtfs/<fecha>/ (+ sha256)
backend/.venv/Scripts/python data/scripts/cargar_gtfs.py               # estaciones/rutas -> PostGIS + data/reportes/gtfs-<fecha>.md
backend/.venv/Scripts/python data/scripts/generar_inventario_demo.py   # GTFS + ajustes_red.csv -> data/demo/{estaciones_red,niveles,equipos,conexiones}.csv
backend/.venv/Scripts/python data/scripts/cargar_inventario_demo.py    # inventario DEMO + perfiles semilla -> PostGIS
backend/.venv/Scripts/python data/scripts/generar_escenario_sintetico.py  # estados SINTÉTICOS de toda la red -> data/synthetic/escenario_red.csv (tras cambiar el inventario)
backend/.venv/Scripts/python data/scripts/aplicar_escenario_demo.py    # red SINTÉTICA + avisos DEMO (flujo1) + estimador; sin esto todo es DESCONOCIDO. --reiniciar borra reportes y votos
backend/.venv/Scripts/python data/scripts/generar_fotos_demo.py        # fotos SINTÉTICAS + analisis.json del analizador simulado
backend/.venv/Scripts/python data/scripts/crear_moderador_dev.py       # imprime el token del moderador de desarrollo (D-23)
backend/.venv/Scripts/python data/scripts/medir_rendimiento.py 100     # p95 de /rutas/plan -> data/reportes/rendimiento-rutas.md
```
Con el backend arriba, prueba `POST /rutas/plan` en http://localhost:8000/docs (trae un ejemplo del flujo 1).
Para cambiar el inventario edita **sólo** `data/demo/ajustes_red.csv` (salidas y accesos de las estaciones que no siguen la plantilla de su sistema) y regenera; los otros CSV son generados (ver `data/demo/README.md`). Los scripts de `data/scripts/` son delgados: la lógica vive en `backend/app/ingesta/` (pura, probada) y `app/ingesta/carga.py` (escritura). Lint de los scripts: `ruff check ../data/scripts --config pyproject.toml` desde `backend/`.

**Frontend** (`frontend/`):
```bash
npm install
npm run dev                  # http://localhost:5173
npm test                     # Vitest una vez (npm run test:watch para modo observador)
npx vitest run src/App.test.tsx -t "Saltar al contenido"   # una sola prueba
npm run lint                 # oxlint
npm run build                # tsc -b + build de producción con service worker (dist/)
npm run api:tipos            # regenera src/api/esquema.d.ts desde el OpenAPI de FastAPI (tras cambiar un contrato)
npm run build && npx vite preview --host 127.0.0.1 --port 4173   # versión de producción (con /api hacia FastAPI)
ngrok http 4173              # túnel público para compartir la demo; la URL sale en http://127.0.0.1:4040 (requiere backend y preview arriba)
npm run e2e                  # Playwright: levanta backend + `vite preview`; requiere PostGIS con datos (reaplica el escenario flujo1)
npx playwright test e2e/teclado.spec.ts --project=escritorio   # una sola prueba en navegador
```

Notas: en `RA_BD_URL` usa `127.0.0.1`, no `localhost` (en Windows cada conexión tarda ~5 s por IPv6). El linter del frontend es **oxlint** (viene con la plantilla de Vite), no ESLint. Las pruebas de accesibilidad usan `axe-core` directamente (`src/pruebas/accesibilidad.ts`); la regla de contraste se apaga en jsdom y se verificará con Playwright en F3-5. El paquete de ruteo es `react-router` (desde la v7 sustituye a `react-router-dom`).
