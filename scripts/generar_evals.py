"""Genera los sets de evaluación de disparo (trigger evals) para los skills de AFIP.

Formato del plugin opencode-skill-creator:
  [{"query": "...", "should_trigger": true|false}, ...]

Uso:  ./.venv/bin/python scripts/generar_evals.py
Escribe evals/triggers/<skill>.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SALIDA = ROOT / "evals" / "triggers"

CASOS = {
    "pagosafip-preflight": [
        ("¿Está todo listo para empezar a cargar facturas en AFIP hoy?", True),
        ("Chequeá que tengamos el entorno, las credenciales y Playwright antes de arrancar", True),
        ("Corré el preflight de PagosAFIP", True),
        ("Antes de cargar, verificá que no falte ninguna dependencia", True),
        ("¿Tenemos todo instalado para procesar las facturas?", True),
        ("Instalá Playwright en un proyecto de otra carpeta", False),
        ("Revisá el login de AFIP y decime si la clave funciona", False),
        ("Cargá las facturas nuevas en SiRADIG", False),
    ],
    "pagosafip-pdf-intake": [
        ("Tengo 60 facturas nuevas en FACTURAS, revisalas y decime cuáles se pueden cargar", True),
        ("Extraé CUIT, fecha, número y total de los PDFs", True),
        ("¿Qué facturas quedaron en revisar y por qué?", True),
        ("Detectá duplicados entre las facturas de la carpeta", True),
        ("Agregá un proveedor nuevo al extractor de PDFs", True),
        ("¿Cómo se calcula el IVA de una factura?", False),
        ("Conciliá lo que ya está cargado en AFIP", False),
        ("Enviá el formulario al empleador", False),
    ],
    "pagosafip-siradig-http": [
        ("Cargá estas facturas en SiRADIG por HTTP", True),
        ("Agregá un comprobante a un gasto de mayo que ya existe", True),
        ("Quitá del borrador un comprobante de marzo", True),
        ("Medí si el formulario está bloqueado por el tope de carga directa", True),
        ("¿Cómo se hace el POST para guardar un gasto de equipamiento?", True),
        ("Leé los PDFs de la carpeta FACTURAS", False),
        ("Armá el informe final antes de enviar", False),
        ("Revisá los logs de la última corrida", False),
    ],
    "pagosafip-playwright": [
        ("Abrí el navegador y mostrame la pantalla de AFIP", True),
        ("El HTTP falló, probá con el navegador visible", True),
        ("Revisá en pantalla el listado de formularios enviados", True),
        ("Necesito ver la Vista Previa en el navegador antes de decidir", True),
        ("Usá Playwright para mirar el formulario de SiRADIG", True),
        ("Cargá las facturas por HTTP", False),
        ("Extraé el texto de estos PDFs", False),
        ("Conciliá los comprobantes contra AFIP", False),
    ],
    "pagosafip-validator": [
        ("Verificá que todas las facturas se hayan cargado bien en AFIP", True),
        ("Conciliá las facturas del lote contra lo que está en SiRADIG", True),
        ("Chequeá que el total de cada gasto cierre con sus comprobantes", True),
        ("¿Quedó algún comprobante duplicado en AFIP?", True),
        ("Decime si falta cargar algo del lote", True),
        ("Cargá las facturas que faltan", False),
        ("Generá el informe para enviar al empleador", False),
        ("Leé y validá los PDFs de la carpeta", False),
    ],
    "pagosafip-revision-final": [
        ("Armá la revisión final antes de enviar el formulario", True),
        ("¿Podemos enviar el formulario? Mostrame totales y marcas", True),
        ("Generá el informe con los totales y lo que hay que confirmar", True),
        ("Prepará el envío de la rectificativa con el total aprobado", True),
        ("Quiero revisar todo antes del último clic", True),
        ("Cargá las facturas nuevas", False),
        ("Extraé los datos de los PDFs", False),
        ("Revisá los logs de errores", False),
    ],
    "pagosafip-diagnostico": [
        ("Falló el login de AFIP, ¿qué hago?", True),
        ("La carga devolvió un error de AFIP y no sé qué significa", True),
        ("Cargué un comprobante pero no aparece en AFIP", True),
        ("El envío dio un resultado dudoso y no sé si se mandó", True),
        ("¿Por qué la Vista Previa dice que supera el tope?", True),
        ("Cargá las facturas nuevas en SiRADIG", False),
        ("Armá el informe final para revisión", False),
        ("Extraé los datos de estos PDFs", False),
    ],
    "pagosafip-observabilidad": [
        ("Mirá los logs de la última corrida y decime qué pasó", True),
        ("¿Qué errores hubo ayer con la carga de facturas?", True),
        ("Revisá el registro de la sesión anterior", True),
        ("¿Cuántos comprobantes se cargaron y cuántos se omitieron hoy?", True),
        ("Mostrame el historial de pasos del pipeline", True),
        ("Activá logs en un proyecto nuevo", False),
        ("Cargá las facturas en AFIP", False),
        ("Mejorá la descripción de este skill", False),
    ],
}


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    for skill, casos in CASOS.items():
        datos = [{"query": q, "should_trigger": t} for q, t in casos]
        (SALIDA / f"{skill}.json").write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{skill}: {len(datos)} casos ({sum(1 for _, t in casos if t)} disparan, {sum(1 for _, t in casos if not t)} no)")
    print(f"Escritos en {SALIDA}")


if __name__ == "__main__":
    main()
