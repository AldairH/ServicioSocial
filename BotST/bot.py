import re
import json
import pandas as pd
import requests
from datetime import datetime
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# -----------------------------------------------------------------------------
# CONFIG / SELECTORES
# -----------------------------------------------------------------------------
URL = "https://seguimientotitulacion.unam.mx/control/login"
SEL_SEGUIMIENTO = (By.XPATH, "//a[normalize-space()='Seguimiento']")
SEL_FILAS   = (By.CSS_SELECTOR, "table.tab-docs tbody tr")
SEL_DETALLE = (By.CSS_SELECTOR, "#expediente, .detalle-expediente")
SEL_FILAS_TABLA  = (By.CSS_SELECTOR, "table.tab-docs tbody tr")
SEL_COL_ESTADO   = (By.CSS_SELECTOR, "table.tab-docs tbody tr td:nth-child(6)")
SEL_TBODY        = (By.CSS_SELECTOR, "table.tab-docs tbody")
DEFAULT_TIMEOUT = 120

MAX_WORKERS = 6

# -----------------------------------------------------------------------------
# UTILS
# -----------------------------------------------------------------------------
def norm(s: str) -> str:
    return " ".join((s or "").split())

def dominio_base(url_actual: str) -> str:
    p = urlparse(url_actual)
    return f"{p.scheme}://{p.netloc}/"

def asegurar_url_absoluta(driver, posible_url: str) -> str:
    if not posible_url:
        return posible_url
    if posible_url.startswith("http://") or posible_url.startswith("https://"):
        return posible_url
    base = dominio_base(driver.current_url or URL)
    return urljoin(base, posible_url)

# -----------------------------------------------------------------------------
# LOGIN
# -----------------------------------------------------------------------------

def esperar_login_e_ir_a_seguimiento(driver):
    driver.get(URL)
    print("-> Inicia sesión manualmente")
    WebDriverWait(driver, 600).until(EC.presence_of_element_located(SEL_SEGUIMIENTO))
    print("-> Login detectado, dando click en Seguimiento")
    driver.find_element(*SEL_SEGUIMIENTO).click()
    WebDriverWait(driver, DEFAULT_TIMEOUT).until(EC.url_contains("/listado/seguimiento"))
    print("-> Estamos en la sección de Seguimiento")

# -----------------------------------------------------------------------------
# FILTROS
# -----------------------------------------------------------------------------

def cambiar_mostrar_100(driver, timeout=DEFAULT_TIMEOUT ):
    wait = WebDriverWait(driver, timeout)

    select_el = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "select[wire\\:model='cantidad']"))
    )
    sel = Select(select_el)

    try:
        actual = sel.first_selected_option.get_attribute("value") or sel.first_selected_option.text
        if "100" in norm(actual):
            wait.until(lambda d: len(d.find_elements(*SEL_FILAS_TABLA)) > 10)
            print("-> El tamaño de la tabla ya estaba en 100")
            return
    except Exception:
        pass

    sel.select_by_value("100")
    driver.execute_script("""
        const el = arguments[0];
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.blur && el.blur();
    """, select_el)

    wait.until(lambda d: len(d.find_elements(*SEL_FILAS_TABLA)) > 10)
    print("-> El tamaño de la página fue ajustado a 100 registros")

def seleccionar_filtro_por_estado(driver, valor="Entrega electrónica y física de documentos", timeout=DEFAULT_TIMEOUT):
    wait = WebDriverWait(driver, timeout)
    valor_norm = norm(valor)

    combo = Select(wait.until(EC.element_to_be_clickable((By.ID, "est_avance"))))
    try:
        combo.select_by_value(valor)
    except Exception:
        combo.select_by_visible_text(valor)

    def ok(d):
        filas = d.find_elements(*SEL_FILAS_TABLA)
        if not filas:
            return True
        for c in d.find_elements(*SEL_COL_ESTADO):
            if norm(c.text) != valor_norm:
                return False
        return True

    wait.until(ok)
    print("-> Filtro aplicado")

    cambiar_mostrar_100(driver, timeout=DEFAULT_TIMEOUT )

# -----------------------------------------------------------------------------
# OBTENER URL DIRECTA DESDE LA FILA
# -----------------------------------------------------------------------------

def _obtener_url_expediente_desde_fila(driver, fila):
    candidatos = fila.find_elements(By.CSS_SELECTOR, "td:last-child button.btn-accion")
    btn = None
    for b in candidatos:
        if b.find_elements(By.CSS_SELECTOR, "i.fa-file-alt"):
            btn = b
            break
    if btn is None:
        raise RuntimeError("No se encontro el botón de expediente en la fila seleccionada")

    attrs = driver.execute_script("""
        var el = arguments[0], out = {};
        for (const a of el.attributes) out[a.name]=a.value;
        return out;
    """, btn)
    onclick   = attrs.get("onclick", "") or ""
    data_href = attrs.get("data-href", "") or ""
    at_click  = attrs.get("@click", "") or attrs.get("x-on:click", "") or attrs.get("hx-get","") or ""

    url = None
    for texto in (onclick, data_href, at_click):
        m = (re.search(r"(https?://[^\s'\"<>]+/expediente[^\s'\"<>]*)", texto)
             or re.search(r"location\\.href\\s*=\\s*'([^']+)'", texto)
             or re.search(r'location\\.href\\s*=\\s*"([^"]+)"', texto))
        if m:
            url = m.group(1) if m.groups() else m.group(0)
            break

    if not url:
        raise RuntimeError("No se puede derivar la URL del expediente desde los atributos del boton")
    return asegurar_url_absoluta(driver, url)

# -----------------------------------------------------------------------------
# SESSION REQUESTS + RETRIES/POOL
# -----------------------------------------------------------------------------
def construir_session_desde_driver(driver):
    s = requests.Session()
    ua = driver.execute_script("return navigator.userAgent;")
    s.headers.update({
        "User-Agent": ua,
        "Accept-Language": "es-ES,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    })
    for c in driver.get_cookies():
        s.cookies.set(c.get("name"), c.get("value"), domain=c.get("domain"), path=c.get("path", "/"))
    return s

def preparar_session(session: requests.Session) -> requests.Session:
    retry = Retry(total=3, backoff_factor=0.8, status_forcelist=[429, 503, 502, 504])
    adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# -----------------------------------------------------------------------------
# HELPERS BS4
# -----------------------------------------------------------------------------
def bs4_obtener_valor(html_soup: BeautifulSoup, label_text: str) -> str:
    def _norm(s): return " ".join((s or "").split())
    for div in html_soup.select("div"):
        if _norm(div.get_text()) == label_text:
            sib = div.find_next_sibling()
            if sib:
                return _norm(sib.get_text())
            break
    return ""

def bs4_obtener_cita_programada(html_soup: BeautifulSoup):
    def _norm(s): return " ".join((s or "").split())
    candidatos = html_soup.select("div.bg-emerald-50, div[class*='bg-emerald-50']")
    for cont in candidatos:
        t = _norm(cont.get_text(" "))
        if "Cita programada" in t:
            return {"cita_fecha": t}
    texto = _norm(html_soup.get_text(" "))
    if "Cita programada" in texto:
        return {"cita_fecha": "Cita programada (detalle no localizado)"}
    return None
# -----------------------------------------------------------------------------
# DESCARGA + PARSEO DEL EXPEDIENTE
# -----------------------------------------------------------------------------
def descargar_y_extraer_expediente(session: requests.Session, url: str):
    r = session.get(url, timeout=30)
    if r.status_code in (401, 403):
        raise PermissionError(f"Sesión expirada o sin permisos al pedir {url}")
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    cita = bs4_obtener_cita_programada(soup)
    if not cita:
        return None

    datos = {
        "numero_cuenta":     bs4_obtener_valor(soup, "Número de cuenta:"),
        "nombre":            bs4_obtener_valor(soup, "Nombre:"),
        "opcion_titulacion": bs4_obtener_valor(soup, "Opción de titulación:"),
        "correo":            bs4_obtener_valor(soup, "Correo electrónico:"),
        "plantel":           bs4_obtener_valor(soup, "Plantel:"),
        "carrera":           bs4_obtener_valor(soup, "Carrera:"),
        "plan_estudios":     bs4_obtener_valor(soup, "Plan de estudios:"),
    }
    datos.update(cita)
    return datos

# -----------------------------------------------------------------------------
# FASE A: RECOLECTAR TODAS LAS URLs
# -----------------------------------------------------------------------------
def recolectar_urls_expedientes(driver):
    urls, vistos = [], set()
    pagina = 1
    while True:
        filas = driver.find_elements(*SEL_FILAS)
        total = len(filas)
        print(f"\n== Página {pagina}: {total} filas ==")

        for fila in filas:
            try:
                url = _obtener_url_expediente_desde_fila(driver, fila)
                if url not in vistos:
                    urls.append(url)
                    vistos.add(url)
            except Exception as e:
                print(f"   -> No se pudo derivar URL de una fila: {e}")

        avanzo = _ir_a_siguiente_pagina(driver)
        if not avanzo:
            break
        pagina += 1
    return urls

def _ir_a_siguiente_pagina(driver, timeout=DEFAULT_TIMEOUT ):
    wait = WebDriverWait(driver, timeout)

    candidatos = driver.find_elements(
        By.CSS_SELECTOR,
        "button[rel='next'], button[wire\\:click^='nextPage']"
    )
    btn = next((b for b in candidatos if b.is_displayed() and b.is_enabled()), None)
    if not btn:
        return False

    try:
        tbody = wait.until(EC.presence_of_element_located(SEL_TBODY))
        filas = tbody.find_elements(*SEL_FILAS_TABLA)
        fila_ref = filas[0] if filas else None
        first_text = filas[0].text if filas else ""
    except Exception:
        fila_ref, first_text = None, ""

    try:
        btn.click()
    except Exception:
        driver.execute_script("arguments[0].click()", btn)

    if fila_ref:
        try:
            wait.until(EC.staleness_of(fila_ref))
        except TimeoutException:
            wait.until(lambda d: d.find_elements(*SEL_FILAS_TABLA)
                               and d.find_elements(*SEL_FILAS_TABLA)[0].text != first_text)
    else:
        wait.until(lambda d: len(d.find_elements(*SEL_FILAS_TABLA)) > 0)

    return True

# -----------------------------------------------------------------------------
# FASE B: PROCESAR EN PARALELO
# -----------------------------------------------------------------------------
def procesar_urls_concurrente(driver, session, urls, max_workers=MAX_WORKERS):
    resultados, omitidos = [], 0
    session = preparar_session(session)

    def tarea(u):
        try:
            return descargar_y_extraer_expediente(session, u)
        except PermissionError:
            # renovar cookies y reintentar una vez
            s2 = preparar_session(construir_session_desde_driver(driver))
            return descargar_y_extraer_expediente(s2, u)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(tarea, u): u for u in urls}
        for fut in as_completed(futs):
            u = futs[fut]
            try:
                datos = fut.result()
                if datos:
                    resultados.append(datos)
                else:
                    omitidos += 1
            except Exception as e:
                print(f"   -> Error en {u}: {e}")
                omitidos += 1

    return resultados, omitidos

# -----------------------------------------------------------------------------
# EXPORTAR
# -----------------------------------------------------------------------------
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
    headers  = [h for _, h in schema]

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

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    options = webdriver.ChromeOptions()
    options.page_load_strategy = 'eager'
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options
    )
    try:
        esperar_login_e_ir_a_seguimiento(driver)
        seleccionar_filtro_por_estado(driver)
        print(f"-> Filas visibles: {len(driver.find_elements(*SEL_FILAS_TABLA))}")

        # FASE A: recolectar todas las URLs
        urls = recolectar_urls_expedientes(driver)
        print(f"-> Total URLs recolectadas: {len(urls)}")

        session = construir_session_desde_driver(driver)

        # FASE B: procesar en paralelo
        resultados, omitidos = procesar_urls_concurrente(driver, session, urls, max_workers=MAX_WORKERS)
        print(f"\n-> Expedientes guardados: {len(resultados)} | Omitidos (sin cita): {omitidos}")

        exportar_excel(resultados, base="expedientes")

        with open("expedientes.json", "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=4)
        print("\n-> Datos guardados en expedientes.json")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

if __name__ == "__main__":
    main()