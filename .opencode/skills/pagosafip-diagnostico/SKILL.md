---
name: pagosafip-diagnostico
description: "Guía de diagnóstico cuando algo falla en PagosAFIP (login, carga, quitar comprobantes, extracción, conciliación, Vista Previa, tope o envío). Síntoma, causa probable, acción y qué decirle al usuario. Usar siempre que un paso falle o dé un resultado inesperado."
---

## Regla general

1. Parar. No reintentar en bucle.
2. Mirar el registro: `./.venv/bin/python scripts/registro.py ver --nivel error --ultimos 20`.
3. Identificar el síntoma en la tabla.
4. Explicar al usuario en lenguaje simple: qué pasó, qué se hizo y qué no.
5. Si hay riesgo de duplicar o de enviar, pedir confirmación antes de tocar nada.

Nunca mostrar claves, tokens, cookies ni `credenciales.env`.

## Síntomas y acciones

| Síntoma | Causa probable | Acción |
|---|---|---|
| Login HTTP falla o "No se encontró el jwt" | Clave rotada, captcha o bloqueo temporal | Pedir confirmar la clave en `credenciales.env` (sin mostrarla). Si hay captcha, usar navegador visible. No reintentar seguido. |
| Respuesta con página de login o "expiredSession" | Sesión vencida | Repetir `sesion_http()` una vez. |
| POST guardar: "Ya existen Gastos registrados para esta CUIT, mes y concepto" | Alta nueva sobre gasto existente | No es error de datos. Enviar con `codigo` = `idReg` existente. |
| POST guardar: "cmp_fila_agregada0: fecha/tipo/monto" | Se mandó `comprobanteIdFilaAgregada` sin datos | Es para agregar: mandar todos los campos del comprobante. Para quitar, no mandar `comprobanteIdFilaAgregada`. |
| `"estado":"error"` con otro campo | Dato no aceptado por AFIP | Detener. Mostrar el mensaje completo. No reintentar sin entender. |
| `extraer` deja comprobantes en `revisar` | Proveedor nuevo, sin CUIT del vendedor, monto ambiguo, año distinto | Leer el PDF como imagen. Confirmar con el usuario. Cargar en `confirmados_manual.json` con `_origen`. Sin CUIT del vendedor: no cargar y pedirlo. |
| Un total sale igual al subtotal | Total leído de la fila de abajo | Ver "Totales" en `pagosafip-pdf-intake`. Corregir o confirmar a mano. |
| Un número de comprobante sale como 14 dígitos o el CAE | El texto mezcla CAE y número | Revisar el PDF y cargar a mano en `confirmados_manual.json`. |
| `conciliar`: "Faltan en AFIP" | Carga incompleta | `cargar` otra vez (idempotente) y luego `conciliar`. |
| `conciliar`: "Monto distinto" | Monto mal convertido | Corregir quitando el comprobante y cargando el correcto (ver `pagosafip-siradig-http`). Pedir aprobación. |
| `revision`: "La Vista Previa no coincide" | Gastos cargados fuera del lote | DETENER. Revisar `siradig_verificar.py` con el usuario. |
| Vista Previa muestra "supera el monto tope" | Total por encima del tope de carga directa | No enviar. Medir con `tope_medir.py`. Ofrecer: trámite "Consulta carga no automática" o quitar comprobantes con aprobación. |
| `enviar` aborta por total distinto | El total aprobado no es el de la Vista Previa | No enviar. Volver a pedir aprobación con el total correcto. |
| Envío dice 200 pero no aparece en el listado | El listado tarda o no trae el período | Verificar con `siradig_revisar_enviados.py` (navegador). No reenviar sin verificar. |
| Listado de enviados vacío por HTTP | El listado HTTP no trae el período seleccionado | Usar el navegador, no HTTP. |
| "Deducción de Alquiler de Inmuebles inválida o inexistente" | El registro ya fue enviado o no existe en el borrador | No reintentar. Validar con `alquiler_verificar.py` y el PDF histórico. |
| El OCR no lee el contrato de alquiler | Escaneo de baja calidad, girado o con letra manuscrita | Probar 300 DPI y `--psm 6`; si sigue, leer visualmente y cargar a mano en el control. |
| `noTitular` | El usuario es titular de un inmueble | No tildar. Consultar al contador; si insiste, cargar por HTTP y registrar la nota. |
| MCP `playwright` no conecta | Bun o configuración | `opencode mcp list`. Los scripts Python no lo necesitan. |
| Timeout o pantalla que no carga | Sitio lento o sesión caída | Esperar y reintentar una vez. Si cambió la pantalla, `volcar_arbol` y revisar selectores. |

## Envío: la acción irreversible

Antes de cualquier reintento:
1. Mirar el listado de presentaciones enviadas (navegador). Si hay una presentación nueva de hoy, el envío ya ocurrió. NO reenviar.
2. Medir el tope y verificar que la Vista Previa tiene el total aprobado.
3. Con ambas verificaciones y aprobación explícita con el total, enviar con `pipeline.py enviar <total>`.

## Qué decirle al usuario

- Lenguaje simple. Qué pasó, qué se hizo, qué NO se hizo.
- Si algo no se puede confirmar, decirlo y dar la forma de verificarlo en pantalla.
- Nunca decir que algo está hecho si no se verificó.
