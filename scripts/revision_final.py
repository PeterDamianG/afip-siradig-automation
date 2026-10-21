"""Arma el informe de revisión final (sólo lectura). NO envía el formulario.

Lee la Vista Previa, el equipamiento y el alquiler por HTTP/control, separa lo
cargado por la automatización de lo preexistente, marca valores sospechosos y
escribe output/revision_final.md.

Uso:  ./.venv/bin/python scripts/revision_final.py
"""
import json
import re
from pathlib import Path

from afip_http import RADIG, sesion_http
from registro import evento
from siradig_http import comprobantes_de_gasto, gastos_servidor, listar_menu

ROOT = Path(__file__).resolve().parent.parent
FACTURAS_JSON = ROOT / "output" / "facturas.json"
PREEXISTENTES_JSON = ROOT / "output" / "preexistentes.json"
ALQUILER_CONTROL = ROOT / "output" / "alquiler" / "control.json"
INFORME = ROOT / "output" / "revision_final.md"
UMBRAL_MONTO_INDIVIDUAL = 1_000_000.0
RANGO_TOTAL = (100_000.0, 50_000_000.0)


def pesos(texto):
    return float(texto.replace(".", "").replace(",", "."))


def fmt(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def total_vista_previa(html):
    txt = re.sub(r"<[^>]+>", " | ", html)
    m = re.search(r"Importe Total:\s*\$\s*\|?\s*\|?\s*([\d.]+,\d{2})", txt)
    return pesos(m.group(1)) if m else None


def cargar_alquiler():
    """Devuelve total deducible, filas mensuales y la nota de la declaración."""
    if not ALQUILER_CONTROL.exists():
        return 0.0, [], None
    control = json.loads(ALQUILER_CONTROL.read_text(encoding="utf-8"))
    filas = []
    total = 0.0
    for contrato in control.get("contratos", {}).values():
        for m in contrato.get("meses", []):
            total += float(m["deducible"])
            filas.append({
                "archivo": contrato.get("archivo"),
                "vigencia": contrato.get("vigencia", {}),
                "mes": m["mes"],
                "alquiler": float(m["alquiler"]),
                "deducible": float(m["deducible"]),
                "factura": m.get("factura"),
            })
    return total, filas, control.get("declaracion_no_titular")


def generar():
    preexistentes = {(c["cuit"], c["pv"], c["numero"])
                     for c in json.loads(PREEXISTENTES_JSON.read_text(encoding="utf-8"))["comprobantes"]}

    with sesion_http() as req:
        vista = req.get(RADIG + "vistaPreviaFormulario.do").body().decode("iso-8859-1")
        total_vp = total_vista_previa(vista)
        gastos = [g for g in gastos_servidor(listar_menu(req)) if g["concepto"] == "Equipamiento"]
        detalle = []
        for g in gastos:
            for c in comprobantes_de_gasto(req, g["idReg"]):
                clave = (g["cuit"], str(c["puntoVenta"]).zfill(5), str(c["numero"]).zfill(8))
                detalle.append({
                    "cuit": g["cuit"], "razon": g["razon"], "mes": g["mes"], "fecha": c["fechaEmision"],
                    "tipo": c["idTipoCmp"], "numero": f"{clave[1]}-{clave[2]}", "monto": float(c["montoFacturado"]),
                    "nuestro": clave not in preexistentes,
                })

    total_gastos = sum(float(g["monto"]) for g in gastos)
    nuestro = sum(d["monto"] for d in detalle if d["nuestro"])
    preexistente = [d for d in detalle if not d["nuestro"]]
    suma_pre = sum(d["monto"] for d in preexistente)
    alquiler_total, alquiler_filas, declaracion = cargar_alquiler()
    total_calculado = total_gastos + alquiler_total

    marcas = []
    for d in detalle:
        if d["monto"] > UMBRAL_MONTO_INDIVIDUAL:
            marcas.append(f"Monto individual alto: {d['razon']} {d['numero']} {fmt(d['monto'])}")
    for d in preexistente:
        marcas.append(f"Preexistente en AFIP (no lo cargó la automatización): {d['razon']}, mes {d['mes']}, "
                      f"{d['numero']}, {d['fecha']}, {fmt(d['monto'])}. Confirmar.")
    if declaracion and not declaracion.get("tildada"):
        marcas.append(f"Declaración noTitular NO tildada. {declaracion.get('nota', '')}")
    if alquiler_total:
        marcas.append(f"Alquiler cargado: {fmt(alquiler_total)} en {len(alquiler_filas)} meses. "
                      "Verificar contrato, aumentos y números de factura.")
    if FACTURAS_JSON.exists():
        for x in json.loads(FACTURAS_JSON.read_text(encoding="utf-8")):
            if x.get("origen") and x["estado"] == "listo":
                marcas.append(f"Leído visualmente (no por texto), confirmar: {x['archivo']} "
                              f"{x.get('emisor_nombre') or ''} {x['pv']}-{x['numero']} {fmt(float(x['monto']))}. {x['origen']}")
            if x["estado"] == "excluido":
                marcas.append(f"Excluido, no se cargó: {x['archivo']}. {x['motivos'][0]}")
    if not (RANGO_TOTAL[0] <= (total_vp or 0) <= RANGO_TOTAL[1]):
        marcas.append(f"Total fuera del rango esperado: {fmt(total_vp or 0)}")
    if total_vp is None or abs(total_vp - total_calculado) > 0.01:
        marcas.append("La Vista Previa no coincide con la suma de equipamiento + alquiler. DETENER.")

    lineas = [
        "# Revisión final: SiRADIG Ganancias — Indumentaria, Equipamiento y Alquiler",
        "",
        "Fuente: Vista Previa (`vistaPreviaFormulario.do`), leída por HTTP. Sin enviar.",
        "",
        "## Total",
        "",
        "| | Monto |",
        "|---|---|",
        f"| **Total Vista Previa** | **$ {fmt(total_vp or 0)}** |",
        f"| Equipamiento cargado por la automatización ({sum(1 for d in detalle if d['nuestro'])} comprobantes) | $ {fmt(nuestro)} |",
        f"| Equipamiento preexistente en AFIP ({len(preexistente)} comprobantes) | $ {fmt(suma_pre)} |",
        f"| Alquiler cargado ({len(alquiler_filas)} meses) | $ {fmt(alquiler_total)} |",
        f"| **Total calculado** | **$ {fmt(total_calculado)}** |",
        "",
        f"Cruce: {fmt(nuestro)} + {fmt(suma_pre)} + {fmt(alquiler_total)} = {fmt(total_calculado)}.",
        "",
        "## Equipamiento por gasto (CUIT + mes)",
        "",
        "| Proveedor | CUIT | Mes | Total gasto | Comprobantes |",
        "|---|---|---|---|---|",
    ]
    for g in sorted(gastos, key=lambda x: (x["razon"], x["mes"])):
        n = sum(1 for d in detalle if d["cuit"] == g["cuit"] and d["mes"] == g["mes"] and d["razon"] == g["razon"])
        lineas.append(f"| {g['razon'][:40]} | {g['cuit']} | {g['mes']} | $ {fmt(float(g['monto']))} | {n} |")

    if alquiler_filas:
        lineas += ["", "## Alquiler", "",
                   "| Contrato | Vigencia | Mes | Alquiler | 40% deducible | Factura |",
                   "|---|---|---|---:|---:|---|"]
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        for f in alquiler_filas:
            v = f["vigencia"]
            lineas.append(f"| {f['archivo']} | {v.get('desde')} a {v.get('hasta')} | {meses[f['mes']-1]} | "
                          f"$ {fmt(f['alquiler'])} | $ {fmt(f['deducible'])} | {f['factura']} |")

    lineas += ["", "## Marcas de revisión", ""]
    lineas += [f"{i}. {m}" for i, m in enumerate(marcas, 1)] or ["Ninguna."]
    lineas += ["", "## Estado", "",
               "- Envío: **no realizado** por este script. Requiere aprobación explícita del usuario.",
               "- Si el envío ya se hizo, ver `output/envio.json`."]
    INFORME.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    evento("revision", "warn" if marcas else "info", "informe", total_vista_previa=total_vp,
           equipamiento=round(nuestro + suma_pre, 2), alquiler=round(alquiler_total, 2),
           preexistente=round(suma_pre, 2), marcas=len(marcas))
    print("\n".join(lineas))
    return total_vp, marcas


if __name__ == "__main__":
    generar()
