# Levantar M-IA en otra computadora

> **Para Claude:** este documento es tu guía para dejar el proyecto M-IA funcionando desde cero en esta computadora. Sigue los pasos en orden, verifica cada uno con su comprobación y, si algo falla, usa la sección de problemas comunes antes de improvisar. Al terminar, **lee completo `CLAUDE.md`** del repositorio: ahí están las reglas de trabajo, las decisiones y las reglas de seguridad del dominio, que son obligatorias. No cambies código para "hacer que funcione" sin explicarlo y pedir aprobación.

## 1. Qué es el proyecto

**M-IA** es una PWA de planificación de viajes accesibles en el transporte público de la CDMX (Metro, Metrobús, Tren Ligero, Tren Suburbano y Tren El Insurgente) para personas con movilidad reducida, sobre todo usuarias de silla de ruedas. Optimiza la **probabilidad de llegar sin barreras**; el tiempo es secundario. Es el proyecto de un curso de cómputo en la nube (Google Cloud), con tono académico de maestría.

- Repositorio público: https://github.com/Abraham-Buenrostro-Cruces/M-IA (rama `main`).
- Backend: Python 3.12 + FastAPI + PostGIS (Docker). Frontend: React + TypeScript + Vite (PWA).
- Todo corre en **modo local** (`RA_MODO=local`): los servicios de IA y nube están simulados con adaptadores; aún no hay cuenta de Google Cloud.
- El inventario de elevadores y rampas es **de demostración** y los estados de los equipos son **sintéticos** (se dice en la app). Las estaciones, líneas y su accesibilidad general vienen del GTFS oficial.

## 2. Requisitos

| Herramienta | Versión | Comprobación |
|---|---|---|
| Git | cualquiera reciente | `git --version` |
| Python | **3.12** (no 3.13) | Windows: `py -3.12 --version` · macOS/Linux: `python3.12 --version` |
| Node.js | 22 o superior (se desarrolló con 26) | `node --version` |
| Docker Desktop | encendido | `docker compose version` y `docker ps` sin error |
| RAM | 8 GB alcanzan | PostGIS usa como máximo 512 MB |

En Windows, si faltan: `winget install Git.Git`, `winget install Python.Python.3.12`, `winget install OpenJS.NodeJS.LTS`, `winget install Docker.DockerDesktop` (Docker pide reiniciar y abrir Docker Desktop una vez). Si `node` o `docker` no se reconocen después de instalar, abre una terminal nueva o agrega `C:\Program Files\nodejs` y `C:\Program Files\Docker\Docker\resources\bin` al PATH.

**Rutas del entorno virtual:** en Windows los ejecutables están en `backend/.venv/Scripts/`; en macOS/Linux, en `backend/.venv/bin/`. Los comandos de abajo usan la forma de Windows; cámbiala si hace falta.

## 3. Pasos

### 3.1 Clonar

Dentro de la carpeta vacía donde se abrió Claude:

```bash
git clone https://github.com/Abraham-Buenrostro-Cruces/M-IA.git .
```

(Si la carpeta no está vacía, clona en `M-IA/` y trabaja dentro de ella.)

✔ Debe existir `CLAUDE.md`, `backend/`, `frontend/`, `data/demo/niveles.csv`.

### 3.2 Archivo `.env`

```bash
cp .env.example .env
```

Edita `.env`:
- Cambia `POSTGRES_PASSWORD` por una contraseña nueva y pon **la misma** dentro de `RA_BD_URL`.
- Llena `RA_JWT_SECRETO` con un secreto de al menos 32 caracteres:
  `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- Deja `RA_BD_URL` con `127.0.0.1`, **no** `localhost` (en Windows, `localhost` intenta IPv6 primero y cada conexión tarda ~5 s).

`.env` nunca se sube a git (está en `.gitignore`).

### 3.3 Base de datos (PostGIS en Docker)

```bash
docker compose up -d
docker compose exec db pg_isready -U ra -d rutaaccesible
```

✔ `accepting connections`. Si el puerto 5432 está ocupado por otro Postgres, cambia `POSTGRES_PUERTO` en `.env` y el puerto en `RA_BD_URL`.

### 3.4 Backend

```bash
cd backend
py -3.12 -m venv .venv              # macOS/Linux: python3.12 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/alembic upgrade head
cd ..
```

✔ `alembic upgrade head` termina sin error y `backend/.venv/Scripts/alembic check` dice `No new upgrade operations detected.`

### 3.5 GTFS de la CDMX (datos crudos, no se versionan)

El inventario versionado en `data/demo/` se generó con el **GTFS publicado el 2026-08-28** (SHA-256 `a2ecd0fbdf56e787b8eee3a6a3719043667b022a849f7f510812054677225384`). Hay dos caminos:

**A. (Preferido) Copiar ese mismo archivo** desde la computadora original: `data/raw/gtfs/2026-08-28/gtfs.zip` (2.4 MB) y su `metadatos.json`, a la misma ruta en esta computadora. Comprueba la huella:

```bash
python -c "import hashlib;print(hashlib.sha256(open('data/raw/gtfs/2026-08-28/gtfs.zip','rb').read()).hexdigest())"
```

✔ Debe imprimir `a2ecd0fb…7225384`.

**B. Descargar el GTFS vigente** del Portal de Datos Abiertos:

```bash
backend/.venv/Scripts/python data/scripts/descargar_gtfs.py
```

Si la carpeta creada en `data/raw/gtfs/` **no** es `2026-08-28`, el GTFS cambió: hay que regenerar el inventario y el escenario sintético (paso 3.6, comandos marcados "sólo si B") y es posible que algunas pruebas que dependen de rutas concretas fallen. En ese caso avísale a la persona antes de seguir.

### 3.6 Cargar los datos

Desde la raíz del repositorio, en este orden (todos son idempotentes):

```bash
# sólo si B (GTFS distinto del 2026-08-28):
backend/.venv/Scripts/python data/scripts/generar_inventario_demo.py
backend/.venv/Scripts/python data/scripts/generar_escenario_sintetico.py

# siempre:
backend/.venv/Scripts/python data/scripts/cargar_gtfs.py
backend/.venv/Scripts/python data/scripts/cargar_inventario_demo.py
backend/.venv/Scripts/python data/scripts/aplicar_escenario_demo.py flujo1 --reiniciar
```

✔ Con el GTFS 2026-08-28 se espera:
- `cargar_gtfs.py`: `{'rutas': 23, 'estaciones': 456, 'estacion_ruta': 1545, 'trazos': 53}`
- `cargar_inventario_demo.py`: `{'niveles': 3027, 'equipos': 899, 'conexiones': 3557}` (± unas cuantas conexiones)
- `aplicar_escenario_demo.py`: `evidencia para 883 equipos`

Sin el último paso todos los equipos quedan en `DESCONOCIDO` y ninguna ruta en silla de ruedas es posible (regla de seguridad 1): no es un error del motor.

En Windows, si un script imprime caracteres raros o falla con `UnicodeEncodeError`, antepón `PYTHONIOENCODING=utf-8` (bash) o `$env:PYTHONIOENCODING='utf-8'` (PowerShell).

### 3.7 Frontend

```bash
cd frontend
npm ci
npx playwright install chromium     # sólo para las pruebas e2e
cd ..
```

### 3.8 Pruebas (comprobación de que todo quedó bien)

```bash
cd backend && .venv/Scripts/python -m pytest -q && cd ..        # ✔ ~300 passed (requiere PostGIS arriba)
cd frontend && npm test && npm run lint && npx tsc -b && cd ..  # ✔ 50 passed, sin errores
cd frontend && npm run e2e && cd ..                              # ✔ 36 passed (~4 min; levanta su propio backend y preview)
```

Las pruebas e2e reinician el escenario de demostración al empezar; es normal.

### 3.9 Levantar la aplicación

Dos terminales (o procesos en segundo plano):

```bash
cd backend && .venv/Scripts/uvicorn app.main:app          # API en http://127.0.0.1:8000 (docs en /docs)
cd frontend && npm run dev                                 # PWA en http://localhost:5173
```

Versión de producción (la que se comparte):

```bash
cd frontend && npm run build && npx vite preview --host 127.0.0.1 --port 4173
```

✔ Comprobaciones:
- `curl http://127.0.0.1:8000/salud` → `{"estado":"ok","modo":"local",...}`
- En la PWA: elegir el perfil "Silla de ruedas manual" en **Mi perfil**, y en **Planear** buscar *Tasqueña → Museo de la Ciudad de México*: deben salir 3 alternativas y una ruta descartada por el elevador de Zócalo.

### 3.10 Opcionales

- **Token de moderación** (para entrar a la consola de Moderación): `backend/.venv/Scripts/python data/scripts/crear_moderador_dev.py`.
- **Compartir por internet con ngrok:** instalar ngrok, iniciar sesión (`ngrok config add-authtoken <token>` lo hace la persona, con su cuenta) y, con la API y el preview arriba, `ngrok http 4173`. La URL pública aparece en http://127.0.0.1:4040. Vite ya permite los dominios de ngrok (`frontend/vite.config.ts`).
- **GitHub CLI** para subir cambios: `gh auth login` lo hace la persona. Sube commits sólo cuando ella lo pida.

## 4. Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| Cada petición a la API tarda ~5 s | `RA_BD_URL` usa `localhost`; cámbialo a `127.0.0.1`. |
| `RA_JWT_SECRETO debe tener al menos 32 caracteres` | Falta o es corto el secreto en `.env` (paso 3.2). |
| `Estaciones no cargadas (¿falta cargar_gtfs.py?)` | Corre los scripts en el orden del paso 3.6. |
| Todas las búsquedas dicen "No hay ruta segura" | Falta `aplicar_escenario_demo.py flujo1 --reiniciar`, o la API guardó estados viejos: espera 60 s o reiníciala. |
| La API no refleja datos recién cargados | La red y la caché de estados se leen al arrancar: reinicia `uvicorn` (con `--reload` en Windows a veces no se recarga bien; mejor sin él y reiniciar a mano). |
| `npm run e2e` falla al iniciar | PostGIS no está arriba o faltan datos (pasos 3.3–3.6); `npx playwright install chromium`. |
| La voz siempre "entiende" Tasqueña → Museo de la Ciudad | Es lo esperado en modo local: no hay reconocimiento de voz real (llega en la Fase 6). El campo "O escríbelo como lo dirías" sí interpreta frases reales. |
| Docker sin memoria | En Windows, `~/.wslconfig` limitaba WSL a 2 GB en la máquina original; PostGIS necesita 512 MB. |

## 5. Estado del proyecto (25 nov 2026)

| Fase | Estado |
|---|---|
| 0–4: entorno, datos, motor de rutas, PWA, reportes y estado | ✅ |
| 4B: red completa (456 estaciones, D-25), otras opciones sin ruta segura (D-26), alternativas por penalización (D-27) | ✅ (falta la capa opcional de Voronoi, F4B-8) |
| 5: voz (D-24), en modo local | ✅ |
| 6: Google Cloud (Cloud Run, Cloud SQL, Storage, Vision, Gemini, Speech-to-Text, monitoreo) | ⏳ requiere abrir la cuenta de prueba (300 USD) |
| 7: datos y ML (historial sintético, BigQuery ML, predicción por lotes, Looker Studio) | ⏳ F7-1 se puede adelantar sin nube |
| 8: cierre (guion de demostración, capturas, entregable para el profesor) | ⏳ formato del entregable pendiente (P-01) |

El nombre del producto cambió de RutaAccesible a **M-IA** (D-28); los identificadores técnicos internos (`RA_`, base `rutaaccesible`, contenedor `ra-db`, claves `ra.*`) se conservan a propósito.

**Siguiente paso acordado:** preparar la demostración (script de arranque de un comando, guion de 5–7 minutos y capturas de respaldo) y después adelantar lo que no necesita la nube (historial sintético F7-1, preparación del despliegue de la Fase 6). Antes de empezar una fase, presenta el plan y espera aprobación (regla de `CLAUDE.md`).

## 6. Dónde leer más

- `CLAUDE.md`: reglas de trabajo, mapa del código, comandos y reglas de seguridad (léelo completo).
- `docs/decisiones.md`: decisiones D-01 a D-28 y pendientes.
- `docs/mvp-backlog.md`: historias por fase con lo hecho.
- `docs/arquitectura/`: la arquitectura completa (entregable del curso).
