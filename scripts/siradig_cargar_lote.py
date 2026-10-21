"""Carga por HTTP los comprobantes con estado 'listo' de output/facturas.json en SiRADIG.

- Un gasto por CUIT + mes + concepto. Si ya existe, el comprobante se agrega a ese gasto.
- Si el comprobante ya está en AFIP (mismo CUIT, punto de venta y número), se omite.
- Se detiene ante el primer error del servidor.

Uso:  ./.venv/bin/python scripts/siradig_cargar_lote.py [N]   (N = cantidad máxima, opcional)
"""
import json
import sys
from pathlib import Path

from afip_http import sesion_http
from registro import evento
from siradig_http import MESES, comprobantes_de_gasto, enviar_gasto, gastos_servidor, listar_menu, razon_social

ROOT = Path(__file__).resolve().parent.parent
FACTURAS_JSON = ROOT / "output" / "facturas.json"
CARGAS_JSON = ROOT / "output" / "cargas.json"
CONCEPTO = "Equipamiento"


def ya_esta(comprobantes, pv, numero):
    return any(int(c["puntoVenta"]) == int(pv) and int(c["numero"]) == int(numero) for c in comprobantes)


def cargar(registros, limite=0):
    listos = [r for r in registros if r["estado"] == "listo"]
    if limite:
        listos = listos[:limite]
    print(f"Comprobantes listos para cargar: {len(listos)}")

    resultados = []
    with sesion_http() as req:
        razones = {}
        for r in listos:
            cuit, pv, numero = r["emisor_cuit"], r["pv"], r["numero"]
            if cuit not in razones:
                razones[cuit] = razon_social(req, cuit)
            mes_nombre = MESES[r["mes"] - 1]

            existente = next((g for g in gastos_servidor(listar_menu(req))
                              if g["cuit"] == cuit and g["concepto"] == CONCEPTO and g["mes"] == mes_nombre), None)
            codigo, total = "", r["monto"]
            if existente:
                if ya_esta(comprobantes_de_gasto(req, existente["idReg"]), pv, numero):
                    resultados.append({"archivo": r["archivo"], "estado": "omitido", "motivo": "ya está en AFIP"})
                    evento("cargar", "info", "omitido", archivo=r["archivo"], motivo="ya está en AFIP")
                    print(r["archivo"][:34].ljust(36), "omitido: ya está en AFIP")
                    continue
                codigo = existente["idReg"]
                total = f"{float(existente['monto']) + float(r['monto']):.2f}"

            gasto = {
                "cuit": cuit, "razon_social": razones[cuit], "concepto": CONCEPTO, "mes": r["mes"],
                "monto": r["monto"], "monto_total": total, "fecha": r["fecha"],
                "tipo_codigo": r["tipo_afip"], "pv": pv, "numero": numero, "codigo": codigo,
            }
            status, cuerpo = enviar_gasto(req, gasto)
            ok = status == 200 and '"estado":"ok"' in cuerpo
            resultados.append({"archivo": r["archivo"], "pv": pv, "numero": numero, "mes": mes_nombre,
                               "monto": r["monto"], "codigo": codigo,
                               "estado": "cargado" if ok else "error",
                               "respuesta": "" if ok else cuerpo[:300]})
            print(r["archivo"][:34].ljust(36), mes_nombre.ljust(11), r["monto"].ljust(12), "OK" if ok else "ERROR: " + cuerpo[:200])
            evento("cargar", "info" if ok else "error", "comprobante", archivo=r["archivo"], mes=mes_nombre,
                   monto=r["monto"], codigo_gasto=codigo, estado="cargado" if ok else "error",
                   http=status, respuesta=None if ok else cuerpo[:300])
            if not ok:
                break

    CARGAS_JSON.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Resultados guardados en output/cargas.json")
    return resultados


if __name__ == "__main__":
    cargar(json.loads(FACTURAS_JSON.read_text(encoding="utf-8")), int(sys.argv[1]) if len(sys.argv) > 1 else 0)
