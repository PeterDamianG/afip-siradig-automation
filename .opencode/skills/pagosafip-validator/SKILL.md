---
name: pagosafip-validator
description: "Valida que los comprobantes listos estén cargados en SiRADIG con el monto correcto y sin duplicados, que cada gasto cierre con la suma de sus comprobantes, y que lo que no está en el lote esté identificado como preexistente. Usar después de cada carga y antes de la revisión final."
---

## Objetivo

Confirmar el estado real en AFIP. Que el script terminó sin error no alcanza.

## Comandos

- `./.venv/bin/python scripts/siradig_conciliar.py` (o `pipeline.py conciliar`): compara `output/facturas.json` (estado `listo`) contra AFIP. Código 0 si todo cuadra.
- `./.venv/bin/python scripts/siradig_verificar.py`: lista todos los gastos de AFIP con sus comprobantes.
- `./.venv/bin/python scripts/tope_medir.py`: mide el tope de carga directa sin enviar.
- `./.venv/bin/python scripts/alquiler_verificar.py`: control de alquiler vs. AFIP; los enviados se validan contra control/PDF.

## Checks

1. **Conciliación**: faltantes y montos distintos deben ser "ninguno".
2. **Totales**: el total de cada gasto (CUIT + mes + Equipamiento) igual a la suma de sus comprobantes.
3. **Sin duplicados**: un mismo (CUIT, punto de venta, número) no aparece dos veces en AFIP.
4. **Preexistentes**: los comprobantes de AFIP que no fueron cargados por la automatización están en `output/preexistentes.json`. Cualquier otro comprobante en AFIP cuenta como cargado por la automatización.
5. **Excluidos**: lo que el usuario decidió no cargar figura en el informe con su motivo, y no está en AFIP.
6. **Tope**: la Vista Previa no está bloqueada por tope.
7. **Estado del proceso**: `output/estado.json` y `output/logs/`.

## Reglas de AFIP (verificadas)

- Un solo gasto por CUIT + mes + concepto. Los comprobantes nuevos se agregan con `codigo`.
- `montoTotal` debe ser la suma del total del gasto después de la operación.
- Para corregir: quitar el comprobante (`comprobantesEliminados`) y, si corresponde, agregar el correcto.

## Salida

Reportar cada check como OK, FALLA o PENDIENTE. Si hay FALLA, no seguir: diagnosticar con `pagosafip-diagnostico`.
