"""The cart lives in a signed cookie: SKUs and quantities only, never prices or buyer data.

The signature (HMAC-SHA256 with ``LULA_TIENDA_SECRET``) stops anyone from editing the cookie
into something the store did not put there; prices are looked up again at checkout anyway.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

NOMBRE = "lm_cart"
MAX_LINEAS = 20
MAX_CANTIDAD = 10


def _firma(secreto: str, datos: bytes) -> str:
    return hmac.new(secreto.encode(), datos, hashlib.sha256).hexdigest()[:32]


def limpiar(lineas: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for sku, n in list(lineas.items())[:MAX_LINEAS]:
        try:
            n = int(n)
        except (TypeError, ValueError):
            continue
        if isinstance(sku, str) and 0 < len(sku) <= 80 and n > 0:
            out[sku] = min(n, MAX_CANTIDAD)
    return out


def codificar(lineas: dict[str, int], secreto: str) -> str:
    datos = base64.urlsafe_b64encode(json.dumps(limpiar(lineas), separators=(",", ":")).encode())
    return f"{datos.decode()}.{_firma(secreto, datos)}"


def decodificar(valor: str | None, secreto: str) -> dict[str, int]:
    """The cart in the cookie, or an empty cart if it's missing, tampered with or unreadable."""
    if not valor or "." not in valor or not secreto:
        return {}
    datos, firma = valor.rsplit(".", 1)
    if not hmac.compare_digest(firma, _firma(secreto, datos.encode())):
        return {}
    try:
        lineas = json.loads(base64.urlsafe_b64decode(datos.encode()))
    except (ValueError, TypeError):
        return {}
    return limpiar(lineas) if isinstance(lineas, dict) else {}


def cookie(lineas: dict[str, int], secreto: str, seguro: bool) -> str:
    """The Set-Cookie value. 30 days; HttpOnly; Secure when served over HTTPS."""
    attrs = f"{NOMBRE}={codificar(lineas, secreto)}; Path=/; Max-Age=2592000; HttpOnly; SameSite=Lax"
    return attrs + ("; Secure" if seguro else "")


def leer_cookie(cabecera: str | None) -> str | None:
    for parte in (cabecera or "").split(";"):
        k, _, v = parte.strip().partition("=")
        if k == NOMBRE:
            return v
    return None
