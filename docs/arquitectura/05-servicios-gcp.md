# 8. Servicios de Google Cloud seleccionados y justificación

## 8.1 Criterio de selección

Un servicio entra a la arquitectura sólo si cumple al menos una de estas condiciones:

1. Resuelve una necesidad funcional que no cubre otro servicio ya elegido.
2. Reduce de forma clara el trabajo de operación (administrado o serverless).
3. Es necesario para la seguridad o el cumplimiento normativo.

Cuando dos servicios cubren lo mismo, se elige el más simple y se documenta la alternativa descartada.

## 8.2 Servicios seleccionados

| Servicio | Rol en M-IA | Justificación | Alternativa descartada y por qué | MVP |
|---|---|---|---|---|
| **Cloud Run** | Aloja `api-core`, `worker-validacion`, `worker-estado` y los Jobs por lotes | Contenedores sin servidores que administrar, escala a cero, escala horizontal automática, soporta tanto servicios HTTP como Jobs | **App Engine**: menos flexible con dependencias nativas (PostGIS, NetworkX) y sin Jobs por lotes; **GKE**: excesivo para el tamaño del proyecto | Sí |
| **Cloud SQL para PostgreSQL + PostGIS** | Fuente de verdad del estado operativo | Relaciones fuertes entre estaciones, equipos y reportes; transacciones; consultas espaciales nativas | **Firestore**: excelente para sincronización en tiempo real, pero sin *joins* ni consultas geoespaciales ricas; se reserva como opción futura para notificaciones en vivo | Sí |
| **Cloud Storage** | Fotos originales y redactadas | Almacenamiento de objetos barato, durable, con URLs firmadas y reglas de ciclo de vida | — | Sí |
| **Pub/Sub** | Bus de eventos de dominio | Desacopla la recepción de un reporte de su verificación con IA; absorbe picos; suscripción directa a BigQuery sin código | **Dataflow**: innecesario porque no hay transformaciones en streaming complejas; **Cloud Tasks**: sirve para tareas puntuales, no para distribuir un evento a varios consumidores | Simulado localmente; real al desplegar |
| **BigQuery** (+ BigQuery ML, BigQuery GIS) | Historial, indicadores, *features*, entrenamiento tabular | Analítica sin servidor, SQL conocido por el equipo, ML con SQL y funciones geoespaciales | **Dataproc/Spark**: excesivo para el volumen esperado | Sí (con datos sintéticos) |
| **Vertex AI** (Gemini Enterprise Agent Platform) | Pipelines, Model Registry, predicción por lotes, acceso a Gemini | Gobierno del ciclo de vida de modelos; Gemini para lenguaje y visión | Entrenar en una VM propia: sin trazabilidad ni versionado | Gemini: sí. Pipelines: versión simplificada |
| **Vision API** | Verificación de fotos, OCR de letreros, difuminado de rostros | Modelos preentrenados; sin necesidad de datos etiquetados al inicio | Clasificador propio desde el día 1: no hay datos para entrenarlo | Sí |
| **Speech-to-Text v2** (Chirp 3) | Voz a texto | Modelo multilingüe con español de México y adaptación de vocabulario | Reconocimiento del navegador (Web Speech API): calidad variable y sin adaptación a nombres de estaciones | Sí |
| **Google Maps Platform** | Mapa, búsqueda de lugares, tramos a pie | Estándar de facto; los usuarios lo reconocen | Mapas abiertos (Leaflet + OpenStreetMap): se usan sólo como respaldo en desarrollo local | Sí |
| **Identity Platform** | Registro, inicio de sesión y emisión de JWT para personas usuarias | IAM gestiona identidades de **servicios**, no de personas; Identity Platform es el servicio de identidad de clientes de Google Cloud, compatible con Firebase Authentication, con MFA para administradores | Autenticación propia: riesgo de seguridad innecesario | Simulado localmente; real al desplegar |
| **API Gateway** | Punto de entrada único | Valida JWT antes de llegar al backend, aplica cuotas y límites de peticiones (defensa contra spam de reportes), habilita llaves para socios institucionales | **Cloud Load Balancing + Cloud Armor**: más potente pero más complejo; se considera si el tráfico crece | No (Cloud Run directo) |
| **IAM** | Permisos de cuentas de servicio y de personas administradoras | Mínimo privilegio, una cuenta de servicio por componente | — | Sí |
| **Secret Manager** | Llaves de Maps, contraseña de base de datos, sal de seudonimización | Sin secretos en código ni en imágenes de contenedor | Variables de entorno en texto plano | Sí |
| **Cloud Logging y Cloud Monitoring** | Bitácoras estructuradas, métricas, alertas, paneles de salud | Integrados de forma nativa con Cloud Run | — | Sí |
| **Cloud Scheduler** | Dispara la carga del GTFS, el reentrenamiento y la sincronización de predicciones | Cron administrado | — | Sí |
| **Artifact Registry + Cloud Build** | Imágenes de contenedor y despliegue continuo | Integración directa con Cloud Run | — | Sí (despliegue manual con `gcloud` también es válido) |
| **Looker Studio** | Dashboard administrativo | Sin costo de licencia, conexión nativa a BigQuery | Dashboard propio en React: más trabajo sin beneficio para el MVP | Sí |

## 8.3 Servicios evaluados y no incluidos

| Servicio | Motivo |
|---|---|
| **App Engine** | Cloud Run cubre el caso con más flexibilidad. |
| **Firestore** | Cloud SQL resuelve el modelo relacional y geoespacial; Firestore se reconsidera para sincronización en vivo con la app. |
| **Cloud Natural Language API** | Gemini cubre clasificación, entidades e intención en una sola integración (ver documento 04). |
| **Dataflow** | Las suscripciones de Pub/Sub a BigQuery bastan para el volumen esperado. |
| **GKE** | Sobredimensionado. |
| **Memorystore (Redis)** | El grafo y el estado caben en memoria de cada instancia; se agrega si la carga lo exige. |
| **Datastream** | Las consultas federadas nocturnas bastan al inicio; Datastream entra cuando se requiera casi tiempo real en BigQuery. |

## 8.4 Regiones

- **Datos y aplicación**: `northamerica-south1` (Querétaro, México), en operación desde diciembre de 2024. Ofrece baja latencia para usuarios en la CDMX y residencia de datos en el país, algo deseable por tratarse de datos sensibles.
- **APIs de IA**: se usan los *endpoints* regionales o globales donde cada modelo esté disponible (por ejemplo, `us-central1`). Antes de desplegar se debe verificar en la consola la disponibilidad por región de Chirp 3, Gemini y Cloud SQL con PostGIS; si algún servicio no está en Querétaro, la aplicación completa puede ubicarse en `us-central1` sin cambiar el diseño.
- Sólo viajan a las APIs de IA los datos estrictamente necesarios (una imagen ya sin metadatos, un audio corto, un texto) y nunca el perfil de accesibilidad.

## 8.5 Costos y cuenta

- Para el proyecto se recomienda abrir la **prueba gratuita de Google Cloud**: 300 USD de crédito durante 90 días, aplicables también a Google Maps Platform. Requiere registrar un método de pago, pero no genera cargos mientras no se active una cuenta de pago.
- Controles de costo: presupuesto con alertas al 50 %, 80 % y 100 %; Cloud Run con escala a cero (excepto `api-core` en producción); cuotas por API en la consola; caché de resultados de Places y de rutas frecuentes según los términos de uso de Maps.
- El costo variable más relevante lo generan las llamadas a Gemini, Vision y Maps; por eso Vision y Gemini sólo se invocan en el camino frío (un reporte = una llamada de cada uno) y nunca al calcular una ruta.
