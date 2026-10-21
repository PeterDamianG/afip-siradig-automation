# Seguridad y datos personales

## Regla principal

Este repositorio es público. **No debe contener datos personales, fiscales ni credenciales.**

Nunca se suben:

- `FACTURAS/` (facturas, CUITs, nombres, direcciones, importes).
- `ALQUILER/` (contratos, locadores, direcciones, importes).
- `PRESENTACIONES/` (declaraciones juradas y PDFs de AFIP).
- `output/` (JSON, logs, evidencia, control, capturas, red).
- `credenciales.env`, `.env`, tokens, cookies o claves.
- `.playwright-mcp/` (snapshots de páginas y logs del navegador).
- Cualquier PDF, log o archivo `.jsonl`.

`.gitignore` bloquea esas rutas. Antes de cada push, revisar:

```sh
git status --short
git diff --cached --stat
git grep -n -E "TU_CUIT|TU_CLAVE|password|token|cookie" --cached
```

## Credenciales

- Viven en `credenciales.env`, con permisos `600`, fuera de Git.
- Los scripts las leen por dentro; nunca las imprimen.
- El registro de red y los logs redactan claves, tokens, cookies, `sign` y `ViewState`.
- Si una credencial se filtra, rotarla de inmediato.

## Datos de facturas y contratos

- Se procesan localmente en `FACTURAS/`, `ALQUILER/` y `output/`.
- El repositorio sólo incluye código y plantillas con datos ficticios.
- Los ejemplos del README usan CUITs e importes inventados.

## Terceros

El proyecto puede usar el plugin **opcional** `opencode-skill-creator` para validar y evaluar skills. Por defecto queda desactivado; se activa sólo para evaluar y se limpia con `scripts/limpiar_eval_sessions.py`.
Es código de terceros con acceso a procesos y a las variables de entorno del usuario.
Recomendaciones:

- Fijar la versión (`opencode-skill-creator@0.3.6`).
- Revisar el changelog antes de actualizar.
- No evaluar skills de terceros no revisados.
- El visor de evaluación carga fuentes de Google en el HTML; no envía datos del proyecto.

## Reportar un problema

Si encontrás una vulnerabilidad, no abras un issue público con datos sensibles. Describí el
problema de forma general y coordiná un canal privado con el mantenedor.
