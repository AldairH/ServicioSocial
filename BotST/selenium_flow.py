import re

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from config import (
    URL,
    SEL_SEGUIMIENTO,
    SEL_FILAS,
    SEL_DETALLE,
    SEL_FILAS_TABLA,
    SEL_COL_ESTADO,
    SEL_TBODY,
    DEFAULT_TIMEOUT,
)
from utils import norm, asegurar_url_absoluta


# -------------------------------------------------------------------------
# LOGIN
# -------------------------------------------------------------------------
def esperar_login_e_ir_a_seguimiento(driver):
    driver.get(URL)
    print("-> Inicia sesión manualmente")
    WebDriverWait(driver, 600).until(EC.presence_of_element_located(SEL_SEGUIMIENTO))
    print("-> Login detectado, dando click en Seguimiento")
    driver.find_element(*SEL_SEGUIMIENTO).click()
    WebDriverWait(driver, DEFAULT_TIMEOUT).until(
        EC.url_contains("/listado/seguimiento")
    )
    print("-> Estamos en la sección de Seguimiento")


# -------------------------------------------------------------------------
# FILTROS
# -------------------------------------------------------------------------
def cambiar_mostrar_100(driver, timeout=DEFAULT_TIMEOUT):
    wait = WebDriverWait(driver, timeout)

    select_el = wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, "select[wire\\:model='cantidad']")
        )
    )
    sel = Select(select_el)

    try:
        actual = (
            sel.first_selected_option.get_attribute("value")
            or sel.first_selected_option.text
        )
        if "100" in norm(actual):
            wait.until(lambda d: len(d.find_elements(*SEL_FILAS_TABLA)) > 10)
            print("-> El tamaño de la tabla ya estaba en 100")
            return
    except Exception:
        pass

    sel.select_by_value("100")
    driver.execute_script(
        """
        const el = arguments[0];
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.blur && el.blur();
    """,
        select_el,
    )

    wait.until(lambda d: len(d.find_elements(*SEL_FILAS_TABLA)) > 10)
    print("-> El tamaño de la página fue ajustado a 100 registros")


def seleccionar_filtro_por_estado(
    driver,
    valor="Entrega electrónica y física de documentos",
    timeout=DEFAULT_TIMEOUT,
):
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

    cambiar_mostrar_100(driver, timeout=DEFAULT_TIMEOUT)


# -------------------------------------------------------------------------
# OBTENER URL DIRECTA DESDE LA FILA
# -------------------------------------------------------------------------
def _obtener_url_expediente_desde_fila(driver, fila):
    candidatos = fila.find_elements(By.CSS_SELECTOR, "td:last-child button.btn-accion")
    btn = None
    for b in candidatos:
        if b.find_elements(By.CSS_SELECTOR, "i.fa-file-alt"):
            btn = b
            break
    if btn is None:
        raise RuntimeError("No se encontro el botón de expediente en la fila seleccionada")

    attrs = driver.execute_script(
        """
        var el = arguments[0], out = {};
        for (const a of el.attributes) out[a.name]=a.value;
        return out;
    """,
        btn,
    )
    onclick = attrs.get("onclick", "") or ""
    data_href = attrs.get("data-href", "") or ""
    at_click = (
        attrs.get("@click", "")
        or attrs.get("x-on:click", "")
        or attrs.get("hx-get", "")
        or ""
    )

    url = None
    for texto in (onclick, data_href, at_click):
        m = (
            re.search(r"(https?://[^\s'\"<>]+/expediente[^\s'\"<>]*)", texto)
            or re.search(r"location\\.href\\s*=\\s*'([^']+)'", texto)
            or re.search(r'location\\.href\\s*=\\s*"([^"]+)"', texto)
        )
        if m:
            url = m.group(1) if m.groups() else m.group(0)
            break

    if not url:
        raise RuntimeError(
            "No se puede derivar la URL del expediente desde los atributos del boton"
        )
    return asegurar_url_absoluta(driver, url)


# -------------------------------------------------------------------------
# NAVEGACIÓN ENTRE PÁGINAS Y RECOLECCIÓN DE URLs
# -------------------------------------------------------------------------
def _ir_a_siguiente_pagina(driver, timeout=DEFAULT_TIMEOUT):
    wait = WebDriverWait(driver, timeout)

    candidatos = driver.find_elements(
        By.CSS_SELECTOR, "button[rel='next'], button[wire\\:click^='nextPage']"
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
            wait.until(
                lambda d: d.find_elements(*SEL_FILAS_TABLA)
                and d.find_elements(*SEL_FILAS_TABLA)[0].text != first_text
            )
    else:
        wait.until(lambda d: len(d.find_elements(*SEL_FILAS_TABLA)) > 0)

    return True


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