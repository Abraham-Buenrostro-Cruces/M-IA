# Registro de decisiones de arquitectura (ADR resumido)

Cada decisión indica el contexto, la elección y la alternativa descartada. Si una decisión cambia, se marca como **Reemplazada** y se agrega una nueva; no se borra.

| ID | Fecha | Decisión | Contexto | Alternativa descartada | Estado |
|---|---|---|---|---|---|
| D-01 | 2026-11-24 | **Motor de rutas propio** sobre el GTFS de la CDMX con NetworkX | La Routes API no ofrece opción de silla de ruedas para transporte público ni permite usar el estado dinámico de los equipos | Delegar el ruteo en Google Routes API; OpenTripPlanner (requiere más memoria de la disponible en el equipo de desarrollo) | Aceptada |
| D-02 | 2026-11-24 | **Monolito modular** (`api-core`) + trabajadores por eventos en Cloud Run | Una persona desarrolladora, plazo < 2 semanas | Microservicios desde el inicio; App Engine | Aceptada |
| D-03 | 2026-11-24 | **Cloud SQL PostgreSQL + PostGIS** como fuente de verdad operativa | Modelo relacional con consultas espaciales | Firestore | Aceptada |
| D-04 | 2026-11-24 | **Gemini en Vertex AI** para NLP (intención, clasificación de reportes) y como segunda opinión visual | Español coloquial, una sola integración, salidas estructuradas | Cloud Natural Language API | Aceptada |
| D-05 | 2026-11-24 | **BigQuery ML** para el modelo de fallas, registrado en **Vertex AI Model Registry** | SQL conocido, datos ya en BigQuery | Entrenamiento custom en Vertex desde el inicio | Aceptada |
| D-06 | 2026-11-24 | **Predicciones por lotes** copiadas a Cloud SQL; sin endpoint en línea | El camino caliente no debe esperar a un modelo; costo | Endpoint de predicción en línea | Aceptada |
| D-07 | 2026-11-24 | **Estimador bayesiano Beta** con decaimiento y **umbrales asimétricos** para el estado de cada equipo | Un falso "funciona" es mucho más grave que un falso "falla" | Último reporte gana; votación simple | Aceptada |
| D-08 | 2026-11-24 | **Restricciones duras + costo aditivo** $-\ln(1-p_k)$; el ML sólo ajusta costos entre rutas factibles | Seguridad e interpretabilidad | Modelo de caja negra que elige la ruta | Aceptada |
| D-09 | 2026-11-24 | **Identity Platform** para personas; **IAM** para servicios | Separar identidad de clientes y de cargas de trabajo | Autenticación propia | Aceptada |
| D-10 | 2026-11-24 | **Patrón de adaptadores** con modo `local` simulado y modo `gcp` real (`RA_MODO`) | Sin cuenta de GCP al inicio; pruebas reproducibles | Desarrollar directamente contra la nube | Aceptada |
| D-11 | 2026-11-24 | **Pub/Sub con suscripción directa a BigQuery** para eventos | Sin transformaciones en streaming | Dataflow | Aceptada |
| D-12 | 2026-11-24 | **Backend Python + FastAPI**; **frontend PWA en React + TypeScript** | Ecosistema de datos/ML; una sola base de código web y móvil | Java/Spring Boot; Flutter; React Native | Aceptada |
| D-13 | 2026-11-24 | Región **`northamerica-south1` (Querétaro)** para datos; APIs de IA en la región donde estén disponibles | Latencia y residencia de datos en México | `us-central1` para todo (se mantiene como respaldo) | Aceptada, sujeta a verificar disponibilidad por servicio |
| D-14 | 2026-11-24 | **API Gateway** en la arquitectura objetivo, **no** en el MVP | Valor real en cuotas y anti-abuso; costo de configuración para el plazo | Cloud Load Balancing + Cloud Armor | Aceptada |
| D-15 | 2026-11-24 | **Looker Studio** para el dashboard administrativo | Gratuito, nativo con BigQuery | Dashboard propio en React | Aceptada |
| D-16 | 2026-11-24 | Perfil de accesibilidad con **necesidades funcionales**, nunca diagnósticos; perfil local para uso anónimo | Dato sensible bajo la LFPDPPP 2025 | Guardar condición médica | Aceptada |
| D-17 | 2026-11-24 | **Corredor piloto: Metro Líneas 2 y 3** (44 estaciones, transbordo en Hidalgo) para el inventario de demostración. Al terminar el MVP, la **primera ampliación es toda la red del Metro** (12 líneas) | Cubre completos los flujos escritos (Tasqueña–Bellas Artes/Hidalgo, Indios Verdes–Copilco) con un esfuerzo de inventario que cabe en el plazo. Ampliar no cambia código ni esquema: el GTFS se carga completo y el inventario es un CSV; fuera del corredor los equipos quedan en `DESCONOCIDO` | Centro Histórico compacto (obligaba a reescribir los ejemplos); L2+L3+L9 a Pantitlán; L2+L3+Metrobús L1 (inventario demasiado grande para el plazo) | Aceptada (resuelve P-02) |

## Decisiones pendientes

| ID | Pregunta | Cuándo decidir |
|---|---|---|
| P-01 | Formato del entregable para el profesor (documento formal, presentación o ambos) | Al terminar la arquitectura y el MVP |
| ~~P-02~~ | ~~Corredor piloto exacto para el inventario de demostración~~ | Resuelta en D-17 |
| P-03 | Fecha de apertura de la cuenta de prueba de Google Cloud | Antes de la Fase 6 del MVP |
| P-04 | Hospedaje de la PWA en la nube (Cloud Run o Firebase Hosting) | Fase 6 |
