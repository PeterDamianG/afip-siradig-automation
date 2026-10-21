import re
from playwright.sync_api import sync_playwright
from siradig import abrir_sesion, llegar_a_gastos, volcar_arbol
from siradig_http import MESES

RADIG = "https://serviciosjava2.afip.gob.ar/radig/jsp/"

with sync_playwright() as p:
    browser, context, page, red = abrir_sesion(p)
    page = llegar_a_gastos(context, page)
    page.goto(RADIG + "verFormulariosEnviados.do")
    page.wait_for_load_state()
    page.wait_for_timeout(2000)
    print("URL:", page.url)
    volcar_arbol(page, "enviados_revision")
    texto = page.locator("body").inner_text()
    print(re.sub(r"\n\s*\n", "\n", texto)[:1200])
    page.wait_for_timeout(15000)
    browser.close()
