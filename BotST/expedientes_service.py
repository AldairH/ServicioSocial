import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import MAX_WORKERS


# -------------------------------------------------------------------------
# SESSION REQUESTS + RETRIES/POOL
# -------------------------------------------------------------------------
def construir_session_desde_driver(driver) -> requests.Session:
    s = requests.Session()
    ua = driver.execute_script("return navigator.userAgent;")
    s.headers.update(
        {
            "User-Agent": ua,
            "Accept-Language": "es-ES,es;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
        }
    )
    for c in driver.get_cookies():
        s.cookies.set(
            c.get("name"),
            c.get("value"),
            domain=c.get("domain"),
            path=c.get("path", "/"),
        )
    return s


def preparar_session(session: requests.Session) -> requests.Session:
    retry = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=[429, 503, 502, 504],
    )
    adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# -------------------------------------------------------------------------
# HELPERS BS4
# -------------------------------------------------------------------------
def bs4_obtener_valor(html_soup: BeautifulSoup, label_text: str) -> str:
    def _norm(s):
        return " ".join((s or "").split())

    for div in html_soup.select("div"):
        if _norm(div.get_text()) == label_text:
            sib = div.find_next_sibling()
            if sib:
                return _norm(sib.get_text())
            break
    return ""


def bs4_obtener_cita_programada(html_soup: BeautifulSoup):
    def _norm(s):
        return " ".join((s or "").split())

    candidatos = html_soup.select("div.bg-emerald-50, div[class*='bg-emerald-50']")
    for cont in candidatos:
        t = _norm(cont.get_text(" "))
        if "Cita programada" in t:
            return {"cita_fecha": t}

    texto = _norm(html_soup.get_text(" "))
    if "Cita programada" in texto:
        return {"cita_fecha": "Cita programada (detalle no localizado)"}

    return None


# -------------------------------------------------------------------------
# DESCARGA + PARSEO DEL EXPEDIENTE
# -------------------------------------------------------------------------
def descargar_y_extraer_expediente(
    session: requests.Session,
    url: str,
):
    r = session.get(url, timeout=30)
    if r.status_code in (401, 403):
        raise PermissionError(f"Sesión expirada o sin permisos al pedir {url}")
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    cita = bs4_obtener_cita_programada(soup)
    if not cita:
        return None

    datos = {
        "numero_cuenta": bs4_obtener_valor(soup, "Número de cuenta:"),
        "nombre": bs4_obtener_valor(soup, "Nombre:"),
        "opcion_titulacion": bs4_obtener_valor(soup, "Opción de titulación:"),
        "correo": bs4_obtener_valor(soup, "Correo electrónico:"),
        "plantel": bs4_obtener_valor(soup, "Plantel:"),
        "carrera": bs4_obtener_valor(soup, "Carrera:"),
        "plan_estudios": bs4_obtener_valor(soup, "Plan de estudios:"),
    }
    datos.update(cita)
    return datos


# -------------------------------------------------------------------------
# FASE B: PROCESAR EN PARALELO
# -------------------------------------------------------------------------
def procesar_urls_concurrente(
    driver,
    session: requests.Session,
    urls,
    max_workers: int = MAX_WORKERS,
):
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