"""Valida la carga en SiRADIG contra output/facturas.json (sólo lectura, no modifica nada).

Checks:
  1. Cada comprobante 'listo' del lote está cargado en AFIP con el monto correcto.
  2. En AFIP no hay comprobantes duplicados (mismo CUIT + punto de venta + número).
  3. Cada gasto cierra: total del gasto == suma de los montos de sus comprobantes.
  4. Lo que está en AFIP y no viene del lote está identificado como preexistente
     (o queda marcado como cargado en una corrida anterior, para que el usuario confirme).
  5. Los totales cruzan: lote + preexistentes == total del formulario en la Vista Previa.

Uso:  ./.venv/bin/python scripts/validar_carga.py
Escribe output/validacion.md y output/validacion.json. Devuelve código 1 si algo no cierra.
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from afip_http import RADIG, sesion_http
from registro import evento
from siradig_http import comprobantes_de_gasto, gastos_servidor, listar_menu

ROOT = Path(__file__).resolve().parent.parent
FACTURAS_JSON = ROOT / "output" / "facturas.json"
PREEXISTENTES_JSON = ROOT / "output" / "preexistentes.json"
INFORME_MD = ROOT / "output" / "validacion.md"
INFORME_JSON = ROOT / "output" / "validacion.json"
TOLERANCIA = 0.01


def pesos(texto):
    """Acepta '1234.56', '1.234,56' o '1234'."""
    if texto is None:
        return None
    t = str(texto).strip().replace("$", "").replace(" ", "")
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    return float(t)


def fmt(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def clave_comprobante(cuit, pv, numero):
    return (str(cuit).strip(), str(pv).zfill(5), str(numero).zfill(8))


def total_vista_previa(html):
    txt = re.sub(r"<[^>]+>", " | ", html)
    m = re.search(r"Importe Total:\s*\$\s*\|?\s*\|?\s*([\d.]+,\d{2})", txt)
    return pesos(m.group(1)) if m else None


def volcar_afip():
    """Una sola sesión: lee el menú de gastos y los comprobantes de cada gasto."""
    with sesion_http() as req:
        vista = req.get(RADIG + "vistaPreviaFormulario.do").body().decode("iso-8859-1")
        gastos = gastos_servidor(listar_menu(req))
        detalle = []
        for g in gastos:
            comprobantes = comprobantes_de_gasto(req, g["idReg"])
            for c in comprobantes:
                detalle.append({
                    "idReg": g["idReg"],
                    "cuit": g["cuit"],
                    "razon": g["razon"],
                    "concepto": g["concepto"],
                    "mes": g["mes"],
                    "total_gasto": pesos(g["monto"]),
                    "pv": str(c["puntoVenta"]).zfill(5),
                    "numero": str(c["numero"]).zfill(8),
                    "tipo": c.get("idTipoCmp"),
                    "fecha": c.get("fechaEmision"),
                    "monto": float(c["montoFacturado"]),
                    "codigo": c.get("codigo"),
                })
    return gastos, detalle, total_vista_previa(vista)


def validar(registros, gastos, detalle, total_vp):
    listos = [r for r in registros if r["estado"] == "listo"]
    excluidos = [r for r in registros if r["estado"] == "excluido"]
    duplicados_carpeta = [r for r in registros if r["estado"] == "duplicado"]

    preexistentes = {clave_comprobante(c["cuit"], c["pv"], c["numero"])
                     for c in json.loads(PREEXISTENTES_JSON.read_text(encoding="utf-8"))["comprobantes"]}

    # --- índice de AFIP ---
    en_afip = defaultdict(list)
    for d in detalle:
        en_afip[clave_comprobante(d["cuit"], d["pv"], d["numero"])].append(d)

    # 1. carga del lote
    faltan, montos_distintos = [], []
    for r in listos:
        clave = clave_comprobante(r["emisor_cuit"], r["pv"], r["numero"])
        if clave not in en_afip:
            faltan.append({"archivo": r["archivo"], "cuit": r["emisor_cuit"],
                           "pv": r["pv"], "numero": r["numero"], "monto": float(r["monto"])})
            continue
        monto_afip = en_afip[clave][0]["monto"]
        if abs(monto_afip - float(r["monto"])) > TOLERANCIA:
            montos_distintos.append({"archivo": r["archivo"], "pv": r["pv"], "numero": r["numero"],
                                      "monto_lote": float(r["monto"]), "monto_afip": monto_afip})

    # 2. duplicados dentro de AFIP
    dups_afip = [{"cuit": k[0], "pv": k[1], "numero": k[2], "veces": len(v),
                  "montos": [x["monto"] for x in v],
                  "gastos": [f"{x['razon'][:30]} {x['mes']}" for x in v]}
                 for k, v in en_afip.items() if len(v) > 1]

    # 2b. duplicados dentro del propio lote (mismo comprobante en dos archivos 'listo')
    vistos = defaultdict(list)
    for r in listos:
        vistos[clave_comprobante(r["emisor_cuit"], r["pv"], r["numero"])].append(r["archivo"])
    dups_lote = [{"cuit": k[0], "pv": k[1], "numero": k[2], "archivos": v}
                 for k, v in vistos.items() if len(v) > 1]

    # 2c. mismo CUIT + punto de venta + fecha + monto con números distintos.
    # No es un duplicado formal, pero puede ser un doble conteo: hay que confirmarlo a mano.
    patron = defaultdict(list)
    for d in detalle:
        patron[(d["cuit"], d["pv"], d["fecha"], round(d["monto"], 2))].append(d)
    posibles_iguales = [
        {"cuit": k[0], "pv": k[1], "fecha": k[2], "monto": k[3],
         "comprobantes": [f"{x['pv']}-{x['numero']}" for x in v],
         "mes": v[0]["mes"], "razon": v[0]["razon"]}
        for k, v in sorted(patron.items()) if len(v) > 1
    ]

    # 3. cierre por gasto
    por_gasto = defaultdict(list)
    for d in detalle:
        por_gasto[d["idReg"]].append(d)
    cierres = []
    for g in gastos:
        comps = por_gasto.get(g["idReg"], [])
        total_gasto = pesos(g["monto"])
        suma = sum(c["monto"] for c in comps)
        if abs(total_gasto - suma) > TOLERANCIA:
            cierres.append({"idReg": g["idReg"], "cuit": g["cuit"], "razon": g["razon"],
                            "mes": g["mes"], "concepto": g["concepto"],
                            "total_gasto": total_gasto, "suma_comprobantes": round(suma, 2),
                            "diferencia": round(total_gasto - suma, 2),
                            "comprobantes": len(comps)})

    # 4. lo que está en AFIP y no viene del lote
    claves_lote = set(vistos)
    extras = []
    for clave, comps in en_afip.items():
        if clave in claves_lote:
            continue
        d = comps[0]
        extras.append({
            "cuit": clave[0], "pv": clave[1], "numero": clave[2],
            "razon": d["razon"], "mes": d["mes"], "concepto": d["concepto"],
            "fecha": d["fecha"], "monto": d["monto"],
            "origen": "preexistente" if clave in preexistentes else "corrida_anterior",
        })
    extras_preexistentes = [e for e in extras if e["origen"] == "preexistente"]
    extras_no_identificados = [e for e in extras if e["origen"] == "corrida_anterior"]

    # 5. totales
    total_lote = round(sum(float(r["monto"]) for r in listos), 2)
    total_afip = round(sum(d["monto"] for d in detalle), 2)
    total_gastos = round(sum(pesos(g["monto"]) for g in gastos), 2)
    total_excluidos = round(sum(float(r["monto"]) for r in excluidos), 2)
    total_preexistentes = round(sum(e["monto"] for e in extras_preexistentes), 2)
    total_no_identificados = round(sum(e["monto"] for e in extras_no_identificados), 2)

    cruces = []
    if total_vp is not None and abs(total_vp - total_afip) > TOLERANCIA:
        cruces.append(f"Vista Previa {fmt(total_vp)} != suma de comprobantes AFIP {fmt(total_afip)}")
    if abs(total_afip - total_gastos) > TOLERANCIA:
        cruces.append(f"Suma de comprobantes {fmt(total_afip)} != suma de gastos {fmt(total_gastos)}")
    if abs((total_lote + total_preexistentes + total_no_identificados) - total_afip) > TOLERANCIA:
        cruces.append("Lote + preexistentes + corridas anteriores no cierra con el total de AFIP")

    ok = not (faltan or montos_distintos or dups_afip or dups_lote or cierres or cruces)

    return {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "ok": ok,
        "totales": {
            "vista_previa": total_vp,
            "total_afip_comprobantes": total_afip,
            "total_afip_gastos": total_gastos,
            "lote_listo": total_lote,
            "lote_listo_cantidad": len(listos),
            "preexistentes": total_preexistentes,
            "preexistentes_cantidad": len(extras_preexistentes),
            "corridas_anteriores": total_no_identificados,
            "corridas_anteriores_cantidad": len(extras_no_identificados),
            "excluido_no_cargado": total_excluidos,
            "excluido_cantidad": len(excluidos),
            "duplicados_carpeta_no_cargados": len(duplicados_carpeta),
        },
        "faltan": faltan,
        "montos_distintos": montos_distintos,
        "duplicados_afip": dups_afip,
        "duplicados_lote": dups_lote,
        "posibles_iguales": posibles_iguales,
        "gastos_no_cierran": cierres,
        "extras_no_identificados": extras_no_identificados,
        "cruces": cruces,
        "extras": extras,
    }


def informe_md(d):
    t = d["totales"]
    lineas = [
        "# Validación de carga en SiRADIG (sólo lectura)",
        "",
        f"Fecha: {d['fecha']}. Fuente: `verMenuDeducciones.do` + `verGastosInduEquip.do` + "
        "`vistaPreviaFormulario.do` por HTTP.",
        "",
        "## Resultado",
        "",
        f"**{'TODO OK' if d['ok'] else 'HAY PROBLEMAS'}**",
        "",
        "| | Valor |",
        "|---|---|",
        f"| Total Vista Previa | $ {fmt(t['vista_previa'] or 0)} |",
        f"| Suma de comprobantes en AFIP | $ {fmt(t['total_afip_comprobantes'])} |",
        f"| Suma de totales de gastos | $ {fmt(t['total_afip_gastos'])} |",
        f"| Lote 'listo' del proyecto ({t['lote_listo_cantidad']} comprobantes) | $ {fmt(t['lote_listo'])} |",
        f"| Preexistentes ({t['preexistentes_cantidad']}) | $ {fmt(t['preexistentes'])} |",
        f"| De corridas anteriores ({t['corridas_anteriores_cantidad']}) | $ {fmt(t['corridas_anteriores'])} |",
        "",
        "## Chequeos",
        "",
        f"- Faltan en AFIP: {len(d['faltan'])}",
        f"- Montos distintos: {len(d['montos_distintos'])}",
        f"- Duplicados en AFIP: {len(d['duplicados_afip'])}",
        f"- Duplicados en el lote: {len(d['duplicados_lote'])}",
        f"- Mismo CUIT + PV + fecha + monto con números distintos (a confirmar): {len(d['posibles_iguales'])}",
        f"- Gastos que no cierran con sus comprobantes: {len(d['gastos_no_cierran'])}",
        f"- Comprobantes en AFIP sin identificar: {len(d['extras_no_identificados'])}",
        f"- Cruces de total que no cierran: {len(d['cruces'])}",
        "",
    ]
    if d["faltan"]:
        lineas += ["## Faltan en AFIP", "", "| Archivo | CUIT | PV | Número | Monto |", "|---|---|---|---|---|"]
        lineas += [f"| {f['archivo']} | {f['cuit']} | {f['pv']} | {f['numero']} | $ {fmt(f['monto'])} |"
                   for f in d["faltan"]]
        lineas += [""]
    if d["montos_distintos"]:
        lineas += ["## Montos que difieren", "", "| Archivo | Comprobante | Lote | AFIP |", "|---|---|---|---|"]
        lineas += [f"| {m['archivo']} | {m['pv']}-{m['numero']} | $ {fmt(m['monto_lote'])} | $ {fmt(m['monto_afip'])} |"
                   for m in d["montos_distintos"]]
        lineas += [""]
    if d["duplicados_afip"]:
        lineas += ["## Duplicados en AFIP", "", "| CUIT | PV | Número | Veces | Montos | Gastos |", "|---|---|---|---|---|---|"]
        lineas += [f"| {x['cuit']} | {x['pv']} | {x['numero']} | {x['veces']} | "
                   f"{', '.join(fmt(m) for m in x['montos'])} | {'; '.join(x['gastos'])} |"
                   for x in d["duplicados_afip"]]
        lineas += [""]
    if d["posibles_iguales"]:
        lineas += ["## A confirmar: mismo CUIT + punto de venta + fecha + monto, números distintos",
                   "", "No es un duplicado formal, pero puede ser un doble conteo.", "",
                   "| CUIT | Razón social | Mes | Fecha | Monto | Comprobantes |", "|---|---|---|---|---|---|"]
        lineas += [f"| {p['cuit']} | {p['razon'][:30]} | {p['mes']} | {p['fecha']} | $ {fmt(p['monto'])} | "
                   f"{'; '.join(p['comprobantes'])} |" for p in d["posibles_iguales"]]
        lineas += [""]
    if d["gastos_no_cierran"]:
        lineas += ["## Gastos que no cierran", "",
                   "| CUIT | Razón social | Mes | Total gasto | Suma comprobantes | Diferencia | Comprobantes |",
                   "|---|---|---|---|---|---|---|"]
        lineas += [f"| {c['cuit']} | {c['razon'][:30]} | {c['mes']} | $ {fmt(c['total_gasto'])} | "
                   f"$ {fmt(c['suma_comprobantes'])} | $ {fmt(c['diferencia'])} | {c['comprobantes']} |"
                   for c in d["gastos_no_cierran"]]
        lineas += [""]
    if d["extras_no_identificados"]:
        lineas += ["## Comprobantes en AFIP que no vienen del lote actual (corridas anteriores)",
                   "", "| CUIT | Razón social | Mes | Comprobante | Fecha | Monto |", "|---|---|---|---|---|---|"]
        lineas += [f"| {e['cuit']} | {e['razon'][:30]} | {e['mes']} | {e['pv']}-{e['numero']} | "
                   f"{e['fecha']} | $ {fmt(e['monto'])} |" for e in d["extras_no_identificados"]]
        lineas += [""]
    if d["cruces"]:
        lineas += ["## Cruces que no cierran", ""] + [f"- {c}" for c in d["cruces"]] + [""]
    return "\n".join(lineas) + "\n"


def main():
    registros = json.loads(FACTURAS_JSON.read_text(encoding="utf-8"))
    gastos, detalle, total_vp = volcar_afip()
    d = validar(registros, gastos, detalle, total_vp)
    INFORME_JSON.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    INFORME_MD.write_text(informe_md(d), encoding="utf-8")
    evento("validar", "info" if d["ok"] else "error", "validacion",
           ok=d["ok"], faltan=len(d["faltan"]), montos_distintos=len(d["montos_distintos"]),
           duplicados_afip=len(d["duplicados_afip"]), gastos_no_cierran=len(d["gastos_no_cierran"]),
           extras_no_identificados=len(d["extras_no_identificados"]), total_vp=d["totales"]["vista_previa"])
    print(informe_md(d))
    return 0 if d["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
