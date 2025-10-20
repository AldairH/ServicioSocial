from __future__ import annotations
from pathlib import Path
import pandas as pd

try:
    import pymupdf as fitz  # PyMuPDF moderno
except ImportError:
    import fitz  # compatibilidad

# ===== CONFIGURACIÓN =====
PDF_FILE = Path("01 Profesor_Asignatura.pdf")   # Nombre del PDF
OUT_DIR = Path("out")                           # Carpeta de salida
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_OUT = OUT_DIR / "01_Profesor_Asignatura_raw.csv"


# ===== FUNCIONES AUXILIARES =====
def coerce(s):
    """Convierte None a cadena vacía y limpia espacios."""
    return "" if s is None else str(s).strip()


# ===== EXTRACCIÓN DE TABLAS =====
def extract_all_tables(pdf_path: Path) -> pd.DataFrame:
    doc = fitz.open(pdf_path)
    rows = []
    max_cols = 0

    try:
        for pidx in range(len(doc)):
            page = doc[pidx]
            if not hasattr(page, "find_tables"):
                raise RuntimeError(
                    "Tu versión de PyMuPDF no tiene 'find_tables()'. "
                    "Actualízala con: pip install --upgrade pymupdf"
                )

            # Detectar tablas en la página
            found = page.find_tables()
            if not found or not found.tables:
                # Página sin tablas detectadas
                rows.append({
                    "page": pidx + 1,
                    "table_index": -1,
                    "row_index": -1,
                    "is_header": "",
                    "col_0": "[NO_TABLES_ON_PAGE]"
                })
                max_cols = max(max_cols, 1)
                continue

            # Extraer cada tabla y fila
            for tidx, table in enumerate(found.tables):
                data = table.extract()
                if not data:
                    continue

                for ridx, r in enumerate(data):
                    if r is None:
                        r = []
                    max_cols = max(max_cols, len(r))
                    entry = {
                        "page": pidx + 1,
                        "table_index": tidx,
                        "row_index": ridx,
                        "is_header": "yes" if ridx == 0 else ""
                    }
                    for cidx, cell in enumerate(r):
                        entry[f"col_{cidx}"] = coerce(cell)
                    rows.append(entry)
    finally:
        doc.close()

    # Asegurar todas las filas con el mismo número de columnas
    for row in rows:
        for cidx in range(max_cols):
            row.setdefault(f"col_{cidx}", "")

    cols = ["page", "table_index", "row_index", "is_header"] + [f"col_{i}" for i in range(max_cols)]
    return pd.DataFrame(rows, columns=cols)


# ===== EJECUCIÓN =====
if __name__ == "__main__":
    df = extract_all_tables(PDF_FILE)
    df.to_csv(CSV_OUT, index=False, encoding="utf-8")
    print(f"✅ Extraído: {len(df)} filas → {CSV_OUT}")
    print(df.head(10).to_string(index=False))
