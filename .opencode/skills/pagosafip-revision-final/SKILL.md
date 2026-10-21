---
name: pagosafip-revision-final
description: "Última validación humana y envío del formulario SiRADIG. Genera el informe (solo lectura), mide el tope de carga directa, pide aprobación con el total exacto y envía por navegador sólo si el total coincide. Nunca enviar sin aprobación explícita con el total. Usar cuando el usuario pide revisar, aprobar o enviar el formulario."
---

## Regla principal

**Nunca enviar sin una aprobación explícita del usuario en el mismo turno, con el total exacto y cada marca de revisión confirmada.** El envío no tiene vuelta atrás. Cada envío genera una presentación nueva (Original la primera vez, después Rectificativa N).

## Pasos

1. Conciliar: `./.venv/bin/python scripts/pipeline.py conciliar`. Debe dar 0 faltantes y 0 montos distintos.
   Si hay `ALQUILER/`, correr también `./.venv/bin/python scripts/alquiler_verificar.py`.
2. Informe: `./.venv/bin/python scripts/pipeline.py revision`. Escribe `output/revision_final.md`. Sólo lectura.
3. Medir tope: `./.venv/bin/python scripts/tope_medir.py`. Si dice BLOQUEADO, no seguir: informar y ofrecer el trámite "Consulta carga no automática" o quitar comprobantes con aprobación.
4. Mostrar al usuario: total de la Vista Previa, cruce (cargado por la automatización + preexistente), marcas, y el tope medido.
5. Pedir aprobación. No enviar en este paso.

## Qué mostrar

- Total con centavos, cantidad de comprobantes cargados por la automatización, y los 4 preexistentes.
- Marcas: montos individuales altos (> 1.000.000), comprobantes leídos visualmente (con su `_origen`), excluidos (con motivo), preexistentes.
- Lo que NO está en el envío (por ejemplo, un comprobante quitado por tope), con su número y monto.
- Estado del tope.

## Aprobación

- La aprobación nombra el total exacto y confirma las marcas. Ejemplo: "Acepto enviar por $ 1.234.567,89, sin el comprobante excluido, y confirmo las marcas".
- Un "ok" general no alcanza si hay marcas abiertas. Pedir confirmación de cada una.
- Si el usuario cambia el total, volver a los pasos 1 a 4 con el nuevo total.

## Guardia de duplicados

Si el total de la Vista Previa es igual al `ultimo_envio.total` de `output/envio.json` y no hay meses ni comprobantes nuevos, **no enviar**. Informar “sin cambios” y no generar una rectificativa idéntica. El script de envío ya lo bloquea; para forzar un reenvío excepcional, `FORZAR_ENVIO=1`.

## Envío (sólo tras aprobación)

Comando:

```
./.venv/bin/python scripts/pipeline.py enviar <total aprobado, ej: 1.234.567,89>
```

El paso hace, en orden:
1. Mide el tope. Si está bloqueado, no envía.
2. Abre la Vista Previa por navegador y compara el total con el aprobado. Si no coincide, aborta sin hacer clic.
3. Hace clic en "Enviar al Empleador…", y después en "Generar Presentación".
4. Registra el evento en `output/logs/`.

Después del envío:
- Verificar la confirmación en pantalla ("Presentación generada y puesta a disposición de su empleador").
- Verificar el número de presentación en `scripts/siradig_revisar_enviados.py` (navegador; el listado por HTTP viene vacío).
- Actualizar `output/envio.json` con el número, el total y lo excluido.

## Resultado histórico

- El proyecto ya envió presentaciones originales y rectificativas en pruebas reales. Este repositorio público no incluye números, fechas ni importes de esas presentaciones.

## Alquiler

- El total de la Vista Previa incluye equipamiento + alquiler. No comparar sólo contra equipamiento.
- Los registros de alquiler enviados no son editables: el error “Deducción de Alquiler de Inmuebles inválida o inexistente” significa que ya se enviaron, no que se perdieron.

## Tope

No hay un límite fijo conocido: medir con `scripts/tope_medir.py` antes de enviar. Si bloquea, ofrecer el trámite de carga no automática o quitar comprobantes con aprobación del usuario.
