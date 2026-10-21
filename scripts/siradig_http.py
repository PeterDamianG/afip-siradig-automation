import json
import re

from siradig import GASTOS

BASE = "https://serviciosjava2.afip.gob.ar/radig/jsp/"
AJAX = BASE + "ajax.do"
GUARDAR = BASE + "guardarGastosInduEquip.do"
MENU_DEDUCCIONES = BASE + "verMenuDeducciones.do"

CONCEPTO = {"Indumentaria": "1", "Equipamiento": "2"}
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _texto(respuesta):
    return respuesta.body().decode("iso-8859-1")


def html_formulario(request, codigo=None):
    params = {"id": str(codigo)} if codigo else None
    return _texto(request.get(GASTOS, params=params))


def opciones_select(html, nombre):
    bloque = re.search(r'<select[^>]*name="%s"[^>]*>(.*?)</select>' % nombre, html, re.S)
    if not bloque:
        return {}
    return {
        texto.strip(): valor
        for valor, texto in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', bloque.group(1), re.S)
    }


def razon_social(request, cuit):
    r = request.get(AJAX, params={"f": "razonsocialcuitocuitpais", "cuit": cuit})
    return json.loads(_texto(r))["datos"]["razonSocial"].strip()


def listar_menu(request):
    return _texto(request.get(MENU_DEDUCCIONES))


def gastos_servidor(menu_html):
    bloque = re.search(r"datosDeduccionesAgrupadasJSON = (\[.*?\]);", menu_html, re.S)
    if not bloque:
        return []
    gastos = []
    for id_reg, celdas in re.findall(r'\{"idReg":(\d+),"celdas":\[([^\]]*)\]\}', bloque.group(1)):
        valores = [v.strip().strip('"') for v in celdas.split('","')]
        if len(valores) == 5:
            cuit, razon, concepto, mes, monto = valores
            gastos.append({"idReg": id_reg, "cuit": cuit, "razon": razon,
                           "concepto": concepto, "mes": mes, "monto": monto})
    return gastos


def comprobantes_de_gasto(request, codigo):
    html = html_formulario(request, codigo)
    m = re.search(r"var datosFormComprobantes = (\[.*?\]);", html, re.S)
    return json.loads(m.group(1)) if m else []


def enviar_gasto(request, gasto):
    datos = {
        "numeroDoc": gasto["cuit"],
        "razonSocial": gasto["razon_social"],
        "idConcepto": CONCEPTO[gasto["concepto"]],
        "mesDesde": str(gasto["mes"]),
        "montoTotal": gasto["monto_total"],
        "numeroDocTmp": "",
        "comprobanteIdFilaAgregada": "0",
        "comprobanteFechaEmision": gasto["fecha"],
        "comprobanteTipo": gasto["tipo_codigo"],
        "comprobantePuntoVenta": gasto["pv"],
        "comprobanteNumero": gasto["numero"],
        "comprobanteNumeroAlternativo": "",
        "comprobanteMontoFacturado": gasto["monto"],
        "comprobantesEliminados": gasto.get("eliminados", ""),
        "codigo": gasto.get("codigo", ""),
    }
    r = request.post(GUARDAR, form=datos)
    return r.status, _texto(r)
