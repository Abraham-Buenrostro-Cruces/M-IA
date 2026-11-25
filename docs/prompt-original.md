# PROMPT: Diseño de arquitectura de producto – RutaAccesible

> Enunciado original, sin cambios. El producto se llamó RutaAccesible hasta el 2026-11-25; desde entonces se llama **M-IA** (D-28).

Quiero que diseñes la arquitectura tecnológica integral de un sistema web y móvil llamado **RutaAccesible**, una plataforma inteligente de transporte público enfocada en personas con movilidad reducida, especialmente personas usuarias de sillas de ruedas.

El proyecto busca resolver un problema de inclusión y accesibilidad: las aplicaciones actuales de transporte público muestran rutas y tiempos estimados, pero no proporcionan información confiable y actualizada sobre la accesibilidad de estaciones, elevadores, rampas y unidades de transporte. Esto dificulta que una persona con movilidad reducida pueda planificar un traslado seguro y confiable.

## 1. Objetivo del producto

Diseñar una plataforma que permita planificar desplazamientos mediante transporte público, priorizando la accesibilidad sobre la rapidez.

El sistema debe identificar rutas que cuenten con:
- Estaciones con elevadores funcionales.
- Rampas de acceso.
- Unidades de transporte con plataformas accesibles.
- Conexiones entre estaciones accesibles.
- Información actualizada sobre obstáculos y fallas de infraestructura.

La plataforma también permitirá que los usuarios reporten problemas de accesibilidad y que la comunidad contribuya a mantener actualizada la información.

## 2. Objetivo del diseño arquitectónico

Necesito que definas una arquitectura de software escalable, modular y orientada a servicios de nube de Google Cloud, integrando capacidades de:

- Data Analytics.
- Machine Learning.
- Inteligencia Artificial.
- Computer Vision.
- Procesamiento de lenguaje y voz.
- APIs y servicios geoespaciales.

La arquitectura debe explicar cómo interactúan los componentes, cómo se procesan los datos y cómo se generan recomendaciones inteligentes.

## 3. Arquitectura funcional del producto

Define los siguientes módulos:

**A. Gestión de usuarios**
- Registro e inicio de sesión.
- Perfil de usuario.
- Preferencias de movilidad y accesibilidad.
- Configuración de necesidades específicas de desplazamiento.

**B. Planificador inteligente de rutas**
- Registro de origen y destino.
- Identificación de estaciones accesibles.
- Consulta del estado de elevadores y rampas.
- Comparación de rutas alternativas.
- Recomendación de la ruta más accesible, aunque no sea la más rápida.
- Visualización de trayectos en un mapa.

**C. Sistema de reportes comunitarios**
- Reportar elevadores fuera de servicio.
- Reportar rampas bloqueadas o dañadas.
- Adjuntar fotografías como evidencia.
- Consultar reportes de otros usuarios.
- Verificar automáticamente evidencias mediante inteligencia artificial.

**D. Motor de recomendaciones con ML**
- Calcular rutas considerando accesibilidad como variable principal.
- Identificar patrones de fallas en estaciones.
- Predecir posibles problemas de accesibilidad.
- Recomendar rutas alternativas.
- Identificar horarios con mayor disponibilidad de infraestructura accesible.

**E. Asistente de voz**
- Permitir que los usuarios indiquen su destino mediante comandos de voz.
- Convertir voz a texto.
- Interpretar la solicitud.
- Generar instrucciones y recomendaciones accesibles.

**F. Dashboard administrativo**
- Visualizar estaciones con mayor cantidad de fallas.
- Consultar reportes comunitarios.
- Identificar zonas con problemas recurrentes.
- Analizar horarios de mayor demanda accesible.
- Consultar indicadores de accesibilidad del sistema.

## 4. Arquitectura de Data, ML e IA

Diseña cómo se integrarán los siguientes servicios y explica la responsabilidad de cada uno:

**Google BigQuery**
- Almacenar y analizar información histórica de estaciones, rutas y reportes.
- Identificar patrones de fallas recurrentes.
- Analizar horarios de mayor demanda.
- Generar indicadores de accesibilidad.

**Vertex AI**
- Desarrollar modelos de Machine Learning para recomendar rutas accesibles.
- Evaluar variables como disponibilidad de elevadores, rampas, conexiones y distancia.
- Identificar patrones y generar predicciones.
- Explicar cómo se entrenarían, evaluarían y actualizarían los modelos.

**Vision API**
- Analizar fotografías enviadas por los usuarios.
- Identificar evidencias visuales de elevadores fuera de servicio, rampas bloqueadas u obstáculos.
- Clasificar automáticamente los reportes.
- Explicar cómo se combinarían los resultados de visión con la validación comunitaria.

**Speech-to-Text**
- Convertir instrucciones de voz en texto.
- Permitir que personas con discapacidad motriz indiquen su destino sin necesidad de escribir.

**Natural Language Processing (NLP)**
- Interpretar solicitudes de los usuarios.
- Comprender reportes escritos.
- Clasificar comentarios y detectar problemas de accesibilidad.

**Google Maps Platform**
- Visualizar estaciones y rutas.
- Mostrar ubicaciones de infraestructura accesible.
- Representar trayectos y alternativas.

## 5. Arquitectura de Google Cloud

Selecciona los servicios de Google Cloud necesarios para construir la solución.

Considera los siguientes servicios:

- Cloud Run o App Engine para alojar el backend.
- BigQuery para análisis de datos.
- Vertex AI para modelos de Machine Learning.
- Cloud Storage para almacenar fotografías y evidencias.
- Cloud SQL o Firestore para información estructurada y operativa.
- Vision API para análisis de imágenes.
- Speech-to-Text para reconocimiento de voz.
- API Gateway para gestionar las solicitudes de los clientes.
- Pub/Sub para procesamiento de eventos y reportes.
- IAM para administración de permisos.
- Secret Manager para proteger credenciales.
- Cloud Logging y Cloud Monitoring para monitoreo.

No es obligatorio utilizar todos los servicios. Selecciona los que realmente aporten valor y justifica cada elección.

## 6. Diseño de flujos de información

Describe paso a paso cómo funcionarían los siguientes escenarios:

**Flujo 1. Búsqueda de una ruta accesible**
1. El usuario indica su origen y destino.
2. El sistema consulta las estaciones y su estado de accesibilidad.
3. El motor inteligente evalúa las alternativas.
4. El modelo recomienda la ruta más accesible.
5. La aplicación muestra el trayecto, estaciones y posibles obstáculos.

**Flujo 2. Reporte de una falla**
1. El usuario identifica un elevador fuera de servicio.
2. Adjunta una fotografía y ubicación.
3. Vision API analiza la imagen.
4. El sistema clasifica el reporte.
5. La información se registra y actualiza el estado de la estación, sujeto a validación.
6. Otros usuarios reciben información actualizada.

**Flujo 3. Recomendación mediante voz**
1. El usuario dicta su destino.
2. Speech-to-Text convierte la voz en texto.
3. NLP interpreta la solicitud.
4. El motor de rutas procesa las preferencias de accesibilidad.
5. Se presenta la recomendación.

**Flujo 4. Análisis predictivo**
1. Se recopilan datos históricos de estaciones y reportes.
2. BigQuery procesa la información.
3. Vertex AI analiza patrones.
4. El modelo identifica estaciones con mayor probabilidad de presentar problemas.
5. El dashboard muestra indicadores y alertas preventivas.

## 7. Diseño de datos

Propón un modelo de datos que incluya las principales entidades:

- Usuario.
- Perfil de accesibilidad.
- Estación.
- Ruta.
- Unidad de transporte.
- Infraestructura accesible.
- Estado de elevadores y rampas.
- Reporte comunitario.
- Evidencia fotográfica.
- Predicción de fallas.
- Recomendación de ruta.

Define los atributos principales, las relaciones entre entidades y qué información se almacenaría en cada servicio de Google Cloud.

## 8. Seguridad y consideraciones técnicas

Explica cómo se protegería la información de los usuarios, considerando:

- Autenticación y autorización.
- Protección de datos personales.
- Permisos de acceso.
- Almacenamiento seguro de evidencias.
- Validación de reportes.
- Disponibilidad y escalabilidad.
- Monitoreo de servicios.

También explica cómo evitar que información incorrecta o desactualizada sobre accesibilidad genere recomendaciones inseguras.

## 9. Entregables de la arquitectura

Quiero que presentes el resultado con la siguiente estructura:

1. Resumen ejecutivo del producto.
2. Problema que resuelve y propuesta de valor.
3. Arquitectura general del sistema.
4. Diagrama de arquitectura utilizando Mermaid.
5. Descripción de cada componente y su responsabilidad.
6. Arquitectura de datos y entidades principales.
7. Integración de Data, Machine Learning e IA.
8. Servicios de Google Cloud seleccionados y justificación.
9. Diagramas de los cuatro flujos principales.
10. Estrategia de seguridad y escalabilidad.
11. Arquitectura del MVP y funcionalidades prioritarias.
12. Tecnologías recomendadas para frontend y backend.
13. Posibles limitaciones y riesgos del proyecto.
14. Evolución futura de la plataforma.

## 10. Consideraciones importantes

- La solución debe ser teórica y conceptual, no un desarrollo completo.
- La arquitectura debe estar alineada con la especialización Data, ML e IA en Google Cloud.
- No quiero una simple lista de tecnologías: necesito entender cómo se conectan y qué función cumple cada servicio.
- Prioriza una arquitectura realista, modular y fácil de explicar.
- Evita agregar servicios innecesarios que compliquen el proyecto.
- Diferencia claramente las funcionalidades que tendría el MVP de las que se implementarían en una versión futura.
- Utiliza ejemplos concretos relacionados con el transporte público y la accesibilidad.
- Explica de manera sencilla los componentes de Machine Learning y cómo aportarían valor al producto.
- Los diagramas deben ser claros, coherentes y representar el flujo real de información.

**Resultado esperado:** una propuesta de arquitectura tecnológica profesional de RutaAccesible que permita comprender cómo funcionaría el producto, cómo se comunicarían sus componentes y cómo Google Cloud, Data, Machine Learning e Inteligencia Artificial ayudarían a resolver el problema de accesibilidad en el transporte público.