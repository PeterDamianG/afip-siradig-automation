"""Contrato HTTP del formulario de alquiler (Beneficio 40%, Art. 85 inc. h).

Formulario: verAlquilerInmuebleInquilinoO.do
Guardar:    guardarAlquilerInmueble.do (x-www-form-urlencoded)
Editar:     verAlquilerInmuebleInquilinoO.do?id=<registro>
Imprimir:   descargarPDF.do?id=<presentacion>&s=a
"""
import json
import re
from urllib.parse import urlencode

from afip_http import RADIG
from registro import evento
from siradig_http import _texto

TIPO_BENEFICIO = "22"
TIPO_COMPROBANTE = "6"
SECCION_PDF = "a"


def _json_var(html, nombre):
    m = re.search(r"var %s\s*=\s*(.*?);\s*(?:\n|</script>)" % re.escape(nombre), html, re.S)
    return json.loads(m.group(1)) if m else None


def _pares(contrato, codigo=""):
    locador = contrato["locador"]
    inmobiliaria = contrato.get("inmobiliaria") or {}
    meses = contrato["meses"]
    pares = [
        ("numeroDoc", locador["cuit"]),
        ("razonSocial", locador["nombre"]),
        ("cuitAdicional", ""),
        ("razonSocialAdicional", ""),
        ("locadorAdicional", "S" if contrato.get("locador_adicional") else "N"),
        ("cuitLocadorAdicional", ""),
        ("razonSocialLocadorAdicional", ""),
        ("cuitInmobiliaria", inmobiliaria.get("cuit", "")),
        ("razonSocialInmobiliaria", inmobiliaria.get("nombre", "")),
        ("inmobiliaria", "S" if inmobiliaria else "N"),
        ("eliminarContratoExistente", ""),
        ("fechaVigenciaDesde", contrato["vigencia"]["desde"]),
        ("fechaVigenciaHasta", contrato["vigencia"]["hasta"]),
        ("mesDesde", str(min(m["mes"] for m in meses))),
        ("mesHasta", str(max(m["mes"] for m in meses))),
        ("detalleIndividualMes", "1"),
        ("detalleIndividualMontoRealMensual", ""),
        ("detalleIndividualMontoMensual", ""),
        ("detalleGrupoMesDesde", "1"),
        ("detalleGrupoMesHasta", "12"),
        ("detalleGrupoMontoRealMensual", ""),
        ("detalleGrupoMontoMensual", ""),
        ("montoTotal", f"{sum(float(m['deducible']) for m in meses):.2f}"),
    ]
    for i, m in enumerate(meses):
        pares += [
            ("detalleMensualIdFilaAgregada", str(i)),
            ("detalleMensualMes", str(m["mes"])),
            ("detalleMensualMonto", f"{float(m['deducible']):.2f}"),
            ("detalleMensualMontoTotalCmp", f"{float(m['alquiler']):.2f}"),
        ]
    pares.append(("detallesMensualesEliminados", ""))
    for i, m in enumerate(meses):
        pares += [
            ("comprobanteIdFilaAgregada", str(i)),
            ("comprobanteMes", str(m["mes"])),
            ("comprobanteFechaEmision", m["fecha"]),
            ("comprobanteTipo", str(contrato.get("tipo_comprobante", TIPO_COMPROBANTE))),
            ("comprobantePuntoVenta", str(contrato.get("punto_venta", "00042")).zfill(5)),
            ("comprobanteNumero", str(m["factura"]).zfill(8)),
            ("comprobanteNumeroAlternativo", ""),
            ("comprobanteMontoFacturado", f"{float(m['alquiler']):.2f}"),
        ]
    pares += [
        ("comprobantesEliminados", ""),
        ("codigo", str(codigo or contrato.get("registro_id") or "")),
        ("tipoBeneficio", str(contrato.get("tipo_beneficio", TIPO_BENEFICIO))),
    ]
    return pares


def guardar_alquiler(req, contrato):
    """Alta o edición de una deducción de alquiler. Devuelve (status, json)."""
    r = req.post(
        RADIG + "guardarAlquilerInmueble.do",
        data=urlencode(_pares(contrato)),
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
    )
    cuerpo = _texto(r)
    try:
        respuesta = json.loads(cuerpo)
    except json.JSONDecodeError:
        respuesta = {"estado": "error", "mensaje": cuerpo[:500]}
    ok = respuesta.get("estado") == "ok"
    evento("alquiler", "info" if ok else "error", "guardado",
           cuit=contrato["locador"]["cuit"], meses=len(contrato["meses"]),
           total=round(sum(float(m["deducible"]) for m in contrato["meses"]), 2),
           http=r.status, estado=respuesta.get("estado"))
    return r.status, respuesta


def obtener_alquiler(req, registro_id):
    """Lee un registro de alquiler: formulario, detalle y comprobantes."""
    html = _texto(req.get(RADIG + "verAlquilerInmuebleInquilinoO.do", params={"id": str(registro_id)}))
    return {
        "form": _json_var(html, "datosForm") or {},
        "detalle": _json_var(html, "datosFormDetalle") or {},
        "comprobantes": _json_var(html, "datosFormComprobantes") or [],
    }


def descargar_presentacion(req, codigo, seccion=SECCION_PDF):
    """Descarga una presentación enviada. Devuelve bytes (PDF)."""
    r = req.get(RADIG + "descargarPDF.do", params={"id": str(codigo), "s": seccion})
    return r.body()
