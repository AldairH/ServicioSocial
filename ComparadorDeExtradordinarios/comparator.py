from __future__ import annotations
from typing import List, Dict, Tuple, FrozenSet
from dataclasses import dataclass

from normalizers import norm_prof

Firma = Tuple[str, str, str, str, FrozenSet[str]]

def firma_sin_materia(rec: Dict[str, str]) -> Firma:
    """Firma operativa (sin nombre de materia y orden de profes ignorado)."""
    return (
        rec.get("GRUPO", ""),
        rec.get("FECHA", ""),
        rec.get("HORA", ""),
        rec.get("SALON", ""),
        frozenset({norm_prof(rec.get("P1", "")), norm_prof(rec.get("P2", ""))} - {""}),
    )

def firma_sort_key(f: Firma):
    grupo, fecha, hora, salon, profes = f
    return (grupo, fecha, hora, salon, tuple(sorted(profes)))

def dedup_por_clave_with_log(rows: List[Dict[str, str]], fuente: str) \
        -> Tuple[Dict[str, Dict[Firma, Dict[str, str]]], List[str], int]:
    """
    Devuelve:
      por_clave[CLAVE][firma] = ejemplo_de_registro
      log_lines: listado de deduplicados colapsados
      total_dedup: cuantos registros se colapsaron
    """
    por_clave: Dict[str, Dict[Firma, Dict[str, str]]] = {}
    counts: Dict[str, Dict[Firma, int]] = {}

    for r in rows:
        clave = str(r.get("CLAVE", "")).strip()
        if not clave:
            continue
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
                pset = {r.get("P1", ""), r.get("P2", "")} - {""}
                log_lines.append(
                    f"- [{fuente}] CLAVE {clave}: colapsados {c-1} duplicados → "
                    f"GRUPO={r.get('GRUPO', '')}, FECHA={r.get('FECHA', '')}, "
                    f"HORA={r.get('HORA', '')}, SALON={r.get('SALON', '')}, "
                    f"PROFES={{{'; '.join(sorted(pset))}}}"
                )
    return por_clave, log_lines, total_dedup

@dataclass
class ComparisonResult:
    coincidencias: int
    discrepancias: int
    mensajes: List[str]
    coincid_rows: List[Dict[str, str]]
    logA: List[str]
    logB: List[str]
    totA: int
    totB: int

def comparar_sets(
    A_rows: List[Dict[str, str]],
    B_rows: List[Dict[str, str]],
    source_a: str = "doc.pdf",
    source_b: str = "INGENIERIA EN COMPUTACION.pdf"
) -> ComparisonResult:

    A, logA, totA = dedup_por_clave_with_log(A_rows, source_a)
    B, logB, totB = dedup_por_clave_with_log(B_rows, source_b)

    claves = sorted(
        set(A.keys()) | set(B.keys()),
        key=lambda x: int(x) if x.isdigit() else x
    )

    coincidencias = 0
    discrepancias = 0
    msgs: List[str] = []
    coincid_rows: List[Dict[str, str]] = []
    i = 1

    for clave in claves:
        A_firmas = set(A.get(clave, {}).keys())
        B_firmas = set(B.get(clave, {}).keys())

        inter = A_firmas & B_firmas
        a_only = A_firmas - B_firmas
        b_only = B_firmas - A_firmas

        coincidencias += len(inter)
        discrepancias += len(a_only) + len(b_only)

        # coincidencias
        for f in sorted(inter, key=firma_sort_key):
            rec = A.get(clave, {}).get(f) or B.get(clave, {}).get(f)
            coincid_rows.append({
                "CLAVE":  clave,
                "GRUPO":  rec.get("GRUPO", ""),
                "MATERIA": rec.get("MATERIA", ""),
                "P1":     rec.get("P1", ""),
                "P2":     rec.get("P2", ""),
                "FECHA":  rec.get("FECHA", ""),
                "HORA":   rec.get("HORA", ""),
                "SALON":  rec.get("SALON", ""),
            })

        # discrepancias solo en A
        for f in sorted(a_only, key=firma_sort_key):
            r = A[clave][f]
            pset = {r.get("P1", ""), r.get("P2", "")} - {""}
            msgs.append(
                f"{i}. Discrepancia en materia {r.get('MATERIA', '')} con clave {clave}: "
                f"Registro presente solo en {source_a} → "
                f"GRUPO={r.get('GRUPO', '')}, FECHA={r.get('FECHA', '')}, "
                f"HORA={r.get('HORA', '')}, SALON={r.get('SALON', '')}, "
                f"PROFES={{{'; '.join(sorted(pset))}}}"
            )
            i += 1

        # discrepancias solo en B
        for f in sorted(b_only, key=firma_sort_key):
            r = B[clave][f]
            pset = {r.get("P1", ""), r.get("P2", "")} - {""}
            msgs.append(
                f"{i}. Discrepancia en materia {r.get('MATERIA', '')} con clave {clave}: "
                f"Registro presente solo en {source_b} → "
                f"GRUPO={r.get('GRUPO', '')}, FECHA={r.get('FECHA', '')}, "
                f"HORA={r.get('HORA', '')}, SALON={r.get('SALON', '')}, "
                f"PROFES={{{'; '.join(sorted(pset))}}}"
            )
            i += 1

    return ComparisonResult(
        coincidencias=coincidencias,
        discrepancias=discrepancias,
        mensajes=msgs,
        coincid_rows=coincid_rows,
        logA=logA,
        logB=logB,
        totA=totA,
        totB=totB,
    )