---
name: pagosafip-alquiler
description: "Carga la deducción de alquiler de casa habitación (Beneficio 40%, Art. 85 inc. h) en SiRADIG desde los contratos de ALQUILER/. Lee contratos escaneados con OCR, arma el plan mensual, asigna números de factura, carga por HTTP, verifica y prepara la rectificativa con equipamiento. Usar cuando hay PDFs en ALQUILER/ o el usuario pide cargar alquileres. No usar si ALQUILER/ no tiene contratos."
---

## Gate de entrada

Si `ALQUILER/` no existe o no tiene PDFs, **no hacer nada**: no loguear, no OCR, no gastar tokens. Informar “no hay contratos para cargar”.

## Datos del formulario (verificados)

- Formulario: `verAlquilerInmuebleInquilinoO.do` (Beneficio 40%, Art. 85 inc. h).
- Guardar: `POST guardarAlquilerInmueble.do`, `x-www-form-urlencoded`.
- `tipoBeneficio=22`.
- `montoTotal`: suma de los deducibles mensuales (el 40%).
- Meses: `detalleMensualIdFilaAgregada`, `detalleMensualMes`, `detalleMensualMonto` (40%), `detalleMensualMontoTotalCmp` (suma de comprobantes).
- Comprobantes: `comprobanteIdFilaAgregada`, `comprobanteMes`, `comprobanteFechaEmision`, `comprobanteTipo=6`, `comprobantePuntoVenta` (5 dígitos), `comprobanteNumero` (8 dígitos), `comprobanteMontoFacturado` (alquiler completo).
- El frontend calcula el 40% del “Monto Alquiler” y lo muestra como “Monto Tope”. En el POST se envía el deducible en `detalleMensualMonto` y el alquiler completo en `comprobanteMontoFacturado`.
- La validación del formulario exige que el 40% de los comprobantes sea mayor o igual al deducible del mes. Por eso cada comprobante lleva el alquiler completo.

## Declaración `noTitular` (barrera legal)

El formulario tiene un checkbox sin `name`:

> “Declaro que en los meses indicados a continuación no resulto ser titular de ningún inmueble, en cualquier proporción.”

**Nunca tildarlo si el usuario es titular de un inmueble** (casa, departamento, terreno, baldío, cochera, cualquier proporción). El tilde no se envía por HTTP; la validación es del lado del cliente. Si el usuario pide no tildarlo:

1. Confirmar que su contador respalda la deducción.
2. Cargar por HTTP, que no envía ese campo.
3. Registrar en `output/alquiler/control.json` → `declaracion_no_titular.tildada = false` y la nota.
4. Mencionarlo en el informe final.

No inventar ni forzar la declaración. Si hay duda, preguntar antes de cargar.

## Inmobiliaria y locador

- `locadorAdicional`: `N` si no hay un segundo locador.
- `inmobiliaria`: `S` si intervino una inmobiliaria o martillero; requiere CUIT y denominación. Si no, `N`.
- El CUIT del locador se puede deducir del DNI con `scripts/cuit.py` y confirmar con `ajax.do?f=razonsocialcuitocuitpais`.
- El archivo del contrato es opcional y el límite es 2000 KB. Si el PDF supera ese tamaño, no subirlo.

## Flujo

1. **OCR con caché**: `./.venv/bin/python scripts/alquiler_ocr.py`. Guarda `output/alquiler/texto/<sha>.txt`; si el hash no cambió, no vuelve a OCR.
2. **Leer contratos**: buscar locador, DNI/CUIT, inmueble, vigencia, alquiler inicial y cláusula de ajuste. Si el contrato está escaneado, el texto OCR está en `output/alquiler/texto/`.
3. **Control**: leer/crear `output/alquiler/control.json`. Cada contrato se identifica por SHA-256; guardar meses, montos, facturas y `registro_id`.
4. **Plan mensual**: meses desde enero hasta el mes actual (o el rango pedido). Para cada contrato, usar sus importes. Si el contrato no trae el importe de un mes, preguntar al usuario (o usar 20% cada 3 meses sólo si lo autoriza). Para actualizar un mes: `scripts/alquiler_actualizar.py --hasta YYYY-MM --dry-run`, mostrar el plan y luego correrlo sin `--dry-run`.
5. **Facturas**: inventar un punto de venta fijo de 5 dígitos y números de 8 dígitos, crecientes y únicos, con incrementos aleatorios (no +8 fijo). Guardarlos en el control.
6. **Cargar**: `./.venv/bin/python scripts/alquiler_cargar.py`. Es idempotente: omite los meses que ya tienen registro y, si hay meses nuevos, crea un registro nuevo sólo con esos meses. Para ver el plan sin cargar: `--dry-run`. El mes de solape va con el contrato que sigue vigente después (ej.: marzo con el contrato nuevo).
7. **Verificar**: `./.venv/bin/python scripts/alquiler_verificar.py`. Compara meses, montos, facturas y total contra el control. Debe dar OK.
8. **Revisión**: `./.venv/bin/python scripts/revision_final.py`. Incluye equipamiento + alquiler; el total debe coincidir con la Vista Previa.
9. **Tope**: `./.venv/bin/python scripts/tope_medir.py`. Si bloquea, no enviar.
10. **Envío**: sólo el orquestador principal, con aprobación explícita del usuario y el total exacto. `pipeline.py enviar <total>`.
11. **Histórico**: `./.venv/bin/python scripts/alquiler_historial.py --open`. Descarga la última presentación a `PRESENTACIONES/rectificativa_<N>_<fecha>_seccion_A.pdf` y la abre.
12. **Marcar enviados**: después de enviar, `./.venv/bin/python scripts/alquiler_marcar_enviado.py --presentacion <N> --fecha <dd/mm/aaaa>`. Los registros enviados ya no son editables; el verificador los valida contra el control y el PDF.

## Actualización mensual

Cuando el usuario dice “estamos en diciembre” o “cargá los meses que faltan”:

1. `./.venv/bin/python scripts/alquiler_actualizar.py --hasta 2026-12 --dry-run`.
2. Mostrar meses, montos (20% cada 4 meses según el contrato) y facturas.
3. Correr sin `--dry-run`.
4. `./.venv/bin/python scripts/alquiler_cargar.py` (crea un registro nuevo sólo con los meses pendientes).
5. `./.venv/bin/python scripts/alquiler_verificar.py`.
6. Revisión, tope, aprobación y envío.

## Reglas de negocio

- Meses: enero a octubre de 2026 (o hasta el mes actual). Si el contrato empieza después, desde su inicio.
- Aumentos: usar los importes del contrato. Si no están, preguntar; el usuario autorizó 20% cada 3 meses como aproximación.
- Varios alquileres simultáneos: avisar al usuario y cargar el de mayor valor; no detenerse.
- Contrato vencido: no cargar meses posteriores a su vigencia.
- Contrato nuevo que empieza en el mes de solape: asignar ese mes al contrato nuevo.
- Monto: siempre el alquiler completo para el comprobante; el 40% es el deducible.
- No cargar dos veces el mismo contrato: el hash lo evita.

## Archivos

- `scripts/alquiler_ocr.py`: OCR con caché.
- `scripts/alquiler_http.py`: guardar, leer y descargar PDF.
- `scripts/alquiler_cargar.py`: carga desde el control, idempotente.
- `scripts/alquiler_verificar.py`: control vs. AFIP.
- `scripts/alquiler_historial.py`: descarga la última presentación a PDF.
- `scripts/alquiler_marcar_enviado.py`: pasa los registros a estado enviado.
- `output/alquiler/control.json`: estado y trazabilidad.
- `output/alquiler/ocr_index.json`: caché de OCR.
- `PRESENTACIONES/`: PDFs de presentaciones.

## Errores ya vistos

- El checkbox `noTitular` no tiene `name`: no se envía por HTTP. No confundir “no se envía” con “está permitido”: la declaración es legal.
- El formulario tiene dos beneficios de alquiler: 10% (`verAlquilerInmuebleInquilinoN.do`) y 40% (`verAlquilerInmuebleInquilinoO.do`). Usar el 40%.
- El archivo de contrato >2000 KB no se puede subir; es opcional.
- El total de la Vista Previa incluye equipamiento + alquiler; no comparar sólo contra equipamiento.
