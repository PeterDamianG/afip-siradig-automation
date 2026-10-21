"""Registro simple de lo que hace el proceso. Un JSON por línea en output/logs/AAAA-MM-DD.jsonl

Cada línea: {"ts", "sesion", "paso", "nivel", "evento", "detalle"}
- nivel: info | warn | error
- Nunca se guardan claves, tokens, cookies ni firmas: los campos con esos nombres se redactan.

Uso desde código:   from registro import evento;  evento("cargar", "info", "comprobante", archivo=..., estado=...)
Uso desde consola:  ./.venv/bin/python scripts/registro.py ver                 (últimas 40 líneas)
                    ./.venv/bin/python scripts/registro.py ver --nivel error  (sólo errores y avisos)
                    ./.venv/bin/python scripts/registro.py resumen            (conteo por paso y evento de hoy)
"""
import argparse
import json
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "output" / "logs"
SESION = uuid.uuid4().hex[:8]
SENSIBLES = ("password", "clave", "token", "sign", "jwt", "cookie", "viewstate", "authorization")


def _limpiar(detalle):
    limpio = {}
    for k, v in detalle.items():
        if any(s in k.lower() for s in SENSIBLES):
            limpio[k] = "<REDACTADO>"
        elif isinstance(v, str) and len(v) > 300:
            limpio[k] = v[:300] + "…"
        else:
            limpio[k] = v
    return limpio


def evento(paso, nivel, nombre, **detalle):
    LOGS.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now()
    linea = {
        "ts": ahora.isoformat(timespec="seconds"),
        "sesion": SESION,
        "paso": paso,
        "nivel": nivel,
        "evento": nombre,
        "detalle": _limpiar(detalle),
    }
    with open(LOGS / f"{ahora:%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(linea, ensure_ascii=False, default=str) + "\n")


def _leer(fecha=None):
    archivo = LOGS / f"{fecha or datetime.now():%Y-%m-%d}.jsonl"
    if not archivo.exists():
        return []
    return [json.loads(l) for l in archivo.read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    ver = sub.add_parser("ver")
    ver.add_argument("--nivel", choices=["info", "warn", "error"])
    ver.add_argument("--ultimos", type=int, default=40)
    ver.add_argument("--fecha")
    res = sub.add_parser("resumen")
    res.add_argument("--fecha")
    args = p.parse_args()

    lineas = _leer(getattr(args, "fecha", None))
    if args.cmd == "ver":
        if args.nivel:
            lineas = [l for l in lineas if l["nivel"] == args.nivel or (args.nivel == "warn" and l["nivel"] == "error")]
        for l in lineas[-args.ultimos:]:
            print(f"{l['ts']} [{l['sesion']}] {l['nivel'].upper():5} {l['paso']}/{l['evento']} {json.dumps(l['detalle'], ensure_ascii=False)}")
    else:
        conteo = Counter((l["paso"], l["evento"], l["nivel"]) for l in lineas)
        for (paso, evt, nivel), n in sorted(conteo.items()):
            print(f"{paso:12} {evt:24} {nivel:6} {n}")
        if not lineas:
            print("Sin registros para esa fecha.")


if __name__ == "__main__":
    sys.exit(main())
