"""Pruebas de montos y CUIT. Correr antes de cargar:  ./.venv/bin/python scripts/test_montos.py

Errores reales (no repetir):
- Un proveedor de internet usa PUNTO decimal: "83650.00" es 83.650,00. Un error lo cargó como 8.365.000,00 (×100).
- Los proveedores de servicios usan COMA decimal: "52.607,88" es 52.607,88.
- Otro proveedor también usa coma decimal: "58.642,01" es 58.642,01.
"""
from cuit import cuit_valido
from montos import MontoAmbiguo, monto_a_decimal

MONTOS = {
    "83650.00": "83650.00",
    "69680.00": "69680.00",
    "7142001.00": "7142001.00",
    "52.607,88": "52607.88",
    "4.080,00": "4080.00",
    "9.546,80": "9546.80",
    "29386,86": "29386.86",
    "435.929,74": "435929.74",
    "$ 52.160,00": "52160.00",
    "1.033.310,00": "1033310.00",
    "47,992.0000": "47992.00",
    "$ 47,992.0000": "47992.00",
    "29,900.00": "29900.00",
    "126.172,00": "126172.00",
    "$ 126.172,00": "126172.00",
    "1,234,567.89": "1234567.89",
    "58.642,01": "58642.01",
}
AMBIGUOS = ["1.500", "1,500", "1.500x", ""]
CUITS = {"30000000007": True, "30000000104": True, "20000000001": True, "30000000008": False}


def main():
    fallos = []
    for entrada, esperado in MONTOS.items():
        try:
            obtenido = monto_a_decimal(entrada)
        except MontoAmbiguo as e:
            obtenido = f"ERROR {e}"
        if obtenido != esperado:
            fallos.append(f"monto {entrada!r} -> {obtenido} (esperado {esperado})")
    for entrada in AMBIGUOS:
        try:
            monto_a_decimal(entrada)
            fallos.append(f"monto {entrada!r} debió ser ambiguo y no lo fue")
        except MontoAmbiguo:
            pass
    for cuit, esperado in CUITS.items():
        if cuit_valido(cuit) != esperado:
            fallos.append(f"CUIT {cuit} validez esperada {esperado}")
    for f in fallos:
        print("FALLA:", f)
    print("OK" if not fallos else f"{len(fallos)} fallas")
    raise SystemExit(1 if fallos else 0)


if __name__ == "__main__":
    main()
