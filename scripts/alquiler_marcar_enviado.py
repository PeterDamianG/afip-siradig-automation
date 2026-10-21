"""Marca como enviados los registros de alquiler cargados.

Se corre después de enviar la rectificativa. A partir de ahí, los registros no
son editables y el verificador los valida contra el control/PDF.

Uso:
  ./.venv/bin/python scripts/alquiler_marcar_enviado.py --presentacion 4 --fecha 20/10/2026
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / "output" / "alquiler" / "control.json"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--presentacion", required=True, help="número de presentación (ej. 4)")
    p.add_argument("--fecha", required=True, help="fecha de envío dd/mm/aaaa")
    args = p.parse_args()

    control = json.loads(CONTROL.read_text(encoding="utf-8"))
    cambiados = 0
    for contrato in control["contratos"].values():
        for reg in contrato.get("registros", []):
            if reg.get("estado") != "enviado":
                reg["estado"] = "enviado"
                reg["presentacion"] = args.presentacion
                reg["fecha_envio"] = args.fecha
                cambiados += 1
    CONTROL.write_text(json.dumps(control, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"registros marcados como enviados: {cambiados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
