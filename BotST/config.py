from selenium.webdriver.common.by import By

# -------------------------------------------------------------------------
# CONFIG / SELECTORES
# -------------------------------------------------------------------------
URL = "https://seguimientotitulacion.unam.mx/control/login"

SEL_SEGUIMIENTO = (By.XPATH, "//a[normalize-space()='Seguimiento']")
SEL_FILAS       = (By.CSS_SELECTOR, "table.tab-docs tbody tr")
SEL_DETALLE     = (By.CSS_SELECTOR, "#expediente, .detalle-expediente")
SEL_FILAS_TABLA = (By.CSS_SELECTOR, "table.tab-docs tbody tr")
SEL_COL_ESTADO  = (By.CSS_SELECTOR, "table.tab-docs tbody tr td:nth-child(6)")
SEL_TBODY       = (By.CSS_SELECTOR, "table.tab-docs tbody")

DEFAULT_TIMEOUT = 120
MAX_WORKERS = 6