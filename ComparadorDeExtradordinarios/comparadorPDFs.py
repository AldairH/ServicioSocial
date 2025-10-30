from __future__ import annotations
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional, FrozenSet

import pymupdf
from unidecode import unidecode
import pandas as pd

# ---------------- Config ----------------
DOC_PATH  = "doc.pdf"
DIAG_PATH = "INGENIERIA EN COMPUTACION.pdf"
OUT_DIR = Path("out"); OUT_DIR.mkdir(exist_ok=True, parents=True)
OUT_TXT = OUT_DIR / "reporte_comparacion.txt"
OUT_XLSX = OUT_DIR / "coincidencias.xlsx"

# ---------- Normalizadores ----------
def norm_header_key(s: str) -> str:
    if s is None: return ""
    u = unidecode(str(s)).upper()
    u = re.sub(r"\s+", "", u)
    return u

def norm_clave(s: str) -> str:
    if not s: return ""
    m = re.search(r"\d+", str(s))
    return str(int(m.group(0))) if m else ""

def norm_fecha(s: str) -> str:
    if not s: return ""
    s = str(s).strip().replace("\n", " ")
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", s)  # dd/mm/yyyy
    if m:
        d, m_, y = m.groups()
        return f"{int(y):04d}-{int(m_):02d}-{int(d):02d}"
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)            # yyyy-mm-dd
    return m.group(0) if m else s

def _pad_time(t: str) -> str:
    h, m = map(int, t.split(":"))
    return f"{h:02d}:{m:02d}"

def norm_hora(s: str) -> str:
    if not s: return ""
    s = str(s).replace("–", "-").replace("—", "-").replace("\u2013", "-")
    s = re.sub(r"\s+", "", s)
    hhmm = re.findall(r"\b\d{1,2}:\d{2}\b", s)
    if len(hhmm) >= 2:
        a, b = _pad_time(hhmm[0]), _pad_time(hhmm[1])
        return f"{a}-{b}"
    return _pad_time(hhmm[0]) if hhmm else s

def norm_prof(s: str) -> str:
    if s is None: return ""
    t = unidecode(str(s)).upper()
    t = re.sub(r"\s+", " ", t).strip()
    return t

def norm_grupo(s: str) -> str:
    if not s: return ""
    s = unidecode(str(s)).upper().strip()
    m = re.search(r"\b([A-Z]{2}\d{2})\b", s)
    return m.group(1) if m else s

def norm_salon(s: str) -> str:
    """Unifica variantes tipo 'VIRTUA'/'VIRTUAL', 'N/D'/'ND'."""
    if not s: return "N/D"
    u = unidecode(str(s)).upper().strip()
    u = u.replace(" ", "")
    if re.fullmatch(r"VIRTU\w*", u) or u == "CLOUD":
        return "VIRTUAL"
    if u in {"N/D", "ND", "NA", "N.A.", "N-A", ""}:
        return "N/D"
    # quitar no alfanuméricos (A-1514 -> A1514)
    u = re.sub(r"[^A-Z0-9]", "", u)
    return u

# ---------- doc.pdf: parse de la celda MATERIA ----------
def parse_materia_cell(cell: str) -> Tuple[str, str, str, str]:
    """
    l1: materia (solo para contexto)
    l2+: 'EA11 Nombre P1', 'EA11 Nombre P2'...
    """
    if not cell: return "", "", "", ""
    lines = [ln.strip() for ln in str(cell).split("\n") if ln.strip()]
    if not lines: return "", "", "", ""
    materia = lines[0]
    prof_lines = lines[1:]

    grupos = []
    profesores = []
    for ln in prof_lines:
        up = unidecode(ln).upper().strip()
        m = re.match(r"^([A-Z]{2}\d{2})\s+(.+)$", up)
        if m:
            g = m.group(1)
            grupos.append(g)
            # saca el nombre preservando acentos del original
            mraw = re.match(r"^[A-Za-z]{2}\d{2}\s+(.+)$", ln.strip())
            profesores.append(mraw.group(1).strip() if mraw else ln.strip()[len(g):].strip())
        else:
            profesores.append(ln.strip())

    grupo = ""
    if grupos:
        grupo = grupos[0] if len(set(grupos)) == 1 else "MULTI"

    p1 = profesores[0] if len(profesores) >= 1 else ""
    p2 = profesores[1] if len(profesores) >= 2 else ""
    return materia, grupo, p1, p2

# ---------- Extracción común ----------
def extract_tables(page) -> List[List[List[str]]]:
    ft = page.find_tables()
    return [t.extract() for t in ft.tables]

# ---------- doc.pdf ----------
def rows_from_doc_matrix(matrix: List[List[str]]) -> List[Dict[str, str]]:
    if not matrix or not matrix[0]: return []
    header_norm = [norm_header_key(h) for h in matrix[0]]

    def idx(*keys_like: str) -> Optional[int]:
        for i, h in enumerate(header_norm):
            if any(k in h for k in keys_like):
                return i
        return None

    i_claveplan = idx("CLAVE","PLAN")
    i_materia   = idx("MATERIA")
    i_hora      = idx("HORA")
    i_salon     = idx("SALON")
    i_fecha     = idx("FECHA")
    if any(x is None for x in [i_claveplan,i_materia,i_hora,i_salon,i_fecha]):
        return []

    out: List[Dict[str,str]] = []
    for row in matrix[1:]:
        if len(row) <= max(i_claveplan,i_materia,i_hora,i_salon,i_fecha): continue

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

def load_doc() -> List[Dict[str,str]]:
    doc = pymupdf.open(DOC_PATH)
    try:
        rows: List[Dict[str,str]] = []
        for p in doc:
            for m in extract_tables(p):
                rows.extend(rows_from_doc_matrix(m))
        for r in rows:
            for k in r: r[k] = str(r[k]).strip()
        rows = [r for r in rows if r["CLAVE"]]
        print(f"[doc.pdf] filas extraídas: {len(rows)}")
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
        "CLAVE":  idx("CVEMAT","CVE","CLAVE"),
        "GRUPO":  idx("GRUPO"),
        "MATERIA":idx("MATERIA","ASIGNATURA"),
        "P1":     idx("PROFESOR1","PROFESOR 1","P1","DOCENTE1"),
        "P2":     idx("PROFESOR2","PROFESOR 2","P2","DOCENTE2"),
        "FECHA":  idx("FECHA"),
        "HORA":   idx("HORA"),
        "SALON":  idx("SALON","AULA"),
    }

def auto_map_diag(matrix: List[List[str]], header_norm: List[str], idxs: Dict[str, Optional[int]]) -> Dict[str,int]:
    n = len(matrix[0])
    cols = list(zip(*matrix[1:])) if len(matrix)>1 else [[]]*n

    def vals(j): return [str(v or "").strip() for v in cols[j]] if j is not None and 0<=j<n else []

    used = {v for v in idxs.values() if isinstance(v,int)}
    remain = [j for j in range(n) if j not in used]

    def pick(score_fn):
        best, bests = None, -1.0
        for j in list(remain):
            v = vals(j)
            if not v: continue
            s = score_fn(v)
            if s>bests:
                best, bests = j, s
        if best is not None: remain.remove(best)
        return best

    pct = lambda cond, N: (sum(1 for b in cond if b)/max(N,1))
    def sc_clave(v): return pct([bool(re.fullmatch(r"\d{4,}", re.sub(r"\D","", x))) for x in v], len(v))
    def sc_grupo(v): return pct([bool(re.fullmatch(r"[A-Z]{2}\d{2}", unidecode(x).upper())) for x in v], len(v))
    def sc_hora(v):  return pct([bool(re.search(r"\d{1,2}:\d{2}", x)) for x in v], len(v))
    def sc_fecha(v): return pct([bool(re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b", x)) for x in v], len(v))
    def sc_salon(v): return pct([bool(re.fullmatch(r"[A-Z]{1,2}\d{2,5}", re.sub(r"[^A-Z0-9]","", unidecode(x).upper()))) or x in {"CLOUD","N/D","ND"} for x in v], len(v))
    def sc_len(v):   return sum(len(x) for x in v)/max(len(v),1)

    if idxs["CLAVE"]  is None: idxs["CLAVE"]  = pick(sc_clave)
    if idxs["FECHA"]  is None: idxs["FECHA"]  = pick(sc_fecha)
    if idxs["HORA"]   is None: idxs["HORA"]   = pick(sc_hora)
    if idxs["GRUPO"]  is None: idxs["GRUPO"]  = pick(sc_grupo)
    if idxs["SALON"]  is None: idxs["SALON"]  = pick(sc_salon)
    if idxs["MATERIA"] is None: idxs["MATERIA"] = pick(sc_len)
    if idxs["P1"]     is None: idxs["P1"]     = pick(sc_len)
    if idxs["P2"]     is None: idxs["P2"]     = pick(sc_len)
    return {k:int(v) for k,v in idxs.items() if v is not None}

def rows_from_diag_matrix(matrix: List[List[str]]) -> List[Dict[str,str]]:
    if not matrix or not matrix[0]: return []
    header_norm = [norm_header_key(h) for h in matrix[0]]
    idxs = indices_diag(header_norm)
    idxs = auto_map_diag(matrix, header_norm, idxs)

    required = {"CLAVE","GRUPO","MATERIA","FECHA","HORA"}
    if not required.issubset(set(idxs.keys())):
        return []

    out: List[Dict[str,str]] = []
    for row in matrix[1:]:
        n = len(row)
        def safe_val(name: str) -> str:
            j = idxs.get(name)
            return str(row[j]).strip() if j is not None and j < n else ""
        rec = {
            "CLAVE":  norm_clave(safe_val("CLAVE")),
            "GRUPO":  norm_grupo(safe_val("GRUPO")),
            "MATERIA":safe_val("MATERIA"),
            "P1":     safe_val("P1"),
            "P2":     safe_val("P2"),
            "FECHA":  norm_fecha(safe_val("FECHA")),
            "HORA":   norm_hora(safe_val("HORA")),
            "SALON":  norm_salon(safe_val("SALON")),
        }
        if rec["CLAVE"]:
            out.append(rec)
    return out

def load_diag() -> List[Dict[str,str]]:
    doc = pymupdf.open(DIAG_PATH)
    try:
        rows: List[Dict[str,str]] = []
        for p in doc:
            for m in extract_tables(p):
                rows.extend(rows_from_diag_matrix(m))
        for r in rows:
            for k in r: r[k] = str(r[k]).strip()
        rows = [r for r in rows if r["CLAVE"]]
        print(f"[diag.pdf] filas extraídas: {len(rows)}")
        return rows
    finally:
        doc.close()

# ---------- Firma y deduplicación ----------
Firma = Tuple[str, str, str, str, FrozenSet[str]]

def firma_sin_materia(rec: Dict[str,str]) -> Firma:
    """Firma operativa (sin nombre de materia y orden de profes ignorado)."""
    return (
        rec.get("GRUPO",""),
        rec.get("FECHA",""),
        rec.get("HORA",""),
        rec.get("SALON",""),
        frozenset({norm_prof(rec.get("P1","")), norm_prof(rec.get("P2",""))} - {""}),
    )

def firma_sort_key(f: Firma):
    grupo, fecha, hora, salon, profes = f
    return (grupo, fecha, hora, salon, tuple(sorted(profes)))

def dedup_por_clave_with_log(rows: List[Dict[str,str]], fuente: str)\
        -> Tuple[Dict[str, Dict[Firma, Dict[str,str]]], List[str], int]:
    """
    Devuelve:
      por_clave[CLAVE][firma] = ejemplo_de_registro
      log_lines: listado de deduplicados colapsados
      total_dedup: cuantos registros se colapsaron
    """
    por_clave: Dict[str, Dict[Firma, Dict[str,str]]] = {}
    counts: Dict[str, Dict[Firma, int]] = {}
    for r in rows:
        clave = str(r.get("CLAVE","")).strip()
        if not clave: continue
        f = firma_sin_materia(r)
        por_clave.setdefault(clave, {})
        counts.setdefault(clave, {})
        counts[clave][f] = counts[clave].get(f, 0) + 1
        if f not in por_clave[clave]:
            por_clave[clave][f] = r

    log_lines: List[str] = []
    total_dedup = 0
    for clave, fdict in counts.items():
        for f, c in fdict.items():
            if c > 1:
                total_dedup += (c - 1)
                r = por_clave[clave][f]
                pset = {r.get("P1",""), r.get("P2","")} - {""}
                log_lines.append(
                    f"- [{fuente}] CLAVE {clave}: colapsados {c-1} duplicados → "
                    f"GRUPO={r.get('GRUPO','')}, FECHA={r.get('FECHA','')}, "
                    f"HORA={r.get('HORA','')}, SALON={r.get('SALON','')}, "
                    f"PROFES={{{'; '.join(sorted(pset))}}}"
                )
    return por_clave, log_lines, total_dedup

# ---------- Comparación ----------
def comparar_sets(A_rows: List[Dict[str,str]], B_rows: List[Dict[str,str]])\
        -> Tuple[int,int,List[str],List[Dict[str,str]],List[str],List[str],int,int]:
    A, logA, totA = dedup_por_clave_with_log(A_rows, "doc.pdf")
    B, logB, totB = dedup_por_clave_with_log(B_rows, "INGENIERIA EN COMPUTACION.pdf")

    claves = sorted(set(A.keys()) | set(B.keys()), key=lambda x: int(x) if x.isdigit() else x)
    coincidencias = 0
    discrepancias = 0
    msgs: List[str] = []
    coincid_rows: List[Dict[str,str]] = []  # para Excel
    i = 1

    for clave in claves:
        A_firmas = set(A.get(clave, {}).keys())
        B_firmas = set(B.get(clave, {}).keys())

        inter = A_firmas & B_firmas
        a_only = A_firmas - B_firmas
        b_only = B_firmas - A_firmas

        coincidencias += len(inter)
        discrepancias += len(a_only) + len(b_only)

        for f in sorted(inter, key=firma_sort_key):
            rec = A.get(clave, {}).get(f) or B.get(clave, {}).get(f)
            coincid_rows.append({
                "CLAVE":  clave,
                "GRUPO":  rec.get("GRUPO",""),
                "MATERIA":rec.get("MATERIA",""),
                "P1":     rec.get("P1",""),
                "P2":     rec.get("P2",""),
                "FECHA":  rec.get("FECHA",""),
                "HORA":   rec.get("HORA",""),
                "SALON":  rec.get("SALON",""),
            })

        # discrepancias solo en A
        for f in sorted(a_only, key=firma_sort_key):
            r = A[clave][f]
            pset = {r.get("P1",""), r.get("P2","")} - {""}
            msgs.append(f"{i}. Discrepancia en materia {r.get('MATERIA','')} con clave {clave}: "
                        f"Registro presente solo en doc.pdf → "
                        f"GRUPO={r.get('GRUPO','')}, FECHA={r.get('FECHA','')}, "
                        f"HORA={r.get('HORA','')}, SALON={r.get('SALON','')}, "
                        f"PROFES={{{'; '.join(sorted(pset))}}}")
            i += 1
        # discrepancias solo en B
        for f in sorted(b_only, key=firma_sort_key):
            r = B[clave][f]
            pset = {r.get("P1",""), r.get("P2","")} - {""}
            msgs.append(f"{i}. Discrepancia en materia {r.get('MATERIA','')} con clave {clave}: "
                        f"Registro presente solo en INGENIERIA EN COMPUTACION.pdf → "
                        f"GRUPO={r.get('GRUPO','')}, FECHA={r.get('FECHA','')}, "
                        f"HORA={r.get('HORA','')}, SALON={r.get('SALON','')}, "
                        f"PROFES={{{'; '.join(sorted(pset))}}}")
            i += 1

    return coincidencias, discrepancias, msgs, coincid_rows, logA, logB, totA, totB

# ---------- Main ----------
def main():
    print("→ Extrayendo doc.pdf…")
    rows_doc = load_doc()

    print("→ Extrayendo INGENIERIA EN COMPUTACION.pdf…")
    rows_diag = load_diag()

    print("→ Colapsando duplicados internos y comparando…")
    coinc, discrep, mensajes, coincid_rows, logA, logB, totA, totB = comparar_sets(rows_doc, rows_diag)

    # ----- TXT -----
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write(f"Total de coincidencias: {coinc}\n")
        f.write(f"Total de Discrepancias: {discrep}\n")

        # Sección de deduplicados
        if logA or logB:
            f.write("\n=== Deduplicados internos (colapsados antes de comparar) ===\n")
            if logA:
                f.write(f"[doc.pdf] Total deduplicados: {totA}\n")
                for line in logA:
                    f.write(line + "\n")
            if logB:
                f.write(f"[INGENIERIA EN COMPUTACION.pdf] Total deduplicados: {totB}\n")
                for line in logB:
                    f.write(line + "\n")

        # Sección de discrepancias
        f.write("\n=== Discrepancias ===\n")
        if mensajes:
            f.write("\n".join(mensajes) + "\n")
        else:
            f.write("Sin discrepancias.\n")

    # ----- Excel con coincidencias -----
    if coincid_rows:
        df = pd.DataFrame(coincid_rows, columns=["CLAVE","GRUPO","MATERIA","P1","P2","FECHA","HORA","SALON"])
        df["CLAVE_INT"] = pd.to_numeric(df["CLAVE"], errors="coerce")
        df.sort_values(by=["CLAVE_INT","GRUPO","FECHA","HORA","SALON"], inplace=True)
        df.drop(columns=["CLAVE_INT"], inplace=True)
        df.to_excel(OUT_XLSX, index=False)
    else:
        df = pd.DataFrame(columns=["CLAVE","GRUPO","MATERIA","P1","P2","FECHA","HORA","SALON"])
        df.to_excel(OUT_XLSX, index=False)

    print("=== RESULTADO ===")
    print(f"Total de coincidencias: {coinc}")
    print(f"Total de Discrepancias: {discrep}")
    print(f"Informe TXT → {OUT_TXT}")
    print(f"Coincidencias Excel → {OUT_XLSX}")

if __name__ == "__main__":
    main()