"""Limpia sesiones y carpetas temporales del evaluador opencode-skill-creator.

El plugin crea proyectos temporales `opencode-skill-eval-*`, los borra al terminar
y deja sesiones que el escritorio puede seguir intentando abrir ("Location not
found"). Este script elimina las sesiones por la API de OpenCode y borra las
carpetas temporales que hayan quedado.

Uso:
  ./.venv/bin/python scripts/limpiar_eval_sessions.py --dry-run
  ./.venv/bin/python scripts/limpiar_eval_sessions.py
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import tempfile


def sesiones():
    r = subprocess.run(["opencode", "api", "get", "/api/session"], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"No se pudo consultar la API de OpenCode: {r.stderr[:300]}")
    return json.loads(r.stdout).get("data", [])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    evals = [s for s in sesiones() if "/opencode-skill-eval-" in s.get("location", {}).get("directory", "")]
    print(f"Sesiones de evaluación: {len(evals)}")
    for s in evals:
        print(f"  {s['id']}  {s['location']['directory'].split('/')[-1]}  {s['title'][:50]}")
    if not args.dry_run:
        borradas = inexistentes = 0
        for s in evals:
            r = subprocess.run(
                ["opencode", "api", "session.remove", "--param", f"sessionID={s['id']}"],
                capture_output=True, text=True,
            )
            if "SessionNotFound" in (r.stdout + r.stderr):
                inexistentes += 1
            elif r.returncode == 0:
                borradas += 1
        print(f"Borradas: {borradas} | ya no existían: {inexistentes}")

    temporales = glob.glob(os.path.join(tempfile.gettempdir(), "opencode-skill-eval-*"))
    print(f"Carpetas temporales: {len(temporales)}")
    for d in temporales:
        print(f"  {d}")
        if not args.dry_run:
            shutil.rmtree(d, ignore_errors=True)

    if args.dry_run:
        print("DRY-RUN: no se modificó nada.")
    else:
        print("Limpieza terminada. Si el escritorio sigue mostrando avisos, reiniciá OpenCode.")


if __name__ == "__main__":
    main()
