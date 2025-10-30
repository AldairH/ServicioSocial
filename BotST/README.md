Bot de extracción de expedientes UNAM

Descripción:

Este bot automatiza la extracción de información de expedientes desde la plataforma de seguimiento de titulación de la UNAM.
El proceso se divide en dos fases:
1.Login manual con Selenium, aplicación de filtros y recolección de todas las URLs de expedientes (incluyendo la paginación automática).
2.Descarga y procesamiento de los expedientes en paralelo mediante requests y BeautifulSoup, con extracción de los campos relevantes.
Los resultados se exportan a un archivo Excel (expedientes-YYYYMMDD-HHMMSS.xlsx) y a un respaldo en expedientes.json.

Requisitos:

-Python 3.9 o superior
-selenium
-webdriver-manager
-pandas
-openpyxl
-requests
-beautifulsoup4
-lxml

Instalación:
pip install selenium webdriver-manager pandas openpyxl requests beautifulsoup4 lxml

Uso:
python bot.py
Se abrirá una ventana de Chrome.
Inicia sesión manualmente en la plataforma.
El bot detectará el login y aplicará automáticamente el filtro configurado (por defecto: "Entrega electrónica y física de documentos").
Recolectará todas las URLs de expedientes, paginando si es necesario.
Descargará y procesará en paralelo los expedientes, omitiendo aquellos sin cita programada.
Exportará los resultados a un archivo Excel (expedientes-YYYYMMDD-HHMMSS.xlsx) y a expedientes.json.

Funcionalidades:

-Login manual mediante Selenium.
-Aplicación automática del filtro por estado (configurable, valor por defecto: "Entrega electrónica y física de documentos").
-Ajuste del número de registros mostrados por página a 100.
-Recolección de todas las URLs de expedientes con paginación automática.
-Descarga y procesamiento en paralelo de los expedientes usando requests y BeautifulSoup.
-Extracción de datos clave del expediente: número de cuenta, nombre completo, opción de titulación, correo electrónico, plantel, carrera, plan de -estudios y cita programada.
-Detección de expedientes sin cita programada (omitidos).
-Exportación de resultados a Excel y JSON.