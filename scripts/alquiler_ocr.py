"""OCR de contratos de ALQUILER con caché por hash.

Si el hash del PDF no cambió, no vuelve a OCR: usa el texto cacheado.
Escribe output/alquiler/texto/<sha256>.txt y output/alquiler/ocr_index.json.

Uso:  ./.venv/bin/python scripts/alquiler_ocr.py
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytesseract
from pdf2image import convert_from_path

ROOT = Path(__file__).resolve().parent.parent
ALQUILER = ROOT / "ALQUILER"
TEXTO = ROOT / "output" / "alquiler" / "texto"
INDICE = ROOT / "output" / "alquiler" / "ocr_index.json"


def sha256(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def main():
    TEXTO.mkdir(parents=True, exist_ok=True)
    indice = json.loads(INDICE.read_text(encoding="utf-8")) if INDICE.exists() else {}
    pdfs = sorted(ALQUILER.glob("*.pdf")) if ALQUILER.is_dir() else []
    if not pdfs:
        print("No hay contratos en ALQUILER/.")
        return 0
    for pdf in pdfs:
        h = sha256(pdf)
        destino = TEXTO / f"{h}.txt"
        if h in indice and destino.exists():
            print(f"{pdf.name}: cacheado ({indice[h]['caracteres']} caracteres)")
            continue
        paginas = convert_from_path(str(pdf), dpi=300)
        textos = []
        for i, img in enumerate(paginas, 1):
            textos.append(f"\n--- PÁGINA {i} ---\n" + pytesseract.image_to_string(img, lang="spa"))
        texto = "".join(textos)
        destino.write_text(texto, encoding="utf-8")
        indice[h] = {
            "archivo": pdf.name,
            "paginas": len(paginas),
            "caracteres": len(texto),
            "texto": str(destino.relative_to(ROOT)),
            "fecha": datetime.now().isoformat(timespec="seconds"),
        }
        print(f"{pdf.name}: OCR {len(paginas)} páginas, {len(texto)} caracteres")
    INDICE.write_text(json.dumps(indice, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
