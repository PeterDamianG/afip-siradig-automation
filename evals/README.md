# Evaluaciones de skills y agentes

## Qué hay

- `triggers/<skill>.json`: casos de disparo. Formato del plugin `opencode-skill-creator`:
  `[{"query": "...", "should_trigger": true|false}]`.
- `triggers/<skill>-regression.json`: set reducido para verificar un cambio puntual.
- `agents/<agente>.json`: casos de comportamiento (qué debe y qué no debe hacer un agente).

## Ruteo real (arnés)

```sh
./.venv/bin/python scripts/routing_eval.py
```

Ejecuta cada pedido con el agente `pagosafip-router-eval` (solo puede cargar
skills, no ejecutar acciones), lee del stream JSON el evento `tool_use` con
`tool: "skill"` y compara el ID cargado con `expected_skill`. No infiere por
menciones. Resultado de la última corrida: **5/5**.

## Cómo se corren

Con las herramientas del plugin global `opencode-skill-creator`:

1. `skill_validate({ skillPath })` — estructura y frontmatter.
2. `skill_eval({ skillPath, evalSetPath, runsPerQuery, numWorkers })` — disparo.
3. `skill_optimize_loop({ skillPath, evalSetPath })` — optimización de la descripción con train/test.

El plugin exige que el skill evaluado **no esté instalado y visible** en `.opencode/skills/`, porque crea un skill sintético con el mismo nombre base. Procedimiento:

```sh
mv .opencode/skills/<skill> /tmp/skill-eval-<skill>
# correr skill_eval con skillPath=/tmp/skill-eval-<skill>
mv /tmp/skill-eval-<skill> .opencode/skills/<skill>
```

Restaurar siempre, incluso si la evaluación falla.

## Cómo interpretar

- `trigger_rate` es la métrica principal. 1 = el skill se activó; 0 = no.
- El evaluador cuenta si el nombre del skill aparece en la salida JSON, no si el modelo lo cargó. Un caso negativo que menciona el dominio puede dar falso positivo. Por eso los sets por skill usan 5 casos del dominio + 3 consultas totalmente ajenas; el ruteo entre skills se mide aparte en `evals/routing/`.
- En un ecosistema con varios skills, un pedido puede activar el skill “equivocado” y aun así terminar bien porque el agente sigue el flujo.
- Los casos negativos que requieren ejecutar el proyecto pueden dar `errors: 1` aunque no disparen. Mirar `trigger_rate: 0` y el error por separado; no confundir error de sandbox con falso positivo.
- Un caso positivo que no dispara es un problema de descripción. Ajustar la descripción, no el cuerpo.
- Guardar descripciones que funcionan con `skill_add_gold_standard`.

## Regla del proyecto

Cada vez que una corrida real falle, agregar el caso a `evals/` antes de tocar el skill. La evaluación queda como evidencia y evita la regresión.

## Comandos de calidad

```sh
./.venv/bin/python scripts/skill_lint.py
./.venv/bin/python scripts/generar_evals.py
```


## Última corrida

- 8 skills del proyecto: **8/8 cada uno** (2026-10-21).
- `skill_optimize_loop` sobre `pagosafip-pdf-intake`: **5/5 train, 3/3 test**, sin cambios.
- Ruteo entre skills: `evals/routing/pagosafip.json` (documentado, no automatizado por el plugin).
