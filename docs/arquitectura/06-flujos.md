# 9. Flujos principales

Los ejemplos usan estaciones reales de la CDMX, pero **los estados de los equipos son hipotéticos** (escenario de demostración `data/demo/escenarios/flujo1.csv`; los flujos 1 y 3 son la salida real del motor con ese escenario) y sirven sólo para ilustrar el comportamiento del sistema. Las estaciones se eligieron para que coincidan con el inventario de demostración del corredor piloto (D-17), que respeta el indicador `wheelchair_boarding` del GTFS (D-19); los tiempos de viaje en tren provienen del GTFS publicado el 2026-08-28.

---

## Flujo 1. Búsqueda de una ruta accesible

**Escenario.** Mariana usa silla de ruedas manual. Quiere ir de su casa, cerca de la estación Tasqueña, al Museo de la Ciudad de México (Av. Pino Suárez 30, en el Centro Histórico). La ruta más rápida es la Línea 2 directa hasta Zócalo (19 min de tren y ~320 m a pie). Supongamos que el elevador de la salida de Zócalo tiene una **falla confirmada** desde ayer.

```mermaid
sequenceDiagram
  autonumber
  actor U as Persona usuaria
  participant PWA as PWA
  participant PL as Places API
  participant GW as API Gateway
  participant API as api-core · rutas
  participant DB as Cloud SQL · PostGIS
  participant MOT as Grafo en memoria
  participant RT as Routes API · a pie
  participant PS as Pub/Sub

  U->>PWA: Indica origen y destino
  PWA->>PL: Autocompletado de lugares
  PL-->>PWA: Coordenadas y place_id
  PWA->>GW: POST /rutas/plan con perfil
  GW->>GW: Valida JWT y cuota
  GW->>API: Petición validada
  API->>DB: Estaciones accesibles cercanas a origen y destino
  API->>DB: Estado vigente y predicciones de equipos involucrados
  Note over API,DB: Lectura con caché de 60 s en memoria
  API->>MOT: Aplica restricciones duras del perfil
  MOT->>MOT: Calcula 3 alternativas con Yen y peso w(e)
  MOT-->>API: Rutas candidatas
  API->>RT: Tramos a pie de primera y última milla
  RT-->>API: Distancia, tiempo y trazo
  API->>API: Calcula IAR, equipos críticos y plan B
  API->>PS: Evento consulta-ruta seudonimizado
  API-->>PWA: Alternativas ordenadas con explicación
  PWA-->>U: Mapa, lista accesible y lectura en voz
  alt No existe ruta con IAR aceptable
    API-->>PWA: Aviso explícito, mejor opción con riesgos y sugerencias
  end
```

**Paso a paso (correspondencia con el enunciado)**

1. **El usuario indica origen y destino.** Por texto con autocompletado o con "mi ubicación". El perfil (silla manual: sin escalones, máximo 800 m a pie) viaja con la petición y no se registra en logs.
2. **El sistema consulta las estaciones y su estado.** PostGIS encuentra estaciones con acceso accesible a menos de 600 m del origen y del destino; se leen el estado vigente y las predicciones de sus equipos.
3. **El motor evalúa las alternativas.** Se eliminan las aristas que dependen del elevador de salida de Zócalo (falla confirmada). El algoritmo de Yen calcula hasta tres rutas factibles usando el peso $w(e)$.
4. **El modelo recomienda la ruta más accesible.** Por ejemplo:
   - **A (recomendada, IAR 92)**: Línea 2 hasta **Pino Suárez** (una estación antes), salida José María Izazaga con elevador verificado hace 3 h, ~760 m a pie por Av. Pino Suárez (estimación local: línea recta × 1.3). Unos 5 minutos más que la ruta directa.
   - **B (IAR 92, con advertencia)**: Línea 2 hasta Pino Suárez, salida Pino Suárez, cuyo elevador tiene un dato de hace 30 h. Su IAR es igual al de A, pero la penalización por incertidumbre $u_e$ la deja en segundo lugar y la aplicación avisa "no se verifica desde hace 30 h".
   - **Descartada**: Línea 2 directa a Zócalo, con la explicación "el elevador de salida tiene falla confirmada y las demás salidas sólo tienen escaleras".
5. **La aplicación muestra el trayecto**, las estaciones, los equipos críticos con su última verificación, los posibles obstáculos y el plan B en cada punto crítico ("si el elevador de la salida José María Izazaga no funciona, usa el de la salida Pino Suárez").

---

## Flujo 2. Reporte de una falla

**Escenario.** Luis llega a la estación Pino Suárez y encuentra el elevador hacia el andén con cinta de restricción y un letrero de "fuera de servicio".

```mermaid
sequenceDiagram
  autonumber
  actor U as Persona reportante
  participant PWA as PWA
  participant API as api-core · reportes
  participant GCS as Cloud Storage
  participant DB as Cloud SQL
  participant PS as Pub/Sub
  participant WV as worker-validacion
  participant VIS as Vision API
  participant GEM as Gemini
  participant WE as worker-estado
  actor MOD as Moderador

  U->>PWA: Elige el problema y toma la foto
  PWA->>API: Solicita URL de subida
  API-->>PWA: URL firmada por 5 min, solo imagen, máximo 10 MB
  PWA->>GCS: Sube la foto al bucket privado
  PWA->>API: POST /reportes con tipo, estación, ubicación y foto
  API->>DB: Inserta reporte PENDIENTE
  API->>PS: Publica reporte-creado
  API-->>PWA: 202 Aceptado, reporte en verificación
  PS->>WV: Entrega reporte-creado
  WV->>GCS: Lee la foto
  WV->>VIS: Etiquetas, OCR, rostros y SafeSearch
  VIS-->>WV: Elevador, texto FUERA DE SERVICIO, 2 rostros
  WV->>GEM: Imagen y reporte con esquema JSON
  GEM-->>WV: problema fuera_de_servicio, confianza 0.88
  WV->>DB: Verifica geocerca, duplicados y reputación
  WV->>WV: Calcula puntaje s
  WV->>GCS: Guarda versión con rostros difuminados y sin EXIF
  WV->>DB: Guarda evidencia y estado de validación
  WV->>PS: Publica reporte-validado
  alt Puntaje en zona gris
    WV->>DB: Envía a cola de moderación
    MOD->>DB: Confirma o rechaza
  end
  PS->>WE: Entrega reporte-validado
  WE->>DB: Actualiza Beta y evalúa transición asimétrica
  alt El estado cambia
    WE->>DB: Guarda estado e historial
    WE->>PS: Publica estado-cambiado
  end
  Note over PS: Todos los eventos se copian a BigQuery por suscripción
```

**Paso a paso**

1. **El usuario identifica el elevador fuera de servicio.** La PWA propone los equipos de la estación más cercana ("Elevador andén dirección Cuatro Caminos", "Elevador salida José María Izazaga") para que elija con un toque.
2. **Adjunta fotografía y ubicación.** La foto se sube directamente a Cloud Storage con una URL firmada; el backend nunca recibe el archivo, sólo su referencia.
3. **Vision API analiza la imagen**: detecta el elevador, lee el letrero "FUERA DE SERVICIO" y localiza dos rostros, que se difuminan. Gemini confirma que la imagen coincide con el reporte.
4. **El sistema clasifica el reporte**: con la evidencia visual, la ubicación dentro de la geocerca y la reputación de Luis, $s = 0.82$ → `VERIFICADO_AUTO`.
5. **Se actualiza el estado, sujeto a validación.** El estimador bayesiano pasa el equipo a `FALLA_PROBABLE`. Si en las siguientes horas otra persona confirma (o llega un aviso oficial), pasa a `FALLA_CONFIRMADA`. Para regresar a `OPERATIVO` se exigirá más evidencia (umbral asimétrico).
6. **Otros usuarios reciben información actualizada**: cualquier ruta calculada a partir de ese momento (con un máximo de 60 s de caché) ya considera el cambio. A quienes pasen cerca de Pino Suárez la app les pregunta "¿Sigue fuera de servicio este elevador?" para corroborar. En la versión futura, quien tenga una ruta guardada que pase por ese equipo recibirá una notificación.

---

## Flujo 3. Recomendación mediante voz

**Escenario.** Rosa, adulta mayor con andadera, vive cerca de la estación La Raza y dice: *"Quiero ir de La Raza al Centro Médico Siglo XXI, sin transbordos si se puede."*

```mermaid
sequenceDiagram
  autonumber
  actor U as Persona usuaria
  participant PWA as PWA
  participant API as api-core · voz
  participant STT as Speech-to-Text v2
  participant GEM as Gemini
  participant PL as Places API
  participant RUT as api-core · rutas

  U->>PWA: Activa el botón Hablar
  PWA->>PWA: Graba audio corto
  PWA->>API: POST /voz/consulta con audio y perfil
  API->>STT: Recognize con chirp_3, es-MX y frases de estaciones
  STT-->>API: Texto y confianza
  API->>GEM: Texto con esquema de intención
  GEM-->>API: JSON con origen, destino y restricciones
  alt Falta un dato o hay ambigüedad
    API-->>PWA: Pregunta de aclaración
    PWA-->>U: Lee la pregunta en voz alta
    U->>PWA: Responde por voz
    PWA->>API: Nueva consulta con contexto
  end
  API->>API: Resuelve origen contra el catálogo de estaciones
  API->>PL: Resuelve Centro Médico Siglo XXI
  PL-->>API: Coordenadas
  API->>RUT: Ejecuta Flujo 1 con perfil y sin transbordos
  RUT-->>API: Alternativas con IAR
  API-->>PWA: Rutas e instrucciones en lenguaje claro
  PWA-->>U: Muestra y lee la recomendación
```

**Paso a paso**

1. **El usuario dicta su destino** con un botón grande, accesible por teclado y lector de pantalla.
2. **Speech-to-Text convierte la voz en texto.** La adaptación con nombres de estaciones evita confundir "La Raza" o "Tlatelolco".
3. **NLP interpreta la solicitud.** Gemini devuelve `{origen: "La Raza", destino: "Centro Médico Siglo XXI", restricciones: {max_transbordos: 0}}`. "Centro Médico" es ambiguo (también existe el Centro Médico Nacional La Raza, junto a la estación de origen): como el texto dice "Siglo XXI", se resuelve con Places API; si no lo dijera, la aplicación preguntaría.
4. **El motor procesa las preferencias de accesibilidad.** Se combinan las restricciones dichas en voz con el perfil guardado (andadera: evitar escaleras largas, tolerancia moderada a caminar). Línea 3 directa satisface "sin transbordos".
5. **Se presenta la recomendación** en pantalla y en voz: *"Te recomiendo la Línea 3 de La Raza a Centro Médico, sin transbordos. El elevador de La Raza fue verificado hace dos horas. En Centro Médico usa la salida Avenida Cuauhtémoc, que tiene rampa; el hospital está a unos 200 metros. Tiempo estimado: 27 minutos."*

---

## Flujo 4. Análisis predictivo

**Escenario.** Cada semana el sistema reentrena el modelo de fallas y cada noche actualiza las predicciones para los próximos 7 días.

```mermaid
sequenceDiagram
  autonumber
  participant SCH as Cloud Scheduler
  participant PIPE as Vertex AI Pipelines
  participant BQ as BigQuery y BigQuery ML
  participant REG as Model Registry
  participant JOB as Cloud Run Job
  participant DB as Cloud SQL
  participant LKS as Looker Studio
  participant MON as Cloud Monitoring

  SCH->>PIPE: Disparo semanal
  PIPE->>BQ: Construye features por equipo, día y franja
  PIPE->>BQ: Entrena modelo challenger
  PIPE->>BQ: Evalúa champion y challenger en el periodo de prueba
  alt Challenger mejora PR-AUC sin perder calibración
    PIPE->>REG: Registra y promueve como champion
  else No mejora
    PIPE->>REG: Registra métricas sin promover
  end
  PIPE->>MON: Publica métricas del modelo
  SCH->>BQ: Disparo diario de predicción por lotes
  BQ->>BQ: ML.PREDICT y ML.EXPLAIN_PREDICT para 7 días
  BQ->>BQ: Escribe pred_falla_equipo
  SCH->>JOB: Disparo diario de sincronización
  JOB->>BQ: Lee predicciones vigentes
  JOB->>DB: Actualiza prediccion_falla
  LKS->>BQ: Consulta vistas gold
  Note over LKS: Ranking de riesgo, factores principales y alertas preventivas
  MON-->>MON: Alerta si la calibración se degrada
```

**Paso a paso**

1. **Se recopilan datos históricos**: reportes, cambios de estado, afluencia, calendario y avisos llegan continuamente a BigQuery.
2. **BigQuery procesa la información**: limpia y construye la tabla de *features* por equipo, día y franja.
3. **Vertex AI analiza patrones**: la *pipeline* entrena, evalúa, compara y registra el modelo.
4. **El modelo identifica las estaciones con mayor probabilidad de problemas**: por ejemplo, "Elevador salida oriente de Pantitlán: 41 % de probabilidad de falla el viernes por la tarde; factores: 4 fallas en 30 días, alta afluencia, temporada de lluvias".
   > Nota (D-17): Pantitlán queda fuera del corredor piloto del MVP (Líneas 2 y 3); en la demostración el ejemplo usa una estación del corredor con elevadores, como Tasqueña o Pino Suárez. Pantitlán se incorpora en la Fase 9, con toda la red del Metro.
5. **El dashboard muestra indicadores y alertas preventivas**: ranking de equipos en riesgo, mapa de zonas críticas, MTTR por línea y evolución de la disponibilidad. Las mismas predicciones ya están en Cloud SQL para que el motor de rutas las use desde la mañana siguiente.
