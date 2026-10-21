import json
import os
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from registro import evento
from siradig import abrir_sesion, llegar_a_gastos, volcar_arbol, guardar_red

RADIG = "https://serviciosjava2.afip.gob.ar/radig/jsp/"

if len(sys.argv) != 2:
    print("Uso: siradig_enviar_ui.py <total aprobado, ej: 1.234.567,89>")
    raise SystemExit(2)
TOTAL_APROBADO = sys.argv[1]
ROOT = Path(__file__).resolve().parent.parent

# Evitar una rectificativa idéntica a la última enviada.
ENVIO = ROOT / "output" / "envio.json"
if ENVIO.exists() and not os.environ.get("FORZAR_ENVIO"):
    try:
        ultimo = json.loads(ENVIO.read_text(encoding="utf-8")).get("ultimo_envio", {})
        if ultimo.get("total") == TOTAL_APROBADO:
            print(f"Sin cambios: ya se envió una presentación por {TOTAL_APROBADO}. No se envía de nuevo.")
            print("Si querés forzar el reenvío, ejecutá con FORZAR_ENVIO=1.")
            raise SystemExit(0)
    except json.JSONDecodeError:
        pass

with sync_playwright() as p:
    browser, context, page, red = abrir_sesion(p)
    page = llegar_a_gastos(context, page)
    page.goto(RADIG + "vistaPreviaFormulario.do")
    page.wait_for_load_state()
    page.wait_for_timeout(2000)
    texto = page.locator("body").inner_text()
    if TOTAL_APROBADO not in texto:
        evento("envio", "error", "abortado_total_distinto", aprobado=TOTAL_APROBADO)
        print("ABORTO: el total de la Vista Previa no coincide con el aprobado.")
        browser.close()
        raise SystemExit(1)
    print("Total verificado:", TOTAL_APROBADO)
    evento("envio", "info", "total_verificado", total=TOTAL_APROBADO)
    volcar_arbol(page, "vista_previa_antes_envio")

    page.locator("#btn_enviar_empleador").click()
    dialogo = page.get_by_role("button", name="Generar Presentación")
    dialogo.wait_for(timeout=10000)
    print("Diálogo de confirmación abierto")
    evento("envio", "info", "confirmacion_enviada")
    dialogo.click()
    page.wait_for_timeout(5000)
    print("URL tras confirmar:", page.url)
    volcar_arbol(page, "envio_resultado")
    print(re.sub(r"\n\s*\n", "\n", page.locator("body").inner_text())[:800])
    guardar_red(red, "envio_ui")

    page.goto(RADIG + "verFormulariosEnviados.do")
    page.wait_for_load_state()
    volcar_arbol(page, "enviados_despues_envio")
    print("--- Consulta de Formularios Enviados:")
    print(re.sub(r"\n\s*\n", "\n", page.locator("body").inner_text())[:600])
    page.wait_for_timeout(10000)
    browser.close()
