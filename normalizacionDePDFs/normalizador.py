# normalizador.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Iterable, Literal, Protocol
import re
import unicodedata

import pandas as pd
from extractor import ExtractorCrudo

# -----------------------------
# Utilidades de texto / parsing 
# -----------------------------
def nz(s: Any) -> str:
    # Convierte a str; devuelve '' para None/NaN.
    if s is None:
        return ""
    try:
        if pd.isna(s):
            return ""
    except Exception:
        pass
    return str(s)

def strip_accents_upper(s: Any) -> str:
    # Quita diacríticos y pasa a UPPER (robusto para encabezados).
    s0 = nz(s)
    s_norm = unicodedata.normalize("NFKD", s0)
    s_ascii = "".join(ch for ch in s_norm if not unicodedata.combining(ch))
    return s_ascii.upper()

def split_lines_basic(cell: str) -> List[str]:
    s = nz(cell).strip()
    if not s:
        return []
    return [x.strip() for x in s.split("\n") if x.strip()]

_num_token_re = re.compile(r"\b\d{3,5}\b")       # 3–5 dígitos (grupos/claves)
_num_float_re = re.compile(r"\d+(?:[.,]\d+)?")   # enteros/decimales (métricas)
ETIQUETA_SEG_RE = re.compile(r"(INTERINO|DEFINITIVO)", re.I)
TOTALES_RE = re.compile(r"\bTOTALES\b", re.I)

def split_cell(cell: str, kind: Literal["clave", "grupo", "metric", "text"]) -> List[str]:
    s = nz(cell).strip()
    if not s:
        return []

    if kind in ("clave", "grupo"):
        parts = split_lines_basic(s)
        if len(parts) > 1:
            return parts
        tokens = _num_token_re.findall(s)
        return tokens if tokens else ([s] if s else [])

    if kind == "metric":
        parts = split_lines_basic(s)
        if len(parts) > 1:
            return [p.replace(",", ".") for p in parts]
        tokens = _num_float_re.findall(s)
        return [t.replace(",", ".") for t in tokens] if tokens else ([s] if s else [])

    return split_lines_basic(s)

def looks_digit(s: str) -> bool:
    return nz(s).strip().isdigit()

def first_line(s: str) -> str:
    lst = split_lines_basic(s)
    return lst[0] if lst else ""

def dedup_categoria(cat: str) -> str:
    s = first_line(cat)
    s = re.sub(r"(PROF\.\s*ASIG\.\s*A\s*(?:INT|DEF)\.)\s*(\1\s*)+", r"\1", s, flags=re.IGNORECASE)
    s = re.sub(r"(PROF\.\s*ASIG\.\s*[A-Z]\s*(?:INT|DEF)\.)\s*(\1\s*)+", r"\1", s, flags=re.IGNORECASE)
    return s

TIPO_RE_INT = re.compile(r"\bINT\.?\b", re.I)
TIPO_RE_DEF = re.compile(r"\bDEF\.?\b", re.I)

def derive_tot_tipo_from_categoria(cat: Any) -> str:
    uc = nz(cat).upper()
    if TIPO_RE_INT.search(uc): return "INTERINO"
    if TIPO_RE_DEF.search(uc): return "DEFINITIVO"
    return ""  # desconocido/ vacío si no macha

# ----------------------------------
# Protocols para tipado de extractor
# ----------------------------------
class _Row(Protocol):
    header_level: int
    cells: List[str]

class _Page(Protocol):
    rows: List[_Row]

# ------- 
# Modelos 
# -------
@dataclass(slots=True)
class ColMap:
    no: int
    profesor: int
    categoria: int
    clave: int
    asignatura: int
    grupo_anterior: int
    grupo_actual: int
    sem_ant_teo: int
    sem_ant_pra: int
    sem_ant_total: int
    sem_act_teo: int
    sem_act_pra: int
    sem_act_total: int

# ------------
# Normalizador
# ------------
class Normalizador:
    """
    Consume páginas crudas (del Extractor) y devuelve un DataFrame normalizado.
    Flujo típico:
        norm = Normalizador()
        for raw_page in ExtractorCrudo(pdf).iter_pages():
            norm.consume_page(raw_page)
        df = norm.finish()
    """

    def __init__(self):
        self.rows: List[Dict] = []
        self.prof = {"no": "", "nombre": ""}
        self._prof_row_idxs: List[int] = []
        self._last_tot_fingerprint: Optional[str] = None
        self._global_order_counter = 0  # para preservar orden de aparición

    def reset(self) -> None:
        self.__init__()

    # detección de columnas por página
    def detect_columns(self, raw_rows: Iterable[_Row]) -> ColMap:
        h0 = next((r for r in raw_rows if r.header_level == 1), None)
        h1 = next((r for r in raw_rows if r.header_level == 2), None)
        if not h0 or not h1:
            raise RuntimeError("No encontré encabezados (header_level 1/2) en esta página.")

        def find_like(cells: List[str], keys: List[str]) -> Optional[int]:
            for i, v in enumerate(cells):
                val = strip_accents_upper(v)
                if any(k in val for k in keys):
                    return i
            return None

        idx_no = find_like(h0.cells, ["NO"])
        idx_prof = find_like(h0.cells, ["PROFESOR"])
        idx_cat = find_like(h0.cells, ["CATEG"])
        idx_clav = find_like(h0.cells, ["CLAVE"])
        idx_asig = find_like(h0.cells, ["ASIGNAT"])

        tokens: Dict[str, List[int]] = {}
        for i, v in enumerate(h1.cells):
            tok = strip_accents_upper(v).strip()
            if tok in ["ANTERIOR", "ACTUAL", "TEO", "PRA", "TOTAL"]:
                tokens.setdefault(tok, []).append(i)

        if not tokens.get("ANTERIOR") or not tokens.get("ACTUAL"):
            raise RuntimeError(f"No encontré 'Anterior/Actual' en subcabecera. Tokens: {tokens}")

        teos = sorted(tokens.get("TEO", []))
        pras = sorted(tokens.get("PRA", []))
        tots = sorted(tokens.get("TOTAL", []))
        if len(teos) < 2 or len(pras) < 2 or len(tots) < 2:
            raise RuntimeError(f"No pude emparejar TEO/PRA/TOTAL para ambas bandas. Tokens: {tokens}")

        sem_ant_teo, sem_act_teo = teos[0], teos[1]
        sem_ant_pra, sem_act_pra = pras[0], pras[1]
        sem_ant_total, sem_act_total = tots[0], tots[1]
        grupo_anterior = min(tokens["ANTERIOR"])
        grupo_actual = min(tokens["ACTUAL"])

        return ColMap(
            no=idx_no,
            profesor=idx_prof,
            categoria=idx_cat,
            clave=idx_clav,
            asignatura=idx_asig,
            grupo_anterior=grupo_anterior,
            grupo_actual=grupo_actual,
            sem_ant_teo=sem_ant_teo,
            sem_ant_pra=sem_ant_pra,
            sem_ant_total=sem_ant_total,
            sem_act_teo=sem_act_teo,
            sem_act_pra=sem_act_pra,
            sem_act_total=sem_act_total,
        )

    # helpers de TOTALES
    def _row_has_totales(self, cells: List[str]) -> bool:
        return bool(TOTALES_RE.search(" | ".join(nz(x) for x in cells)))

    def _row_tipo_totales(self, cells: List[str]) -> str:
        m = ETIQUETA_SEG_RE.search(" | ".join(nz(x) for x in cells))
        return (m.group(1).upper() if m else "TOTALES")

    def _apply_totals_to_prof_rows(self, nums: List[str], tipo: str) -> int:
        """
        Aplica totales a las filas del profesor actual; devuelve cuántas filas se actualizaron.
        Cambios:
          - Fallback: si no hay INT/DEF en categorías visibles, aplica a todos.
          - Si tot_tipo no puede derivarse desde la categoría, usa 'tipo' de la línea de totales (si es INTERINO/DEFINITIVO).
        """
        if not self._prof_row_idxs:
            return 0

        cats = [str(self.rows[ridx].get("categoria", "")) for ridx in self._prof_row_idxs]
        has_int = any("INT" in c.upper() for c in cats)
        has_def = any("DEF" in c.upper() for c in cats)

        def matches_tipo(cat: str) -> bool:
            uc = str(cat).upper()
            if has_int or has_def:
                if tipo == "INTERINO":
                    return "INT" in uc
                if tipo == "DEFINITIVO":
                    return "DEF" in uc
                return True  # "TOTALES" genérico
            # Fallback: sin INT/DEF en categorías → aplica a todos
            return True

        updated = 0
        for ridx in self._prof_row_idxs:
            r = self.rows[ridx]
            if matches_tipo(r.get("categoria", "")):
                (r["TOT_sem_ant_teo"], r["TOT_sem_ant_pra"], r["TOT_sem_ant_total"],
                 r["TOT_sem_act_teo"], r["TOT_sem_act_pra"], r["TOT_sem_act_total"]) = nums

                derived = derive_tot_tipo_from_categoria(r.get("categoria", ""))
                # Si no se puede derivar desde la categoría y el tipo de la línea es válido, úsalo
                r["tot_tipo"] = derived or (tipo if tipo in ("INTERINO", "DEFINITIVO") else r.get("tot_tipo", ""))
                updated += 1

        return updated

    def _start_new_prof(self, no: str, nombre: str):
        self._prof_row_idxs.clear()
        self.prof["no"] = no
        self.prof["nombre"] = nombre
        self._last_tot_fingerprint = None

    # detección de filas de continuación
    def _is_cont_right_only(self, cells, colmap) -> bool:
        c0 = nz(cells[colmap.no]) if colmap.no is not None else ""
        c1 = nz(cells[colmap.profesor]) if colmap.profesor is not None else ""
        c2 = nz(cells[colmap.categoria]) if colmap.categoria is not None else ""
        c3 = nz(cells[colmap.clave]) if colmap.clave is not None else ""
        c4 = nz(cells[colmap.asignatura]) if colmap.asignatura is not None else ""
        return (not c0 and not c1 and not c2 and not c3 and bool(c4))

    def _is_cont_shifted(self, cells, colmap) -> bool:
        c0 = nz(cells[colmap.no]) if colmap.no is not None else ""
        c1 = nz(cells[colmap.profesor]) if colmap.profesor is not None else ""
        c4 = nz(cells[colmap.asignatura]) if colmap.asignatura is not None else ""
        if c4:
            return False
        g_ant = nz(cells[colmap.grupo_anterior])
        return (not c0 and not c1 and len(g_ant) > 10 and " " in g_ant)

    def _get_next_order(self) -> int:
        current = self._global_order_counter
        self._global_order_counter += 1
        return current

    # consume una página completa
    def consume_page(self, raw_page: _Page) -> None:
        if not raw_page.rows:
            return

        colmap = self.detect_columns(raw_page.rows)

        i = 0
        while i < len(raw_page.rows):
            rr = raw_page.rows[i]
            if rr.header_level in (1, 2):
                i += 1
                continue

            cells = rr.cells
            c_no = nz(cells[colmap.no]) if colmap.no is not None else ""
            c_prof = nz(cells[colmap.profesor]) if colmap.profesor is not None else ""
            c_cat = nz(cells[colmap.categoria]) if colmap.categoria is not None else ""
            c_clav = nz(cells[colmap.clave]) if colmap.clave is not None else ""
            c_asig = nz(cells[colmap.asignatura]) if colmap.asignatura is not None else ""
            c_gant = nz(cells[colmap.grupo_anterior])
            c_gact = nz(cells[colmap.grupo_actual])

            # TOTALES (en cualquier columna)
            if self._row_has_totales(cells):
                nums = [
                    nz(cells[colmap.sem_ant_teo]),
                    nz(cells[colmap.sem_ant_pra]),
                    nz(cells[colmap.sem_ant_total]),
                    nz(cells[colmap.sem_act_teo]),
                    nz(cells[colmap.sem_act_pra]),
                    nz(cells[colmap.sem_act_total]),
                ]
                fp = "|".join(nums)
                if self._last_tot_fingerprint != fp:
                    tipo = self._row_tipo_totales(cells)  # "INTERINO"/"DEFINITIVO"/"TOTALES"
                    applied = self._apply_totals_to_prof_rows(nums, tipo)
                    if applied > 0:
                        self._last_tot_fingerprint = fp
                i += 1
                continue

            # Nueva persona
            if looks_digit(c_no) and c_prof:
                self._start_new_prof(no=c_no, nombre=c_prof)

            # Fila de continuación
            if self._is_cont_right_only(cells, colmap) or self._is_cont_shifted(cells, colmap):
                if self._is_cont_right_only(cells, colmap):
                    extra_claves = nz(cells[colmap.clave])
                    extra_asigs = nz(cells[colmap.asignatura])
                    gant_extra = nz(cells[colmap.grupo_anterior])
                    gact_extra = nz(cells[colmap.grupo_actual])
                    ant_teo_e = nz(cells[colmap.sem_ant_teo])
                    ant_pra_e = nz(cells[colmap.sem_ant_pra])
                    ant_tot_e = nz(cells[colmap.sem_ant_total])
                    act_teo_e = nz(cells[colmap.sem_act_teo])
                    act_pra_e = nz(cells[colmap.sem_act_pra])
                    act_tot_e = nz(cells[colmap.sem_act_total])
                else:
                    # Desplazada
                    extra_claves = nz(cells[colmap.asignatura])
                    extra_asigs = nz(cells[colmap.grupo_anterior])
                    gant_extra = nz(cells[colmap.grupo_actual])
                    gact_extra = nz(cells[colmap.sem_ant_teo])
                    ant_teo_e = nz(cells[colmap.sem_ant_pra])
                    ant_pra_e = nz(cells[colmap.sem_ant_total])
                    ant_tot_e = nz(cells[colmap.sem_act_teo])
                    act_teo_e = nz(cells[colmap.sem_act_pra])
                    act_pra_e = nz(cells[colmap.sem_act_total])
                    act_tot_e = (
                        nz(cells[colmap.sem_act_total + 1]) if len(cells) > colmap.sem_act_total + 1 else ""
                    )

                claves_extra = split_cell(extra_claves, kind="clave")
                asigns_extra = split_cell(extra_asigs, kind="text")
                gant_extra = split_cell(gant_extra, kind="grupo")
                gact_extra = split_cell(gact_extra, kind="grupo")
                ant_teo_extra = split_cell(ant_teo_e, kind="metric")
                ant_pra_extra = split_cell(ant_pra_e, kind="metric")
                ant_tot_extra = split_cell(ant_tot_e, kind="metric")
                act_teo_extra = split_cell(act_teo_e, kind="metric")
                act_pra_extra = split_cell(act_pra_e, kind="metric")
                act_tot_extra = split_cell(act_tot_e, kind="metric")

                K = max(1, len(asigns_extra))

                def fitK(lst: List[str]) -> List[str]:
                    if len(lst) == K:
                        return lst
                    if len(lst) > K:
                        return lst[:K]
                    return lst + [""] * (K - len(lst))

                claves_extra = fitK(claves_extra)
                asigns_extra = fitK(asigns_extra)
                gant_extra = fitK(gant_extra)
                gact_extra = fitK(gact_extra)
                ant_teo_extra = fitK(ant_teo_extra)
                ant_pra_extra = fitK(ant_pra_extra)
                ant_tot_extra = fitK(ant_tot_extra)
                act_teo_extra = fitK(act_teo_extra)
                act_pra_extra = fitK(act_pra_extra)
                act_tot_extra = fitK(act_tot_extra)

                # Huecos (últimas filas sin asignatura) en orden de aparición
                hole_indices = [idx for idx in self._prof_row_idxs if self.rows[idx].get("asignatura", "") == ""]
                fill_n = min(len(hole_indices), K)

                # Rellenar; si los datos venían invertidos.
                for j in range(fill_n):
                    ridx = hole_indices[j]
                    data_idx = fill_n - 1 - j  # reverso
                    self.rows[ridx]["asignatura"] = asigns_extra[data_idx]
                    self.rows[ridx]["grupo_anterior"] = gant_extra[data_idx]
                    self.rows[ridx]["grupo_actual"] = gact_extra[data_idx]
                    self.rows[ridx]["sem_ant_teo"] = ant_teo_extra[data_idx]
                    self.rows[ridx]["sem_ant_pra"] = ant_pra_extra[data_idx]
                    self.rows[ridx]["sem_ant_total"] = ant_tot_extra[data_idx]
                    self.rows[ridx]["sem_act_teo"] = act_teo_extra[data_idx]
                    self.rows[ridx]["sem_act_pra"] = act_pra_extra[data_idx]
                    self.rows[ridx]["sem_act_total"] = act_tot_extra[data_idx]
                    if not self.rows[ridx].get("clave_asig"):
                        self.rows[ridx]["clave_asig"] = claves_extra[data_idx]

                # Si sobran, agregarlas como nuevas filas
                if K > fill_n:
                    last_cat = ""
                    for idx in reversed(self._prof_row_idxs):
                        last_cat = self.rows[idx].get("categoria", "")
                        if last_cat:
                            break
                    for j in range(fill_n, K):
                        rec = {
                            "no_prof": self.prof["no"],
                            "profesor": self.prof["nombre"],
                            "categoria": last_cat,
                            "clave_asig": claves_extra[j],
                            "asignatura": asigns_extra[j],
                            "grupo_anterior": gant_extra[j],
                            "grupo_actual": gact_extra[j],
                            "sem_ant_teo": ant_teo_extra[j],
                            "sem_ant_pra": ant_pra_extra[j],
                            "sem_ant_total": ant_tot_extra[j],
                            "sem_act_teo": act_teo_extra[j],
                            "sem_act_pra": act_pra_extra[j],
                            "sem_act_total": act_tot_extra[j],
                            "tot_tipo": "",
                            "TOT_sem_ant_teo": "",
                            "TOT_sem_ant_pra": "",
                            "TOT_sem_ant_total": "",
                            "TOT_sem_act_teo": "",
                            "TOT_sem_act_pra": "",
                            "TOT_sem_act_total": "",
                            "_order": self._get_next_order(),
                        }
                        self.rows.append(rec)
                        self._prof_row_idxs.append(len(self.rows) - 1)

                i += 1
                continue

            # Fila vacía irrelevante
            if not (c_clav or c_asig):
                i += 1
                continue

            # Fila normal (con clave/asignatura explícita)
            claves = split_cell(c_clav, kind="clave")
            asigns = split_cell(c_asig, kind="text")
            gant = split_cell(c_gant, kind="grupo")
            gact = split_cell(c_gact, kind="grupo")
            ant_teo = split_cell(cells[colmap.sem_ant_teo], kind="metric")
            ant_pra = split_cell(cells[colmap.sem_ant_pra], kind="metric")
            ant_tot = split_cell(cells[colmap.sem_ant_total], kind="metric")
            act_teo = split_cell(cells[colmap.sem_act_teo], kind="metric")
            act_pra = split_cell(cells[colmap.sem_act_pra], kind="metric")
            act_tot = split_cell(cells[colmap.sem_act_total], kind="metric")

            cat_lines = split_lines_basic(c_cat)
            K = max(1, len(claves))

            def fitK(lst: List[str]) -> List[str]:
                if len(lst) == K:
                    return lst
                if len(lst) > K:
                    return lst[:K]
                return lst + [""] * (K - len(lst))

            if len(asigns) == 1 and K > 1:
                asigns = asigns * K

            claves = fitK(claves)
            asigns = fitK(asigns)
            gant = fitK(gant)
            gact = fitK(gact)
            ant_teo = fitK(ant_teo)
            ant_pra = fitK(ant_pra)
            ant_tot = fitK(ant_tot)
            act_teo = fitK(act_teo)
            act_pra = fitK(act_pra)
            act_tot = fitK(act_tot)

            def cat_for(j: int) -> str:
                if cat_lines:
                    if j < len(cat_lines) and cat_lines[j]:
                        return cat_lines[j]
                    return cat_lines[-1]
                return ""

            for j in range(K):
                rec = {
                    "no_prof": self.prof["no"],
                    "profesor": self.prof["nombre"],
                    "categoria": cat_for(j),
                    "clave_asig": claves[j],
                    "asignatura": asigns[j],
                    "grupo_anterior": gant[j],
                    "grupo_actual": gact[j],
                    "sem_ant_teo": ant_teo[j],
                    "sem_ant_pra": ant_pra[j],
                    "sem_ant_total": ant_tot[j],
                    "sem_act_teo": act_teo[j],
                    "sem_act_pra": act_pra[j],
                    "sem_act_total": act_tot[j],
                    "tot_tipo": "",
                    "TOT_sem_ant_teo": "",
                    "TOT_sem_ant_pra": "",
                    "TOT_sem_ant_total": "",
                    "TOT_sem_act_teo": "",
                    "TOT_sem_act_pra": "",
                    "TOT_sem_act_total": "",
                    "_order": self._get_next_order(),
                }
                self.rows.append(rec)
                self._prof_row_idxs.append(len(self.rows) - 1)

            i += 1

    def finish(self) -> pd.DataFrame:
        df = pd.DataFrame(self.rows)

        # Orden natural de aparición
        if "_order" in df.columns:
            df = df.sort_values("_order").reset_index(drop=True)
            df = df.drop(columns=["_order"])

        # Voltear claves en bloques DEF sólo si el profesor tiene INT y DEF (runs contiguos)
        if not df.empty and {"no_prof", "categoria", "clave_asig"}.issubset(df.columns):
            for _, g in df.groupby("no_prof", sort=False):
                cats = g["categoria"].astype(str)
                tiene_int = cats.str.contains("INT", case=False, na=False).any()
                tiene_def = cats.str.contains("DEF", case=False, na=False).any()
                if not (tiene_int and tiene_def):
                    continue
                # runs contiguos DEF (añadimos centinela False)
                idxs = g.index.to_list()
                is_def = cats.str.contains("DEF", case=False, na=False).to_list()
                run_start = None
                for k, flag in enumerate(is_def + [False]):
                    if flag and run_start is None:
                        run_start = k
                    elif not flag and run_start is not None:
                        run_end = k - 1
                        block_idx = idxs[run_start:run_end + 1]
                        if len(block_idx) > 1:
                            df.loc[block_idx, "clave_asig"] = list(df.loc[block_idx, "clave_asig"])[::-1]
                        run_start = None

        # Reparación de mojibake común (latin1->utf8) en textos principales (aplica con cuidado)
        def _fix_mojibake(s: Any) -> Any:
            if not isinstance(s, str) or not s:
                return s
            try:
                return s.encode("latin1", "ignore").decode("utf8", "ignore")
            except Exception:
                return s

        for col in ("asignatura", "profesor", "categoria"):
            if col in df.columns:
                df[col] = df[col].map(_fix_mojibake)

        # Convierte métricas a float donde aplique
        metric_cols = [
            "sem_ant_teo", "sem_ant_pra", "sem_ant_total",
            "sem_act_teo", "sem_act_pra", "sem_act_total",
            "TOT_sem_ant_teo", "TOT_sem_ant_pra", "TOT_sem_ant_total",
            "TOT_sem_act_teo", "TOT_sem_act_pra", "TOT_sem_act_total",
        ]
        for mcol in metric_cols:
            if mcol in df.columns:
                df[mcol] = pd.to_numeric(df[mcol], errors="coerce")

        # Deriva tot_tipo sólo donde esté vacío; respeta lo ya asignado en la aplicación de totales
        if "categoria" in df.columns:
            derived = df["categoria"].map(derive_tot_tipo_from_categoria)
            if "tot_tipo" in df.columns:
                existing = df["tot_tipo"].astype(str)
                df["tot_tipo"] = existing.where(existing.str.len() > 0, derived)
            else:
                df["tot_tipo"] = derived

        return df

# --------------------
# Helper de alto nivel
# --------------------
def normalizar_pdf(pdf_path: Union[str, Path]) -> pd.DataFrame:
    """
    Atajo: abre el PDF con ExtractorCrudo, consume todas las páginas
    con el Normalizador y devuelve el DataFrame final.
    """
    norm = Normalizador()
    for raw_page in ExtractorCrudo(pdf_path).iter_pages():
        norm.consume_page(raw_page)
    return norm.finish()