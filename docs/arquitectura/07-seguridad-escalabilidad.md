# 10. Estrategia de seguridad y escalabilidad

## 10.1 Autenticación y autorización

**Autenticación de personas** con Identity Platform: correo y contraseña, o inicio de sesión con Google. MFA obligatorio para moderadores, operadores y administradores. La app emite un JWT de vida corta que API Gateway valida antes de que la petición llegue a Cloud Run; el backend vuelve a verificar el token y extrae el rol (defensa en profundidad).

**Uso anónimo permitido**: consultar rutas no requiere cuenta. El perfil de movilidad de una persona anónima se guarda **sólo en su dispositivo** y viaja con cada petición sin persistirse en el servidor. La cuenta sólo es necesaria para reportar, votar y guardar rutas.

**Autorización por roles (RBAC)**

| Acción | Anónimo | Usuario | Usuario confiable | Moderador | Operador institucional | Admin |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Consultar rutas y estado | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Guardar perfil y rutas en servidor | | ✓ | ✓ | ✓ | ✓ | ✓ |
| Crear reportes y votar | | ✓ | ✓ (mayor peso) | ✓ | ✓ | ✓ |
| Ver fotos sin redactar | | | | ✓ | | ✓ |
| Confirmar o rechazar reportes | | | | ✓ | | ✓ |
| Publicar avisos oficiales | | | | | ✓ | ✓ |
| Ver dashboard | | | | ✓ | ✓ | ✓ |
| Administrar usuarios y catálogos | | | | | | ✓ |

"Usuario confiable" no se asigna a mano: se obtiene por reputación (antigüedad de la cuenta, porcentaje de reportes confirmados) y teléfono verificado.

**Identidades de servicio con IAM (mínimo privilegio)**

| Cuenta de servicio | Permisos principales |
|---|---|
| `sa-api-core` | Cliente de Cloud SQL; crear URLs firmadas en el bucket de evidencias (sólo escritura en la ruta de subidas); publicar en Pub/Sub; usar Speech-to-Text y Vertex AI; leer secretos específicos |
| `sa-worker-validacion` | Leer y escribir en el bucket de evidencias; usar Vision API y Vertex AI; cliente de Cloud SQL; publicar en Pub/Sub |
| `sa-worker-estado` | Cliente de Cloud SQL; publicar en Pub/Sub |
| `sa-jobs` | Cliente de Cloud SQL; editor de datos en datasets de BigQuery específicos |
| `sa-pipelines` | Usuario de Vertex AI; editor de datos en `ra_ml`; lectura en `ra_silver` |
| `sa-dashboard` | Lector de datos sólo en `ra_gold` |

Nadie (ni personas ni servicios) tiene el rol de propietario del proyecto en operación diaria; los cambios de infraestructura pasan por Cloud Build.

## 10.2 Protección de datos personales

**Marco legal.** En México rige la **Ley Federal de Protección de Datos Personales en Posesión de los Particulares** (nueva ley publicada en el DOF el 20 de marzo de 2025). La información sobre discapacidad o movilidad es un **dato personal sensible**, por lo que su tratamiento exige **consentimiento expreso y por escrito**, que puede otorgarse por medios electrónicos de autenticación. Si la plataforma la operara una entidad pública, aplicaría la ley general correspondiente a sujetos obligados.

**Medidas**

| Principio | Implementación |
|---|---|
| Consentimiento expreso | Pantalla específica antes de guardar el perfil en el servidor, con casilla no marcada por defecto; se registra fecha y versión del aviso de privacidad. |
| Minimización | Se guardan **necesidades funcionales** ("requiere elevador", "máximo 600 m a pie"), nunca diagnósticos. El correo vive sólo en Identity Platform. |
| Privacidad por diseño | Perfil local para uso anónimo; los audios no se almacenan; la ubicación sólo se toma al reportar o al pedir "mi ubicación". |
| Seudonimización | En BigQuery el `id_usuario` se sustituye por un hash con sal guardada en Secret Manager; los orígenes y destinos se generalizan. |
| Retención limitada | Orígenes/destinos exactos: 30 días; fotos originales: 90 días; después, sólo agregados. |
| Derechos ARCO | Endpoints para exportar y eliminar los datos propios; la eliminación propaga a Cloud SQL, Cloud Storage y BigQuery. |
| Cifrado | En tránsito con TLS; en reposo con el cifrado predeterminado de Google Cloud; llaves administradas por el cliente (CMEK) como opción para producción institucional. |
| Datos hacia APIs de IA | Sólo se envía lo indispensable: imagen sin metadatos, audio corto o texto. El perfil de accesibilidad nunca se envía a modelos externos. |

## 10.3 Almacenamiento seguro de evidencias

- **Bucket privado** con acceso uniforme a nivel de bucket y prevención de acceso público activada.
- **Subida con URL firmada** de corta duración, restringida a tipo de contenido de imagen y tamaño máximo; el nombre del objeto lo genera el servidor (la persona no controla la ruta).
- **Saneamiento**: el trabajador vuelve a codificar la imagen (elimina cargas ocultas), borra los metadatos EXIF de la versión pública y **difumina rostros** detectados con Vision API.
- **Dos versiones**: `originales/` (sólo moderadores y el trabajador de validación) y `redactadas/` (lo que ven otras personas, entregado con URLs firmadas de lectura de pocos minutos).
- **Ciclo de vida**: eliminación automática de originales a los 90 días.
- **Auditoría**: Cloud Audit Logs registra cada acceso a originales.

## 10.4 Validación de reportes y defensa contra abuso

| Riesgo | Control |
|---|---|
| Spam o saturación de reportes | Cuotas en API Gateway y límite por usuario en la aplicación (por ejemplo, máximo N reportes por hora y por estación). |
| Reportes falsos intencionales | Puntaje de confianza (visión + geocerca + reputación + corroboración); umbrales asimétricos para cambiar el estado. |
| Fotos recicladas o de internet | Hash exacto y hash perceptual contra todas las evidencias previas; fecha EXIF. |
| Cuentas falsas coordinadas | El peso de un reporte crece con la antigüedad y el historial de la cuenta; votos de cuentas nuevas pesan poco; detección de ráfagas desde la misma red. |
| Contenido inapropiado | SafeSearch de Vision API y filtros de seguridad de Gemini. |
| Errores de la IA | Zona gris de puntaje → moderación humana; el resultado del moderador alimenta el reentrenamiento del puntaje. |

## 10.5 Evitar recomendaciones inseguras por datos incorrectos o desactualizados

Esta es la consideración de seguridad más importante del producto. Se aplican diez reglas de diseño:

1. **"Desconocido" no es "accesible".** Un equipo sin evidencia reciente se trata como incierto y penaliza la ruta; nunca se asume que funciona.
2. **Umbrales asimétricos.** Marcar un equipo como "en falla" requiere poca evidencia; marcarlo como "funciona" de nuevo requiere evidencia fuerte (documento 04, sección 7.4).
3. **Vigencia y decaimiento.** Toda información tiene fecha de expiración; la confianza decae con el tiempo.
4. **Jerarquía de fuentes.** Aviso oficial > moderador > reportes verificados y corroborados > reporte individual > predicción del modelo > dato estático del GTFS.
5. **El ML nunca relaja restricciones duras.** Las predicciones sólo ajustan costos entre rutas factibles; ningún modelo puede "habilitar" una arista bloqueada.
6. **Transparencia.** Cada ruta muestra su IAR, los equipos críticos, la hora de su última verificación y la fuente.
7. **Plan B siempre visible.** En cada punto crítico se indica la alternativa (otra salida, la estación siguiente) y se puede consultar sin señal.
8. **Ciclo de retroalimentación en el viaje.** El botón "No pude pasar" en plena ruta recalcula de inmediato desde la posición actual y registra evidencia de alto peso.
9. **Humano en el circuito.** Las restauraciones a `OPERATIVO` y los casos de puntaje ambiguo pasan por moderación cuando no hay fuente oficial.
10. **Seguridad medida como indicador.** La **tasa de rutas fallidas** (viajes recomendados en los que la persona encontró una barrera) se monitorea como objetivo de nivel de servicio; si sube, se dispara una alerta y se revisan pesos y umbrales.

**Cuando no hay ruta segura (D-26).** La app lo dice primero ("No hay ruta segura hasta tu destino") y, en lugar de dejar a la persona sin nada, ofrece otras opciones separadas de las alternativas: una ruta segura por otros sistemas, una ruta segura hasta la estación accesible más cercana al destino, la ruta que funcionaría si se repara un equipo y, **siempre al final**, la ruta completa con asistencia, que marca en rojo cada punto donde se necesita ayuda del personal y el motivo. Esta última es la única forma en que una ruta que viola una restricción dura puede aparecer, y nunca se ordena junto con las alternativas.

Además, la app comunica con claridad que la información proviene de la comunidad y de modelos estadísticos, y que no sustituye los avisos oficiales del operador.

## 10.6 Disponibilidad y escalabilidad

| Aspecto | Estrategia |
|---|---|
| Escalado de la API | Cloud Run escala horizontalmente por concurrencia; `api-core` mantiene al menos una instancia activa para evitar arranques en frío (el grafo de Metro, Metrobús y Tren Ligero se carga en memoria en pocos segundos y ocupa poco). |
| Picos de demanda (eventos masivos, cierres) | Pub/Sub absorbe ráfagas de reportes; los trabajadores escalan de forma independiente; las rutas frecuentes se cachean con vida corta. |
| Base de datos | Cloud SQL con alta disponibilidad (réplica en otra zona) en producción; réplica de lectura si las consultas crecen; *pool* de conexiones limitado por instancia. |
| Degradación controlada | Si Vision o Gemini fallan, el reporte queda en cola de moderación (no se pierde). Si Speech-to-Text falla, la app ofrece entrada de texto. Si Maps falla, se muestra la ruta como lista textual. Si Cloud SQL no responde, la app muestra la última ruta guardada en el dispositivo. |
| Uso sin señal | La PWA guarda en caché la ruta activa, sus instrucciones y los planes B, porque dentro de algunas estaciones la conectividad es limitada. |
| Accesibilidad de la propia app | WCAG 2.2 AA: compatible con lectores de pantalla (TalkBack, VoiceOver), alto contraste, objetivos táctiles grandes, sin depender sólo del color, navegación completa por teclado y pruebas automáticas con axe-core. |

## 10.7 Monitoreo de servicios

- **Cloud Logging**: bitácoras estructuradas en JSON con identificador de correlación por petición; sin datos personales en los logs.
- **Cloud Monitoring**: paneles por servicio y alertas sobre estos objetivos de nivel de servicio:

| Indicador (SLI) | Objetivo (SLO) inicial |
|---|---|
| Latencia p95 de `/rutas/plan` | < 2.5 s |
| Disponibilidad de `api-core` | ≥ 99.5 % mensual |
| Tiempo desde reporte hasta estado actualizado (p95) | < 3 min |
| Cobertura de datos frescos en equipos del corredor piloto | ≥ 80 % con verificación en las últimas 24 h |
| Mensajes en *dead-letter* de Pub/Sub | 0 sostenido |
| Tasa de rutas fallidas | Tendencia a la baja; alerta ante aumentos |

- **Error Reporting y Cloud Trace** (incluidos con Cloud Run) para diagnosticar errores y latencias.
- **Comprobaciones de disponibilidad** externas sobre el endpoint de salud.
- **Presupuesto y alertas de costo** como parte del monitoreo.
