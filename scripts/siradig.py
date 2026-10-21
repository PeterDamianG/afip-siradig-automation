import json
import re
from urllib.parse import parse_qsl, urlencode

from afip_login import EVIDENCIA, ROOT, cargar_credenciales, login
from playwright.sync_api import TimeoutError as PWTimeout

PORTAL = "https://portalcf.cloud.afip.gob.ar/portal/app/"
GASTOS = "https://serviciosjava2.afip.gob.ar/radig/jsp/verGastosInduEquip.do"
RED = ROOT / "output" / "red"
OCULTAR = {"cookie", "authorization", "set-cookie"}
SENSIBLE = re.compile(r"password|clave|token|jwt|viewstate|sign", re.I)
REDACTADO = "<REDACTADO>"


def abrir_sesion(p):
    browser = p.chromium.launch(headless=False, slow_mo=300)
    context = browser.new_context()
    page = context.new_page()
    login(page, cargar_credenciales())
    red = []
    context.on("request", lambda r: red.append({
        "metodo": r.method,
        "url": r.url,
        "tipo": r.resource_type,
        "post_data": _redactar_body(r.post_data),
        "headers": {k: v for k, v in r.headers.items() if k.lower() not in OCULTAR},
        "estado": None,
    }))
    context.on("response", lambda resp: _marcar_estado(red, resp))
    return browser, context, page, red


def _redactar_body(body):
    if not body:
        return body
    pares = parse_qsl(body, keep_blank_values=True)
    if pares and all("=" in p or p == "" for p in body.split("&")):
        return urlencode([(k, REDACTADO if SENSIBLE.search(k) else v) for k, v in pares])
    return REDACTADO if SENSIBLE.search(body) else body


def _marcar_estado(red, resp):
    for r in reversed(red):
        if r["url"] == resp.url and r["estado"] is None:
            r["estado"] = resp.status
            break


def guardar_red(red, nombre):
    RED.mkdir(parents=True, exist_ok=True)
    solo_relevante = [r for r in red if r["tipo"] in ("document", "xhr", "fetch")]
    (RED / f"{nombre}.json").write_text(json.dumps(solo_relevante, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Red guardada: output/red/{nombre}.json ({len(solo_relevante)} peticiones)")


def llegar_a_gastos(context, page):
    page.get_by_text("SiRADIG - Trabajador").first.click()
    page.wait_for_timeout(3000)
    page = context.pages[-1]
    page.wait_for_load_state()

    tabla = page.locator("table").filter(has_text="Seleccione la Persona a representar")
    tabla.get_by_role("button").first.click()
    page.wait_for_url("**determinarContribuyente**", timeout=15000)

    try:
        page.get_by_role("button", name="Aceptar").first.click(timeout=5000)
    except PWTimeout:
        pass

    page.get_by_role("button", name="Carga de Formulario").click()
    page.wait_for_url("**verMenuDeducciones**", timeout=15000)

    page.get_by_text("Deducciones y desgravaciones").first.click()
    page.wait_for_timeout(1500)

    page.goto(GASTOS)
    page.wait_for_load_state()
    return page


def volcar_arbol(page, nombre):
    EVIDENCIA.mkdir(parents=True, exist_ok=True)
    (EVIDENCIA / f"{nombre}.yaml").write_text(page.locator("body").aria_snapshot(), encoding="utf-8")
    page.screenshot(path=EVIDENCIA / f"{nombre}.png", full_page=True)
    print(f"Árbol y captura guardados: output/evidencia/{nombre}.*")
