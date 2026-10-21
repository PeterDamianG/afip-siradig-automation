"""Extrae y valida los comprobantes de FACTURAS/ y escribe output/facturas.json.

Estados por comprobante:
- listo:     proveedor conocido, todos los campos válidos, sin duplicado.
- revisar:   falta algún campo, proveedor no reconocido o monto fuera de rango. Un humano lo confirma.
- duplicado: mismo CUIT emisor + punto de venta + número que otro archivo. No se carga.
- error:     el PDF no tiene texto o no se pudo leer.

Uso:  ./.venv/bin/python scripts/pdf_extraer.py
"""
import csv
import glob
import json
import os
import re
from datetime import datetime
from pathlib import Path

import pdfplumber

from cuit import cuit_valido
from montos import MontoAmbiguo, monto_a_decimal
from proveedores import CUIT_USUARIO, extraer_generico, identificar
from registro import evento

ROOT = Path(__file__).resolve().parent.parent
FACTURAS = ROOT / "FACTURAS"
SALIDA = ROOT / "output" / "facturas.json"
CSV_SALIDA = ROOT / "output" / "extracto.csv"
MONTO_MAXIMO = 50_000_000.0
PERIODO_ANIO = 2026
CONFIRMADOS_JSON = ROOT / "output" / "confirmados_manual.json"
CONFIRMADOS = json.loads(CONFIRMADOS_JSON.read_text(encoding="utf-8")) if CONFIRMADOS_JSON.exists() else {}


def leer_texto(ruta):
    """dedupe_chars elimina las letras dibujadas dos veces (texto en negrita o contorneado)."""
    with pdfplumber.open(ruta) as pdf:
        return "\n".join((p.dedupe_chars(tolerance=1).extract_text() or "") for p in pdf.pages)


def normalizar_fecha(fecha):
    """'15/5/26' -> '15/05/2026'. Devuelve None si no es una fecha real."""
    if not fecha:
        return None
    for formato in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(fecha, formato).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return None


def fecha_valida(fecha):
    return normalizar_fecha(fecha) is not None


def normalizar(crudo, proveedor_id):
    r = {"proveedor": proveedor_id or "generico", "motivos": []}
    r["emisor_cuit"] = crudo.get("emisor_cuit")
    r["emisor_nombre"] = crudo.get("emisor_nombre")
    r["tipo_afip"] = crudo.get("tipo_afip")
    r["tipo_texto"] = crudo.get("tipo_texto")
    r["pv"] = (crudo.get("pv") or "").zfill(5) if crudo.get("pv") else None
    r["numero"] = (crudo.get("numero") or "").zfill(8) if crudo.get("numero") else None
    r["fecha"] = normalizar_fecha(crudo.get("fecha"))
    r["total_texto"] = crudo.get("total")

    if not proveedor_id:
        r["motivos"].append("proveedor no reconocido")
    if not r["emisor_cuit"] or not cuit_valido(r["emisor_cuit"]) or r["emisor_cuit"] == CUIT_USUARIO:
        r["motivos"].append("CUIT emisor inválido o faltante")
    if not r["tipo_afip"]:
        r["motivos"].append("tipo de comprobante no identificado")
    if not r["pv"] or not r["numero"]:
        r["motivos"].append("punto de venta o número faltante")
    if not fecha_valida(r["fecha"]):
        r["motivos"].append("fecha de emisión faltante o inválida")
    elif r["fecha"][-4:] != str(PERIODO_ANIO):
        r["motivos"].append(f"fecha de emisión {r['fecha']} fuera del año del formulario ({PERIODO_ANIO})")
    r["monto"] = None
    if not r["total_texto"]:
        r["motivos"].append("total faltante")
    else:
        try:
            r["monto"] = monto_a_decimal(r["total_texto"])
            if float(r["monto"]) > MONTO_MAXIMO:
                r["motivos"].append(f"monto {r['monto']} supera el máximo de revisión")
        except MontoAmbiguo as e:
            r["motivos"].append(str(e))
    r["mes"] = int(r["fecha"][3:5]) if fecha_valida(r["fecha"]) else None
    return r


def asignar_estado(r, origen, confirmado):
    """Fija el estado inicial del comprobante y devuelve el registro.

    - confirmado con 'excluir' -> 'excluido' (decisión del usuario, no se carga).
    - sin motivos -> 'listo'.
    - con motivos -> 'revisar' (falta un campo, hay que confirmarlo a mano).

    Error real: el estado 'excluido' se pisaba enseguida con 'listo'/'revisar' y
    todo comprobante excluido volvía a la lista de 'revisar' en cada extracción.
    """
    if confirmado.get("excluir"):
        r["estado"] = "excluido"
        r["motivos"] = [origen or "Excluido por decisión del usuario."]
    else:
        r["estado"] = "listo" if not r["motivos"] else "revisar"
    return r


def procesar():
    registros = []
    for ruta in sorted(glob.glob(str(FACTURAS / "*.[pP][dD][fF]"))):
        nombre = os.path.basename(ruta)
        try:
            texto = leer_texto(ruta)
        except Exception as e:
            registros.append({"archivo": nombre, "estado": "error", "motivos": [f"no se pudo leer: {e}"]})
            continue
        if len(texto.strip()) < 20:
            registros.append({"archivo": nombre, "estado": "error", "motivos": ["sin texto (¿escaneo?)"]})
            continue
        proveedor = identificar(texto)
        crudo = proveedor["extrae"](texto) if proveedor else extraer_generico(texto)
        if proveedor:
            proveedor_id = proveedor["id"]
        elif crudo.get("_confianza") == "alta":
            proveedor_id = "afip_estandar"
        else:
            proveedor_id = None
        origen = None
        if nombre in CONFIRMADOS:
            crudo = {**crudo, **{k: v for k, v in CONFIRMADOS[nombre].items() if not k.startswith("_")}}
            proveedor_id = proveedor_id or "lectura_visual"
            origen = CONFIRMADOS[nombre].get("_origen")
        r = normalizar(crudo, proveedor_id)
        r["archivo"] = nombre
        r["cae"] = crudo.get("cae")
        if origen:
            r["origen"] = origen
        asignar_estado(r, origen, CONFIRMADOS.get(nombre, {}))
        registros.append(r)

    vistos = {}
    for r in registros:
        if r["estado"] not in ("listo", "revisar"):
            continue
        claves = []
        if r.get("emisor_cuit") and r.get("numero"):
            claves.append(("cuit", r["emisor_cuit"], r["pv"], r["numero"]))
        if r.get("cae"):
            claves.append(("cae", r["cae"]))
        original = next((vistos[c] for c in claves if c in vistos), None)
        if original:
            r["estado"] = "duplicado"
            r["duplicado_de"] = original
            r["motivos"].append(f"mismo comprobante que {original}")
        for c in claves:
            vistos.setdefault(c, r["archivo"])

    por_grupo = {}
    for r in registros:
        if r["estado"] == "listo":
            por_grupo.setdefault((r["emisor_cuit"], r["fecha"], r["monto"]), []).append(r["archivo"])
    for grupo, archivos in por_grupo.items():
        if len(archivos) > 1:
            for r in registros:
                if r["archivo"] in archivos:
                    otros = [a for a in archivos if a != r["archivo"]]
                    r.setdefault("alertas", []).append(
                        f"mismo CUIT+fecha+monto que {', '.join(otros)} (número distinto, se cargan ambos si el usuario lo confirmó)")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(registros, indent=2, ensure_ascii=False), encoding="utf-8")
    escribir_csv(registros)
    return registros


def numero_es(monto):
    """1234567.89 -> '1.234.567,89' (formato es-AR)."""
    if monto is None:
        return ""
    return f"{float(monto):,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def escribir_csv(registros):
    """Escribe output/extracto.csv: una fila por comprobante, en el orden de facturas.json.

    Es un espejo del JSON. Antes lo escribía un proceso suelto y quedó desactualizado
    (con un estado 'revisar' donde el JSON decía 'excluido'). Si se genera acá, no puede
    divergir de la fuente de verdad.
    """
    CSV_SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with CSV_SALIDA.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["archivo", "cuit_emisor", "fecha", "numero", "total", "estado", "nota"])
        for r in registros:
            pv, num = r.get("pv"), r.get("numero")
            numero = f"{pv}-{num}" if pv and num else (num or pv or "")
            w.writerow([
                r.get("archivo", ""),
                r.get("emisor_cuit") or "",
                r.get("fecha") or "",
                numero,
                numero_es(r.get("monto")),
                r.get("estado", ""),
                "; ".join(m for m in r.get("motivos", []) if m),
            ])


def resumen(registros):
    conteo = {}
    for r in registros:
        conteo[r["estado"]] = conteo.get(r["estado"], 0) + 1
    return conteo


if __name__ == "__main__":
    regs = procesar()
    for r in regs:
        print(
            r["archivo"][:34].ljust(35),
            r["estado"].ljust(10),
            r.get("proveedor", "-").ljust(18),
            str(r.get("fecha")).ljust(11),
            str(r.get("monto")).ljust(12),
            "; ".join(r.get("motivos", [])),
        )
    print("\nResumen:", resumen(regs))
    for r in regs:
        if r["estado"] != "listo":
            evento("extraer", "warn" if r["estado"] == "revisar" else "info", "comprobante_no_listo",
                   archivo=r["archivo"], estado=r["estado"], motivos=r.get("motivos", []))
    evento("extraer", "info", "resumen", **resumen(regs))
