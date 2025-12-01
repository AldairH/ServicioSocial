# Comparador de Horarios Extraordinarios

## Descripción:
Este programa automatiza la extracción, normalización y comparación de horarios de exámenes extraordinarios provenientes de dos PDFs:
- doc.pdf (generalmente más variable e inestable en su estructura)
- INGENIERIA EN COMPUTACION.pdf (formato más consistente)

## El sistema realiza:
1. Extracción de tablas desde ambos PDFs mediante PyMuPDF.
2. Normalización completa de campos clave (clave de materia, grupo, fecha, hora, salón, profesores).
3. Unificación y deduplicación interna de registros, detectando duplicados basados en “firma operativa”.
4. Comparación entre ambos documentos, identificando:
    - Coincidencias exactas en horarios.
    - Registros presentes solo en doc.pdf.
    - Registros presentes solo en INGENIERIA EN COMPUTACION.pdf.
5. Generación de reportes automáticos:
    - out/reporte_comparacion.txt
    - out/coincidencias.xlsx
El objetivo es automatizar un proceso que antes implicaba revisión manual de cientos de horarios y detectar discrepancias entre la planeación oficial y la versión departamental.

## Estructura del Proyecto:
ComparadorDeExtradordinarios/ <br>
│── config.py <br>
│── normalizers.py       ← Normalización de todos los campos <br>
│── parsers.py           ← Parsers independientes para cada PDF <br>
│── comparator.py        ← Comparación basada en firmas <br>
│── report.py            ← Generación de TXT y Excel <br>
│── main.py              ← Punto de entrada <br>
│── doc.pdf <br>
│── INGENIERIA EN COMPUTACION.pdf <br>
└── out/ <br> 

## Principales Funcionalidades
- Extracción automática de tablas con PyMuPDF.
- Normalización robusta de:
    - CLAVE
    - GRUPO
    - FECHA
    - HORA
    - SALON
    - PROFESORES
- Manejo inteligente de inconsistencias (tildes, mayúsculas, espacios, estilos de fecha/hora).
- Parser especializado para doc.pdf (por su formato altamente volátil).
- Deduplicación interna por firma operativa: (GRUPO, FECHA, HORA, SALON, {PROFES})
- Comparación por CLAVE y firma.
- Reportes automáticos en TXT y Excel.
- Carpeta out/ creada automáticamente en el directorio del proyecto (sin depender del directorio desde el que se ejecute el script).

## Requisitos:
- Python 3.9 o superior
- pymupdf
- pandas
- openpyxl
- unidecode
**Instalación:** pip install pymupdf pandas openpyxl unidecode

## Qué hacer si cambian los PDF o el formato de los datos
### Este proyecto fue diseñado de manera modular justamente para facilitar el mantenimiento frente a cambios de formato.
### Dependiendo del tipo de cambio, se debe modificar solo un archivo, sin tocar todo el programa.

1. Si **cambia la estructura** del PDF doc.pdf
    Archivo a modificar: parsers.py → rows_from_doc_matrix() / parse_materia_cell()
    Cambiar aquí cuando:
    - Las celdas mezclan materia, grupo y profesor de manera distinta.
    - Cambian saltos de línea.
    - Cambian encabezados.
    - Se agregan o eliminan columnas.
    - El contenido de la celda “Materia” cambia de formato.
2. Si **cambia la estructura** del PDF INGENIERIA EN COMPUTACION.pdf
    Archivo a modificar: parsers.py → indices_diag() o auto_map_diag()
    Cambiar aquí cuando:
    - Los encabezados cambien (ej. “Docente 1” → “Profesor Titular”).
    - Aparezcan nuevas columnas o se reordenen.
    - La tabla venga con columnas sin identificar.
    - La estructura interna no siga el patrón histórico.
    - auto_map_diag() contiene heurísticas que detectan automáticamente:
    - columnas con CLAVES (numéricas largas)
    - columnas con HORA (hh:mm)
    - columnas con FECHA
    - columnas con GRUPO (AA11)
    - columnas de SALÓN
    Si la heurística falla, solo se ajusta aquí.
3. Si **cambia el formato** esperado (fecha, hora, grupo, salón, profesor)
    Archivo a modificar: normalizers.py
    Cambiar aquí cuando:
    - Nuevos formatos de fecha aparezcan (ej. “12 ene 2025”).
    - Nuevos formatos de hora (ej. “De 8 a 10 hrs”).
    - Nuevas reglas de salón (“LAB-05”, “VIRTUAL-2”).
    - Nuevas nomenclaturas de grupo.
    - Profesores necesiten normalización especial.
    El normalizador actúa como contrato interno.
    Si un cambio afecta el formato final deseado, solo se modifica este archivo.
4. Si **cambia la lógica** de comparación
    Archivo a modificar: comparator.py
    Solo tocar cuando:
    - Quieran que MATERIA influya en la firma.
    - Quieran detectar coincidencias parciales.
    - Quieran comparar asignaciones de profesor más estrictamente.
    - Se necesite una nueva métrica de discrepancia.
    Por diseño, esta lógica es estable y casi nunca cambia.
5. Si **cambian los formatos de salida** (Excel/TXT)
    Archivo a modificar: report.py
    Cambiar cuando:
    - Quieran otro orden de columnas.
    - Quieran agregar totales o estadísticas.
    - Quieran cambiar el estilo del Excel.
    - Quieran exportar a CSV u otro formato.

## Resumen de mantenimiento
| Tipo de cambio                     | Archivo a modificar                   |
| ---------------------------------- | ------------------------------------- |
| Cambió doc.pdf                     | `parsers.py` (parser específico)      |
| Cambió INGENIERIA.pdf              | `parsers.py` (diagnóstico y auto-map) |
| Cambió formato esperado            | `normalizers.py`                      |
| Cambió la lógica de comparación    | `comparator.py`                       |
| Cambió el formato del reporte      | `report.py`                           |
| Cambió el nombre/ubicación de PDFs | `config.py`                           |