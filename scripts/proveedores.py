"""Registro de proveedores de facturas.

Cada proveedor conocido tiene: cómo se detecta en el texto y cómo se extraen sus
campos. Los tres de abajo son plantillas de ejemplo con CUITs ficticios. Agregá
las tuyas en `PROVEEDORES`; si un PDF no coincide con ninguna, se usa
`extraer_generico` y el comprobante queda en estado `revisar` hasta que un humano
lo confirme.

Códigos de tipo AFIP usados en SiRADIG:
  6  = Factura B
  10 = Nota de Venta al contado B
  11 = Factura C
  40 = Otro comprobante B (RG 1415), para liquidaciones de servicios públicos.
"""
import re
from pathlib import Path

from cuit import cuits_en_texto


def _cuit_usuario():
    """CUIT del propio contribuyente, leído de credenciales.env. Nunca es emisor."""
    env = Path(__file__).resolve().parent.parent / "credenciales.env"
    if not env.exists():
        return ""
    for linea in env.read_text(encoding="utf-8").splitlines():
        if linea.strip().startswith("AFIP_USUARIO="):
            return linea.split("=", 1)[1].strip()
    return ""


CUIT_USUARIO = _cuit_usuario()

FECHA = r"(\d{2}/\d{2}/\d{4})"
FECHA_CORTA = r"(\d{1,2}/\d{1,2}/\d{2,4})"
MONTO = r"([\d.]+,\d{2}|\d+\.\d{2})"


def _grupo(m, i):
    return m.group(i) if m else None


def _total_fila_tabla(t):
    """Total de una tabla cuyo rótulo va espaciado ('T o t a l').

    La fila de importes va en la línea siguiente y el total es su último valor.
    """
    m = re.search(r"T\s+o\s+t\s+a\s+l[ \t]*\r?\n([\d., \t]+)", t)
    if not m:
        return None
    importes = m.group(1).split()
    return importes[-1] if importes else None


def _extraer_cae(t):
    """CAE de 14 dígitos, tolerando rótulos separados del número por el pie legal."""
    estricto = re.search(r"C\.?\s?A\.?\s?E\.?\s*(?:N[º°o]\.?|Nro\.?)?\s*:?\s*(\d{14})", t)
    if estricto:
        return estricto.group(1)
    laxo = re.search(
        r"C\.?\s?A\.?\s?E\.?\s*(?:N[º°o]\.?|Nro\.?)?\s*:?\s*.{0,160}?(?<![\d])(\d{14})(?![\d])",
        t, re.S)
    return laxo.group(1) if laxo else None


# --- Plantillas de ejemplo -------------------------------------------------

def gas_proveedor(t):
    """Factura de gas con número pv-número/dv y total a pagar."""
    m = re.search(r"(\d{5})-(\d{8})/\d\s+" + FECHA, t)
    total = re.search(r"TOTAL\s*A\s*PAGAR\s*\$\s*" + MONTO, t)
    return {
        "emisor_cuit": "30000000007",
        "emisor_nombre": "PROVEEDOR DE GAS",
        "tipo_afip": "6", "tipo_texto": "Factura B",
        "pv": _grupo(m, 1), "numero": _grupo(m, 2), "fecha": _grupo(m, 3),
        "total": _grupo(total, 1),
    }


def cooperativa_local(t):
    """Factura o liquidación de una cooperativa de servicios."""
    tipo_factura = 'FACTURA "B"' in t
    num = re.search(r"N[°º]\s*(\d{4})\s*(\d{8})", t)
    fecha = re.search(r"Emisi[oó]n:\s*" + FECHA, t)
    total = re.search(r"Total a pagar\s*\$?\s*" + MONTO, t)
    return {
        "emisor_cuit": "30000000104",
        "emisor_nombre": "COOPERATIVA LOCAL",
        "tipo_afip": "6" if tipo_factura else "40",
        "tipo_texto": "Factura B" if tipo_factura else "Liquidación B",
        "pv": _grupo(num, 1), "numero": _grupo(num, 2), "fecha": _grupo(fecha, 1),
        "total": _grupo(total, 1),
    }


def internet_proveedor(t):
    """Factura de internet con número FB pv-número, fecha corta y total en dólares."""
    num = re.search(r"FB\s*(\d{4})\s*(\d{8})", t)
    fecha = re.search(r"FECHA\s*:\s*(\d{2})/(\d{2})/(\d{2})", t)
    total = re.search(r"\n\$(\d+\.\d{2})", t)
    return {
        "emisor_cuit": "30000000309",
        "emisor_nombre": "PROVEEDOR DE INTERNET",
        "tipo_afip": "6", "tipo_texto": "Factura B",
        "pv": _grupo(num, 1), "numero": _grupo(num, 2),
        "fecha": f"{fecha.group(1)}/{fecha.group(2)}/20{fecha.group(3)}" if fecha else None,
        "total": _grupo(total, 1),
    }


PROVEEDORES = [
    {"id": "gas_proveedor", "detecta": lambda t: "FACTURADEGAS" in t or "PROVEEDOR DE GAS" in t.upper(), "extrae": gas_proveedor},
    {"id": "cooperativa_local", "detecta": lambda t: "COOPERATIVA LOCAL" in t.upper(), "extrae": cooperativa_local},
    {"id": "internet_proveedor", "detecta": lambda t: "PROVEEDOR DE INTERNET" in t.upper() or "INTERNET" in t.upper(), "extrae": internet_proveedor},
]

TIPOS_GENERICOS = [
    (r"FACTURA\s+A\b", "1", "Factura A"),
    (r"FACTURA\s+\"?B\"?\b", "6", "Factura B"),
    (r"FACTURA\s+C\b", "11", "Factura C"),
    (r"LIQ\.?\s*DE\s*SERV|LIQUIDACI[OÓ]N\s+DE\s+SERVICIOS", "40", "Liquidación B"),
]

PATRONES_TOTAL = [
    r"(?<![A-Za-z-])Importe[ \t]+Total[ \t]*:?[ \t]*\$?[ \t]*([\d.,]*\d)",
    r"(?<![A-Za-z-])TOTAL[ \t]*(?:Pesos[ \t]*\(ARS\)|Pesos[ \t]*\.?[ \t]*:?|ARS)?[ \t]*:?[ \t]*\$?[ \t]*:?[ \t]*([\d.,]*\d)",
    r"(?<![A-Za-z-])Total[ \t]*(?:ARS|\$)[ \t]*:?[ \t]*([\d.,]*\d)",
    r"(?<![A-Za-z-])Total[ \t]*:[ \t]*\$?[ \t]*([\d.,]*\d)",
    r"(?<![A-Za-z-])TOTAL[ \t]*\n[^\n]*?\$[ \t]*([\d.,]*\d)",
]

CODIGO_TIPO_AFIP = {
    "1": ("1", "Factura A"),
    "6": ("6", "Factura B"),
    "10": ("10", "Nota de Venta al contado B"),
    "11": ("11", "Factura C"),
    "18": ("40", "Liquidación B"),
}


def _extraer_total(t):
    """Último total del comprobante (los totales suelen ir al final)."""
    hallados = []
    for patron in PATRONES_TOTAL:
        for m in re.finditer(patron, t):
            hallados.append((m.start(), m.group(1)))
    return max(hallados)[1] if hallados else None


def identificar(texto):
    for p in PROVEEDORES:
        if p["detecta"](texto):
            return p
    return None


def extraer_generico(t):
    """Formato de factura AFIP estándar, para proveedores sin plantilla propia."""
    cuits = [c for c in cuits_en_texto(t) if c != CUIT_USUARIO]
    emisor = cuits[0] if cuits else None

    fecha = (re.search(r"[Ff]echa\s+(?:de\s+)?[Ee]misi[oó]n\s*:?\s*" + FECHA_CORTA, t)
             or re.search(r"[Ee]misi[oó]n\s*:?\s*" + FECHA_CORTA, t)
             or re.search(r"(?<![A-Za-z])Fecha\s*:\s*" + FECHA_CORTA, t, re.I))

    sin_cae = re.sub(r"\d{14}", " ", t)
    num = (re.search(r"Comp\.?\s*Nro\.?\s*:?\s*(\d{4,5})\s*[-—–]\s*(\d{8})", sin_cae)
           or re.search(r"(?:N[º°o]\.?|Nro\.?|N°|FACTURA:?|FB|Fc\.?\s*[A-Z]?)\s*:?\s*[A-Z]?(\d{4,5})\s*[-—–]?\s*(\d{8})", sin_cae)
           or re.search(r"(?<![\d-])(\d{4,5})[-—–](\d{8})(?!\d)", sin_cae))

    total = _extraer_total(t)

    tipo = None
    cod = re.search(r"C[oó]d(?:igo|\.)?\s*(?:N°)?\s*0*(\d{1,2})\b", t, re.I)
    if cod and cod.group(1) in CODIGO_TIPO_AFIP:
        tipo = CODIGO_TIPO_AFIP[cod.group(1)]
    elif not re.search(r"NOTA\s+DE", t, re.I):
        cabecera = t[:400].upper()
        if "FACTURA" in cabecera and re.search(r"(?<![A-Z])B(?![A-Z])", t[:200]):
            tipo = ("6", "Factura B")

    if re.search(r"NOTA\s+DE\s+(CR[ÉE]DITO|D[ÉE]BITO)", t, re.I):
        tipo = None

    cae = _extraer_cae(t)
    confianza = all([emisor, fecha, num, total, tipo])
    return {
        "emisor_cuit": emisor, "emisor_nombre": None,
        "tipo_afip": tipo[0] if tipo else None, "tipo_texto": tipo[1] if tipo else None,
        "pv": num.group(1) if num else None, "numero": num.group(2) if num else None,
        "fecha": fecha.group(1) if fecha else None,
        "total": total,
        "cae": cae,
        "_confianza": "alta" if confianza else "baja",
    }
