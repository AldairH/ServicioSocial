# Comparador / Normalizador de tablas PDF

## Descripción:
Este proyecto extrae tablas de PDF de la UNAM, normaliza sus filas (incluyendo encabezados en dos niveles, filas de continuación y renglones de TOTALES) y genera un Excel por cada PDF procesado.

## La arquitectura:
- extractor.py → Lee el PDF con PyMuPDF y emite páginas/filas crudas (sin pandas).
- normalizador.py → Consume esas páginas crudas, detecta columnas, expande subfilas, aplica TOTALES por tipo, y devuelve un DataFrame.
- main.py → Orquesta: detecta todos los PDFs en la carpeta de ejecución y genera un Excel por archivo en out/.
Está pensado para PDFs con un molde recurrente (p. ej. “Profesor_Asignatura”, “Profesor_Carrera”, “Ayudantes_Profesor”), pero con pequeñas variaciones.

## Requisitos:
-Python 3.9+
-pymupdf
-pandas
-xlsxwriter (opcional; para formateo de columnas y freeze_panes)
-openpyxl (opcional; pandas lo usa como fallback si no está xlsxwriter)
**Instalación:**
pip install pymupdf pandas xlsxwriter openpyxl

## Uso:
1. Coloca uno o varios PDFs junto a main.py (misma carpeta).
2. Ejecuta python main.py.
3. El script:
- Detecta todos los *.pdf de la carpeta (no recursivo).
- Extrae y normaliza cada uno.
- Escribe un Excel por PDF en out/<NOMBRE>_normalizado.xlsx.

## Funcionalidades:
- Extracción cruda con PyMuPDF:
    extractor.py usa page.find_tables() y entrega filas con marcas de encabezado:
    header_level=1 (header principal), header_level=2 (subheader), 0 (datos).

- Autodetección de columnas por subcabecera:
    El normalizador localiza índices de columnas clave mediante tokens (NO, PROFESOR, CATEG, CLAVE, ASIGNAT) y la subcabecera ANTERIOR/ACTUAL con TEO/PRA/TOTAL.
    Filas de continuación (dos patrones):
        - “Derecha”: columnas de identificación vacías y asignatura/métricas presentes.
        - “Desplazada”: corrimiento hacia la derecha; el normalizador reubica y rellena huecos.

- Expansión multivalor:
    Celdas con listas (claves, grupos, métricas) se expanden a K subfilas coherentes.

- TOTALES por tipo con tolerancia inteligente:
    Aplica totales cuando detecta renglones con “TOTALES” y etiqueta de INTERINO/DEFINITIVO o genérica.
    Fallback: si la categoría de filas no trae “INT/DEF” visibles (p. ej., “AYUD. DE PROF. B”), los totales se aplican a todas las filas del profesor.
    El fingerprint de TOTALES solo se memoriza si sí aplicó algo; así un “TOTALES” genérico posterior puede completar lo que falte.

- Postproceso consistente:
    Corrección de mojibake común (latin1→utf8) en asignatura/profesor/categoria (no intrusiva).
    Conversión de métricas a numérico (float) con NaN tolerante.
    Cálculo de tot_tipo respetando valores ya asignados durante aplicación de TOTALES.

- Exportación a Excel por archivo PDF, con freeze_panes y anchos autoajustados.

## Errores y solución de problemas:
- page.find_tables() no existe
Actualiza PyMuPDF: pip install --upgrade pymupdf.

- “No encontré encabezados (header_level 1/2)”
El PDF no trae la cabecera en el layout esperado. Revisa que el archivo sea del molde compatible.

- No se aplican TOTALES en “Ayudantes de profesor”
El normalizador trae fallback: si las categorías no contienen INT/DEF, los TOTALES con etiqueta (INTERINO/DEFINITIVO) o genéricos se aplican a todas las filas del profesor, y el fingerprint solo se graba si hubo actualización.
Si aún no ves los valores, revisa que tus celdas de totales contengan los seis números esperados.

- Excel sin formato/anchos
Instala xlsxwriter. Sin él, pandas usa un backend alternativo y no aplica el ajuste de columnas ni freeze_panes.

- PDF cifrado o corrupto
extractor.py no desencripta; asegúrate de que el PDF se pueda abrir y copiar.