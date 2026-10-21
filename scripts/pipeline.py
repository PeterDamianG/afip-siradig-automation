"""Punto de entrada único del proceso PagosAFIP. Pasos en orden:

  preflight   Verifica entorno, dependencias, credenciales (sin mostrarlas), pruebas de montos y login HTTP.
  extraer     Lee FACTURAS/ y genera output/facturas.json con estado listo / revisar / duplicado / error.
  cargar      Carga por HTTP los comprobantes 'listo' en SiRADIG. Omite los que ya están.
  conciliar   Compara facturas listas contra AFIP.
  validar     Valida la carga en SiRADIG: montos, duplicados, cierre de cada gasto
              y qué comprobantes son preexistentes. Escribe output/validacion.md.
  revision    Arma output/revision_final.md (solo lectura). NUNCA envía.

El envío final NO está en este script. Es una acción irreversible que sólo se hace con
aprobación explícita del usuario, con el skill pagosafip-revision-final.

Uso:  ./.venv/bin/python scripts/pipeline.py <paso> [N | total aprobado]

El paso 'enviar' exige el total aprobado por el usuario, mide el tope antes y sólo envía
si la Vista Previa coincide con ese total.
Cada paso queda registrado en output/estado.json.
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from registro import evento

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PY = str(ROOT / ".venv" / "bin" / "python")
ESTADO = ROOT / "output" / "estado.json"
PASOS = ["preflight", "extraer", "cargar", "conciliar", "validar", "revision", "enviar"]


def registrar(paso, ok, detalle):
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    datos = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}
    datos[paso] = {"ok": ok, "detalle": detalle, "fecha": datetime.now().isoformat(timespec="seconds")}
    ESTADO.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    evento(paso, "info" if ok else "error", "paso_terminado", ok=ok, detalle=str(detalle)[:300])


def correr(script, *args):
    return subprocess.run([PY, str(SCRIPTS / script), *args], cwd=ROOT).returncode


def _ocr_faltantes():
    """OCR sólo es obligatorio si hay contratos de alquiler para leer."""
    alquiler = ROOT / "ALQUILER"
    if not alquiler.is_dir() or not any(alquiler.glob("*.pdf")):
        return []
    faltan = []
    if not shutil.which("tesseract"):
        faltan.append("falta tesseract (brew install tesseract tesseract-lang)")
    else:
        langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True)
        if "spa" not in langs.stdout.split():
            faltan.append("tesseract no tiene el idioma español (brew install tesseract-lang)")
    if not shutil.which("pdftoppm"):
        faltan.append("falta pdftoppm (brew install poppler)")
    for modulo in ["pytesseract", "pdf2image"]:
        if subprocess.run([PY, "-c", f"import {modulo}"], capture_output=True).returncode:
            faltan.append(f"falta el módulo Python {modulo} (pip install -r requirements.txt)")
    return faltan


def preflight(con_login=True):
    fallos = []
    if not Path(PY).exists():
        fallos.append("falta .venv (ver skill pagosafip-preflight)")
    else:
        for modulo in ["playwright", "pdfplumber"]:
            if subprocess.run([PY, "-c", f"import {modulo}"], capture_output=True).returncode:
                fallos.append(f"falta el módulo {modulo}")
    env = ROOT / "credenciales.env"
    if not env.exists():
        fallos.append("falta credenciales.env")
    else:
        claves = {l.split("=", 1)[0].strip() for l in env.read_text(encoding="utf-8").splitlines() if "=" in l}
        for c in ["AFIP_URL", "AFIP_USUARIO", "AFIP_PASSWORD"]:
            if c not in claves:
                fallos.append(f"credenciales.env no tiene {c}")
    if not (ROOT / "FACTURAS").is_dir():
        fallos.append("falta la carpeta FACTURAS")
    fallos.extend(_ocr_faltantes())
    if correr("test_montos.py") != 0:
        fallos.append("fallan las pruebas de montos (scripts/test_montos.py)")
    if correr("test_proveedores.py") != 0:
        fallos.append("fallan las pruebas de proveedores (scripts/test_proveedores.py)")
    if con_login and not fallos:
        codigo = subprocess.run(
            [PY, "-c", "import sys; sys.path.insert(0,'scripts'); from afip_http import sesion_http;"
                       "from playwright.sync_api import sync_playwright\n"
                       "with sesion_http() as r:\n"
                       "    import siradig_http as s; s.listar_menu(r)\n"
                       "print('LOGIN_OK')"],
            cwd=ROOT, capture_output=True, text=True)
        if "LOGIN_OK" not in codigo.stdout:
            fallos.append("el login HTTP a AFIP falló. Ver skill pagosafip-diagnostico (¿clave rotada? ¿captcha?)")
    return fallos


def main(paso, arg):
    evento(paso, "info", "paso_iniciado", argumento=arg)
    if paso == "preflight":
        fallos = preflight(con_login=arg != "--sin-login")
        registrar(paso, not fallos, fallos or "OK")
        print("PREFLIGHT:", "OK" if not fallos else "BLOQUEADO")
        for f in fallos:
            print(" -", f)
        return 0 if not fallos else 1

    if paso == "extraer":
        codigo = correr("pdf_extraer.py")
    elif paso == "cargar":
        codigo = correr("siradig_cargar_lote.py", *([arg] if arg else []))
    elif paso == "conciliar":
        codigo = correr("siradig_conciliar.py")
    elif paso == "validar":
        codigo = correr("validar_carga.py")
    elif paso == "revision":
        codigo = correr("revision_final.py")
    elif paso == "alquiler":
        codigo = correr("alquiler_ocr.py")
        if codigo == 0:
            codigo = correr("alquiler_verificar.py")
    elif paso == "enviar":
        if not arg:
            print("Falta el total aprobado. Uso: pipeline.py enviar <total, ej: 1.234.567,89>")
            return 2
        if correr("tope_medir.py") != 0:
            registrar(paso, False, "bloqueado por tope de carga directa: no se envía")
            print("NO SE ENVÍA: AFIP bloquea el formulario por tope de carga directa.")
            return 1
        codigo = correr("siradig_enviar_ui.py", arg)
    else:
        print("Paso desconocido. Pasos:", ", ".join(PASOS))
        return 2
    registrar(paso, codigo == 0, "OK" if codigo == 0 else f"código {codigo}")
    return codigo


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: pipeline.py <" + "|".join(PASOS) + "> [N]")
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
