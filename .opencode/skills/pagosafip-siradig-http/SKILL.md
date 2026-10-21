---
name: pagosafip-siradig-http
description: "Contrato HTTP de SiRADIG para cargar, corregir y quitar comprobantes de Indumentaria y Equipamiento, leer la Vista Previa y medir el tope de carga directa. Usar para altas, correcciones y consultas por HTTP. No usar para extraer PDFs ni para el cierre final: ese paso es de pagosafip-revision-final."
---

## Principio

HTTP primero. El navegador (skill `pagosafip-playwright`) es respaldo. Sólo el envío final y la lista de presentaciones enviadas se hacen con navegador (ver abajo por qué).

## Módulos

- `scripts/afip_http.py`: `sesion_http()` (login y SSO a SiRADIG, devuelve cliente con cookies), `RADIG`.
- `scripts/siradig_http.py`: `gastos_servidor`, `comprobantes_de_gasto`, `enviar_gasto`, `razon_social`, `listar_menu`.
- `scripts/siradig_cargar_lote.py`: carga los `listo` de `output/facturas.json`.
- `scripts/siradig_conciliar.py`: compara lo listo contra AFIP.
- `scripts/tope_medir.py`: mide si la Vista Previa está bloqueada por tope, sin enviar.
- `scripts/revision_final.py`: informe de la Vista Previa (sólo lectura).

## Login y sesión (verificado)

1. GET `AFIP_URL` → formulario `F1` y `javax.faces.ViewState`.
2. POST al `action` con `F1=F1`, `F1:username`, `F1:btnSiguiente=Siguiente`, `ViewState`.
3. POST con `F1:captcha=""`, `F1:username`, `F1:password`, `F1:btnIngresar=Ingresar`, `ViewState` nuevo.
4. Respuesta con formulario `jwt` → POST a `portalcf.cloud.afip.gob.ar/portal/login`.
5. GET `portal/api/servicios/<CUIT>/servicio/radig/autorizacion` → `token` y `sign`.
6. POST `serviciosjava2.afip.gob.ar/radig/jsp/index.jsp` con `token` y `sign`.
7. GET `setearContribuyente.do?idContribuyente=0` y `determinarContribuyente.do?codigo=2026`.

AFIP bloquea tras varios intentos fallidos. No reintentar seguido con la misma clave.

## Endpoints

| Acción | Método y URL | Notas |
|---|---|---|
| Lista de gastos | GET `verMenuDeducciones.do` | JSON `datosDeduccionesAgrupadasJSON` con `idReg` y `celdas` |
| Formulario de un gasto | GET `verGastosInduEquip.do?id=<idReg>` | JSON `datosFormComprobantes`: `codigo`, `puntoVenta`, `numero`, `montoFacturado` |
| Guardar (alta, edición, quitar) | POST `guardarGastosInduEquip.do` | form-urlencoded. Respuesta `{"estado":"ok"}` o `{"estado":"error","camposErrores":...}` |
| Razón social | GET `ajax.do?f=razonsocialcuitocuitpais&cuit=...` | JSON `datos.razonSocial` |
| Vista Previa | GET `vistaPreviaFormulario.do` | Total en "Importe Total: $". Si está bloqueada, el HTML contiene "supera el monto tope" (se ve antes de cualquier clic) |
| Presentaciones enviadas | GET `verFormulariosEnviados.do` | **No confiable por HTTP** (ver abajo) |

Respuestas en ISO-8859-1.

## Campos del POST

- `numeroDoc`: CUIT del proveedor. `razonSocial`: denominación.
- `idConcepto`: 1 = Indumentaria, 2 = Equipamiento (el usuario usa 2).
- `mesDesde`: mes de emisión (1-12).
- `montoTotal`: total del gasto después de la operación.
- `codigo`: vacío para gasto nuevo; `idReg` del gasto existente para sumar, editar o quitar.
- Comprobante nuevo: `comprobanteIdFilaAgregada`, `comprobanteFechaEmision` (dd/mm/aaaa), `comprobanteTipo`, `comprobantePuntoVenta` (5 dígitos), `comprobanteNumero` (8), `comprobanteNumeroAlternativo`, `comprobanteMontoFacturado`.
- `comprobantesEliminados`: códigos a quitar, separados por `;`.

## Tipos de comprobante (`comprobanteTipo`)

- `1` Factura A · `6` Factura B · `11` Factura C
- `10` Nota de Venta al contado B (notas de venta "NOTA CONTADO")
- `40` Otro comprobante B (RG 1415). Liquidaciones de servicios públicos (el formulario no tiene "Liquidación B").

## Reglas verificadas

- Un solo gasto por CUIT + mes + concepto. Alta nueva sobre un gasto existente da "Ya existen Gastos registrados…": usar `codigo`.
- **Agregar** un comprobante: `comprobanteIdFilaAgregada=0` más todos los campos del comprobante. Si se manda `comprobanteIdFilaAgregada` sin datos, da `cmp_fila_agregada0: fecha inválida / tipo inválido / Monto obligatorio`.
- **Quitar** un comprobante: POST con `codigo` (gasto), `comprobantesEliminados` (código del comprobante), `montoTotal` nuevo, y **sin** `comprobanteIdFilaAgregada` ni campos de comprobante. Probado quitando un comprobante de un gasto existente.
- Para corregir un monto: quitar el comprobante y agregar el correcto en el mismo POST.
- La fecha del comprobante debe caer en el mes del gasto, o en el anterior o siguiente.
- El `montoTotal` que se envía es el total del gasto después de la operación. Si no coincide con la suma de comprobantes, el listado queda inconsistente.

## Tope de carga directa (verificado)

- Si el total del rubro supera el tope, la Vista Previa muestra: *"El monto informado en el rubro 'Gastos de indumentaria y equipamiento…' supera el monto tope para su carga directa… deberás realizar una Presentación Digital – trámite 'SIRADIG – Consulta carga no automática'… adjuntando la documentación de respaldo."* y no se puede enviar.
- Límite: se midió en una prueba real que el formulario acepta un total y bloquea otro mayor; el tope está entre ambos. No asumir un número fijo. Medir siempre con `scripts/tope_medir.py` antes de enviar.
- Medir sin enviar: `./.venv/bin/python scripts/tope_medir.py`.

## Presentaciones enviadas: sólo con navegador

- `verFormulariosEnviados.do` por HTTP vuelve vacío: no trae el período seleccionado en el navegador.
- Para verificar envíos: `./.venv/bin/python scripts/siradig_revisar_enviados.py` (solo lectura, navegador).

## Qué no hacer

- No llamar `generacion_presentacion.jsp` ni usar el envío sin aprobación explícita con el total.
- No leer ni mostrar `credenciales.env`. Los módulos la leen internamente.
- No guardar cookies, tokens, `sign` ni claves en `output/`. El registro de red y los logs los redactan.
