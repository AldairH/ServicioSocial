# main.py
from __future__ import annotations
from pathlib import Path
from typing import List

import pandas as pd

from normalizador import normalizar_pdf


def _exportar_excel(df: pd.DataFrame, out_xlsx: Path) -> None:
    out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    try:
        with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="normalizado", index=False)
            ws = writer.sheets["normalizado"]

            # Ancho de columnas (heurística rápida) + congelar encabezado
            for i, col in enumerate(df.columns):
                sample_lens = [len(str(col))] + [len(str(x)) for x in df[col].head(200)]
                width = min(max(sample_lens) + 2, 42)
                ws.set_column(i, i, width)
            ws.freeze_panes(1, 0)
    except Exception:
        # Fallback si no está xlsxwriter
        df.to_excel(out_xlsx, sheet_name="normalizado", index=False)


def _listar_pdfs_en_cwd() -> List[Path]:
    cwd = Path.cwd()
    return sorted(p for p in cwd.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


def main() -> None:
    pdfs = _listar_pdfs_en_cwd()
    if not pdfs:
        print("No se encontraron PDFs en la ruta de ejecución.")
        return

    out_dir = Path("out")
    procesados = 0
    fallidos = []

    print(f"Detectados {len(pdfs)} PDF(s) en {Path.cwd()}\n")

    for pdf in pdfs:
        try:
            print(f"→ Procesando: {pdf.name} ...", end="", flush=True)
            df = normalizar_pdf(pdf)
            out_xlsx = out_dir / f"{pdf.stem}_normalizado.xlsx"
            _exportar_excel(df, out_xlsx)
            print(f" OK  ({len(df)} filas)  →  {out_xlsx}")
            procesados += 1
        except Exception as e:
            print(" ERROR")
            fallidos.append((pdf.name, str(e)))

    # Resumen
    print("\n Completado.")
    print(f"   PDFs procesados con éxito: {procesados}/{len(pdfs)}")
    if fallidos:
        print("   Fallidos:")
        for name, msg in fallidos:
            print(f"     - {name}: {msg}")


if __name__ == "__main__":
    main()
