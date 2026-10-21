"""Descarga la última presentación enviada y la guarda en PRESENTACIONES/.

Uso:
  ./.venv/bin/python scripts/alquiler_historial.py --open
  ./.venv/bin/python scripts/alquiler_historial.py --codigo 12345678 --open
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from afip_http import RADIG, sesion_http
from alquiler_http import descargar_presentacion

ROOT = Path(__file__).resolve().parent.parent
DESTINO = ROOT / "PRESENTACIONES"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--codigo", help="código de presentación; si se omite, usa la última")
    p.add_argument("--open", action="store_true", help="abrir el PDF al terminar")
    args = p.parse_args()

    DESTINO.mkdir(parents=True, exist_ok=True)
    with sesion_http() as req:
        if args.codigo:
            codigo, version, fecha = args.codigo, None, None
        else:
            html = req.get(RADIG + "verFormulariosEnviados.do").body().decode("iso-8859-1")
            m = re.search(r"var datosFormulariosJSON = (\[.*?\]);", html, re.S)
            datos = json.loads(m.group(1))
            ultima = max(datos, key=lambda d: d["version"])
            codigo, version, fecha = str(ultima["codigo"]), ultima["version"], ultima["fechaEnvio"]
        pdf = descargar_presentacion(req, codigo, "a")
        if not pdf.startswith(b"%PDF"):
            print("La descarga no devolvió un PDF.")
            return 1
        if version is None:
            nombre = f"presentacion_{codigo}_seccion_A.pdf"
        else:
            fecha_iso = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")
            nombre = f"rectificativa_{version - 1}_{fecha_iso}_seccion_A.pdf"
        destino = DESTINO / nombre
        destino.write_bytes(pdf)
        print(f"guardado: {destino} ({len(pdf)} bytes)")
        if args.open:
            subprocess.run(["open", str(destino)], check=False)
            print("abierto")
    return 0


if __name__ == "__main__":
    sys.exit(main())
