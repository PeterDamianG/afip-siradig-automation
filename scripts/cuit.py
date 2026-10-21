import re

PESOS = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
CUIT_PATRON = re.compile(r"(?<!\d)(\d{2})-?(\d{8})-?(\d)(?!\d)")


def cuit_valido(cuit):
    if not re.fullmatch(r"\d{11}", cuit or ""):
        return False
    suma = sum(int(d) * p for d, p in zip(cuit[:10], PESOS))
    resto = 11 - suma % 11
    verificador = 0 if resto == 11 else resto
    return verificador != 10 and verificador == int(cuit[10])


def cuits_en_texto(texto):
    encontrados = []
    for m in CUIT_PATRON.finditer(texto):
        cuit = "".join(m.groups())
        if cuit_valido(cuit) and cuit not in encontrados:
            encontrados.append(cuit)
    return encontrados
