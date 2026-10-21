"""Arma output/duplicados.md a partir de output/facturas.json.

No vuelve a leer los PDF: usa lo que ya extrajo pdf_extraer.py (CUIT emisor, PV, número,
fecha, monto y CAE) y lo cruza con el hash MD5 del archivo para confirmar cada copia.

Criterio de duplicado (el mismo que aplica pdf_extraer.py):
- misma clave de comprobante: CUIT emisor + punto de venta + número, o
- mismo CAE.

Uso:  ./.venv/bin/python scripts/duplicados.py
"""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from registro import evento

ROOT = Path(__file__).resolve().parent.parent
FACTURAS = ROOT / "FACTURAS"
FACTURAS_JSON = ROOT / "output" / "facturas.json"
CARGA_JSON = ROOT / "output" / "cargas.json"
SALIDA = ROOT / "output" / "duplicados.md"


def _md5(ruta):
    return hashlib.md5(Path(ruta).read_bytes()).hexdigest()


def _dinero(monto):
    if monto is None:
        return "(sin dato)"
    entero, decimales = f"{float(monto):.2f}".split(".")
    return "$ " + f"{int(entero):,}".replace(",", ".") + "," + decimales


def cargar_registros():
    if not FACTURAS_JSON.exists():
        raise SystemExit("Falta output/facturas.json. Corré antes: ./.venv/bin/python scripts/pipeline.py extraer")
    return json.loads(FACTURAS_JSON.read_text(encoding="utf-8"))


def agrupar(registros):
    """Devuelve (grupos, archivos_duplicados).

    grupos: {archivo_original: [copias...]} usando el campo 'duplicado_de' del extractor.
    """
    grupos = defaultdict(list)
    for r in registros:
        if r.get("estado") == "duplicado" and r.get("duplicado_de"):
            grupos[r["duplicado_de"]].append(r["archivo"])
    return grupos, [a for copias in grupos.values() for a in copias]


def como_coincide(original, copia):
    """Por qué se detecta el duplicado: número, CAE, o ambos."""
    por_numero = (
        original.get("emisor_cuit")
        and original.get("numero")
        and original.get("emisor_cuit") == copia.get("emisor_cuit")
        and original.get("pv") == copia.get("pv")
        and original.get("numero") == copia.get("numero")
    )
    por_cae = bool(original.get("cae")) and original.get("cae") == copia.get("cae")
    if por_numero and por_cae:
        return "número + CAE"
    if por_cae:
        return "CAE"
    if por_numero:
        return "número"
    return "comprobante repetido"


def verificar_hashes(grupos):
    """Cada copia debería ser idéntica byte a byte al original."""
    detalle = {}
    for original, copias in grupos.items():
        h_original = _md5(FACTURAS / original)
        iguales = [c for c in copias if (FACTURAS / c).exists() and _md5(FACTURAS / c) == h_original]
        detalle[original] = {"md5": h_original, "identicas": len(iguales), "copias": len(copias)}
    return detalle


def generar(registros):
    por_archivo = {r["archivo"]: r for r in registros}
    grupos, duplicados = agrupar(registros)
    hashes = verificar_hashes(grupos)

    pdfs = sorted(p for p in FACTURAS.glob("*.pdf"))
    listo = [r for r in registros if r.get("estado") == "listo"]
    revisar = [r for r in registros if r.get("estado") == "revisar"]
    alertas = [r for r in registros if r.get("alertas")]

    lineas = []
    lineas.append("# Duplicados detectados en FACTURAS/")
    lineas.append("")
    lineas.append(f"Detectado sobre {len(pdfs)} PDFs de `FACTURAS/`. Extracción: `scripts/pdf_extraer.py` → `output/facturas.json`.")
    lineas.append("Criterio: mismo CUIT emisor + punto de venta + número, **o** mismo CAE.")
    lineas.append("")
    lineas.append("## Resultado")
    lineas.append("")
    lineas.append("| | |")
    lineas.append("|---|---|")
    lineas.append(f"| Archivos analizados | {len(pdfs)} |")
    lineas.append(f"| Comprobantes únicos (listos) | {len(listo)} |")
    lineas.append(f"| Archivos duplicados | {len(duplicados)} (en {len(grupos)} grupos) |")
    lineas.append(f"| En `revisar` | {len(revisar)} |")
    lineas.append("")

    if revisar:
        lineas.append("## Pendiente de confirmación manual")
        lineas.append("")
        for r in revisar:
            motivos = "; ".join(r.get("motivos") or [])
            lineas.append(f"- `{r['archivo']}` — {motivos}")
            if r.get("origen") and r["origen"] not in motivos:
                lineas.append(f"  - origen: {r['origen']}")
        lineas.append("")

    lineas.append("## Grupos de duplicados")
    lineas.append("")
    lineas.append("| Original a conservar | CUIT emisor | PV | Número | Fecha | Monto | Copias a descartar | CAE |")
    lineas.append("|---|---|---|---|---|---|---|---|")
    for original in sorted(grupos):
        o = por_archivo.get(original, {})
        lineas.append(
            f"| {original} | {o.get('emisor_cuit') or '(sin CUIT legible)'} | {o.get('pv') or '-'} | "
            f"{o.get('numero') or '-'} | {o.get('fecha') or '-'} | {_dinero(o.get('monto'))} | "
            f"{len(grupos[original])} | {o.get('cae') or '(sin CAE legible)'} |"
        )
    lineas.append("")

    lineas.append(f"## Copias a descartar ({len(duplicados)} archivos)")
    lineas.append("")
    lineas.append("| Duplicado | Original | Coincide por |")
    lineas.append("|---|---|---|")
    for original in sorted(grupos):
        o = por_archivo.get(original, {})
        for copia in sorted(grupos[original]):
            lineas.append(f"| {copia} | {original} | {como_coincide(o, por_archivo.get(copia, {}))} |")
    lineas.append("")

    exposicion = 0.0
    for original, copias in grupos.items():
        o = por_archivo.get(original, {})
        monto = o.get("monto")
        if monto:
            exposicion += float(monto) * len(copias)
    lineas.append("## Exposición")
    lineas.append("")
    lineas.append(
        f"Si se cargaran las {len(duplicados)} copias, se sumarían **{_dinero(round(exposicion, 2))}** de comprobantes repetidos "
        f"({len(duplicados)} archivos, {len(grupos)} comprobantes distintos)."
    )
    lineas.append("")

    lineas.append("## Verificación")
    lineas.append("")
    identicas = sum(h["identicas"] for h in hashes.values())
    if identicas == len(duplicados):
        lineas.append(f"- Los {len(duplicados)} duplicados son **copias byte a byte** del original (mismo MD5 de archivo).")
    else:
        lineas.append(f"- {identicas} de {len(duplicados)} duplicados son copias byte a byte (mismo MD5). Los demás son el mismo comprobante con otro archivo.")
    por_cae = sum(1 for o, cs in grupos.items() if all(por_archivo.get(c, {}).get("cae") for c in cs))
    por_numero = sum(1 for o, cs in grupos.items() if all(
        por_archivo.get(c, {}).get("numero") and por_archivo.get(c, {}).get("emisor_cuit") for c in cs))
    lineas.append(f"- {por_numero} de {len(grupos)} grupos tienen CUIT + PV + número legibles; {por_cae} de {len(grupos)} tienen CAE legible.")
    lineas.append("")

    cargados = set()
    if CARGA_JSON.exists():
        cargados = {c.get("archivo") for c in json.loads(CARGA_JSON.read_text(encoding="utf-8"))}
    en_carga = sorted(set(duplicados) & cargados)
    lineas.append("## Estado de la carga en SiRADIG")
    lineas.append("")
    if en_carga:
        lineas.append(f"**Atención:** {len(en_carga)} duplicados están en la carga anterior (`output/cargas.json`) y hay que quitarlos:")
        lineas.append("")
        for a in en_carga:
            lineas.append(f"- {a}")
    else:
        lineas.append(
            f"La carga anterior (`output/cargas.json`, {len(cargados)} comprobantes) **no** incluyó ninguno de los "
            f"{len(duplicados)} duplicados: los {len(grupos)} originales ya están cargados y no hay que corregir nada del lado de AFIP."
        )
    lineas.append("")

    lineas.append("## Alertas por monto")
    lineas.append("")
    if alertas:
        lineas.append("Hay comprobantes distintos con el mismo CUIT + fecha + monto. Requieren confirmación manual antes de cargar ambos:")
        lineas.append("")
        for r in alertas:
            lineas.append(f"- {r['archivo']}: {r['alertas'][0]}")
    else:
        lineas.append("Ninguna. No hay dos comprobantes distintos con el mismo CUIT + fecha + monto")
        lineas.append("(si los hubiera, quedarían marcados con `alertas` en `output/facturas.json` y requieren")
        lineas.append("confirmación manual antes de cargar ambos).")
    lineas.append("")

    return "\n".join(lineas), grupos, duplicados


def main():
    registros = cargar_registros()
    texto, grupos, duplicados = generar(registros)
    SALIDA.write_text(texto, encoding="utf-8")
    evento("duplicados", "info", "duplicados_detectados", grupos=len(grupos), archivos_duplicados=len(duplicados))
    print(f"output/duplicados.md escrito: {len(duplicados)} archivos duplicados en {len(grupos)} grupos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
