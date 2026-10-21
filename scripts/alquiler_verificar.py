"""Verifica los registros de alquiler del control contra AFIP.

Los registros con estado "enviado" ya no son editables: se validan contra el
control y el PDF histórico, no contra el borrador. Los "cargado" se leen en vivo.

Uso:  ./.venv/bin/python scripts/alquiler_verificar.py
Código 0 si todo coincide, 1 si hay diferencias.
"""
import json
import sys
from pathlib import Path

from afip_http import sesion_http
from alquiler_http import obtener_alquiler

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / "output" / "alquiler" / "control.json"


def _registros(contrato):
    if contrato.get("registros"):
        return contrato["registros"]
    if contrato.get("registro_id"):
        return [{"registro_id": contrato["registro_id"], "meses": contrato["meses"], "estado": "cargado"}]
    return []


def verificar():
    control = json.loads(CONTROL.read_text(encoding="utf-8"))
    total = 0.0
    errores = []
    with sesion_http() as req:
        for contrato in control["contratos"].values():
            plan = {m["mes"]: m for m in contrato["meses"]}
            total += sum(float(m["deducible"]) for m in plan.values())
            registros = _registros(contrato)
            cubiertos = {m["mes"] for r in registros for m in r["meses"]}
            faltan = sorted(set(plan) - cubiertos)
            print(f"\n{contrato['archivo']}  meses plan={sorted(plan)}")
            if faltan:
                errores.append(f"{contrato['archivo']}: meses sin registro {faltan}")
            for reg in registros:
                rid = reg.get("registro_id")
                estado = reg.get("estado", "cargado")
                meses = {m["mes"]: m for m in reg["meses"]}
                if estado == "enviado":
                    print(f"  registro {rid}: ENVIADO (presentación {reg.get('presentacion', '?')}). "
                          f"Meses {sorted(meses)}. Se valida con el control/PDF, no en el borrador.")
                    continue
                real = obtener_alquiler(req, rid)
                form = real["form"]
                if not form:
                    errores.append(f"{contrato['archivo']}: registro {rid} no editable y no marcado enviado")
                    continue
                print(f"  registro {rid}: {form.get('mesDesde')} a {form.get('mesHasta')}  total={form.get('montoTotal')}")
                comps = real["comprobantes"]
                if len(comps) != len(meses):
                    errores.append(f"{contrato['archivo']}: registro {rid} tiene {len(comps)} comprobantes, esperados {len(meses)}")
                for c in comps:
                    esperado = meses.get(c["mes"])
                    if not esperado:
                        errores.append(f"{contrato['archivo']}: mes {c['mes']} inesperado en registro {rid}")
                        continue
                    ok = (float(c["montoFacturado"]) == float(esperado["alquiler"])
                          and int(c["numero"]) == int(esperado["factura"])
                          and c["idTipoCmp"] == 6)
                    print(f"    mes {c['mes']:2}  factura {c['puntoVenta']:05d}-{c['numero']:08d}  "
                          f"monto={c['montoFacturado']:,.2f}  {'OK' if ok else 'DIFERENTE'}")
                    if not ok:
                        errores.append(f"{contrato['archivo']}: mes {c['mes']} no coincide")
    print(f"\nTotal alquiler: {total:,.2f}")
    if errores:
        print("ERRORES:")
        for e in errores:
            print(" -", e)
        return 1
    print("OK: el plan está cubierto y los registros cargados coinciden con el control.")
    return 0


if __name__ == "__main__":
    sys.exit(verificar())
