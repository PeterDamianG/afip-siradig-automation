import re
from urllib.parse import urljoin

PORTAL_API = "https://portalcf.cloud.afip.gob.ar/portal/api/"


def _texto(respuesta):
    return respuesta.body().decode("utf-8", "replace")


def _viewstate(html):
    m = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html) or \
        re.search(r'value="([^"]+)"[^>]*name="javax\.faces\.ViewState"', html)
    return m.group(1) if m else None


def _formulario(html, base_url, campo):
    for m in re.finditer(r"<form[^>]*action=\"([^\"]*)\"[^>]*>(.*?)</form>", html, re.S):
        if re.search(r'name="%s"' % re.escape(campo), m.group(2)):
            return urljoin(base_url, m.group(1).replace("&amp;", "&"))
    return None


def login_http(req, cred, cuit_login=None):
    url_login = cred["AFIP_URL"]
    r = req.get(url_login)
    html = _texto(r)
    action = _formulario(html, url_login, "F1:username")
    vs = _viewstate(html)

    r = req.post(action, form={
        "F1": "F1",
        "F1:username": cred["AFIP_USUARIO"],
        "F1:btnSiguiente": "Siguiente",
        "javax.faces.ViewState": vs,
    })
    html = _texto(r)
    action = _formulario(html, r.url, "F1:password")
    vs = _viewstate(html)

    r = req.post(action, form={
        "F1": "F1",
        "F1:captcha": "",
        "F1:username": cred["AFIP_USUARIO"],
        "F1:password": cred["AFIP_PASSWORD"],
        "F1:btnIngresar": "Ingresar",
        "javax.faces.ViewState": vs,
    })
    html = _texto(r)
    m = re.search(r'<form[^>]*action="([^"]+)"[^>]*>(?:(?!</form>).)*name="jwt"[^>]*value="([^"]+)"', html, re.S) or \
        re.search(r'<form[^>]*action="([^"]+)"[^>]*>(?:(?!</form>).)*value="([^"]+)"[^>]*name="jwt"', html, re.S)
    if not m:
        raise RuntimeError("No se encontró el jwt tras el login (¿clave incorrecta o captcha?)")
    r = req.post(urljoin(r.url, m.group(1)), form={"jwt": m.group(2)})
    return r.status


RADIG = "https://serviciosjava2.afip.gob.ar/radig/jsp/"


def sesion_siradig(req, cred):
    import json
    login_http(req, cred)
    cuit = cred["AFIP_USUARIO"]
    aut = json.loads(_texto(req.get(PORTAL_API + f"servicios/{cuit}/servicio/radig/autorizacion")))
    req.post(RADIG + "index.jsp", form={"token": aut["token"], "sign": aut["sign"]})
    req.get(RADIG + "setearContribuyente.do", params={"idContribuyente": "0"})
    req.get(RADIG + "determinarContribuyente.do", params={"codigo": "2026"})
    return req


from contextlib import contextmanager


@contextmanager
def sesion_http():
    from playwright.sync_api import sync_playwright
    from afip_login import cargar_credenciales
    from registro import evento
    with sync_playwright() as p:
        try:
            req = sesion_siradig(p.request.new_context(), cargar_credenciales())
        except Exception as e:
            evento("login", "error", "login_fallido", error=str(e)[:200])
            raise
        evento("login", "info", "sesion_ok")
        try:
            yield req
        finally:
            req.dispose()
