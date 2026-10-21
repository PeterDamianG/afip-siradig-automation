"""Compara output/facturas.json (estado 'listo') contra lo que AFIP tiene cargado.

Uso:  ./.venv/bin/python scripts/siradig_conciliar.py
Devuelve código 1 si falta algo o hay montos distintos.
"""
import json
import sys
from pathlib import Path

from afip_http import sesion_http
from registro import evento
from siradig_http import comprobantes_de_gasto, gastos_servidor, listar_menu

ROOT = Path(__file__).resolve().parent.parent
FACTURAS_JSON = ROOT / "output" / "facturas.json"


def conciliar(registros):
    listos = [r for r in registros if r["estado"] == "listo"]
    cuits = {r["emisor_cuit"] for r in listos}
    en_afip = {}
    with sesion_http() as req:
        for g in gastos_servidor(listar_menu(req)):
            if g["concepto"] != "Equipamiento" or g["cuit"] not in cuits:
                continue
            for c in comprobantes_de_gasto(req, g["idReg"]):
                clave = (g["cuit"], str(c["puntoVenta"]).zfill(5), str(c["numero"]).zfill(8))
                en_afip[clave] = float(c["montoFacturado"])

    faltan, montos_distintos = [], []
    for r in listos:
        clave = (r["emisor_cuit"], r["pv"], r["numero"])
        if clave not in en_afip:
            faltan.append(r["archivo"])
        elif abs(en_afip[clave] - float(r["monto"])) > 0.01:
            montos_distintos.append((r["archivo"], en_afip[clave], r["monto"]))

    print(f"Comprobantes listos: {len(listos)}")
    print(f"Presentes en AFIP con monto correcto: {len(listos) - len(faltan) - len(montos_distintos)}")
    print(f"Faltan en AFIP: {faltan or 'ninguno'}")
    print(f"Monto distinto: {montos_distintos or 'ninguno'}")
    ok = not faltan and not montos_distintos
    evento("conciliar", "info" if ok else "error", "resultado", listos=len(listos), faltan=faltan,
           montos_distintos=len(montos_distintos))
    return ok


if __name__ == "__main__":
    ok = conciliar(json.loads(FACTURAS_JSON.read_text(encoding="utf-8")))
    sys.exit(0 if ok else 1)
