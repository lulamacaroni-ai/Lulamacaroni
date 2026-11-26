"""A small Stripe client: Checkout Sessions, webhook signatures and gated refunds.

Plain HTTPS with ``requests`` (no Stripe SDK), so tests pass a fake session and never touch
the network. Keys: ``STRIPE_SECRET_KEY`` (``sk_test_...`` while building, ``sk_live_...`` at
launch) and ``STRIPE_WEBHOOK_SECRET`` (``whsec_...``). Card numbers never reach this server:
the buyer types them on Stripe's own checkout page.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from .. import config

API = "https://api.stripe.com/v1"
TOLERANCIA_FIRMA = 300  # seconds; Stripe's own default
TAX_CODE_ARTE = "txcd_99999999"  # general tangible goods


class StripeError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"Stripe {status}: {message}")
        self.status = status


class FirmaInvalida(ValueError):
    """The webhook did not come from Stripe (or is too old)."""


def aplanar(datos: Any, prefijo: str = "") -> list[tuple[str, str]]:
    """Stripe's form encoding: ``{"a": {"b": [1]}}`` -> ``[("a[b][0]", "1")]``."""
    out: list[tuple[str, str]] = []
    if isinstance(datos, dict):
        for k, v in datos.items():
            out += aplanar(v, f"{prefijo}[{k}]" if prefijo else str(k))
    elif isinstance(datos, (list, tuple)):
        for i, v in enumerate(datos):
            out += aplanar(v, f"{prefijo}[{i}]")
    elif isinstance(datos, bool):
        out.append((prefijo, "true" if datos else "false"))
    elif datos is not None:
        out.append((prefijo, str(datos)))
    return out


@dataclass
class StripeClient:
    secret_key: str = field(repr=False)
    session: Any = None
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()

    @classmethod
    def from_env(cls) -> StripeClient:
        return cls(config.require("STRIPE_SECRET_KEY"))

    @property
    def modo(self) -> str:
        return "live" if self.secret_key.startswith(("sk_live_", "rk_live_")) else "test"

    def _request(self, method: str, path: str, datos: dict | None = None,
                 params: list[tuple[str, str]] | None = None,
                 idempotency_key: str | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self.secret_key}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        resp = self.session.request(method, f"{API}{path}", headers=headers,
                                    data=aplanar(datos) if datos else None,
                                    params=params, timeout=self.timeout)
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        if resp.status_code >= 400:
            msg = (payload.get("error") or {}).get("message") or resp.text[:200]
            raise StripeError(resp.status_code, msg)
        return payload

    def crear_checkout(self, parametros: dict, idempotency_key: str | None = None) -> dict:
        return self._request("POST", "/checkout/sessions", parametros,
                             idempotency_key=idempotency_key)

    def checkout(self, session_id: str) -> dict:
        """A Checkout Session with its line items and their products (for the SKU)."""
        return self._request("GET", f"/checkout/sessions/{session_id}", params=[
            ("expand[]", "line_items"), ("expand[]", "line_items.data.price.product"),
            ("expand[]", "payment_intent"),
        ])

    def reembolsar(self, contenido: dict, *, approval) -> dict:
        """Refund a payment. Only with an approved ``reembolso`` record for exactly this content
        (``{"payment_intent": ..., "monto_centavos": ... or None, "pedido": ..., "motivo": ...}``).
        """
        from ..approval.gate import assert_approved

        assert_approved(approval, tipo="reembolso", contenido=contenido)
        datos = {"payment_intent": contenido["payment_intent"],
                 "metadata": {"pedido": contenido.get("pedido", ""),
                              "aprobacion": approval.aprobacion_id}}
        if contenido.get("monto_centavos"):
            datos["amount"] = int(contenido["monto_centavos"])
        return self._request("POST", "/refunds", datos, idempotency_key=approval.aprobacion_id)


def verificar_webhook(cuerpo: bytes, cabecera: str | None, secreto: str,
                      ahora: float | None = None) -> dict:
    """The event, if ``Stripe-Signature`` proves Stripe sent this exact body; else FirmaInvalida."""
    if not secreto:
        raise FirmaInvalida("STRIPE_WEBHOOK_SECRET is not set")
    partes: dict[str, list[str]] = {}
    for item in (cabecera or "").split(","):
        k, _, v = item.strip().partition("=")
        partes.setdefault(k, []).append(v)
    try:
        t = int((partes.get("t") or [""])[0])
    except ValueError:
        raise FirmaInvalida("no timestamp") from None
    if abs((ahora or time.time()) - t) > TOLERANCIA_FIRMA:
        raise FirmaInvalida("timestamp outside tolerance")
    esperada = hmac.new(secreto.encode(), f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(esperada, v) for v in partes.get("v1", [])):
        raise FirmaInvalida("signature mismatch")
    return json.loads(cuerpo)


def firmar(cuerpo: bytes, secreto: str, t: int | None = None) -> str:
    """A valid ``Stripe-Signature`` header (for tests and local replays)."""
    t = int(t if t is not None else time.time())
    v1 = hmac.new(secreto.encode(), f"{t}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    return f"t={t},v1={v1}"


def centavos(usd: float) -> int:
    return int(round(usd * 100))


def parametros_checkout(lineas: list[dict], *, url: str, envio_usd: float, impuestos: bool,
                        metadata: dict[str, str]) -> dict:
    """Checkout Session parameters. ``lineas``: ``{"sku", "nombre", "detalle", "imagen",
    "precio", "cantidad"}`` with prices already taken from the catalog."""
    items = []
    for li in lineas:
        producto = {"name": li["nombre"], "description": li["detalle"],
                    "metadata": {"sku": li["sku"]}, "tax_code": TAX_CODE_ARTE}
        if li.get("imagen", "").startswith("https://"):
            producto["images"] = [li["imagen"]]
        items.append({"quantity": li["cantidad"], "price_data": {
            "currency": "usd", "unit_amount": centavos(li["precio"]),
            "tax_behavior": "exclusive", "product_data": producto}})
    envio = {"type": "fixed_amount", "tax_behavior": "exclusive",
             "fixed_amount": {"amount": centavos(envio_usd), "currency": "usd"},
             "display_name": "Free shipping" if envio_usd <= 0 else "Standard shipping",
             "delivery_estimate": {"minimum": {"unit": "business_day", "value": 5},
                                   "maximum": {"unit": "business_day", "value": 13}}}
    meta = {k: str(v)[:500] for k, v in metadata.items() if v}
    return {
        "mode": "payment",
        "line_items": items,
        "success_url": f"{url}/thank-you?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{url}/cart",
        "shipping_address_collection": {"allowed_countries": ["US"]},
        "shipping_options": [{"shipping_rate_data": envio}],
        "automatic_tax": {"enabled": impuestos},
        "customer_creation": "always",
        "billing_address_collection": "auto",
        "metadata": meta,
        "payment_intent_data": {"metadata": meta},
    }
