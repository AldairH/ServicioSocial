from __future__ import annotations
import re
from typing import Tuple
from unidecode import unidecode

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
    # dd/mm/yyyy o dd-mm-yyyy
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", s)
    if m:
        d, m_, y = m.groups()
        return f"{int(y):04d}-{int(m_):02d}-{int(d):02d}"
    # yyyy-mm-dd
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)
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