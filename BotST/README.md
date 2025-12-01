# Bot de extracción de expedientes

## Descripción:
Este bot automatiza la extracción masiva de expedientes desde la plataforma de seguimiento de titulación de la UNAM.
El proceso se divide en dos fases:
1. Automatización con Selenium:
    - Login manual
    - Aplicación del filtro deseado
    - Recolección de todas las URLs de expedientes (incluyendo paginación)
2. Procesamiento masivo con Requests + BeautifulSoup:
    - Descarga de cada expediente
    - Extracción de datos relevantes
    - Ejecución en paralelo usando ThreadPoolExecutor
Los resultados se guardan como:
- expedientes-YYYYMMDD-HHMMSS.xlsx
- expedientes.json

## Estructura de archivos
/bot-expedientes/ <br>
│ <br>
├── config.py                 # Selectores, constantes y configuración general <br>
├── utils.py                  # Funciones auxiliares (normalización, URLs absolutas) <br>
│ <br>
├── selenium_flow.py          # Navegación web: login, filtros, paginación, extracción de URLs <br>
├── expedientes_service.py    # Requests, retries, parsing con BS4, multithreading <br>
├── export_utils.py           # Exportación a Excel y JSON <br>
│ <br>
├── main.py                   # Punto de entrada del bot <br>
└── README.md <br>


## Requisitos:
- Python 3.9 o superior
- selenium
- webdriver-manager
- pandas
- openpyxl
- requests
- beautifulsoup4
- lxml

**Instalación:**
pip install selenium webdriver-manager pandas openpyxl requests beautifulsoup4 lxml

## Uso:
1. Ejecuta: **python main.py**
2. Se abrirá Chrome automáticamente.
3. Inicia sesión manualmente en la plataforma.
4. El bot detectará el login y:
    - Aplicará el filtro configurado
    - Ajustará el tamaño de página a 100
    - Recolectará todas las URLs paginando
    - Descargará y procesará expedientes en paralelo
    - Exportará resultados a Excel y JSON

## Funcionalidades:
- Login manual mediante Selenium.
- Aplicación automática del filtro por estado (configurable, valor por defecto: "Entrega electrónica y física de documentos").
- Ajuste del número de registros mostrados por página a 100.
- Recolección de todas las URLs de expedientes con paginación automática.
- Descarga y procesamiento en paralelo de los expedientes usando requests y BeautifulSoup.
- Extracción de datos clave del expediente: número de cuenta, nombre completo, opción de titulación, correo electrónico, plantel, carrera, plan de estudios y cita programada.
- Detección de expedientes sin cita programada (omitidos).
- Exportación de resultados a Excel y JSON.

## ¿Qué hacer si la página cambia?

1. **Cambió algún selector CSS/XPATH (muy común)** <br>
    Archivo a revisar: config.py <br>
    Ahí están todos los selectores: <br>
        - SEL_SEGUIMIENTO = (...) <br>
        - SEL_FILAS = (...) <br>
        - SEL_COL_ESTADO = (...) <br>
        - SEL_TBODY = (...) <br>

2. **Cambió el botón que abre un expediente** <br>
    Archivo a revisar: selenium_flow.py → función _obtener_url_expediente_desde_fila() <br>
    Esto ocurre si: <br>
    - Ya no tiene onclick <br>
    - Cambió el atributo data-href <br>
    - El botón se movió de columna <br>
    Qué modificar: <br>
    Ajustar el selector del botón o la lógica que extrae la URL. <br>

3. **Cambió la estructura interna del expediente (HTML)** <br>
    Archivo a revisar: expedientes_service.py <br>
    Funciones: <br>
    - bs4_obtener_valor() <br>
    - bs4_obtener_cita_programada() <br>
    - descargar_y_extraer_expediente() <br>
    Qué cambiar: <br>
    Los textos de los labels o las clases que usa la página. <br>
    Ejemplo: bs4_obtener_valor(soup, "Nombre:"), si ahora dice "Nombre completo:", solo actualiza la cadena.

4. **Cambió la URL base o rutas internas del sistema**  <br>
    Archivo a revisar: config.py <br>
    Modifica: <br>
    URL = "nueva_url" <br>
    Todo lo demás se ajustará automáticamente. <br>

5. **Cambió el flujo de navegación después del login** <br>
    Archivo a revisar: <br>
    selenium_flow.py → esperar_login_e_ir_a_seguimiento() <br>
    Actualiza: <br>
    - El selector del botón Seguimiento <br>
    - La URL parcial "/listado/seguimiento" <br>

**Resumen**
| Síntoma                      | Archivo a revisar                                                 |
| ---------------------------- | ----------------------------------------------------------------- |
| No encuentra filas           | `config.py` (selectores)                                          |
| No abre un expediente        | `selenium_flow.py` (función `_obtener_url_expediente_desde_fila`) |
| No detecta login             | `selenium_flow.py` (función `esperar_login_*`)                    |
| Excel vacío                  | `expedientes_service.py` (BS4)                                    |
| No encuentra cita programada | `bs4_obtener_cita_programada`                                     |
| Error 403 en expedientes     | cookies → bot se arregla solo, pero revisar sesión                |
| No exporta                   | `export_utils.py`                                                 |