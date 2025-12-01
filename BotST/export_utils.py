from datetime import datetime

import pandas as pd


def exportar_excel(resultados, base="expedientes", tz="America/Mexico_City"):
    schema = [
        ("numero_cuenta", "Número de cuenta"),
        ("nombre", "Nombre completo"),
        ("opcion_titulacion", "Opción de titulación"),
        ("correo", "Correo"),
        ("plantel", "Plantel"),
        ("carrera", "Carrera"),
        ("plan_estudios", "Plan de estudios"),
        ("cita_fecha", "Cita programada"),
    ]
    raw_cols = [k for k, _ in schema]
    headers = [h for _, h in schema]

    df = pd.DataFrame(resultados)

    for k in raw_cols:
        if k not in df.columns:
            df[k] = ""
    df = df[raw_cols]
    for k in raw_cols:
        df[k] = df[k].astype("string").fillna("")

    df.columns = headers

    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(tz))
    except Exception:
        now = datetime.now()
    ts = now.strftime("%Y%m%d-%H%M%S")

    ruta_xlsx = f"{base}-{ts}.xlsx"
    try:
        df.to_excel(ruta_xlsx, index=False, sheet_name="Expedientes")
        print(f"-> Excel generado: {ruta_xlsx}")
    except ModuleNotFoundError:
        print("-> Falta 'openpyxl', instálalo con: pip install openpyxl")
        ruta_csv = f"{base}-{ts}.csv"
        df.to_csv(ruta_csv, index=False, encoding="utf-8-sig")
        print(f"-> CSV de respaldo generado: {ruta_csv}")