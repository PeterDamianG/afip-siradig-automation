from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "credenciales.env"
EVIDENCIA = ROOT / "output" / "evidencia"


def cargar_credenciales(path=ENV_FILE):
    datos = {}
    for linea in path.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        datos[clave.strip()] = valor.strip()
    return datos


def login(page, cred):
    page.goto(cred["AFIP_URL"])
    page.get_by_role("spinbutton").fill(cred["AFIP_USUARIO"])
    page.get_by_role("button", name="Siguiente").click()
    page.get_by_role("textbox", name="TU CLAVE").fill(cred["AFIP_PASSWORD"])
    page.get_by_role("button", name="Ingresar").click()
    page.wait_for_load_state()
    page.wait_for_timeout(5000)


def main():
    cred = cargar_credenciales()
    EVIDENCIA.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=400)
        page = browser.new_page()
        login(page, cred)

        print("URL:", page.url)
        print("Título:", page.title())
        page.screenshot(path=EVIDENCIA / "login.png", full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
