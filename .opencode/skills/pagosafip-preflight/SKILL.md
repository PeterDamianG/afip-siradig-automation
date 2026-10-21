---
name: pagosafip-preflight
description: "Verifica que el entorno de PagosAFIP está listo (Python 3.12 del venv, dependencias, credenciales presentes sin mostrarlas, carpeta FACTURAS, pruebas de montos y login HTTP). Usar al inicio de cada sesión de trabajo y antes de cargar."
---

## Comando

```
./.venv/bin/python scripts/pipeline.py preflight --sin-login
```

Usar `--sin-login` para revisar el entorno sin entrar a AFIP. Quitar la opción sólo antes de cargar o revisar, porque cada login cuenta para los bloqueos de AFIP.

Resultado: `PREFLIGHT: OK` o `BLOQUEADO`, con la lista de problemas. Queda registrado en `output/estado.json`.

## Qué revisa

1. `.venv` existe y tiene `playwright` y `pdfplumber`.
2. `credenciales.env` existe y tiene `AFIP_URL`, `AFIP_USUARIO`, `AFIP_PASSWORD`. No muestra los valores.
3. La carpeta `FACTURAS/` existe.
4. `scripts/test_montos.py` pasa (conversión de montos y CUIT).
5. Con login: entra a AFIP por HTTP y lee la lista de gastos. Sólo si no se usa `--sin-login`.

## Si está BLOQUEADO

- `.venv` o módulos faltantes: `python3.12 -m venv .venv`, luego `pip install -r requirements.txt`, luego `playwright install chromium`.
- OCR faltante: `brew install tesseract tesseract-lang poppler` y `pip install -r requirements.txt`.
- `credenciales.env` incompleto: pedir al usuario que lo complete. No pedir la clave en el chat.
- Pruebas de montos fallidas: no cargar. Revisar `scripts/montos.py`.
- Login fallido: ver `pagosafip-diagnostico`.

## Herramientas del entorno (informativo)

- Bun 1.3.10 (para el MCP de Playwright).
- Node v26 (respaldo).
- Python 3.12 (`/opt/homebrew/opt/python@3.12/bin/python3.12`).
