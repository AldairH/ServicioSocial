from __future__ import annotations
from typing import List, Dict, Optional
import re

import pymupdf

from normalizers import (
    norm_header_key, norm_clave, norm_fecha, norm_hora,
    norm_grupo, norm_salon, parse_materia_cell
)

# ---------- Extracción común ----------

def extract_tables(page) -> List[List[List[str]]]:
    ft = page.find_tables()
    return [t.extract() for t in ft.tables]

# ---------- doc.pdf ----------

def rows_from_doc_matrix(matrix: List[List[str]]) -> List[Dict[str, str]]:
    if not matrix or not matrix[0]:
        return []

    header_norm = [norm_header_key(h) for h in matrix[0]]

    def idx(*keys_like: str) -> Optional[int]:
        for i, h in enumerate(header_norm):
            if any(k in h for k in keys_like):
                return i
        return None

    i_claveplan = idx("CLAVE", "PLAN")
    i_materia   = idx("MATERIA")
    i_hora      = idx("HORA")
    i_salon     = idx("SALON")
    i_fecha     = idx("FECHA")
    if any(x is None for x in [i_claveplan, i_materia, i_hora, i_salon, i_fecha]):
        return []

    out: List[Dict[str, str]] = []
    for row in matrix[1:]:
        if len(row) <= max(i_claveplan, i_materia, i_hora, i_salon, i_fecha):
            continue

        # CLAVE: primera línea de CLAVE/PLAN
        clave_plan = (row[i_claveplan] or "").strip()
        first_line = clave_plan.split("\n")[0] if "\n" in clave_plan else clave_plan
        clave = norm_clave(first_line)

        materia_cell = (row[i_materia] or "")
        materia, grupo, p1, p2 = parse_materia_cell(materia_cell)

        rec = {
            "CLAVE": clave,
            "GRUPO": norm_grupo(grupo),
            "MATERIA": materia,
            "P1": p1,
            "P2": p2,
            "FECHA": norm_fecha(row[i_fecha] or ""),
            "HORA":  norm_hora(row[i_hora] or ""),
            "SALON": norm_salon(row[i_salon] or ""),
        }
        if rec["CLAVE"] and (rec["GRUPO"] or rec["HORA"] or rec["FECHA"]):
            out.append(rec)
    return out

def load_doc(path: str) -> List[Dict[str, str]]:
    doc = pymupdf.open(path)
    try:
        rows: List[Dict[str, str]] = []
        for p in doc:
            for m in extract_tables(p):
                rows.extend(rows_from_doc_matrix(m))
        for r in rows:
            for k in r:
                r[k] = str(r[k]).strip()
        rows = [r for r in rows if r["CLAVE"]]
        print(f"[{path}] filas extraídas: {len(rows)}")
        return rows
    finally:
        doc.close()

# ---------- INGENIERIA EN COMPUTACION.pdf ----------

def indices_diag(header_norm: List[str]) -> Dict[str, Optional[int]]:
    def idx(*keys_like: str) -> Optional[int]:
        for i, h in enumerate(header_norm):
            if any(k in h for k in keys_like):
                return i
        return None

    return {
        "CLAVE":  idx("CVEMAT", "CVE", "CLAVE"),
        "GRUPO":  idx("GRUPO"),
        "MATERIA": idx("MATERIA", "ASIGNATURA"),
        "P1":     idx("PROFESOR1", "PROFESOR 1", "P1", "DOCENTE1"),
        "P2":     idx("PROFESOR2", "PROFESOR 2", "P2", "DOCENTE2"),
        "FECHA":  idx("FECHA"),
        "HORA":   idx("HORA"),
        "SALON":  idx("SALON", "AULA"),
    }

def auto_map_diag(matrix: List[List[str]], header_norm: List[str],
                  idxs: Dict[str, Optional[int]]) -> Dict[str, int]:
    n = len(matrix[0])
    cols = list(zip(*matrix[1:])) if len(matrix) > 1 else [[]] * n

    def vals(j):
        return [str(v or "").strip() for v in cols[j]] if j is not None and 0 <= j < n else []

    used = {v for v in idxs.values() if isinstance(v, int)}
    remain = [j for j in range(n) if j not in used]

    def pick(score_fn):
        best, bests = None, -1.0
        for j in list(remain):
            v = vals(j)
            if not v:
                continue
            s = score_fn(v)
            if s > bests:
                best, bests = j, s
        if best is not None:
            remain.remove(best)
        return best

    pct = lambda cond, N: (sum(1 for b in cond if b) / max(N, 1))

    def sc_clave(v):
        return pct([bool(re.fullmatch(r"\d{4,}", re.sub(r"\D", "", x))) for x in v], len(v))

    def sc_grupo(v):
        return pct([bool(re.fullmatch(r"[A-Z]{2}\d{2}", norm_grupo(x))) for x in v], len(v))

    def sc_hora(v):
        return pct([bool(re.search(r"\d{1,2}:\d{2}", x)) for x in v], len(v))

    def sc_fecha(v):
        return pct([
            bool(re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b", x))
            for x in v
        ], len(v))

    def sc_salon(v):
        return pct([
            (
                lambda norm: (
                    bool(re.fullmatch(r"[A-Z]{1,2}\d{2,5}", norm))
                    or norm in {"VIRTUAL", "N/D"}
                )
            )(norm_salon(x))
            for x in v
        ], len(v))

    def sc_len(v):
        return sum(len(x) for x in v) / max(len(v), 1)

    if idxs["CLAVE"]  is None: idxs["CLAVE"]  = pick(sc_clave)
    if idxs["FECHA"]  is None: idxs["FECHA"]  = pick(sc_fecha)
    if idxs["HORA"]   is None: idxs["HORA"]   = pick(sc_hora)
    if idxs["GRUPO"]  is None: idxs["GRUPO"]  = pick(sc_grupo)
    if idxs["SALON"]  is None: idxs["SALON"]  = pick(sc_salon)
    if idxs["MATERIA"] is None: idxs["MATERIA"] = pick(sc_len)
    if idxs["P1"]     is None: idxs["P1"]     = pick(sc_len)
    if idxs["P2"]     is None: idxs["P2"]     = pick(sc_len)
    return {k: int(v) for k, v in idxs.items() if v is not None}

def rows_from_diag_matrix(matrix: List[List[str]]) -> List[Dict[str, str]]:
    if not matrix or not matrix[0]:
        return []

    header_norm = [norm_header_key(h) for h in matrix[0]]
    idxs = indices_diag(header_norm)
    idxs = auto_map_diag(matrix, header_norm, idxs)

    required = {"CLAVE", "GRUPO", "MATERIA", "FECHA", "HORA"}
    if not required.issubset(set(idxs.keys())):
        return []

    out: List[Dict[str, str]] = []
    for row in matrix[1:]:
        n = len(row)

        def safe_val(name: str) -> str:
            j = idxs.get(name)
            return str(row[j]).strip() if j is not None and j < n else ""

        rec = {
            "CLAVE":  norm_clave(safe_val("CLAVE")),
            "GRUPO":  norm_grupo(safe_val("GRUPO")),
            "MATERIA": safe_val("MATERIA"),
            "P1":     safe_val("P1"),
            "P2":     safe_val("P2"),
            "FECHA":  norm_fecha(safe_val("FECHA")),
            "HORA":   norm_hora(safe_val("HORA")),
            "SALON":  norm_salon(safe_val("SALON")),
        }
        if rec["CLAVE"]:
            out.append(rec)
    return out

def load_diag(path: str) -> List[Dict[str, str]]:
    doc = pymupdf.open(path)
    try:
        rows: List[Dict[str, str]] = []
        for p in doc:
            for m in extract_tables(p):
                rows.extend(rows_from_diag_matrix(m))
        for r in rows:
            for k in r:
                r[k] = str(r[k]).strip()
        rows = [r for r in rows if r["CLAVE"]]
        print(f"[{path}] filas extraídas: {len(rows)}")
        return rows
    finally:
        doc.close()