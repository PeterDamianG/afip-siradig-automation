"""Carga en AFIP los meses del plan que todavía no tienen registro.

- Si un contrato ya tiene todos los meses cubiertos por registros (enviados o
  cargados), lo omite.
- Si hay meses nuevos, crea un registro nuevo sólo con esos meses.
- Es idempotente.

Uso:
  ./.venv/bin/python scripts/alquiler_cargar.py --dry-run
  ./.venv/bin/python scripts/alquiler_cargar.py
  ./.venv/bin/python scripts/alquiler_cargar.py --contrato <sha256>
"""
import argparse
import json
import sys
from pathlib import Path

from afip_http import sesion_http
from alquiler_http import guardar_alquiler
from registro import evento

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / "output" / "alquiler" / "control.json"


def _total(meses):
    return sum(float(m["deducible"]) for m in meses)


def _buscar_id(respuesta, cuit, total):
    filas = respuesta.get("datos", {}).get("filas", [])
    objetivo = f"{total:.2f}"
    for fila in reversed(filas):
        celdas = fila.get("celdas", [])
        if len(celdas) >= 4 and celdas[0] == cuit and celdas[3] == objetivo:
            return fila.get("idReg")
    return None


def _registros(contrato):
    return contrato.setdefault("registros", [])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--contrato", help="SHA-256 de un contrato específico")
    args = p.parse_args()

    control = json.loads(CONTROL.read_text(encoding="utf-8"))
    cambios = False
    with sesion_http() as req:
        for sha, contrato in control["contratos"].items():
            if args.contrato and sha != args.contrato:
                continue
            cubiertos = {m["mes"] for r in _registros(contrato) for m in r["meses"]}
            pendientes = [m for m in contrato["meses"] if m["mes"] not in cubiertos]
            if not pendientes:
                print(f"{contrato['archivo']}: todos los meses ya tienen registro")
                continue
            total = _total(pendientes)
            print(f"{contrato['archivo']}: {len(pendientes)} meses pendientes, total deducible {total:,.2f}")
            if args.dry_run:
                for m in pendientes:
                    print(f"  mes {m['mes']:2}  alquiler {float(m['alquiler']):,.2f}  "
                          f"40% {float(m['deducible']):,.2f}  factura {m['factura']}")
                continue
            nuevo = {**contrato, "meses": pendientes}
            status, respuesta = guardar_alquiler(req, nuevo)
            print(f"  HTTP {status}  estado={respuesta.get('estado')}")
            if respuesta.get("estado") != "ok":
                print("  respuesta:", json.dumps(respuesta, ensure_ascii=False)[:500])
                break
            registro = _buscar_id(respuesta, contrato["locador"]["cuit"], total)
            if not registro:
                print("  no se pudo identificar el registro en la respuesta; revisar a mano")
                break
            _registros(contrato).append({"registro_id": str(registro), "meses": pendientes, "estado": "cargado"})
            cambios = True
            evento("alquiler", "info", "cargado", archivo=contrato["archivo"], registro_id=str(registro),
                   meses=[m["mes"] for m in pendientes], total=round(total, 2))
            print(f"  registro: {registro}")

    if cambios:
        CONTROL.write_text(json.dumps(control, indent=2, ensure_ascii=False), encoding="utf-8")
        print("control actualizado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
