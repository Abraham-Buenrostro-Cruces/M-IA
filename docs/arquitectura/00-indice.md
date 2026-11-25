# M-IA — Propuesta de arquitectura tecnológica

**Curso:** Cómputo en la nube — especialización en Data, Machine Learning e IA en Google Cloud
**Autor:** Abraham
**Versión:** 1.0 · 24 de noviembre de 2026
**Ciudad de referencia:** Ciudad de México (Metro, Metrobús, Tren Ligero)

## Contenido

| # | Sección del enunciado | Documento |
|---|---|---|
| 1 | Resumen ejecutivo del producto | [01-resumen-y-propuesta.md](01-resumen-y-propuesta.md#1-resumen-ejecutivo) |
| 2 | Problema que resuelve y propuesta de valor | [01-resumen-y-propuesta.md](01-resumen-y-propuesta.md#2-problema-que-resuelve) |
| 3 | Arquitectura general del sistema | [02-arquitectura-general.md](02-arquitectura-general.md#3-arquitectura-general-del-sistema) |
| 4 | Diagrama de arquitectura (Mermaid) | [02-arquitectura-general.md](02-arquitectura-general.md#4-diagrama-de-arquitectura) |
| 5 | Descripción de cada componente y su responsabilidad | [02-arquitectura-general.md](02-arquitectura-general.md#5-componentes-y-responsabilidades) |
| 6 | Arquitectura de datos y entidades principales | [03-datos.md](03-datos.md) |
| 7 | Integración de Data, Machine Learning e IA | [04-data-ml-ia.md](04-data-ml-ia.md) |
| 8 | Servicios de Google Cloud seleccionados y justificación | [05-servicios-gcp.md](05-servicios-gcp.md) |
| 9 | Diagramas de los cuatro flujos principales | [06-flujos.md](06-flujos.md) |
| 10 | Estrategia de seguridad y escalabilidad | [07-seguridad-escalabilidad.md](07-seguridad-escalabilidad.md) |
| 11 | Arquitectura del MVP y funcionalidades prioritarias | [08-mvp-y-tecnologias.md](08-mvp-y-tecnologias.md#11-arquitectura-del-mvp-y-funcionalidades-prioritarias) |
| 12 | Tecnologías recomendadas para frontend y backend | [08-mvp-y-tecnologias.md](08-mvp-y-tecnologias.md#12-tecnologías-recomendadas) |
| 13 | Posibles limitaciones y riesgos | [09-riesgos-y-evolucion.md](09-riesgos-y-evolucion.md#13-posibles-limitaciones-y-riesgos) |
| 14 | Evolución futura de la plataforma | [09-riesgos-y-evolucion.md](09-riesgos-y-evolucion.md#14-evolución-futura-de-la-plataforma) |

Documentos de apoyo:

- [Registro de decisiones de arquitectura](../decisiones.md)
- [Backlog del MVP](../mvp-backlog.md)
- [Fuentes consultadas](../fuentes.md)

## La arquitectura en una página

1. **Qué es**: un planificador de transporte público para personas con movilidad reducida que optimiza la **probabilidad de completar el viaje**, no el tiempo.
2. **Cómo sabe qué está accesible**: un **estado vivo** por equipo (elevador, rampa) que combina GTFS, reportes comunitarios verificados con **Vision API + Gemini** y predicciones de **BigQuery ML / Vertex AI**, mediante un estimador bayesiano con umbrales asimétricos.
3. **Cómo calcula la ruta**: un grafo propio (estaciones descompuestas en niveles; aristas ligadas a equipos) con restricciones duras por perfil y un costo aditivo $-\ln(1-p_k)$ que permite usar Dijkstra (y, para alternativas, el método de penalización, D-27).
4. **Cómo se usa**: PWA en React con mapa de Google, consulta por voz (**Speech-to-Text v2 + Gemini**) y reportes con foto.
5. **Dónde corre**: Cloud Run (API y trabajadores), Cloud SQL + PostGIS (estado operativo), Cloud Storage (fotos), Pub/Sub (eventos), BigQuery (historial y ML), Looker Studio (dashboard), con IAM, Secret Manager, Identity Platform y Cloud Logging/Monitoring.
6. **Cómo evita recomendaciones inseguras**: "desconocido ≠ accesible", vigencia de datos, jerarquía de fuentes, el ML nunca relaja restricciones, plan B visible y la tasa de rutas fallidas como indicador de seguridad.
