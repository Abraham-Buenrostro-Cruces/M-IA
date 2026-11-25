# M-IA

Plataforma web y móvil de planificación de viajes en transporte público de la Ciudad de México que **prioriza la accesibilidad sobre la rapidez**, pensada para personas con movilidad reducida y, en particular, usuarias de silla de ruedas.

Proyecto del curso de cómputo en la nube — especialización Data, Machine Learning e IA en Google Cloud.

## Estado

| Etapa | Estado |
|---|---|
| Arquitectura | ✅ Definida (24 nov 2026) |
| MVP | 🚧 Fases 0–4 terminadas (datos, motor de rutas, PWA, reportes y estado en local); sigue Fase 5 (voz) — ver [backlog](docs/mvp-backlog.md) |
| Entregable final | ⏳ Formato por decidir |

## Documentación

Empieza por el [índice de la arquitectura](docs/arquitectura/00-indice.md).

- [Resumen, problema y propuesta de valor](docs/arquitectura/01-resumen-y-propuesta.md)
- [Arquitectura general, diagrama y componentes](docs/arquitectura/02-arquitectura-general.md)
- [Datos y entidades](docs/arquitectura/03-datos.md)
- [Data, ML e IA](docs/arquitectura/04-data-ml-ia.md)
- [Servicios de Google Cloud](docs/arquitectura/05-servicios-gcp.md)
- [Flujos principales](docs/arquitectura/06-flujos.md)
- [Seguridad y escalabilidad](docs/arquitectura/07-seguridad-escalabilidad.md)
- [MVP y tecnologías](docs/arquitectura/08-mvp-y-tecnologias.md)
- [Riesgos y evolución](docs/arquitectura/09-riesgos-y-evolucion.md)
- [Decisiones de arquitectura](docs/decisiones.md) · [Fuentes](docs/fuentes.md)

Los diagramas están en Mermaid y se ven directamente en GitHub, VS Code (con la extensión de vista previa de Mermaid) u Obsidian.

## Desarrollo local

Requisitos: Python 3.12, Node.js LTS, Docker Desktop y Git.

```bash
cp .env.example .env                 # y cambia la contraseña
docker compose up -d                 # PostGIS
cd backend && py -3.12 -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]" && .venv/Scripts/uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

Por defecto `RA_MODO=local`: todos los servicios de nube se sustituyen por adaptadores simulados.
