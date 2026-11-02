"""Prodigi Print API v4 client (POD provider for the US line).

Docs: https://www.prodigi.com/print-api/docs/reference/

Orders from Shopify and Etsy reach Prodigi through Prodigi's own sales-channel
apps, so this client mostly *reads*: order status, tracking, real costs, quotes
and product details (for the discontinued-product guard). Creating an order by
hand is only for reprints and manual orders, and it requires an approved
``pedido-manual`` record from the approval gate.

Settings: ``PRODIGI_ENV`` (``sandbox``, the default, or ``live``) picks the key:
``PRODIGI_SANDBOX_API_KEY`` for sandbox, ``PRODIGI_API_KEY`` for live. Keeping two
names means a sandbox run can never pick up the live key by accident.

    python -m lulamacaroni.connectors.prodigi --check            # sandbox, read-only
    PRODIGI_ENV=live python -m lulamacaroni.connectors.prodigi --check
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

import requests

from .. import config

BASE_URLS = {
    "sandbox": "https://api.sandbox.prodigi.com/v4.0",
    "live": "https://api.prodigi.com/v4.0",
}


KEY_VARS = {"sandbox": "PRODIGI_SANDBOX_API_KEY", "live": "PRODIGI_API_KEY"}


class ProdigiError(RuntimeError):
    def __init__(self, status: int, message: str, payload: Any = None):
        super().__init__(f"Prodigi {status}: {message}")
        self.status = status
        self.payload = payload


@dataclass
class ProdigiClient:
    api_key: str
    env: str = "sandbox"
    timeout: float = 30.0
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        if self.env not in BASE_URLS:
            raise ValueError(f"PRODIGI_ENV must be one of {sorted(BASE_URLS)}, got {self.env!r}")
        if self.session is None:
            self.session = requests.Session()

    @classmethod
    def from_env(cls) -> "ProdigiClient":
        env = config.get("PRODIGI_ENV", "sandbox")
        name = KEY_VARS.get(env)
        if name is None:
            raise ValueError(f"PRODIGI_ENV must be one of {sorted(KEY_VARS)}, got {env!r}")
        return cls(api_key=config.require(name), env=env)

    @property
    def base_url(self) -> str:
        return BASE_URLS[self.env]

    # -- low level -----------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        resp = self.session.request(method, f"{self.base_url}{path}", headers=headers,
                                    timeout=self.timeout, **kwargs)
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text}
        if resp.status_code >= 400:
            message = body.get("statusText") or body.get("outcome") or resp.reason
            raise ProdigiError(resp.status_code, str(message), body)
        return body

    # -- reads ---------------------------------------------------------------
    def get_order(self, order_id: str) -> dict:
        return self._request("GET", f"/orders/{order_id}")["order"]

    def iter_orders(self, page_size: int = 50, **filters: Any) -> Iterator[dict]:
        """Yield every order, following Prodigi's ``top``/``skip`` paging."""
        skip = 0
        while True:
            params = {"top": page_size, "skip": skip, **filters}
            body = self._request("GET", "/orders", params=params)
            orders = body.get("orders", [])
            yield from orders
            if not body.get("hasMore") or not orders:
                return
            skip += len(orders)

    def get_product(self, sku: str) -> dict:
        """Product details for a Prodigi SKU (raises ProdigiError 404 if it no longer exists)."""
        return self._request("GET", f"/products/{sku}")["product"]

    def quote(self, items: list[dict], destination_country: str = "US",
              shipping_method: str = "Standard", currency: str = "USD") -> dict:
        """Price a basket. ``items`` look like ``{"sku": ..., "copies": 1, "attributes": {...}, "assets": [...]}``."""
        payload = {
            "shippingMethod": shipping_method,
            "destinationCountryCode": destination_country,
            "currencyCode": currency,
            "items": items,
        }
        return self._request("POST", "/quotes", json=payload)

    # -- writes (gated) --------------------------------------------------------
    def create_order(self, order: dict, *, approval) -> dict:
        """Create a manual order or reprint. ``approval`` must be an approved record
        from :mod:`lulamacaroni.approval` whose fingerprint matches ``order``.
        """
        from ..approval.gate import assert_approved

        assert_approved(approval, tipo="pedido-manual", contenido=order)
        # One approval prints once: the gate refuses an approval already marked executed,
        # and the approval id travels as merchantReference so a duplicate is traceable
        # in Prodigi's dashboard. (Check Prodigi's own idempotency support in sandbox.)
        body = dict(order)
        body.setdefault("merchantReference", approval.aprobacion_id)
        return self._request("POST", "/orders", json=body)["order"]


def product_is_available(client: ProdigiClient, sku: str) -> bool:
    """True if Prodigi still offers ``sku``. Used by the discontinued-product guard."""
    try:
        client.get_product(sku)
    except ProdigiError as exc:
        if exc.status == 404:
            return False
        raise
    return True


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Prodigi Print API (read-only check)")
    parser.add_argument("--check", action="store_true",
                        help="confirm the key works and count orders; changes nothing")
    args = parser.parse_args(argv)
    if not args.check:
        parser.print_help()
        return 0
    client = ProdigiClient.from_env()
    orders = list(client.iter_orders(page_size=50))
    statuses: dict[str, int] = {}
    for o in orders:
        stage = ((o.get("status") or {}).get("stage")) or "?"
        statuses[stage] = statuses.get(stage, 0) + 1
    print(f"Prodigi {client.env}: key OK, {len(orders)} order(s) {statuses or ''}")
    for o in orders[:3]:  # references only, no recipient data
        print(f"  {o.get('id')}  ref={o.get('merchantReference')}  created={o.get('created')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
