# PagosAFIP — instrucciones del proyecto

Automatización para cargar facturas de servicios y equipamiento en SiRADIG (Ganancias, deducción de Indumentaria y Equipamiento) y enviar el formulario al empleador.

## Reglas

- Hablar en español rioplatense, claro y sin jerga.
- **HTTP primero.** El navegador es respaldo (`pagosafip-playwright`).
- **Nunca leer ni mostrar `credenciales.env`** ni claves, tokens o cookies.
- **Nunca enviar el formulario sin aprobación explícita del usuario con el total exacto.**
- Cargar sólo comprobantes en estado `listo`.
- Ante un error, mirar `output/logs/` antes de reintentar. Máximo 2 reintentos del mismo paso.
- No afirmar que algo está hecho sin verificarlo con la conciliación.

## Frases típicas del usuario

- “Estamos en <mes>, actualizá los alquileres” → `alquiler_actualizar.py --hasta YYYY-MM`, `alquiler_cargar.py`, `alquiler_verificar.py`, revisión, tope, aprobación, envío.
- “Tengo más facturas en la carpeta, cargalas” → `pipeline.py extraer`, `cargar`, `conciliar`.
- Las dos cosas juntas → hacer ambas y enviar **una sola** rectificativa con el total combinado.
- El agente ejecuta los scripts; el usuario no corre comandos. El navegador es sólo para el envío final o si el HTTP falla.
- Si el total no cambió respecto de la última presentación y no hay meses/comprobantes nuevos, no enviar: informar “sin cambios”.

## Flujo

```
./.venv/bin/python scripts/pipeline.py preflight --sin-login
./.venv/bin/python scripts/test_montos.py
./.venv/bin/python scripts/pipeline.py extraer
./.venv/bin/python scripts/pipeline.py cargar
./.venv/bin/python scripts/pipeline.py conciliar
./.venv/bin/python scripts/pipeline.py revision
./.venv/bin/python scripts/tope_medir.py
./.venv/bin/python scripts/pipeline.py enviar <total aprobado>
```

## Skills

Preflight, PDF intake, SiRADIG HTTP, Playwright, validator, revisión final, diagnóstico, observabilidad, alquiler y mantenimiento de skills están en `.opencode/skills/`.

## Agentes

- `pagosafip-orquestador`: agente principal.
- `pagosafip-verificador`: subagente de solo lectura, obligatorio antes de enviar (maker-checker).
- `pagosafip-alquiler-especialista`: subagente para cargar y verificar alquileres; no envía.

## Ruteo de tareas

- Extraer o revisar PDFs: `pagosafip-pdf-intake`.
- Cargar, corregir o quitar comprobantes: `pagosafip-siradig-http`.
- Enviar el formulario o armar la revisión final: `pagosafip-revision-final`.
- Cargar alquileres de `ALQUILER/`: `pagosafip-alquiler` (subagente especialista).
- Falló algo: `pagosafip-diagnostico`.
- Revisar qué pasó: `pagosafip-observabilidad`.

## Evaluaciones y calidad

- Linter: `./.venv/bin/python scripts/skill_lint.py`.
- Sets de disparo: `evals/triggers/*.json`.
- Ruteo real: `./.venv/bin/python scripts/routing_eval.py`.
- Alquiler: `./.venv/bin/python scripts/alquiler_verificar.py` y `alquiler_historial.py --open`.
- Casos de comportamiento del agente: `evals/agents/pagosafip-orquestador.json`.
- Plugin global `opencode-skill-creator`: validar, evaluar y optimizar descripciones.
- Flujo completo en el skill `pagosafip-skill-maintenance`.

## Estado

`output/estado.json` (pasos), `output/logs/` (eventos), `output/revision_final.md` (informe), `output/envio.json` (último envío).
