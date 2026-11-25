# 1–2. Resumen ejecutivo, problema y propuesta de valor

## 1. Resumen ejecutivo

**RutaAccesible** es una plataforma web y móvil (PWA) de planificación de viajes en transporte público de la Ciudad de México (Metro, Metrobús y Tren Ligero) diseñada para personas con movilidad reducida, en particular usuarias y usuarios de silla de ruedas.

Su idea central invierte la lógica de los planificadores convencionales:

> **La accesibilidad es una restricción y el criterio principal de optimización; la rapidez es un criterio secundario.**

Un planificador tradicional minimiza el tiempo de viaje. RutaAccesible maximiza la **probabilidad de completar el viaje sin encontrar una barrera insalvable** (un elevador fuera de servicio, una rampa bloqueada, un transbordo sin circulación vertical accesible) y, entre las rutas igualmente seguras, prefiere la más rápida.

Para lograrlo, la plataforma mantiene un **estado vivo de la infraestructura accesible**: un inventario de elevadores, rampas y accesos a nivel por estación, cuyo estado se actualiza combinando tres fuentes:

1. **Datos base abiertos**: GTFS estático de la CDMX (estaciones, líneas, horarios y un indicador de accesibilidad por parada).
2. **Reportes comunitarios** con fotografía, verificados automáticamente con **Vision API** y un modelo multimodal **Gemini** en Vertex AI, y ponderados por la reputación de quien reporta y la corroboración de otras personas.
3. **Predicciones de Machine Learning** entrenadas sobre el historial en **BigQuery** y gestionadas en **Vertex AI**, que estiman la probabilidad de falla de cada equipo por día y franja horaria.

Ese estado alimenta un **motor de rutas propio** basado en grafos, que calcula alternativas, les asigna un **Índice de Accesibilidad de Ruta (IAR)** y explica a la persona usuaria por qué recomienda cada una. El sistema admite consultas por **voz** (Speech-to-Text + interpretación con Gemini), y un **dashboard administrativo** (Looker Studio sobre BigQuery) da a operadores e instituciones indicadores de fallas, zonas críticas y horarios de mayor demanda accesible.

La solución se construye sobre **Google Cloud** con una arquitectura serverless y modular: Cloud Run, Cloud SQL (PostgreSQL + PostGIS), Cloud Storage, Pub/Sub, BigQuery, Vertex AI, Vision API, Speech-to-Text, Google Maps Platform e Identity Platform, con IAM, Secret Manager, Cloud Logging y Cloud Monitoring como base de seguridad y operación.

> **Nota de nomenclatura (noviembre 2026).** En abril de 2026 Google renombró Vertex AI como *Gemini Enterprise Agent Platform*; las capacidades de Vertex AI (entrenamiento, Model Registry, Pipelines, predicción y acceso a Gemini) siguen disponibles dentro de esa plataforma. En este documento se usa "Vertex AI" por ser el nombre que pide el enunciado y el más reconocido, entendiendo que hoy se accede a él como parte de Agent Platform.

---

## 2. Problema que resuelve

### 2.1 El problema

Las aplicaciones de transporte público muestran rutas y tiempos estimados, pero **no responden a la pregunta que importa a una persona en silla de ruedas: "¿podré realmente salir de la estación a la que voy a llegar?"**

Tres brechas concretas explican el problema en la CDMX:

| Brecha | Evidencia | Consecuencia |
|---|---|---|
| **La accesibilidad cambia día a día y nadie la publica en tiempo real.** | La prensa reporta elevadores fuera de servicio durante semanas o meses (por ejemplo, en el CETRAM Indios Verdes y en estaciones de la Línea 2 durante su remodelación en 2026). | Una ruta "accesible" según datos estáticos puede terminar en un andén sin salida. |
| **No existe un inventario público y consistente de equipos.** | Las cifras oficiales de elevadores del Metro citadas en distintas notas no coinciden entre sí (se han reportado 128, 187 y 200 equipos según la fuente y la fecha). | No hay una base confiable sobre la cual planificar. |
| **Las APIs de rutas no exponen la opción de silla de ruedas.** | Google Maps ofrece rutas "accesibles en silla de ruedas" en su app para la CDMX desde 2018, pero la Routes API para desarrolladores sólo permite preferir "menos caminata" o "menos transbordos" en rutas de transporte público. | Un tercero no puede construir sobre esa capacidad; además, se basa en atributos estáticos de estación, no en el estado actual de los equipos. |

El GTFS estático de la CDMX sí incluye un indicador de accesibilidad por parada, pero no describe **qué equipo** hace accesible la estación ni su estado, y no incluye el archivo `pathways.txt` (circulaciones internas de estación).

### 2.2 A quién afecta

- En México viven alrededor de **6.2 millones de personas con discapacidad** (Censo 2020), y la dificultad más frecuente es **caminar, subir o bajar**.
- También se benefician personas adultas mayores, personas con lesiones temporales, con bastón o andadera, y quienes viajan con carriola.

### 2.3 Por qué importa el "costo de una ruta fallida"

Para la mayoría de las personas, un elevador descompuesto significa subir escaleras. Para una persona usuaria de silla de ruedas significa **quedar atrapada en un andén**, depender de terceros para ser cargada (con riesgo físico) o desandar el viaje. Por eso el objetivo de optimización no puede ser el tiempo: un minuto adicional es aceptable; una barrera insalvable no lo es.

---

## 2.4 Propuesta de valor

### Para personas usuarias

- **Rutas que priorizan llegar, no llegar rápido**: cada alternativa muestra su probabilidad estimada de éxito, la fecha de la última verificación de cada equipo crítico y un plan B.
- **Perfil de movilidad personalizado**: silla manual, silla eléctrica, andadera, adulto mayor, carriola; cada perfil cambia qué cuenta como barrera.
- **Consulta por voz** para quien no puede o prefiere no escribir ("llévame de Tasqueña al Zócalo sin transbordos").
- **Transparencia**: el sistema dice "no sé" cuando no sabe, en lugar de suponer que un equipo funciona.

### Para la comunidad

- Reportar una falla toma menos de 30 segundos (foto + ubicación automática), y el reporte beneficia de inmediato a otras personas.
- La reputación y la corroboración entre pares hacen que la información sea confiable sin depender sólo de moderación humana.

### Para operadores e instituciones (STC Metro, Metrobús, SEMOVI)

- **Dashboard** de estaciones con más fallas, tiempo medio de restablecimiento, zonas con problemas recurrentes y demanda accesible por horario.
- **Mantenimiento preventivo**: el modelo predictivo señala los equipos con mayor probabilidad de fallar en los próximos días.
- **Datos abiertos de retorno**: el inventario de equipos verificado puede publicarse como extensión del GTFS de la ciudad.

### Diferenciadores frente a un planificador convencional

| Criterio | Planificador convencional | RutaAccesible |
|---|---|---|
| Objetivo de optimización | Minimizar tiempo | Maximizar probabilidad de completar el viaje; tiempo como desempate |
| Dato de accesibilidad | Estático por estación (si existe) | Estado dinámico por equipo (elevador, rampa) con nivel de confianza |
| Manejo de incertidumbre | Asume que todo funciona | "Desconocido" no equivale a "accesible"; se penaliza y se explica |
| Fuente de actualización | Agencia de transporte | Agencia + comunidad verificada por IA + predicción ML |
| Interacción | Texto | Texto y voz |
| Valor para el operador | Ninguno | Dashboard e indicadores de mantenimiento |
