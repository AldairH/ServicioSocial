from __future__ import annotations
from pathlib import Path
import pandas as pd

from comparator import ComparisonResult

def write_report_txt(out_txt: Path, result: ComparisonResult):
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(f"Total de coincidencias: {result.coincidencias}\n")
        f.write(f"Total de Discrepancias: {result.discrepancias}\n")

        # Sección de deduplicados
        if result.logA or result.logB:
            f.write("\n=== Deduplicados internos (colapsados antes de comparar) ===\n")
            if result.logA:
                f.write(f"[doc.pdf] Total deduplicados: {result.totA}\n")
                for line in result.logA:
                    f.write(line + "\n")
            if result.logB:
                f.write(f"[INGENIERIA EN COMPUTACION.pdf] Total deduplicados: {result.totB}\n")
                for line in result.logB:
                    f.write(line + "\n")

        # Sección de discrepancias
        f.write("\n=== Discrepancias ===\n")
        if result.mensajes:
            f.write("\n".join(result.mensajes) + "\n")
        else:
            f.write("Sin discrepancias.\n")

def write_coincidencias_excel(out_xlsx: Path, result: ComparisonResult):
    cols = ["CLAVE", "GRUPO", "MATERIA", "P1", "P2", "FECHA", "HORA", "SALON"]
    if result.coincid_rows:
        df = pd.DataFrame(result.coincid_rows, columns=cols)
        df["CLAVE_INT"] = pd.to_numeric(df["CLAVE"], errors="coerce")
        df.sort_values(by=["CLAVE_INT", "GRUPO", "FECHA", "HORA", "SALON"], inplace=True)
        df.drop(columns=["CLAVE_INT"], inplace=True)
        df.to_excel(out_xlsx, index=False)
    else:
        df = pd.DataFrame(columns=cols)
        df.to_excel(out_xlsx, index=False)