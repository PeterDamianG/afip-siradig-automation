---
name: pagosafip-skill-maintenance
description: "Mantiene y mejora los skills y agentes de PagosAFIP con el estándar actual: linter propio, validador y evaluador de disparo de opencode-skill-creator, sets de evaluación y revisión de permisos. Usar cuando se crea, edita o revisa un skill o agente, o cuando una corrida real revela un fallo que hay que convertir en prueba."
---

## Principio

Un skill se mejora con evidencia, no con intuición. El ciclo es: **detectar un fallo real → convertirlo en caso de evaluación → cambiar el skill → volver a medir**. Los logs de `output/logs/` son la materia prima.

## Herramientas instaladas

- **Linter global**: `python3 ~/.config/opencode/skills/opencode-skill-lint/scripts/skill_lint.py --root .`. Funciona en cualquier proyecto. Hay una copia en `scripts/skill_lint.py` para el flujo local.
- **Linter del proyecto**: `./.venv/bin/python scripts/skill_lint.py`. Valida frontmatter, nombre, descripción, 500 líneas, rutas, referencias, YAML con `: ` y permisos de agentes.
- **opencode-skill-creator** (plugin global, `~/.config/opencode/opencode.json`): aporta `skill_validate`, `skill_eval`, `skill_optimize_loop`, `skill_aggregate_benchmark` y el visor de revisión.
- **Sets de disparo**: `evals/triggers/<skill>.json` con `[{"query": "...", "should_trigger": true|false}]`.
- **Ruteo entre skills**: `evals/routing/pagosafip.json` con el skill esperado para pedidos que cruzan dominios.
- **Arnés de ruteo**: `./.venv/bin/python scripts/routing_eval.py`. Ejecuta el pedido con el agente `pagosafip-router-eval`, lee el `tool_use` del skill y compara con el esperado. Última corrida: 5/5.
- **Casos de agente**: `evals/agents/<agente>.json`.
- **Generador**: `./.venv/bin/python scripts/generar_evals.py`.

## Flujo para crear o editar un skill

1. **Capturar la intención**: qué problema resuelve, cuándo debe dispararse y cuándo no, qué salida produce.
2. **Partir de una tarea real**: usar el transcript o los logs de una corrida. No inventar contenido genérico.
3. **Escribir el SKILL.md**: menos de 500 líneas; lo específico del proyecto, no explicaciones que el modelo ya sabe. Detalles largos a `references/`.
4. **Descripción**: tercera persona, qué hace y cuándo se usa, con límites explícitos ("No usar para…"). Citar la descripción si contiene `: `.
5. **Pasar el linter**: `scripts/skill_lint.py`. Cero errores.
6. **Pasar el validador del plugin**: `skill_validate` con el path del skill.
7. **Evaluar el disparo**: `skill_eval` con el set de `evals/triggers/`. Mover el skill instalado fuera de `.opencode/skills/` durante la prueba, porque el plugin exige que no esté visible; restaurarlo al terminar.
8. **Iterar**: si hay falsos positivos o negativos, ajustar la descripción y volver a medir. Para un ajuste fino, `skill_optimize_loop` con train/test.
9. **Documentar**: actualizar el skill, `AGENTS.md` y el set de evaluación si cambió el alcance.

## Interpretar `skill_eval`

- `trigger_rate` es la métrica principal.
- Los casos negativos que requieren ejecutar el proyecto pueden dar `errors: 1` aunque no disparen; mirar `trigger_rate: 0` y el error por separado. No confundir error de sandbox con falso positivo.
- Un caso positivo que no dispara es un problema de descripción, no del cuerpo.
- El evaluador del plugin cuenta si el nombre del skill aparece en la salida JSON, no si el modelo lo cargó. Por eso un caso negativo que menciona el dominio puede dar falso positivo. Los sets por skill usan 5 casos del dominio + 3 consultas totalmente ajenas; el ruteo entre skills se mide aparte en `evals/routing/`.
- Resultado de la última corrida (2026-10-21): 8/8 en los 8 skills del proyecto. `skill_optimize_loop` sobre pdf-intake: 5/5 train y 3/3 test, sin cambios necesarios.
- Guardar las descripciones que funcionan con `skill_add_gold_standard`.

## Flujo para crear o editar un agente

1. Un agente, un trabajo. Si necesita dos roles, separar en subagentes.
2. `mode`: `primary` para el que lleva la sesión; `subagent` para verificadores y especialistas.
3. `steps`: límite explícito para evitar bucles (40 para el orquestador, 15 para el verificador).
4. Permisos de mínimo privilegio: `shell` amplio en `ask`, allow sólo para los scripts del proyecto, deny para `rm`, envío y lectura de `credenciales.env`.
5. Maker-checker: el que ejecuta no es el que verifica. Antes de una acción irreversible, invocar el subagente verificador y exigir `VEREDICTO: OK`.
6. Contrato de salida: `ESTADO: LISTO | PENDIENTE | BLOQUEADO`, qué se hizo, qué se verificó y próximo paso.
7. Casos de comportamiento en `evals/agents/`: rechazar envío sin aprobación, no leer credenciales, no cargar `revisar` sin confirmación, no enviar con tope, no reintentar en bucle.
8. Revisar los cambios de prompt y permisos como código: son los que más cambian el comportamiento.

## Alquiler

El skill `pagosafip-alquiler` y el subagente `pagosafip-alquiler-especialista` tienen su propio control en `output/alquiler/control.json` (hash SHA-256 por contrato, meses, facturas y `registro_id`). El OCR tiene caché en `output/alquiler/ocr_index.json`; si el hash no cambió, no se vuelve a OCR. Los scripts son `alquiler_ocr.py`, `alquiler_actualizar.py`, `alquiler_cargar.py`, `alquiler_verificar.py`, `alquiler_marcar_enviado.py` y `alquiler_historial.py`. La evaluación de disparo está en `evals/triggers/pagosafip-alquiler.json` (8/8) y el ruteo incluye alquiler y actualización mensual (8/8). Los pedidos mixtos (facturas + alquileres) se resuelven en una sola rectificativa.

## Reglas de oro

- Si un skill supera las 500 líneas, dividirlo con referencias de un solo nivel.
- Si un caso falla dos veces en producción, agregarlo a `evals/` antes de tocar el skill.
- No agregar un skill nuevo si el problema se resuelve con una sección del existente.
- No agregar un subagente si el orquestador puede hacerlo con un script determinista.
- Las descripciones son la interfaz de descubrimiento: invertir tiempo ahí, no en el cuerpo.
- Versionar los cambios importantes en `output/logs/` o en el historial del proyecto.
