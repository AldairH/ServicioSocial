# extractor.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Iterator, Union, Optional
try:
    import pymupdf as fitz
except Exception:
    import fitz

# -------
# Modelos
# -------
@dataclass(slots=True)
class RawRow:
    """Fila cruda extraída de una tabla PDF."""
    page: int                 # 1-based
    table_index: int          # 0-based dentro de la página
    row_index: int            # 0-based dentro de la tabla
    header_level: int         # 0 = dato, 1 = header “grande”, 2 = subheader
    cells: List[str]          # ["col_0", "col_1", ..., "col_N"] (siempre str)


@dataclass(slots=True)
class RawPage:
    """Página cruda con las filas detectadas."""
    page: int                 # 1-based
    rows: List[RawRow]        # filas crudas detectadas en esta página

# ---------------
# Extractor crudo
# ---------------
class ExtractorCrudo:
    def __init__(self, pdf_path: Union[str, Path]):
        self.pdf_path = Path(pdf_path)

    @staticmethod
    def _coerce_cell(x) -> str:
        #Normaliza la celda a str, preservando saltos de línea.
        if x is None:
            return ""
        s = str(x)
        # Normaliza finales de línea, pero SIN colapsarlos
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        # Limpia espacios a los lados en cada línea, preservando saltos de línea
        s = "\n".join(part.strip() for part in s.split("\n"))
        return s

    def iter_pages(self) -> Iterator[RawPage]:
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"No existe el archivo: {self.pdf_path}")

        doc = fitz.open(self.pdf_path)
        try:
            for pidx in range(len(doc)):  # pidx: 0-based
                page = doc[pidx]

                # Requiere PyMuPDF con page.find_tables()
                if not hasattr(page, "find_tables"):
                    raise RuntimeError(
                        "Tu versión de PyMuPDF no tiene page.find_tables(). "
                        "Actualiza con: pip install --upgrade pymupdf"
                    )

                rows_out: List[RawRow] = []
                ft = page.find_tables()

                # Si no detecta tablas, devolvemos una página vacía
                if not ft or not getattr(ft, "tables", None):
                    yield RawPage(page=pidx + 1, rows=rows_out)
                    continue

                for tidx, t in enumerate(ft.tables):
                    data = t.extract()  # list[list[celda]]
                    if not data:
                        continue

                    # Calcula ancho máximo para rectangularizar por tabla
                    max_cols = max(len(r) if r else 0 for r in data)

                    for ridx, r in enumerate(data):
                        r = r or []
                        # Rectangulariza y normaliza celdas a str
                        cells = [self._coerce_cell(c) for c in r] + [""] * (max_cols - len(r))

                        header_level = 0
                        if ridx == 0:
                            header_level = 1     # encabezado “grande”
                        elif ridx == 1:
                            header_level = 2     # subencabezado

                        rows_out.append(
                            RawRow(
                                page=pidx + 1,
                                table_index=tidx,
                                row_index=ridx,
                                header_level=header_level,
                                cells=cells,
                            )
                        )
                yield RawPage(page=pidx + 1, rows=rows_out)
        finally:
            doc.close()