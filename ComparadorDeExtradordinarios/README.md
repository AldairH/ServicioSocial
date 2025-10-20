Comparador de tablas PDF (UNAM)

Descripción: Este script compara tablas extraídas de dos PDF con formatos distintos (doc.pdf e INGENIERIA EN COMPUTACION.pdf). Extrae las tablas con PyMuPDF, normaliza campos (CLAVE, FECHA, HORA, GRUPO, SALON, PROFES), deduplica registros internos por firma (sin nombre de materia y con profesores en conjunto) y luego detecta coincidencias y discrepancias por CLAVE/firma. Genera un reporte TXT y un Excel con las coincidencias normalizadas.

Requisitos: -Python -pymupdf -pandas -unidecode -openpyxl

Instalación: pip install pymupdf pandas unidecode openpyxl

Uso: python comparador.py 
1.Coloca doc.pdf e INGENIERIA EN COMPUTACION.pdf junto al script (o ajusta DOC_PATH/DIAG_PATH en el archivo).
2.Ejecuta el script.
3.Se extraerán y normalizarán las tablas de ambos PDFs.
4.Se colapsarán duplicados internos y se compararán ambos conjuntos.
5.Se generarán los archivos out/reporte_comparacion.txt y out/coincidencias.xlsx.

Funcionalidades: 
Autodetección de columnas en el segundo PDF (heurísticas cuando cambian encabezados).
Normalización de CLAVE (solo dígitos, sin ceros a la izquierda), FECHA (YYYY-MM-DD), HORA (HH:MM o HH:MM-HH:MM con zero-pad), GRUPO (AA00) y SALON (unifica VIRTUAL/N/D y limpia separadores).
Firma de comparación sin nombre de materia e ignorando el orden de profesores ({P1,P2}).
Deduplicación interna por firma con registro de colapsados en el TXT.
Comparación por CLAVE y firma: cuenta coincidencias y lista discrepancias de cada lado.
Exportación: TXT con totales, deduplicados y discrepancias; Excel con coincidencias ordenadas por CLAVE (numérico), GRUPO, FECHA, HORA y SALON. Tolerancia a columnas opcionales (P2 y SALON pueden faltar sin romper el flujo).