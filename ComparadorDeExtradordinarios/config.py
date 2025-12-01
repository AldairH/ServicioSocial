from pathlib import Path

# ---------------- Config ----------------
BASE_DIR = Path(__file__).resolve().parent

DOC_PATH  = BASE_DIR / "doc.pdf"
DIAG_PATH = BASE_DIR / "INGENIERIA EN COMPUTACION.pdf"

OUT_DIR = BASE_DIR / ("out")
OUT_DIR.mkdir(exist_ok=True, parents=True)

OUT_TXT = OUT_DIR / "reporte_comparacion.txt"
OUT_XLSX = OUT_DIR / "coincidencias.xlsx"