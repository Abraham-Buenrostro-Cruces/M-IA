# ⚠️ Datos SINTÉTICOS — no describen el estado real de ningún equipo

| Archivo | Contenido |
|---|---|
| `escenario_red.csv` | Estado buscado para cada equipo de la red (F4B-4). Lo genera `data/scripts/generar_escenario_sintetico.py` con semilla fija; no se edita a mano. |

`aplicar_escenario_demo.py` lo carga como base y aplica encima `data/demo/escenarios/flujo1.csv`.
No escribe estados: crea la evidencia que el estimador convierte en estado (D-21):

| Estado buscado | Evidencia sintética | Proporción |
|---|---|---:|
| OPERATIVO | aviso DEMO de operación | 85 % |
| FALLA_PROBABLE | reporte sin foto ni persona, marcado "Reporte SINTÉTICO de demostración" | 7 % |
| FALLA_CONFIRMADA | aviso DEMO de falla | 4 % |
| MANTENIMIENTO | aviso DEMO de mantenimiento | 2 % |
| DESCONOCIDO | ninguna | 2 % |

Las estaciones de las líneas 2 y 3 del Metro quedan operativas: sus estados los fija `flujo1`,
del que dependen la demostración y las pruebas e2e. Las proporciones son un supuesto, no una
medición (ver `backend/app/ingesta/escenario_sintetico.py`).
