"""Arnés de ruteo: ejecuta pedidos reales contra OpenCode y verifica qué skill se carga.

A diferencia de `skill_eval` (que evalúa un skill aislado y busca su nombre en la
salida), este arnés usa el agente `pagosafip-router-eval`, que sólo puede cargar
skills, y lee del stream JSON el evento `tool_use` con `tool: "skill"`.

Uso:
  ./.venv/bin/python scripts/routing_eval.py
  ./.venv/bin/python scripts/routing_eval.py --only "Extraé"
  ./.venv/bin/python scripts/routing_eval.py --json
  ./.venv/bin/python scripts/routing_eval.py --dry-run
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASOS = ROOT / "evals" / "routing" / "pagosafip.json"
SALIDA = ROOT / "output" / "quality" / "routing_eval.json"
AGENTE = "pagosafip-router-eval"


def comando(query, modelo=None):
    cmd = ["opencode", "run", "--agent", AGENTE, "--format", "json"]
    if modelo:
        cmd += ["--model", modelo]
    cmd.append(query)
    return cmd


def skills_cargados(stdout):
    """Devuelve los ids de skill en orden de carga y el texto de respuesta."""
    cargados, textos = [], []
    for linea in stdout.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            evento = json.loads(linea)
        except json.JSONDecodeError:
            continue
        parte = evento.get("part", {})
        if evento.get("type") == "tool_use" and parte.get("tool") == "skill":
            entrada = parte.get("state", {}).get("input", {})
            if isinstance(entrada, dict) and entrada.get("id"):
                cargados.append(entrada["id"])
        if evento.get("type") == "text":
            textos.append(parte.get("text", ""))
    if not cargados:
        for texto in textos:
            m = re.search(r"SKILL:\s*([a-z0-9-]+)", texto)
            if m:
                cargados.append(m.group(1))
    return cargados, " ".join(textos).strip()


def correr(query, timeout, modelo=None):
    try:
        r = subprocess.run(comando(query, modelo), cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return [], "", f"timeout de {timeout}s"
    if r.returncode != 0:
        return [], "", f"opencode run exit {r.returncode}: {r.stderr[:200]}"
    cargados, texto = skills_cargados(r.stdout)
    return cargados, texto, None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", help="filtra por texto de la consulta")
    p.add_argument("--json", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--model", help="provider/model para las corridas")
    args = p.parse_args()

    casos = json.loads(CASOS.read_text(encoding="utf-8"))
    if args.only:
        casos = [c for c in casos if args.only.lower() in c["query"].lower()]
    if not casos:
        print("No hay casos para esa consulta.")
        return 2

    resultados = []
    for caso in casos:
        query, esperado = caso["query"], caso["expected_skill"]
        if args.dry_run:
            print("DRY:", " ".join(comando(query, args.model)))
            continue
        cargados, texto, error = correr(query, args.timeout, args.model)
        primero = cargados[0] if cargados else None
        ok = primero == esperado
        if ok:
            estado = "OK"
        elif esperado in cargados:
            estado = "ORDEN"
        else:
            estado = "FALLA"
        resultados.append({
            "query": query, "esperado": esperado, "primero": primero,
            "cargados": cargados, "estado": estado, "error": error,
            "respuesta": texto[:300],
        })
        if not args.json:
            print(f"{estado:6} esperado={esperado:28} primero={str(primero):28} cargados={cargados}")
            if error:
                print(f"        ERROR: {error}")

    if args.dry_run:
        return 0

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps({
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "agente": AGENTE,
        "resultados": resultados,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(resultados, indent=2, ensure_ascii=False))
    fallas = [r for r in resultados if r["estado"] == "FALLA"]
    print(f"\nResumen: {len(resultados) - len(fallas)}/{len(resultados)} OK. Guardado en output/quality/routing_eval.json")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
