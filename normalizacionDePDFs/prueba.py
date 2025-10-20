import pandas as pd
import math
from pathlib import Path

RAW_CSV = Path("out/01_Profesor_Asignatura_raw.csv")
OUT_XLSX = Path("out/01_Profesor_Asignatura_p1_normalizado.xlsx")
OUT_CSV  = Path("out/01_Profesor_Asignatura_p1_normalizado.csv")  # opcional

# ===== Utilidades =====
def nz(s):
    return "" if (s is None or (isinstance(s, float) and math.isnan(s))) else str(s)

def split_lines(cell):
    s = nz(cell).strip()
    if not s:
        return []
    return [x.strip() for x in s.split("\n") if x.strip()]

def is_totales_cell(s):
    return "TOTALES" in nz(s).upper()

def looks_digit(s):
    return nz(s).strip().isdigit()

def first_line(s):
    lst = split_lines(s)
    return lst[0] if lst else ""

def find_col_indices_from_headers(df_page):
    sample_cols = [c for c in df_page.columns if c.startswith("col_")]

    h0 = df_page[df_page["row_index"] == 0]
    h1 = df_page[df_page["row_index"] == 1]
    if h0.empty or h1.empty:
        raise RuntimeError("No encontré filas de encabezado (row_index 0/1) en la página 1.")
    h0, h1 = h0.iloc[0], h1.iloc[0]

    def find_like_in_row(row, keys):
        for c in sample_cols:
            val = nz(row[c]).upper()
            val = (val
                   .replace("Í","I").replace("Á","A").replace("É","E")
                   .replace("Ó","O").replace("Ú","U"))
            if any(k in val for k in keys):
                return int(c.split("_")[1])
        return None

    idx_no   = find_like_in_row(h0, ["NO"])
    idx_prof = find_like_in_row(h0, ["PROFESOR"])
    idx_cat  = find_like_in_row(h0, ["CATEG"])
    idx_clav = find_like_in_row(h0, ["CLAVE"])
    idx_asig = find_like_in_row(h0, ["ASIGNAT"])

    # Tokens de la subcabecera (fila 1)
    tokens = {}
    for c in sample_cols:
        v = nz(h1[c]).strip().upper()
        if v in ["ANTERIOR", "ACTUAL", "TEO", "PRA", "TOTAL"]:
            tokens.setdefault(v, []).append(int(c.split("_")[1]))

    if not tokens.get("ANTERIOR") or not tokens.get("ACTUAL"):
        raise RuntimeError(f"No encontré 'Anterior/Actual' en subcabecera. Tokens: {tokens}")

    teos = sorted(tokens.get("TEO", []))
    pras = sorted(tokens.get("PRA", []))
    tots = sorted(tokens.get("TOTAL", []))
    if len(teos) >= 2 and len(pras) >= 2 and len(tots) >= 2:
        sem_ant_teo, sem_act_teo = teos[0], teos[1]
        sem_ant_pra, sem_act_pra = pras[0], pras[1]
        sem_ant_total, sem_act_total = tots[0], tots[1]
    else:
        raise RuntimeError(f"No pude emparejar TEO/PRA/TOTAL. Tokens: {tokens}")

    grupo_anterior = min(tokens["ANTERIOR"])
    grupo_actual   = min(tokens["ACTUAL"])

    return {
        "no": idx_no,
        "profesor": idx_prof,
        "categoria": idx_cat,
        "clave": idx_clav,
        "asignatura": idx_asig,
        "grupo_anterior": grupo_anterior,
        "grupo_actual": grupo_actual,
        "sem_ant_teo": sem_ant_teo,
        "sem_ant_pra": sem_ant_pra,
        "sem_ant_total": sem_ant_total,
        "sem_act_teo": sem_act_teo,
        "sem_act_pra": sem_act_pra,
        "sem_act_total": sem_act_total,
    }

# ===== Cargar y filtrar página 1 =====
raw = pd.read_csv(RAW_CSV)
page1 = raw[raw["page"] == 1].copy()
idx = find_col_indices_from_headers(page1)

# ===== Normalización (página 1) =====
result = []

# Estado del bloque (usamos un dict para evitar nonlocal/global)
state = {
    "current_no": "",
    "current_prof": "",
    "current_cat": "",
    "block_row_idxs": [],  # índices en result del bloque actual
    "tot_final": None,     # TOTALES (sin tipo) -> preferido
    "tot_def": None,       # DEFINITIVO
    "tot_int": None,       # INTERINO
}

def apply_block_totals(state_dict):
    """Aplica el mejor total del bloque (TOTALES > DEFINITIVO > INTERINO) a todas las filas del bloque."""
    chosen, tipo = None, ""
    if state_dict["tot_final"] is not None:
        chosen, tipo = state_dict["tot_final"], "TOTALES"
    elif state_dict["tot_def"] is not None:
        chosen, tipo = state_dict["tot_def"], "DEFINITIVO"
    elif state_dict["tot_int"] is not None:
        chosen, tipo = state_dict["tot_int"], "INTERINO"
    if chosen is None:
        return
    for ridx in state_dict["block_row_idxs"]:
        r = result[ridx]
        (r["TOT_sem_ant_teo"], r["TOT_sem_ant_pra"], r["TOT_sem_ant_total"],
         r["TOT_sem_act_teo"], r["TOT_sem_act_pra"], r["TOT_sem_act_total"]) = chosen
        r["tot_tipo"] = tipo

for _, row in page1.iterrows():
    if row["row_index"] in (0, 1):
        continue

    c_no   = nz(row.get(f"col_{idx['no']}"))
    c_prof = nz(row.get(f"col_{idx['profesor']}"))
    c_cat  = nz(row.get(f"col_{idx['categoria']}"))
    c_clav = nz(row.get(f"col_{idx['clave']}"))
    c_asig = nz(row.get(f"col_{idx['asignatura']}"))
    c_gant = nz(row.get(f"col_{idx['grupo_anterior']}"))
    c_gact = nz(row.get(f"col_{idx['grupo_actual']}"))

    # --- ¿fila de TOTALES? (puede estar en grupo_anterior o en asignatura)
    if is_totales_cell(c_gant) or is_totales_cell(c_asig):
        tipo = nz(row.get(f"col_{idx['grupo_actual']}")).strip().upper()
        nums = [
            nz(row.get(f"col_{idx['sem_ant_teo']}")),
            nz(row.get(f"col_{idx['sem_ant_pra']}")),
            nz(row.get(f"col_{idx['sem_ant_total']}")),
            nz(row.get(f"col_{idx['sem_act_teo']}")),
            nz(row.get(f"col_{idx['sem_act_pra']}")),
            nz(row.get(f"col_{idx['sem_act_total']}")),
        ]
        if tipo.startswith("DEFINIT"):
            state["tot_def"] = nums
        elif tipo.startswith("INTERIN"):
            state["tot_int"] = nums
        else:
            state["tot_final"] = nums
        # No agregamos registro
        continue

    # --- ¿Nueva persona?
    if looks_digit(c_no) and c_prof:
        # cerrar bloque anterior aplicando totales
        if state["block_row_idxs"]:
            apply_block_totals(state)
        # iniciar estado
        state["current_no"] = c_no
        state["current_prof"] = c_prof
        state["current_cat"] = first_line(c_cat)  # solo la 1ª línea
        state["block_row_idxs"] = []
        state["tot_final"] = state["tot_def"] = state["tot_int"] = None

    # --- Fila útil (con asignatura/clave). Puede ser subfila
    if not (c_clav or c_asig):
        continue

    # expandir subfilas multilínea
    claves = split_lines(c_clav)
    asigns = split_lines(c_asig)
    gant   = split_lines(c_gant)
    gact   = split_lines(c_gact)
    ant_teo = split_lines(row.get(f"col_{idx['sem_ant_teo']}"))
    ant_pra = split_lines(row.get(f"col_{idx['sem_ant_pra']}"))
    ant_tot = split_lines(row.get(f"col_{idx['sem_ant_total']}"))
    act_teo = split_lines(row.get(f"col_{idx['sem_act_teo']}"))
    act_pra = split_lines(row.get(f"col_{idx['sem_act_pra']}"))
    act_tot = split_lines(row.get(f"col_{idx['sem_act_total']}"))

    n = max(len(claves), len(asigns), len(gant), len(gact), len(ant_teo), len(ant_pra), len(ant_tot), len(act_teo), len(act_pra), len(act_tot))
    def pick(lst, i): return lst[i] if i < len(lst) else ""

    for i in range(n):
        rec = {
            "no_prof": state["current_no"],
            "profesor": state["current_prof"],
            "categoria": state["current_cat"],   # siempre la del encabezado del profesor
            "clave_asig": pick(claves, i),
            "asignatura": pick(asigns, i),
            "grupo_anterior": pick(gant, i),
            "grupo_actual": pick(gact, i),
            "sem_ant_teo": pick(ant_teo, i),
            "sem_ant_pra": pick(ant_pra, i),
            "sem_ant_total": pick(ant_tot, i),
            "sem_act_teo": pick(act_teo, i),
            "sem_act_pra": pick(act_pra, i),
            "sem_act_total": pick(act_tot, i),
            "tot_tipo": "",
            "TOT_sem_ant_teo": "",
            "TOT_sem_ant_pra": "",
            "TOT_sem_ant_total": "",
            "TOT_sem_act_teo": "",
            "TOT_sem_act_pra": "",
            "TOT_sem_act_total": "",
        }
        result.append(rec)
        state["block_row_idxs"].append(len(result)-1)

# Cerrar el último bloque de la página (aplicar totales elegidos)
if state["block_row_idxs"]:
    apply_block_totals(state)

df_norm = pd.DataFrame(result)

# Correcciones de texto mínimas
df_norm["asignatura"] = (df_norm["asignatura"]
                         .str.replace("DISEÃ?O", "DISEÑO", regex=False)
                         .str.replace("Ã‘", "Ñ", regex=False)
                         .str.replace("Ã", "Í", regex=False)
                         .str.replace("Â", "", regex=False))

print(f"Filas normalizadas (página 1): {len(df_norm)}")
print(df_norm.head(20).to_string(index=False))

# Guardar CSV y Excel
df_norm.to_csv(OUT_CSV, index=False, encoding="utf-8")
try:
    with pd.ExcelWriter(OUT_XLSX, engine="xlsxwriter") as writer:
        df_norm.to_excel(writer, sheet_name="p1_normalizado", index=False)
        ws = writer.sheets["p1_normalizado"]
        for i, col in enumerate(df_norm.columns):
            maxlen = max([len(str(col))] + [len(str(x)) for x in df_norm[col].head(200)])
            ws.set_column(i, i, min(maxlen + 2, 40))
        ws.freeze_panes(1, 0)
except Exception:
    df_norm.to_excel(OUT_XLSX, sheet_name="p1_normalizado", index=False)

print(f"✅ Excel creado: {OUT_XLSX}")
print(f"✅ CSV creado  : {OUT_CSV}")