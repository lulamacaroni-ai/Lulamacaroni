"""Order emails to buyers, sent through Resend from the store's own domain.

Two fixed templates, in English: the order confirmation and the "your print shipped" note
with tracking. They are part of the purchase (no marketing), reviewed in the repo, and never
carry anything but the order itself. Any other message to a customer is a ``respuesta-cliente``
approval, not this module.

``RESEND_API_KEY`` unset -> nothing is sent and the caller records that, so a missing key
never looks like a delivered email.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any

import requests

from .. import config
from .ajustes import Ajustes

API = "https://api.resend.com/emails"


class CorreoError(RuntimeError):
    pass


@dataclass
class Correo:
    api_key: str = field(repr=False, default="")
    session: Any = None
    timeout: float = 20.0

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()

    @classmethod
    def from_env(cls) -> Correo:
        return cls(config.get("RESEND_API_KEY", ""))

    @property
    def activo(self) -> bool:
        return bool(self.api_key)

    def enviar(self, *, de: str, para: str, asunto: str, html: str, texto: str,
               responder_a: str, clave: str) -> str:
        """Send one email; returns Resend's id. ``clave`` makes a retry send it only once."""
        if not self.activo:
            raise CorreoError("RESEND_API_KEY is not set")
        resp = self.session.post(API, timeout=self.timeout, json={
            "from": de, "to": [para], "subject": asunto, "html": html, "text": texto,
            "reply_to": responder_a,
        }, headers={"Authorization": f"Bearer {self.api_key}", "Idempotency-Key": clave[:256]})
        if resp.status_code >= 400:
            raise CorreoError(f"Resend {resp.status_code}: {resp.text[:200]}")
        return str((resp.json() or {}).get("id", ""))


def _usd(v: float) -> str:
    return f"${v:,.2f}"


def _marco(a: Ajustes, cuerpo: str) -> str:
    return (
        "<!doctype html><html><body style=\"margin:0;background:#f6f1e7;"
        "font-family:Helvetica,Arial,sans-serif;color:#2b2522\">"
        "<div style=\"max-width:560px;margin:0 auto;padding:28px 20px\">"
        f"<p style=\"font-size:22px;color:#9C0F0C;margin:0 0 18px\">{escape(a.marca)}</p>"
        f"{cuerpo}"
        f"<p style=\"color:#6f655e;font-size:13px;margin-top:28px\">Questions? Just reply to this "
        f"email or write to {escape(a.soporte)}.<br>{escape(a.texto(a.razon_social))}</p>"
        "</div></body></html>"
    )


def confirmacion(a: Ajustes, pedido: dict) -> tuple[str, str, str]:
    """(subject, html, text). ``pedido``: numero, nombre, lineas[{nombre, detalle, cantidad,
    total}], subtotal, envio, impuesto, total."""
    filas = "".join(
        f"<tr><td style=\"padding:6px 0\">{escape(li['nombre'])}<br><span style=\"color:#6f655e;"
        f"font-size:13px\">{escape(li['detalle'])} · qty {li['cantidad']}</span></td>"
        f"<td style=\"text-align:right\">{_usd(li['total'])}</td></tr>" for li in pedido["lineas"])
    totales = "".join(
        f"<tr><td style=\"color:#6f655e\">{k}</td><td style=\"text-align:right\">{_usd(v)}</td></tr>"
        for k, v in (("Subtotal", pedido["subtotal"]), ("Shipping", pedido["envio"]),
                     ("Tax", pedido["impuesto"])))
    plano = f"Hi {pedido['nombre']}," if pedido.get("nombre") else "Hi,"
    saludo = escape(plano)
    html = _marco(a, (
        f"<p>{saludo}</p><p>Thank you for your order <b>{escape(pedido['numero'])}</b>. "
        "Each print is made to order for you: production takes 2 to 5 business days, then "
        "shipping 3 to 8. We'll email you the tracking number as soon as it ships.</p>"
        f"<table style=\"width:100%;border-collapse:collapse;font-size:15px\">{filas}{totales}"
        f"<tr><td style=\"padding-top:8px\"><b>Total</b></td><td style=\"text-align:right;"
        f"padding-top:8px\"><b>{_usd(pedido['total'])}</b></td></tr></table>"))
    texto = "\n".join([
        plano, "",
        f"Thank you for your order {pedido['numero']}. Each print is made to order: production "
        "takes 2 to 5 business days, then shipping 3 to 8. We'll email you tracking when it ships.",
        "", *[f"- {li['nombre']} ({li['detalle']}) x{li['cantidad']}: {_usd(li['total'])}"
              for li in pedido["lineas"]],
        f"Subtotal {_usd(pedido['subtotal'])} · Shipping {_usd(pedido['envio'])} · "
        f"Tax {_usd(pedido['impuesto'])}", f"Total {_usd(pedido['total'])}", "",
        f"Questions? Reply to this email or write to {a.soporte}."])
    return f"Your {a.marca} order {pedido['numero']}", html, texto


def enviado(a: Ajustes, numero: str, nombre: str, tracking: str, url: str,
            transportista: str) -> tuple[str, str, str]:
    plano = f"Hi {nombre}," if nombre else "Hi,"
    saludo = escape(plano)
    enlace = (f"<p><a href=\"{escape(url)}\" style=\"color:#8A4F12\">Track your package</a></p>"
              if url.startswith("https://") else "")
    via = f" with {escape(transportista)}" if transportista else ""
    html = _marco(a, (f"<p>{saludo}</p><p>Good news: your order <b>{escape(numero)}</b> shipped"
                      f"{via}. Tracking number: <b>{escape(tracking)}</b>.</p>{enlace}"
                      "<p>Tracking can take 24 to 48 hours to show its first scan.</p>"))
    texto = (f"{plano}\n\nYour order {numero} shipped{via}. Tracking number: {tracking}\n"
             f"{url}\n\nTracking can take 24 to 48 hours to show its first scan.")
    return f"Your {a.marca} order {numero} has shipped", html, texto
