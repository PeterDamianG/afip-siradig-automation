---
name: pagosafip-observabilidad
description: "Registro de lo que hace el proceso (logs JSON por línea en output/logs). Usar para revisar qué pasó en una corrida, investigar un error, o mejorar el agente y los skills a partir de lo que sucedió."
---

## Dónde

- `output/logs/AAAA-MM-DD.jsonl`: un JSON por línea. Un archivo por día.
- Cada línea: `ts` (fecha y hora), `sesion` (id de la corrida), `paso`, `nivel` (info | warn | error), `evento`, `detalle`.
- Los campos con claves, tokens, cookies o firmas se redactan automáticamente.

## Cómo leer

```
./.venv/bin/python scripts/registro.py resumen                  # conteo por paso y evento de hoy
./.venv/bin/python scripts/registro.py ver --nivel error        # errores y avisos
./.venv/bin/python scripts/registro.py ver --ultimos 60         # lo último que pasó
./.venv/bin/python scripts/registro.py ver --fecha 2026-10-14   # un día concreto
```

Para revisar una corrida puntual, buscar por `sesion` en el archivo `.jsonl`.

## Eventos que se registran

| Paso | Evento | Qué significa |
|---|---|---|
| pipeline | paso_iniciado / paso_terminado | Cada paso del pipeline, con resultado |
| login | sesion_ok / login_fallido | Entrada a AFIP por HTTP |
| extraer | comprobante_no_listo | Un PDF que no quedó `listo`, con sus motivos |
| extraer | resumen | Conteo de estados de la extracción |
| cargar | comprobante | Carga de un comprobante (cargado o error, con código HTTP) |
| cargar | omitido | Ya estaba en AFIP |
| conciliar | resultado | Faltantes y montos distintos |
| revision | informe | Total de la Vista Previa y cantidad de marcas |
| tope | medicion / limite_acotado | Si la Vista Previa está bloqueada por tope, y el rango medido |
| envio | total_verificado / confirmacion_enviada / enviado / abortado_total_distinto / bloqueado_por_tope | Cada paso del envío |

## Cómo usarlo para mejorar

1. Ante un error, leer primero `registro.py ver --nivel error` antes de tocar código.
2. Si un proveedor cae siempre en `revisar` con el mismo motivo, agregar su regla en `scripts/proveedores.py` y anotarlo en el skill `pagosafip-pdf-intake`.
3. Si un login falla repetido, anotar la causa en `pagosafip-diagnostico` (síntoma → causa → acción).
4. Si una respuesta de AFIP tiene un mensaje nuevo, agregarlo a la tabla de `pagosafip-diagnostico`.

## Reglas

- No borrar los logs salvo pedido del usuario. Son el historial.
- Nunca copiar claves ni tokens a un log a mano.
- Los logs son locales (`output/`) y no se envían a ningún lado.
