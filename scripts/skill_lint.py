"""Linter genérico de skills y agentes de OpenCode.

Funciona en cualquier proyecto. Busca skills en `.opencode/skills`, `.claude/skills`
y `.agents/skills` (y sus equivalentes de agentes), o recibe rutas explícitas.

Uso:
  python3 skill_lint.py                 # proyecto actual
  python3 skill_lint.py --root ~/otro   # otro proyecto
  python3 skill_lint.py --json          # salida para CI
  python3 skill_lint.py ruta/al/skill ruta/al/agente.md

Código de salida: 0 sin errores, 1 con errores.
"""
import json
import re
import sys
from pathlib import Path

RESERVADOS = {"anthropic", "claude"}
NOMBRE_OK = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RUTA_WINDOWS = re.compile(r"(?<![\w/])(?:[A-Za-z]:\\|\\\\)")
LINK_MD = re.compile(r"\[[^\]]+\]\(([^)]+\.md)\)")
DIRS_SKILLS = [".opencode/skills", ".claude/skills", ".agents/skills", "skills", ".config/opencode/skills"]
DIRS_AGENTS = [".opencode/agents", ".claude/agents", ".agents/agents", "agents", ".config/opencode/agents"]


def _frontmatter(texto):
    if not texto.startswith("---"):
        return None, texto
    fin = texto.find("\n---", 3)
    if fin == -1:
        return None, texto
    crudo = texto[3:fin].strip("\n")
    resto = texto[fin + 4:]
    datos = {}
    for linea in crudo.splitlines():
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        if linea[0].isspace() or ":" not in linea:
            continue
        clave, valor = linea.split(":", 1)
        datos[clave.strip()] = valor.strip().strip('"').strip("'")
    return datos, resto


def _revisar_skill(carpeta):
    problemas, avisos = [], []
    archivo = carpeta / "SKILL.md"
    if not archivo.exists():
        return ["falta SKILL.md"], []
    texto = archivo.read_text(encoding="utf-8")
    fm, cuerpo = _frontmatter(texto)
    if fm is None:
        return ["frontmatter ausente o mal cerrado"], []
    nombre = fm.get("name", "")
    desc = fm.get("description", "")
    if not nombre:
        problemas.append("falta name")
    elif len(nombre) > 64:
        problemas.append("name supera 64 caracteres")
    elif not NOMBRE_OK.match(nombre):
        problemas.append("name debe ser minúsculas, números y guiones")
    if any(r in nombre.lower() for r in RESERVADOS):
        problemas.append("name usa una palabra reservada")
    if nombre and nombre != carpeta.name:
        avisos.append(f"name ({nombre}) distinto del directorio ({carpeta.name})")
    if not desc:
        problemas.append("falta description")
    else:
        if "\n" in desc:
            problemas.append("description debe ser una sola línea")
        if len(desc) > 1024:
            problemas.append("description supera 1024 caracteres")
        if len(desc) < 40:
            avisos.append("description muy corta")
        if re.match(r"^(i|you|te|puedo|voy a)\b", desc.lower()):
            avisos.append("description no está en tercera persona")
        if not re.search(r"usar cuando|use when|usar al|usar antes|usar después|usar despues|usar siempre|usar sólo|usar solo|usar en|cuando|para ", desc.lower()):
            avisos.append("description no indica cuándo usarse")
    linea_desc = re.search(r"^description:\s*(.+)$", texto, re.M)
    if linea_desc and ": " in linea_desc.group(1) and not linea_desc.group(1).strip().startswith('"'):
        problemas.append("description con ': ' debe ir entre comillas (YAML estricto)")
    lineas = cuerpo.count("\n") + 1
    if lineas > 500:
        problemas.append(f"cuerpo de {lineas} líneas (máximo recomendado 500)")
    cuerpo_sin_codigo = re.sub(r"```.*?```", "", cuerpo, flags=re.S)
    if RUTA_WINDOWS.search(cuerpo_sin_codigo):
        avisos.append("posible ruta estilo Windows fuera de un bloque de código")
    for ref in LINK_MD.findall(cuerpo):
        if ref.startswith(("http://", "https://", "#")):
            continue
        ruta = (carpeta / ref).resolve()
        if not str(ruta).startswith(str(carpeta.resolve())):
            avisos.append(f"referencia fuera del skill: {ref}")
        if not ruta.exists():
            problemas.append(f"referencia inexistente: {ref}")
        elif LINK_MD.findall(ruta.read_text(encoding="utf-8")):
            avisos.append(f"referencia anidada dentro de {ref}")
    return problemas, avisos


def _revisar_agente(archivo):
    problemas, avisos = [], []
    texto = archivo.read_text(encoding="utf-8")
    fm, _ = _frontmatter(texto)
    if fm is None:
        return ["frontmatter ausente o mal cerrado"], []
    if not fm.get("description"):
        problemas.append("falta description")
    modo = fm.get("mode", "")
    if modo and modo not in ("primary", "subagent", "all"):
        problemas.append(f"mode inválido: {modo}")
    if "permissions:" in texto:
        if re.search(r"action:\s*edit\s*\n\s*resource:\s*\"?credenciales\.env\"?\s*\n\s*effect:\s*allow", texto):
            problemas.append("permite editar credenciales.env")
        if re.search(r"action:\s*shell\s*\n\s*resource:\s*\"\*\"\s*\n\s*effect:\s*allow", texto):
            avisos.append("permite shell sin restricción")
    else:
        avisos.append("sin permissions: el agente hereda las globales")
    return problemas, avisos


def _descubrir(root):
    skills, agents = [], []
    for base in DIRS_SKILLS:
        d = root / base
        if d.is_dir():
            skills += [p for p in sorted(d.glob("*/")) if (p / "SKILL.md").exists()]
    for base in DIRS_AGENTS:
        d = root / base
        if d.is_dir():
            agents += sorted(d.glob("*.md"))
    return skills, agents


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    como_json = "--json" in sys.argv
    root = Path.cwd()
    if "--root" in sys.argv:
        i = sys.argv.index("--root")
        if i + 1 >= len(sys.argv):
            print("Falta el valor de --root", file=sys.stderr)
            return 2
        root = Path(sys.argv[i + 1]).expanduser().resolve()
        args = [a for a in args if a != sys.argv[i + 1]]

    filas = []
    if args:
        objetivos = [Path(a).expanduser().resolve() for a in args]
        for o in objetivos:
            if (o / "SKILL.md").exists():
                filas.append(("skill", o.name, *_revisar_skill(o)))
            elif o.suffix == ".md":
                filas.append(("agent", o.stem, *_revisar_agente(o)))
            else:
                filas.append(("?", o.name, ["no es skill ni agente"], []))
    else:
        skills, agents = _descubrir(root)
        for carpeta in skills:
            filas.append(("skill", carpeta.name, *_revisar_skill(carpeta)))
        for archivo in agents:
            filas.append(("agent", archivo.stem, *_revisar_agente(archivo)))
        if not filas:
            print(f"No se encontraron skills ni agentes en {root}")
            return 0

    if como_json:
        print(json.dumps([{"tipo": t, "nombre": n, "problemas": p, "avisos": a} for t, n, p, a in filas], indent=2, ensure_ascii=False))
    else:
        for tipo, nombre, problemas, avisos in filas:
            estado = "ERROR" if problemas else ("AVISO" if avisos else "OK")
            print(f"{tipo:6} {nombre:34} {estado:6} {len(problemas)} errores, {len(avisos)} avisos")
            for p in problemas:
                print(f"        ERROR: {p}")
            for a in avisos:
                print(f"        AVISO: {a}")
        print(f"\nResumen: {len(filas)} archivos, {sum(len(p) for _, _, p, _ in filas)} errores, {sum(len(a) for _, _, _, a in filas)} avisos")
    return 1 if any(p for _, _, p, _ in filas) else 0


if __name__ == "__main__":
    sys.exit(main())
