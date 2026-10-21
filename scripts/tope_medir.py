"""Mide el tope de carga directa SIN enviar: lee la Vista Previa y dice si AFIP la bloquea.

Uso:  ./.venv/bin/python scripts/tope_medir.py
Devuelve código 0 si NO hay bloqueo por tope, 1 si lo hay.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from afip_http import RADIG, sesion_http
from registro import evento
from revision_final import total_vista_previa


def medir():
    with sesion_http() as req:
        html = req.get(RADIG + "vistaPreviaFormulario.do").body().decode("iso-8859-1")
    total = total_vista_previa(html)
    bloqueado = "supera el monto tope" in html
    evento("tope", "error" if bloqueado else "info", "medicion", total=total, bloqueado_por_tope=bloqueado)
    print(f"Total Vista Previa: {total:,.2f}")
    print("BLOQUEADO por tope de carga directa" if bloqueado else "SIN bloqueo por tope")
    return 1 if bloqueado else 0


if __name__ == "__main__":
    sys.exit(medir())
