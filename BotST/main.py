import json

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from config import SEL_FILAS_TABLA, MAX_WORKERS
from selenium_flow import (
    esperar_login_e_ir_a_seguimiento,
    seleccionar_filtro_por_estado,
    recolectar_urls_expedientes,
)
from expedientes_service import (
    construir_session_desde_driver,
    procesar_urls_concurrente,
)
from export_utils import exportar_excel


def main():
    options = webdriver.ChromeOptions()
    options.page_load_strategy = "eager"
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options,
    )

    try:
        # LOGIN + IR A SEGUIMIENTO
        esperar_login_e_ir_a_seguimiento(driver)

        # APLICAR FILTRO
        seleccionar_filtro_por_estado(driver)
        print(f"-> Filas visibles: {len(driver.find_elements(*SEL_FILAS_TABLA))}")

        # FASE A: recolectar todas las URLs
        urls = recolectar_urls_expedientes(driver)
        print(f"-> Total URLs recolectadas: {len(urls)}")

        # Construir session HTTP a partir del driver
        session = construir_session_desde_driver(driver)

        # FASE B: procesar en paralelo
        resultados, omitidos = procesar_urls_concurrente(
            driver, session, urls, max_workers=MAX_WORKERS
        )
        print(
            f"\n-> Expedientes guardados: {len(resultados)} | Omitidos (sin cita): {omitidos}"
        )

        # EXPORTAR
        exportar_excel(resultados, base="expedientes")

        # RESPALDO JSON
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