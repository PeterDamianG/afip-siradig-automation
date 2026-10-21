"""Activa o desactiva el plugin global opencode-skill-creator.

El plugin crea proyectos temporales para evaluar skills. Se recomienda tenerlo
desactivado por defecto y activarlo sólo cuando se vayan a correr evaluaciones.

Uso:
  ./.venv/bin/python scripts/skill_creator_plugin.py status
  ./.venv/bin/python scripts/skill_creator_plugin.py off
  ./.venv/bin/python scripts/skill_creator_plugin.py on
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

CONFIG = Path.home() / ".config" / "opencode" / "opencode.json"
PAQUETE = "opencode-skill-creator@0.3.6"


def leer():
    if not CONFIG.exists():
        raise SystemExit(f"No existe {CONFIG}")
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def guardar(datos):
    backup = CONFIG.parent / "backup"
    backup.mkdir(exist_ok=True)
    destino = backup / f"opencode.json.{datetime.now():%Y%m%d-%H%M%S}"
    destino.write_text(CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    CONFIG.write_text(json.dumps(datos, indent=2) + "\n", encoding="utf-8")
    print(f"Backup: {destino}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("accion", choices=["status", "on", "off"])
    args = p.parse_args()
    datos = leer()
    plugins = datos.setdefault("plugins", [])
    actuales = [x for x in plugins if str(x).startswith("opencode-skill-creator")]

    if args.accion == "status":
        print("plugins:", plugins or "ninguno")
        print("skill-creator:", "activo" if actuales else "desactivado")
        return 0

    if args.accion == "off":
        datos["plugins"] = [x for x in plugins if not str(x).startswith("opencode-skill-creator")]
        guardar(datos)
        print("opencode-skill-creator desactivado. Reiniciá OpenCode para que desaparezca del contexto.")
    else:
        if not actuales:
            plugins.append(PAQUETE)
        guardar(datos)
        print(f"opencode-skill-creator activado ({PAQUETE}). Reiniciá OpenCode para cargarlo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
