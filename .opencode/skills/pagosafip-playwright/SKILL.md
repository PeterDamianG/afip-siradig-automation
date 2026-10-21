---
name: pagosafip-playwright
description: "Respaldo con navegador (Playwright) para el portal de AFIP y SiRADIG. Usar sólo cuando el HTTP falla, cuando hace falta ver la pantalla, o para pasos que no tienen contrato HTTP (como el envío final con confirmación en pantalla)."
---

## Alcance actual

El único paso que hoy usa navegador es el **envío final** de la rectificativa. La carga de equipamiento, la carga de alquileres, la conciliación, la Vista Previa y el PDF histórico van por HTTP. No levantar el navegador para esas tareas.

## Cuándo usar el navegador

Usar el navegador SOLO si:
1. El HTTP falló y el diagnóstico (skill `pagosafip-diagnostico`) indica que hace falta la pantalla.
2. El usuario pide ver la pantalla.
3. Hay que confirmar visualmente un resultado (por ejemplo, el listado de presentaciones enviadas).

Si el HTTP funciona, no usar el navegador. Es más lento y más caro.

## Reglas

1. Las credenciales están en `credenciales.env`. Los scripts las leen. Nunca mostrarlas ni leer el archivo en el chat.
2. El navegador es visible (`headless=False`). El usuario puede seguir los pasos.
3. No enviar ni confirmar nada sin aprobación explícita del usuario en la sesión actual.
4. Usar el MCP `playwright` sólo para explorar una pantalla nueva. Para operar, usar scripts Python.

## Scripts disponibles

- `scripts/siradig.py`: `abrir_sesion(p)` (login visible), `llegar_a_gastos(context, page)` (recorre SiRADIG hasta el formulario), `volcar_arbol(page, nombre)` (guarda árbol de accesibilidad y captura en `output/evidencia/`), `guardar_red(red, nombre)` (registro de peticiones, redactado).
- `scripts/siradig_revisar_enviados.py`: abre "Consulta de Formularios Enviados" y lo muestra. Solo lectura.
- `scripts/siradig_enviar_ui.py <total>`: envío por pantalla. Recibe el total aprobado como argumento y aborta si la Vista Previa no coincide. Usar siempre a través de `pipeline.py enviar <total>`, que además mide el tope antes. Solo con aprobación explícita.

## Flujo de navegación SiRADIG (verificado)

1. Portal `portalcf.cloud.afip.gob.ar/portal/app/` → clic en "SiRADIG - Trabajador".
2. `menu_sel_empresa.jsp` → botón con el nombre del contribuyente.
3. `determinarContribuyente.do?codigo=2026` → modal "Recordatorio" → botón "Aceptar" (si aparece).
4. Botón "Carga de Formulario" → `verMenuDeducciones.do`.
5. Pestaña "3 - Deducciones y desgravaciones".
6. `verGastosInduEquip.do` (formulario).
7. Abajo: "Vista Previa" → `vistaPreviaFormulario.do`. Abajo: "Enviar al Empleador..." → diálogo "Generar Presentación" → `generacion_presentacion.jsp`.

## Selectores verificados

- Login: `spinbutton` (CUIT), botón "Siguiente", `textbox` "TU CLAVE", botón "Ingresar".
- Representar: `button` con el nombre del contribuyente.
- Carga de formulario: `button` "Carga de Formulario".
- Alta de comprobante: link "Alta de Comprobante" → `dialog` "Alta de Comprobante" (campos Fecha, Tipo, Punto de Venta, Número, Monto; botones Agregar y Cancelar).
- Guardar gasto: botón "Guardar".
- Vista previa: `#btn_enviar_empleador`. Diálogo: botón "Generar Presentación".
- El "+" del grupo de Indumentaria no navega con clic. Usar la URL directa.

## Estado

- Login y sesión SiRADIG: verificados por navegador y HTTP.
- Carga de gastos: verificada por HTTP (ver `pagosafip-siradig-http`).
- Envío final: verificado por navegador en una presentación real. El diálogo “Enviar al Empleador” → “Generar Presentación” funciona; el repositorio no incluye números ni importes reales.
