# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Proyecto: RutaAccesible.** Léelo completo antes de proponer o escribir código.

## Qué es este proyecto

**RutaAccesible** es una PWA de planificación de viajes en transporte público de la CDMX (Metro, Metrobús, Tren Ligero) para personas con movilidad reducida, especialmente usuarias de silla de ruedas. Optimiza la **probabilidad de completar el viaje sin barreras**; el tiempo es criterio secundario.

Es el proyecto de un **curso de cómputo en la nube** (especialización Data, ML e IA en Google Cloud). Se presentará ante el profesor con **tono académico de nivel maestría**. La carpeta del repositorio se llama `mapaUsuarios`; el producto se llama RutaAccesible.

## Estado actual

- **2026-11-24**: arquitectura definida y documentada en `docs/`. **Aún no hay código.**
- Siguiente paso: **MVP funcional** en menos de dos semanas, siguiendo `docs/mvp-backlog.md` (Fase 0 en adelante).
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
- **Node.js no está instalado** actualmente: hay que instalar la versión LTS antes de la Fase 0.
- **Docker**: verificar si está instalado (F0-1).
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
│   │   ├── dominio/            # modelos y reglas puras (sin I/O)
│   │   ├── modulos/
│   │   │   ├── usuarios/
│   │   │   ├── rutas/          # grafo, costo, IAR, endpoints
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
- **Ruteo en dos pasos** (D-08, `02-arquitectura-general.md` §B): primero se **eliminan** las aristas que violan restricciones duras del perfil; luego Yen (k = 3) con costo aditivo
  $w(e) = \lambda_{\text{perfil}} \sum_{k \in \text{req}(e)} -\ln(1-p_k) + \alpha t_e + \beta\,\text{transbordo}_e + \gamma d^{\text{pie}}_e + \delta u_e$.
  Como $-\ln(1-p)$ es aditivo, minimizar el costo maximiza $P_{\text{éxito}}$; con $\lambda \gg \alpha$ el tiempo sólo desempata.
- **IAR** $= 100 \cdot P_{\text{éxito}}(r)$; categorías alta ≥ 90, media 70–89, baja < 70.
- **Estado de equipos** (`modulos/estado`, `04-data-ml-ia.md` §7.4): Beta($\alpha_k,\beta_k$) con *prior* de la predicción de BigQuery ML, evidencia ponderada por el puntaje de confianza $s$ del reporte, decaimiento temporal (la evidencia de "funciona" se olvida más rápido) y la tabla de **transiciones asimétricas**, que es la especificación de las pruebas de F4-4.
- **Puertos/adaptadores** (D-10, `08-mvp-y-tecnologias.md` §11.5): `AlmacenEvidencias`, `BusEventos`, `AnalizadorImagen`, `TranscriptorVoz`, `InterpreteLenguaje`, `Geocodificador`, `CaminataProveedor`, `ProveedorIdentidad`. `RA_MODO` elige la implementación `local` (simulada y determinista) o `gcp`. El código de dominio y de módulos depende sólo de los puertos.
- **ML fuera del camino caliente** (D-06): predicciones por lotes copiadas a Cloud SQL; ningún endpoint espera a un modelo.

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
3. Ningún modelo ni ranking puede devolver una ruta que viole una restricción dura del perfil.
4. Toda ruta muestra IAR, equipos críticos, última verificación y plan B.
5. Si no hay ruta segura, se dice explícitamente; no se muestra una ruta riesgosa como si fuera buena.
6. El perfil de accesibilidad es dato sensible: no se envía a APIs de IA ni aparece en logs.

## Comandos

(Se completarán en la Fase 0: levantar PostGIS, crear el venv, correr el backend, pytest completo y **una sola prueba** (`pytest ruta::nombre`), migraciones Alembic, `npm run dev`/test/lint del frontend y Playwright. Mantén esta sección al día cada vez que se agregue un comando.)
