"""Muestra la Vista Previa de SiRADIG en el navegador, en modo SOLO LECTURA. NO envía nada.

Abre un Chromium con ventana (headed), deja la Vista Previa a la vista para que el usuario
decida, y guarda el árbol de accesibilidad y una captura en output/evidencia/.

Nunca hace clic en "Enviar al Empleador" ni en "Generar Presentación".

Uso:  ./.venv/bin/python scripts/siradig_vista_previa_ui.py [minutos_abierto]
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright

from registro import evento
from revision_final import fmt, total_vista_previa
from siradig import abrir_sesion, guardar_red, llegar_a_gastos, volcar_arbol

RADIG = "https://serviciosjava2.afip.gob.ar/radig/jsp/"
MINUTOS = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0


def _total_desde_texto(texto):
    m = re.search(r"Importe Total:\s*\$\s*([\d.,]+)", texto)
    if not m:
        return None
    try:
        return float(m.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def main():
    with sync_playwright() as p:
        browser, context, page, red = abrir_sesion(p)
        page = llegar_a_gastos(context, page)
        page.goto(RADIG + "vistaPreviaFormulario.do")
        page.wait_for_load_state()
        page.wait_for_timeout(3000)

        html = page.content()
        texto = re.sub(r"\n\s*\n", "\n", page.locator("body").inner_text())
        total = total_vista_previa(html)
        if total is None:
            total = _total_desde_texto(texto)
        bloqueado = "supera el monto tope" in html or "supera el monto tope" in texto

        print("=== VISTA PREVIA (solo lectura, no se envio nada) ===")
        print(texto[:5000])
        print("=== fin de la Vista Previa ===")
        print(f"Total: $ {fmt(total or 0)}")
        print("BLOQUEADO por tope de carga directa" if bloqueado else "Sin bloqueo por tope")

        volcar_arbol(page, "vista_previa_ui")
        guardar_red(red, "vista_previa_ui")
        evento("vista_previa", "error" if bloqueado else "info", "vista_previa_ui",
               total=total, bloqueado_por_tope=bloqueado, minutos_abierto=MINUTOS)

        print(f"El navegador queda abierto {MINUTOS:g} min para que veas la pantalla. No se hace ningun clic.")
        page.wait_for_timeout(int(MINUTOS * 60 * 1000))
        browser.close()


if __name__ == "__main__":
    main()
