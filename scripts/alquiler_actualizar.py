"""Extiende el plan de alquiler hasta un mes determinado.

Calcula los meses faltantes con la regla del contrato (base + aumento cada N
meses) y les asigna números de factura aleatorios crecientes. No carga en AFIP:
después se corre `alquiler_cargar.py`.

Uso:
  ./.venv/bin/python scripts/alquiler_actualizar.py --hasta 2026-12 --dry-run
  ./.venv/bin/python scripts/alquiler_actualizar.py --hasta 2026-12
"""
import argparse
import json
import random
import sys
from datetime import date, datetime
from pathlib import Path

from registro import evento

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / "output" / "alquiler" / "control.json"
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _parse_fecha(texto):
    return datetime.strptime(texto, "%d/%m/%Y").date()


def importe_para(contrato, mes):
    base = contrato.get("alquiler_base")
    inicio = contrato.get("mes_inicio")
    if not base or not inicio:
        return None
    cada = int(contrato.get("aumento_cada", 4))
    pct = float(contrato.get("aumento_porcentaje", 20))
    tramos = max(0, (mes - int(inicio)) // cada)
    return round(float(base) * (1 + pct / 100) ** tramos, 2)


def siguiente_factura(meses, rng):
    ultima = max((int(m["factura"]) for m in meses), default=450)
    return str(ultima + rng.randint(3, 17)).zfill(8)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hasta", help="YYYY-MM; por defecto, el mes actual")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    hoy = date.today()
    if args.hasta:
        anio, mes = [int(x) for x in args.hasta.split("-")]
    else:
        anio, mes = hoy.year, hoy.month
    if anio != 2026:
        print("Este plan es para el período fiscal 2026. Para otro año hay que revisar el formulario.")
        return 2

    control = json.loads(CONTROL.read_text(encoding="utf-8"))
    rng = random.SystemRandom()
    cambios = 0
    for contrato in control["contratos"].values():
        desde = _parse_fecha(contrato["vigencia"]["desde"])
        hasta = _parse_fecha(contrato["vigencia"]["hasta"])
        existentes = {m["mes"] for m in contrato["meses"]}
        nuevos = []
        for m in range(1, mes + 1):
            if m in existentes:
                continue
            if date(2026, m, 1) < desde.replace(day=1) or date(2026, m, 1) > hasta.replace(day=1):
                continue
            importe = importe_para(contrato, m)
            if importe is None:
                print(f"{contrato['archivo']}: falta alquiler_base/mes_inicio; no se puede calcular el mes {m}")
                return 1
            nuevos.append({
                "mes": m,
                "alquiler": importe,
                "deducible": round(importe * 0.40, 2),
                "factura": siguiente_factura(contrato["meses"] + nuevos, rng),
                "fecha": f"01/{m:02d}/2026",
            })
        if not nuevos:
            print(f"{contrato['archivo']}: sin meses nuevos hasta {MESES[mes-1]} {anio}")
            continue
        print(f"\n{contrato['archivo']}: agregar {len(nuevos)} mes(es)")
        for n in nuevos:
            print(f"  {MESES[n['mes']-1]:10} alquiler {n['alquiler']:,.2f}  40% {n['deducible']:,.2f}  factura {n['factura']}")
        if not args.dry_run:
            contrato["meses"] = sorted(contrato["meses"] + nuevos, key=lambda x: x["mes"])
            cambios += len(nuevos)

    if args.dry_run:
        print("\nDRY-RUN: no se modificó el control.")
    elif cambios:
        CONTROL.write_text(json.dumps(control, indent=2, ensure_ascii=False), encoding="utf-8")
        evento("alquiler", "info", "plan_actualizado", hasta=f"{anio}-{mes:02d}", meses_nuevos=cambios)
        print(f"\nControl actualizado: {cambios} mes(es) nuevos. Ahora correr alquiler_cargar.py.")
    else:
        print("\nNo hubo cambios.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
