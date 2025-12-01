from __future__ import annotations

from config import DOC_PATH, DIAG_PATH, OUT_TXT, OUT_XLSX
from parsers import load_doc, load_diag
from comparator import comparar_sets
from report import write_report_txt, write_coincidencias_excel

def main():
    print("→ Extrayendo doc.pdf…")
    rows_doc = load_doc(DOC_PATH)

    print("→ Extrayendo INGENIERIA EN COMPUTACION.pdf…")
    rows_diag = load_diag(DIAG_PATH)

    print("→ Colapsando duplicados internos y comparando…")
    result = comparar_sets(rows_doc, rows_diag)

    write_report_txt(OUT_TXT, result)
    write_coincidencias_excel(OUT_XLSX, result)

    print("=== RESULTADO ===")
    print(f"Total de coincidencias: {result.coincidencias}")
    print(f"Total de Discrepancias: {result.discrepancias}")
    print(f"Informe TXT → {OUT_TXT}")
    print(f"Coincidencias Excel → {OUT_XLSX}")

if __name__ == "__main__":
    main()