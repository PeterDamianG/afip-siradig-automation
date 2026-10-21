import re


class MontoAmbiguo(ValueError):
    pass


def monto_a_decimal(texto):
    """Convierte el texto de un monto de factura a 'NNNN.NN'.

    Reglas (errores reales ya cometidos, no cambiar sin correr test_montos.py):
    - Con coma: la coma es decimal y el punto es separador de miles.
      '52.607,88' -> 52607.88   '29386,86' -> 29386.86
    - Sin coma: el punto es decimal sólo si tiene exactamente 2 decimales.
      '83650.00' -> 83650.00 (proveedor de internet). Un error aquí lo cargó ×100.
    - Sin coma y con punto seguido de 3 dígitos ('1.500'): ambiguo, no se adivina.
    """
    t = re.sub(r"[$\s]", "", texto or "")
    if re.fullmatch(r"\d{1,3}(,\d{3})+\.\d{1,4}|\d{1,3}(\.\d{3})+,\d{1,2}", t):
        # Formato con miles y decimal explícito: el último separador es el decimal.
        if t.rfind(",") > t.rfind("."):
            valor = t.replace(".", "").replace(",", ".")
        else:
            valor = t.replace(",", "")
    elif not re.fullmatch(r"\d+(,\d{1,2})?|\d+(\.\d{1,4})?", t):
        raise MontoAmbiguo(f"formato de monto no reconocido: {texto!r}")
    elif "," in t:
        valor = t.replace(",", ".")
    elif re.fullmatch(r"\d+\.\d{2}", t):
        valor = t
    elif re.fullmatch(r"\d+", t):
        valor = t
    else:
        raise MontoAmbiguo(f"monto ambiguo (¿miles o decimal?): {texto!r}")
    numero = float(valor)
    if numero <= 0:
        raise MontoAmbiguo(f"monto no positivo: {texto!r}")
    return f"{numero:.2f}"
