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


# --- costs into Pedidos -------------------------------------------------------------
#
# Prodigi's Shopify app creates the Prodigi order itself, so the link back to the
# Shopify order has to be read from the Prodigi order. Which field carries it is not
# confirmed yet (no orders on 2026-11-02), so every likely field is tried:
# ``merchantReference``, ``idempotencyKey`` and ``metadata`` values, matched against the
# Shopify legacy order id and the order name ("#1005", kept in ``numero_canal``).
# A Prodigi order that matches nothing is reported, never guessed.

POD_ROUTES = ("prodigi-app", "prodigi-api", "desconocida")


def _amount(money: dict | None) -> float:
    try:
        return float((money or {}).get("amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def _norm(ref: Any) -> str:
    return str(ref).strip().lstrip("#").lower() if ref not in (None, "") else ""


def order_refs(order: dict) -> list[str]:
    """Every value on a Prodigi order that could carry the sales-channel order."""
    refs = [order.get("merchantReference"), order.get("idempotencyKey")]
    meta = order.get("metadata") or {}
    if isinstance(meta, dict):
        refs.extend(v for v in meta.values() if isinstance(v, (str, int)))
    out = []
    for ref in refs:
        n = _norm(ref)
        if not n:
            continue
        out.append(n)
        # "shopify-123", "lulamacaroni-1005", gid://shopify/Order/123 -> trailing number
        tail = n.replace("/", "-").rsplit("-", 1)[-1]
        if tail.isdigit() and tail != n:
            out.append(tail)
    return list(dict.fromkeys(out))


def charges(order: dict) -> tuple[float, float, dict[str, float]] | None:
    """(item cost, shipping cost, cost per Prodigi item id) from the order's charges.

    ``None`` when Prodigi has not charged the order yet: the cost is then missing,
    not zero. Charge lines without an ``itemId`` are shipping.
    """
    lines = [li for c in order.get("charges") or [] for li in c.get("items") or []]
    if not lines:
        return None
    per_item: dict[str, float] = {}
    shipping = 0.0
    for li in lines:
        cost = _amount(li.get("cost"))
        if li.get("itemId"):
            per_item[li["itemId"]] = per_item.get(li["itemId"], 0.0) + cost
        else:
            shipping += cost
    return round(sum(per_item.values()), 2), round(shipping, 2), per_item


def cost_rows(order: dict, lines: list[dict]) -> list[dict]:
    """Partial ``Pedidos`` rows (only the Prodigi columns) for one matched order.

    ``lines`` are the order's Pedidos rows. Item cost goes to the line whose SKU matches
    the Prodigi item's ``merchantReference`` or SKU; if any item can't be placed, the
    whole item cost goes on the first POD line and 0 on the rest, so the order's margin
    is right even when a line's is not. Shipping always goes on the first POD line.
    """
    pod = [r for r in lines if r.get("ruta_pod") in POD_ROUTES] or list(lines)
    pod.sort(key=lambda r: str(r["linea_pedido_id"]))
    got = charges(order)
    base = [{"linea_pedido_id": r["linea_pedido_id"], "linea": r.get("linea") or "US-POD",
             "pod_pedido_id": order.get("id", "")} for r in pod]
    if got is None:
        return base
    item_total, shipping, per_item = got
    by_sku: dict[str, dict] = {}
    for r in pod:
        if r.get("sku"):
            by_sku.setdefault(_norm(r["sku"]), r)
    placed: dict[str, float] = {}
    for it in order.get("items") or []:
        target = by_sku.get(_norm(it.get("merchantReference"))) or by_sku.get(_norm(it.get("sku")))
        if target is None or it.get("id") not in per_item:
            placed = {}
            break
        key = target["linea_pedido_id"]
        placed[key] = placed.get(key, 0.0) + per_item[it["id"]]
    if not placed or round(sum(placed.values()), 2) != item_total:
        placed = {pod[0]["linea_pedido_id"]: item_total}
    for i, row in enumerate(base):
        row["costo_pod"] = round(placed.get(row["linea_pedido_id"], 0.0), 2)
        row["envio_pod"] = shipping if i == 0 else 0.0
    return base


def match_orders(orders: list[dict], pedidos: list[dict]) -> tuple[list[dict], list[dict]]:
    """Match Prodigi orders to Pedidos rows. Returns (partial rows, unmatched orders)."""
    by_ref: dict[str, list[dict]] = {}
    for r in pedidos:
        keys = {_norm(r.get("numero_canal"))}
        pid = str(r.get("pedido_id") or "")
        if pid:
            keys.update({_norm(pid), _norm(pid.rsplit("-", 1)[-1])})
        for k in keys - {""}:
            by_ref.setdefault(k, []).append(r)
    rows, unmatched = [], []
    for o in orders:
        if ((o.get("status") or {}).get("stage")) == "Cancelled":
            continue
        lines = next((by_ref[k] for k in order_refs(o) if k in by_ref), None)
        if lines is None:
            unmatched.append(o)
            continue
        rows.extend(cost_rows(o, lines))
    return rows, unmatched


def sync(client: ProdigiClient, wb) -> dict:
    """Write Prodigi ids and real costs into Pedidos; then recompute margin if available."""
    orders = list(client.iter_orders(page_size=50))
    rows, unmatched = match_orders(orders, wb.read("Pedidos"))
    if rows:
        wb.upsert("Pedidos", rows)
    try:
        from .. import margen
    except ImportError:
        margen = None
    if margen is not None and hasattr(margen, "recalcular"):
        margen.recalcular(wb)
    sin_costo = sum(1 for r in rows if "costo_pod" not in r)
    note = []
    if unmatched:
        note.append(f"{len(unmatched)} pedido(s) Prodigi sin pedido de canal")
    if sin_costo:
        note.append(f"{sin_costo} línea(s) sin cargo de Prodigi todavía")
    # the app reads the "prodigi" source; a sandbox run must not look like live data
    wb.stamp_source("prodigi" if client.env == "live" else "prodigi-sandbox", rows=len(rows), note="; ".join(note))
    return {"pedidos_prodigi": len(orders), "lineas": len(rows), "sin_emparejar": unmatched}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Prodigi Print API")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true",
                       help="confirm the key works and count orders; changes nothing")
    group.add_argument("--sync", action="store_true",
                       help="write Prodigi ids and real costs into Pedidos (reads Prodigi only)")
    args = parser.parse_args(argv)
    if not (args.check or args.sync):
        parser.print_help()
        return 0
    client = ProdigiClient.from_env()
    if args.sync:
        from ..localbook import open_workbook

        result = sync(client, open_workbook())
        print(f"Prodigi {client.env}: {result['pedidos_prodigi']} pedido(s), "
              f"{result['lineas']} línea(s) de Pedidos actualizadas, "
              f"{len(result['sin_emparejar'])} sin emparejar")
        for o in result["sin_emparejar"][:5]:  # field names and references only
            print(f"  sin emparejar: {o.get('id')}  refs={order_refs(o)}")
        return 0
    orders = list(client.iter_orders(page_size=50))
    statuses: dict[str, int] = {}
    for o in orders:
        stage = ((o.get("status") or {}).get("stage")) or "?"
        statuses[stage] = statuses.get(stage, 0) + 1
    print(f"Prodigi {client.env}: key OK, {len(orders)} order(s) {statuses or ''}")
    for o in orders[:3]:  # references only, no recipient data
        print(f"  {o.get('id')}  ref={o.get('merchantReference')}  "
              f"metadata={sorted((o.get('metadata') or {}).keys())}  created={o.get('created')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
