from urllib.parse import urljoin, urlparse
from config import URL


def norm(s: str) -> str:
    """Normaliza espacios en blanco en una cadena."""
    return " ".join((s or "").split())


def dominio_base(url_actual: str) -> str:
    """Obtiene dominio base a partir de una URL."""
    p = urlparse(url_actual)
    return f"{p.scheme}://{p.netloc}/"


def asegurar_url_absoluta(driver, posible_url: str) -> str:
    """
    Asegura que la URL del expediente sea absoluta, basada en la URL actual
    del driver o en la URL base del sistema.
    """
    if not posible_url:
        return posible_url
    if posible_url.startswith("http://") or posible_url.startswith("https://"):
        return posible_url

    base = dominio_base(driver.current_url or URL)
    return urljoin(base, posible_url)