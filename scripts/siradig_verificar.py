
from afip_http import sesion_http
from siradig_http import comprobantes_de_gasto, gastos_servidor, listar_menu


def main():
    with sesion_http() as req:
        for g in gastos_servidor(listar_menu(req)):
            print(f"{g['mes']:<12} {g['cuit']} {g['razon'][:30]:<30} {g['concepto']:<14} total={g['monto']}  (idReg {g['idReg']})")
            for c in comprobantes_de_gasto(req, g["idReg"]):
                print(f"    {c['fechaEmision']}  tipo={c['idTipoCmp']}  {str(c['puntoVenta']).zfill(5)}-{str(c['numero']).zfill(8)}  {c['montoFacturado']}")


if __name__ == "__main__":
    main()
