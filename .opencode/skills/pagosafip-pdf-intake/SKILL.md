---
name: pagosafip-pdf-intake
description: "Lee las facturas de FACTURAS/ (muchos proveedores y formatos), valida cada comprobante, detecta duplicados (por número y por CAE) y deja listo output/facturas.json para cargar. Incluye confirmaciones manuales con trazabilidad. Usar antes de cualquier carga y cada vez que llegan facturas nuevas. No usar para llenar o cargar el formulario en SiRADIG, conciliar ni enviar: para esas tareas están pagosafip-siradig-http, pagosafip-validator y pagosafip-revision-final."
---

## Fuente de verdad

AFIP es la fuente de verdad, no la carpeta. El usuario puede dejar las facturas viejas en `FACTURAS/` o borrarlas y poner solo las nuevas. Ambos casos funcionan:
- El cargador omite lo que ya está en AFIP (`omitido: ya está en AFIP`). Es idempotente.
- El informe clasifica como "cargado por la automatización" todo lo que está en AFIP, salvo los 4 preexistentes de `output/preexistentes.json`.

Nunca asumir que lo que no está en la carpeta no fue cargado.

## Estados por comprobante

| Estado | Significado | Qué hacer |
|---|---|---|
| `listo` | Campos válidos, sin duplicado | Se carga |
| `revisar` | Falta un campo, proveedor no reconocido o monto fuera de rango | Leer el PDF (como imagen), confirmar y cargarlo en `output/confirmados_manual.json` |
| `duplicado` | Mismo comprobante que otro archivo (mismo CUIT+pv+número, o mismo CAE) | No se carga |
| `excluido` | El usuario decidió no cargarlo | No se carga. Queda registrado con el motivo |
| `error` | Sin texto o no se pudo leer | Revisar a mano |

## Comando

```
./.venv/bin/python scripts/pipeline.py extraer
```

Escribe `output/facturas.json` (una entrada por archivo), `output/extracto.csv` (espejo del JSON, una fila por comprobante) y registra en `output/logs/`.

El CSV lo genera el mismo `extraer`: es un espejo del JSON y no se edita a mano. Si algún día los dos no coinciden, el JSON manda.

## Cómo funciona (no romper)

1. `leer_texto`: pdfplumber con `dedupe_chars`. Elimina letras dibujadas dos veces (texto en negrita).
2. Si el PDF es de un proveedor conocido (`scripts/proveedores.py`, `PROVEEDORES`), usa su extractor.
3. Si no, `extraer_generico` busca por rótulo (formato AFIP estándar). Si encuentra CUIT emisor, fecha, número, total y tipo, queda `listo` como `afip_estandar`. Si falta algo, `revisar` con el motivo.
4. `normalizar`: valida CUIT (dígito verificador), fecha (año del formulario = 2026), monto, tipo y punto de venta/número.
5. Duplicados: por (CUIT, pv, número) y por CAE (14 dígitos). El primero gana.
6. `output/confirmados_manual.json`: confirmaciones manuales por archivo. Pueden traer los datos (`emisor_cuit`, `tipo_afip`, `pv`, `numero`, `fecha`, `total`, `cae`), `excluir: true`, y siempre `_origen` (de dónde salió el dato). Los comprobantes con `origen` aparecen como marca en el informe final.
7. Estado inicial (`asignar_estado`): `excluir: true` → `excluido`; sin motivos → `listo`; con motivos → `revisar`. El estado `excluido` no puede caer en `revisar`: si eso pasa, el comprobante vuelve a la lista de "por revisar" en cada corrida. Cubierto por `scripts/test_proveedores.py`.

## Reglas de datos

- Fecha: la de emisión (no vencimiento ni período). El mes del gasto es el mes de emisión.
- Monto: total de la factura. El usuario lo confirmó.
- Categoría: todas son Equipamiento (home office). No cuestionar la categoría.
- Dos liquidaciones de un mismo período (proveedor de gas "1 de 2" y "2 de 2") son facturas individuales. Se cargan ambas.
- Año: sólo 2026. Un año distinto manda a `revisar`.

## Montos (errores reales ya cometidos, no repetir)

Ver `scripts/montos.py` y `scripts/test_montos.py`. Antes de cargar: `./.venv/bin/python scripts/test_montos.py`.

| Texto en el PDF | Monto |
|---|---|
| `83650.00` (proveedor de internet, punto decimal) | 83650.00 |
| `52.607,88` (coma decimal) | 52607.88 |
| `29386,86` | 29386.86 |
| `47,992.0000` (formato inglés) | 47992.00 |
| `1.500` o `1,500` (3 decimales) | **ambiguo**: no se adivina, va a `revisar` |

- Regla: si hay coma y punto, el último separador es el decimal. Si sólo hay coma, es decimal. Si sólo hay punto, es decimal sólo con 2 dígitos.
- Error real: un proveedor de internet se cargó ×100 cuando el punto se trató como separador de miles.

## Totales (errores reales ya cometidos)

- Un total con la etiqueta en una línea y el valor en la línea siguiente puede capturar el subtotal de la fila de abajo. Los patrones de total leen **sólo la misma línea** (`[ \t]`, no `\s`), y hay un patrón específico para "TOTAL" seguido de salto de línea y `$`.
- El total es el último total del documento (`_extraer_total`).
- Un número de comprobante puede confundirse con el CAE (14 dígitos). Antes de buscar el número se quitan los CAE del texto.

## CAE (errores reales ya cometidos)

- El rótulo del CAE puede quedar **separado del número** por el pie legal: "Área de CAE Nro.:" en una línea y el CAE dos líneas más abajo, junto al teléfono de defensa del consumidor. El extractor genérico devolvía `cae=None` y el comprobante quedaba sin CAE. `_extraer_cae` primero busca el rótulo pegado al número y, si no lo encuentra, busca el primer bloque de 14 dígitos **suelto** que sigue al rótulo.
- Los 14 dígitos tienen que ser un token propio (`(?<!\d)` / `(?!\d)`). Hay comprobantes que imprimen CUIT+tipo+pv+número+CAE+fecha pegados en una sola cadena numérica: un CAE dentro de esa cadena no es el CAE.

## Proveedores de ejemplo

El registro público trae tres plantillas genéricas en `scripts/proveedores.py`:

- **Gas**: `FACTURADEGAS`, número `pv-número/dv`.
- **Cooperativa local**: `COOPERATIVA LOCAL`. "FACTURA B" → 6, "LIQ. DE SERV." → 40.
- **Internet**: `PROVEEDOR DE INTERNET`, punto decimal.

El formato AFIP estándar (vendedores de Mercado Libre, electrónica, indumentaria) se resuelve con `extraer_generico`: `Comp. Nro`, `Nº`, `Nro`, `Fc B`, `FB`, `Código 06`, `Importe Total`, `TOTAL $`, `TOTAL Pesos (ARS)`, `Total ARS`. Algunos no traen el CUIT del vendedor, o lo traen con el DNI del comprador. Ver "Revisar" abajo.

## Agregar un proveedor nuevo

1. `extraer`. Si el formato es AFIP estándar y tiene todos los campos, ya queda `listo` sin cambios.
2. Si queda en `revisar`, leer el PDF como imagen y completar `confirmados_manual.json` con `_origen` ("Lectura visual").
3. Si el formato se repite y tiene campos siempre en el mismo lugar, agregar un extractor en `proveedores.py` y un caso a `test_montos.py` si cambia el formato de monto.
4. Volver a correr `extraer` y comparar con el PDF.

La plantilla propia sirve aunque el genérico ya lea los campos: además de anclarlos a la posición fija del comprobante, es la única forma de que el emisor tenga nombre (el genérico deja `emisor_nombre` en null y el informe final no identifica al proveedor).

## Revisar (sin CUIT del vendedor)

Si el PDF no muestra el CUIT del vendedor, NO se carga. Se pide el CUIT al usuario. Si el usuario dice que se ignore, se marca `excluir: true` con el motivo.

## Duplicados

- Mismo CUIT emisor + pv + número, o mismo CAE → `duplicado`. Se indica cuál es el original.
- Mismo CUIT + fecha + monto con número distinto → alerta en el JSON, no se bloquea. Si no está claro, preguntar. Caso resuelto: las dos liquidaciones de un mismo período se cargan completas.
