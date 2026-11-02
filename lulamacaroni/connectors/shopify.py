"""Shopify Admin API connector (US line, principal store).

Auth: the "LulaMacaroni Operaciones" app from Shopify's Dev Dashboard, installed in
Lorena's store, uses the **client-credentials grant**. The Client ID and secret are
exchanged for a short-lived Admin API token, which is cached in memory and renewed when
it expires or a call returns 401. Nothing is written to disk.

Settings (cloud environment secrets, or .env locally):
    SHOPIFY_STORE_DOMAIN   e.g. lula-macaroni.myshopify.com
    SHOPIFY_CLIENT_ID
    SHOPIFY_CLIENT_SECRET
    SHOPIFY_API_VERSION    optional, defaults to DEFAULT_API_VERSION

What it does
------------
* Reads products, variants and inventory into ``Listados`` rows.
* Reads orders into ``Pedidos`` rows (one per line item), tagged ``US-POD``.
* Tags each line with ``ruta_pod``: who fulfils it. The Prodigi and Frame It Easy apps
  already receive Shopify orders on their own, so a line routed to one of them must
  **never** also be sent through the Prodigi API (``connectors/prodigi.py``), or the
  print is made and charged twice. The Prodigi API is only for approved reprints and
  manual orders.
* Writes only drafts, and only with an approved record from the approval gate.

Routing comes from each order's fulfilment orders (the location Shopify assigned), which
needs the ``read_merchant_managed_fulfillment_orders`` and
``read_third_party_fulfillment_orders`` scopes; the store's app has had them since
2026-11-02. If a reinstall ever drops them, the orders query falls back to routing each
line by its variant's stock location, matched against the store's fulfilment services
(Manual, FIE Fulfillment, Prodigi).

Scope notes: the app has read orders but not ``read_all_orders``, so Shopify returns
only the last 60 days of orders. That is fine for a daily sync; history beyond it needs
the extra scope (Shopify approval) or a one-time CSV export.

    python -m lulamacaroni.connectors.shopify --dry-run          # counts + sample rows
    python -m lulamacaroni.connectors.shopify --to-json exports/  # files, before the workbook exists
    python -m lulamacaroni.connectors.shopify                    # upsert into the workbook
                                                                 # (local data/libro/ until the sheet exists)
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import requests

from .. import config

DEFAULT_API_VERSION = "2025-10"
TOKEN_SAFETY_MARGIN = 120  # seconds: renew a little before Shopify says it expires
MAX_THROTTLE_RETRIES = 5

# Fulfilment routing: fulfilment-service / location names that mean an app prints it.
ROUTES = (
    ("prodigi", "prodigi-app"),
    ("frame it easy", "frame-it-easy-app"),
    ("frameiteasy", "frame-it-easy-app"),
    ("fie fulfillment", "frame-it-easy-app"),   # the app's fulfilment-service name in the store
    ("fie-fulfillment", "frame-it-easy-app"),
)


class ShopifyError(RuntimeError):
    def __init__(self, message: str, payload: Any = None, status: int | None = None):
        super().__init__(message)
        self.payload = payload
        self.status = status


@dataclass
class ShopifyClient:
    store_domain: str
    client_id: str
    client_secret: str = field(repr=False)
    api_version: str = DEFAULT_API_VERSION
    timeout: float = 30.0
    session: requests.Session | None = None
    sleep: Any = time.sleep
    _token: str | None = field(default=None, repr=False)
    _token_expires: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        self.store_domain = (self.store_domain.strip().removeprefix("https://")
                             .removeprefix("http://").rstrip("/"))
        if not self.store_domain.endswith(".myshopify.com"):
            raise ValueError("SHOPIFY_STORE_DOMAIN must be the store's *.myshopify.com address")
        if self.session is None:
            self.session = requests.Session()

    @classmethod
    def from_env(cls) -> "ShopifyClient":
        return cls(
            store_domain=config.require("SHOPIFY_STORE_DOMAIN"),
            client_id=config.require("SHOPIFY_CLIENT_ID"),
            client_secret=config.require("SHOPIFY_CLIENT_SECRET"),
            api_version=config.get("SHOPIFY_API_VERSION", DEFAULT_API_VERSION),
        )

    # -- auth ------------------------------------------------------------------
    def _fetch_token(self) -> None:
        resp = self.session.post(
            f"https://{self.store_domain}/admin/oauth/access_token",
            data={"grant_type": "client_credentials", "client_id": self.client_id,
                  "client_secret": self.client_secret},
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            # Never echo the request (it holds the secret); Shopify's error text is enough.
            raise ShopifyError(f"token exchange failed ({resp.status_code}): {resp.text[:200]}",
                               status=resp.status_code)
        body = resp.json()
        self._token = body["access_token"]
        expires_in = float(body.get("expires_in") or 3600)
        self._token_expires = time.time() + max(expires_in - TOKEN_SAFETY_MARGIN, 60)

    def token(self) -> str:
        if not self._token or time.time() >= self._token_expires:
            self._fetch_token()
        return self._token  # type: ignore[return-value]

    # -- GraphQL -----------------------------------------------------------------
    @property
    def graphql_url(self) -> str:
        return f"https://{self.store_domain}/admin/api/{self.api_version}/graphql.json"

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        renewed = False
        for attempt in range(MAX_THROTTLE_RETRIES + 1):
            resp = self.session.post(
                self.graphql_url,
                headers={"X-Shopify-Access-Token": self.token(),
                         "Content-Type": "application/json"},
                json={"query": query, "variables": variables or {}},
                timeout=self.timeout,
            )
            if resp.status_code == 401 and not renewed:
                self._token, renewed = None, True
                continue
            if resp.status_code in (429, 503) or _throttled(resp):
                self.sleep(min(2 ** attempt, 30))
                continue
            if resp.status_code >= 400:
                raise ShopifyError(f"Shopify {resp.status_code}: {resp.text[:300]}",
                                   status=resp.status_code)
            body = resp.json()
            if body.get("errors"):
                raise ShopifyError(f"GraphQL errors: {body['errors']}", body)
            return body["data"]
        raise ShopifyError("Shopify kept throttling; try again later")

    def paginate(self, query: str, path: str, variables: dict | None = None,
                 page_size: int = 50) -> Iterator[dict]:
        """Yield every node of the connection at ``path`` (e.g. ``"products"``)."""
        variables = dict(variables or {})
        cursor = variables.pop("after", None)
        while True:
            data = self.graphql(query, {**variables, "first": page_size, "after": cursor})
            conn = data[path]
            yield from conn["nodes"]
            if not conn["pageInfo"]["hasNextPage"]:
                return
            cursor = conn["pageInfo"]["endCursor"]

    # -- reads -------------------------------------------------------------------
    def iter_products(self) -> Iterator[dict]:
        # One product per page: up to 100 variants x their stock locations stays well
        # under Shopify's 1,000-point query cost limit.
        return self.paginate(PRODUCTS_QUERY, "products", page_size=1)

    def location_routes(self) -> dict[str, str]:
        """Location id -> ruta_pod, from the store's fulfilment services."""
        data = self.graphql(FULFILLMENT_SERVICES_QUERY)
        return {fs["location"]["id"]: route_for(fs["serviceName"])
                for fs in data["shop"]["fulfillmentServices"] if fs.get("location")}

    def iter_orders(self, since: datetime | None = None) -> Iterator[dict]:
        query = f"updated_at:>='{since.isoformat()}'" if since else None
        variables = {"query": query}
        orders_q, by_variant_q = ORDERS_QUERY, ORDERS_QUERY_BY_VARIANT
        for _ in range(3):  # at most: drop the journey block, then fall back to variants
            try:
                first = self.graphql(orders_q, {**variables, "first": 25, "after": None})
                break
            except ShopifyError as e:
                if _denied_field(e, "customerJourneySummary") and JOURNEY_BLOCK in orders_q:
                    orders_q = orders_q.replace(JOURNEY_BLOCK, "")
                    by_variant_q = by_variant_q.replace(JOURNEY_BLOCK, "")
                    continue
                if not _denied_field(e, "fulfillmentOrders"):
                    raise
                # Missing fulfilment-order scopes: route by variant stock location instead.
                yield from self._orders_by_variant(by_variant_q, variables)
                return
        else:
            raise ShopifyError("Shopify kept denying fields of the orders query")
        conn = first["orders"]
        yield from conn["nodes"]
        if conn["pageInfo"]["hasNextPage"]:
            yield from self.paginate(orders_q, "orders",
                                     {**variables, "after": conn["pageInfo"]["endCursor"]},
                                     page_size=25)

    def _orders_by_variant(self, query: str, variables: dict) -> Iterator[dict]:
        try:
            yield from self.paginate(query, "orders", variables, page_size=25)
        except ShopifyError as e:
            if not (_denied_field(e, "customerJourneySummary") and JOURNEY_BLOCK in query):
                raise
            yield from self.paginate(query.replace(JOURNEY_BLOCK, ""), "orders", variables,
                                     page_size=25)

    def iter_payouts(self) -> Iterator[dict]:
        """Shopify Payments payouts, newest first.

        Needs the ``read_shopify_payments_payouts`` and ``read_shopify_payments_accounts``
        scopes; without them Shopify answers ACCESS_DENIED (see :func:`payouts_denied`).
        """
        cursor = None
        while True:
            data = self.graphql(PAYOUTS_QUERY, {"first": 50, "after": cursor})
            account = data.get("shopifyPaymentsAccount")
            if not account:  # store without Shopify Payments
                return
            conn = account["payouts"]
            yield from conn["nodes"]
            if not conn["pageInfo"]["hasNextPage"]:
                return
            cursor = conn["pageInfo"]["endCursor"]

    # -- writes (gated) ----------------------------------------------------------
    def create_draft_product(self, product: dict, *, approval) -> dict:
        """Create a product as DRAFT. Publishing it is a separate approved step in Shopify."""
        from ..approval.gate import assert_approved

        assert_approved(approval, tipo="listado", contenido=product)
        payload = {**product, "status": "DRAFT"}
        data = self.graphql(PRODUCT_CREATE, {"product": payload})
        result = data["productCreate"]
        if result["userErrors"]:
            raise ShopifyError(f"productCreate: {result['userErrors']}", result)
        return result["product"]


def _denied_field(error: ShopifyError, field_name: str) -> bool:
    errors = (error.payload or {}).get("errors") if isinstance(error.payload, dict) else None
    return any((e.get("extensions") or {}).get("code") == "ACCESS_DENIED"
               and field_name in (e.get("path") or []) for e in errors or [])


def _throttled(resp) -> bool:
    if resp.status_code != 200:
        return False
    try:
        errors = resp.json().get("errors") or []
    except ValueError:
        return False
    return any((e.get("extensions") or {}).get("code") == "THROTTLED" for e in errors)


PRODUCTS_QUERY = """
query Products($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id legacyResourceId title handle status onlineStoreUrl vendor productType updatedAt
      variants(first: 100) {
        nodes {
          id legacyResourceId sku title price inventoryQuantity
          inventoryItem { inventoryLevels(first: 5) { nodes { location { id } } } }
        }
      }
    }
  }
}
"""

ORDERS_QUERY = """
query Orders($first: Int!, $after: String, $query: String) {
  orders(first: $first, after: $after, query: $query, sortKey: UPDATED_AT) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id legacyResourceId name createdAt updatedAt cancelledAt test
      displayFinancialStatus displayFulfillmentStatus
      currencyCode
      totalRefundedSet { shopMoney { amount } }
      shippingLine { originalPriceSet { shopMoney { amount } } }
      lineItems(first: 50) {
        nodes {
          id sku quantity name
          originalTotalSet { shopMoney { amount } }
          totalDiscountSet { shopMoney { amount } }
          taxLines { priceSet { shopMoney { amount } } }
        }
      }
      fulfillmentOrders(first: 10) {
        nodes {
          status
          assignedLocation { name }
          lineItems(first: 50) { nodes { lineItem { id } } }
        }
      }
      fulfillments(first: 10) {
        trackingInfo { number }
        fulfillmentLineItems(first: 50) { nodes { lineItem { id } } }
      }
      transactions(first: 20) {
        kind status gateway
        fees { amount { amount } type }
      }
      customerJourneySummary {
        ready
        lastVisit {
          source sourceType referrerUrl
          utmParameters { source medium campaign }
        }
      }
    }
  }
}
"""

# Attribution block, dropped if Shopify ever denies it so the order sync keeps working.
JOURNEY_BLOCK = """
      customerJourneySummary {
        ready
        lastVisit {
          source sourceType referrerUrl
          utmParameters { source medium campaign }
        }
      }"""

# Same as ORDERS_QUERY minus fulfillmentOrders, plus each line's variant stock location.
ORDERS_QUERY_BY_VARIANT = ORDERS_QUERY.replace("""
      fulfillmentOrders(first: 10) {
        nodes {
          status
          assignedLocation { name }
          lineItems(first: 50) { nodes { lineItem { id } } }
        }
      }""", "").replace("""
          taxLines { priceSet { shopMoney { amount } } }""", """
          taxLines { priceSet { shopMoney { amount } } }
          variant { inventoryItem { inventoryLevels(first: 5) { nodes { location { id } } } } }""")

PAYOUTS_QUERY = """
query Payouts($first: Int!, $after: String) {
  shopifyPaymentsAccount {
    payouts(first: $first, after: $after, sortKey: ISSUED_AT, reverse: true) {
      pageInfo { hasNextPage endCursor }
      nodes {
        id legacyResourceId issuedAt status transactionType
        net { amount currencyCode }
        summary {
          chargesFee { amount } refundsFee { amount } adjustmentsFee { amount }
          reservedFundsFee { amount } retriedPayoutsFee { amount }
          refundsFeeGross { amount } reservedFundsGross { amount }
        }
      }
    }
  }
}
"""

FULFILLMENT_SERVICES_QUERY = """
{ shop { fulfillmentServices { serviceName location { id } } } }
"""

PRODUCT_CREATE = """
mutation ProductCreate($product: ProductCreateInput!) {
  productCreate(product: $product) {
    product { id legacyResourceId status title }
    userErrors { field message }
  }
}
"""

# --- mapping to workbook rows (pure, tested offline) ---------------------------

# UNLISTED (API 2025-10+): live but hidden from the storefront and search.
LISTING_STATUS = {"ACTIVE": "publicado", "UNLISTED": "pausado", "DRAFT": "borrador",
                  "ARCHIVED": "retirado"}


def _money(node: dict | None) -> float:
    try:
        return float(node["shopMoney"]["amount"])  # type: ignore[index]
    except (TypeError, KeyError, ValueError):
        return 0.0


def route_for(location_name: str | None) -> str:
    name = (location_name or "").lower()
    for needle, route in ROUTES:
        if needle in name:
            return route
    return "manual" if name else "desconocida"


def listing_route(variant: dict, location_routes: dict[str, str] | None) -> str:
    """Who prints a variant, from the locations that stock it.

    One print location -> that route; only locations that are no print app (the store's
    "Manual" location) -> ``manual``; two different print apps -> ``varias`` (an order
    could be printed twice); a print app plus a manual location, or no location data ->
    ``desconocida`` (Shopify's location priority decides, so nobody can say who prints).
    """
    if location_routes is None:
        return ""
    levels = (((variant.get("inventoryItem") or {}).get("inventoryLevels") or {})
              .get("nodes") or [])
    routes = {location_routes.get(n["location"]["id"], "manual") for n in levels}
    printers = routes - {"manual"}
    if len(printers) > 1:
        return "varias"
    if printers and routes == printers:
        return printers.pop()
    return "manual" if routes == {"manual"} else "desconocida"


def product_to_listing_rows(product: dict, now: str,
                            location_routes: dict[str, str] | None = None) -> list[dict]:
    rows = []
    for v in product["variants"]["nodes"]:
        rows.append({
            "listado_ref": f"shopify-{v['legacyResourceId']}",
            "sku": v.get("sku") or "",
            "linea": "US-POD",
            "canal": "shopify",
            "id_en_canal": v["legacyResourceId"],
            "titulo_en_canal": product["title"] if v["title"] == "Default Title"
            else f"{product['title']} / {v['title']}",
            "url": product.get("onlineStoreUrl") or "",
            "precio": v.get("price") or "",
            "inventario": "" if v.get("inventoryQuantity") is None else v["inventoryQuantity"],
            "estado": LISTING_STATUS.get(product["status"], "borrador"),
            "ultima_sync": now,
            "id_producto_canal": product["legacyResourceId"],
            **({"ruta_pod": listing_route(v, location_routes)} if location_routes is not None
               else {}),
        })
    return rows


def _order_state(order: dict) -> str:
    if order.get("cancelledAt"):
        return "cancelado"
    if order.get("displayFinancialStatus") in ("REFUNDED",):
        return "reembolsado"
    f = order.get("displayFulfillmentStatus")
    if f == "FULFILLED":
        return "enviado"
    if f in ("IN_PROGRESS", "PARTIALLY_FULFILLED", "SCHEDULED"):
        return "en-produccion"
    return "recibido"


def _variant_route(line: dict, location_routes: dict[str, str]) -> str:
    levels = ((((line.get("variant") or {}).get("inventoryItem") or {})
               .get("inventoryLevels") or {}).get("nodes") or [])
    routes = {location_routes.get(n["location"]["id"], "manual") for n in levels}
    return routes.pop() if len(routes) == 1 else "desconocida"


# Payment gateways whose fee Shopify reports on the transaction. Other gateways (PayPal,
# manual payments) charge outside Shopify, so their fee is unknown here, never zero.
FEE_GATEWAYS = {"shopify_payments"}
FEE_FREE_GATEWAYS = {"gift_card"}
PAID_KINDS = {"SALE", "CAPTURE"}


def order_fee(order: dict) -> float | None:
    """Total Shopify Payments fee on the order, or None if a fee is unknown.

    Sums the fees of every successful transaction (Shopify does not give the processing
    fee back on a refund, so it stays). An order with no successful payment has a real
    fee of 0.
    """
    total = 0.0
    for t in order.get("transactions") or []:
        if t.get("status") != "SUCCESS":
            continue
        gateway = (t.get("gateway") or "").lower()
        if t.get("kind") in PAID_KINDS and gateway not in FEE_GATEWAYS | FEE_FREE_GATEWAYS:
            return None
        for f in t.get("fees") or []:
            try:
                total += float(f["amount"]["amount"])
            except (KeyError, TypeError, ValueError):
                return None
    return round(total, 2)


def split_fee(fee: float | None, weights: list[float]) -> list:
    """Split an order fee across its lines by sale share; cents add up exactly.

    Unknown fee -> "" on every line (``faltante``).
    """
    if fee is None:
        return ["" for _ in weights]
    if not weights:
        return []
    total = sum(w for w in weights if w > 0)
    if total <= 0:
        parts = [0.0] * len(weights)
        parts[0] = fee
        return parts
    parts = [round(fee * max(w, 0) / total, 2) for w in weights]
    parts[-1] = round(fee - sum(parts[:-1]), 2)
    return parts


def order_to_rows(order: dict, location_routes: dict[str, str] | None = None) -> list[dict]:
    """One ``Pedidos`` row per line item.

    Sale amounts are real. ``comision_canal`` is the real Shopify Payments fee from the
    order's transactions, split across lines by their share of the sale; it stays empty
    when a payment went through another gateway (PayPal, etc.), whose fee Shopify does
    not report. Prodigi cost, ``margen_contribucion`` and ``calidad_dato`` are left out
    on purpose: the Prodigi sync owns the costs and :func:`lulamacaroni.margen.recalcular`
    owns the margin, so a Shopify re-sync never wipes a cost already filled in.
    """
    if order.get("test"):
        return []
    route_by_line: dict[str, str] = {}
    for fo in (order.get("fulfillmentOrders") or {}).get("nodes") or []:
        route = route_for((fo.get("assignedLocation") or {}).get("name"))
        for li in fo["lineItems"]["nodes"]:
            route_by_line[li["lineItem"]["id"]] = route
    tracking_by_line: dict[str, list[str]] = {}
    for f in order.get("fulfillments") or []:
        numbers = [t["number"] for t in f.get("trackingInfo") or [] if t.get("number")]
        for li in f["fulfillmentLineItems"]["nodes"]:
            tracking_by_line.setdefault(li["lineItem"]["id"], []).extend(numbers)

    lines = order["lineItems"]["nodes"]
    shipping = _money((order.get("shippingLine") or {}).get("originalPriceSet"))
    refunded = _money(order.get("totalRefundedSet"))
    estado = _order_state(order)
    origin = order_origin(order)
    fees = split_fee(order_fee(order), [
        _money(li["originalTotalSet"]) - _money(li["totalDiscountSet"]) for li in lines])
    rows = []
    for i, li in enumerate(lines):
        line_id = li["id"].rsplit("/", 1)[-1]
        rows.append({
            "linea_pedido_id": f"shopify-{order['legacyResourceId']}-{line_id}",
            "pedido_id": f"shopify-{order['legacyResourceId']}",
            "linea": "US-POD",
            "canal": "shopify",
            "fecha": order["createdAt"],
            "sku": li.get("sku") or "",
            "cantidad": li["quantity"],
            "moneda": order["currencyCode"],
            "venta_bruta": _money(li["originalTotalSet"]),
            "descuento": _money(li["totalDiscountSet"]),
            "impuesto_cobrado": round(sum(_money(t["priceSet"]) for t in li.get("taxLines") or []), 2),
            # order-level amounts sit on the first line so they are counted once
            "envio_cobrado": shipping if i == 0 else 0.0,
            "reembolso": refunded if i == 0 else 0.0,
            "comision_canal": fees[i],
            "ruta_pod": route_by_line.get(li["id"])
            or (_variant_route(li, location_routes) if location_routes is not None
                else "desconocida"),
            "tracking": ", ".join(dict.fromkeys(tracking_by_line.get(li["id"], []))),
            "estado": estado,
            "producto": li.get("name") or "",
            "numero_canal": order.get("name") or "",
            **origin,
        })
    return rows


def _domain(url: str | None) -> str:
    """Only the referring site's host (no path or query, which can carry personal data)."""
    if not url:
        return ""
    host = urlparse(url if "//" in url else "//" + url).hostname or ""
    return host.removeprefix("www.").lower()


def order_origin(order: dict) -> dict:
    """Where the visit that led to the order came from, per Shopify's customer journey.

    Uses the last visit before the order (Shopify's own last-click view). Keeps UTM tags
    and the referrer's domain only. ``origen_estado`` says whether Shopify had a journey
    for the order, is still computing it, or the field was not requested (no permission).
    """
    if "customerJourneySummary" not in order:
        return {"origen_estado": "sin-permiso"}
    journey = order.get("customerJourneySummary")
    if journey is not None and journey.get("ready") is False:
        return {"origen_estado": "pendiente"}
    visit = (journey or {}).get("lastVisit")
    if not visit:
        return {"origen_estado": "sin-recorrido", "origen_fuente": "", "origen_tipo": "",
                "utm_fuente": "", "utm_medio": "", "utm_campana": "", "referente": ""}
    utm = visit.get("utmParameters") or {}
    return {
        "origen_estado": "ok",
        "origen_fuente": (visit.get("source") or "").lower(),
        "origen_tipo": (visit.get("sourceType") or "").lower(),
        "utm_fuente": (utm.get("source") or "").lower(),
        "utm_medio": (utm.get("medium") or "").lower(),
        "utm_campana": utm.get("campaign") or "",
        "referente": _domain(visit.get("referrerUrl")),
    }


PAYOUT_STATUS = {"SCHEDULED": "programado", "IN_TRANSIT": "en-transito", "PAID": "pagado",
                 "FAILED": "fallido", "CANCELED": "cancelado"}


def _amount(node: dict | None) -> float:
    try:
        return float(node["amount"])  # type: ignore[index]
    except (TypeError, KeyError, ValueError):
        return 0.0


def payout_to_row(payout: dict) -> dict:
    """One ``Pagos`` row: what actually reaches the Chase account, kept apart from sales."""
    summ = payout.get("summary") or {}
    sign = -1 if payout.get("transactionType") == "WITHDRAWAL" else 1
    fees = sum(_amount(summ.get(k)) for k in ("chargesFee", "refundsFee", "adjustmentsFee",
                                              "reservedFundsFee", "retriedPayoutsFee"))
    return {
        "pago_id": f"shopify-payout-{payout['legacyResourceId']}",
        "linea": "US-POD",
        "canal": "shopify",
        "fecha": payout.get("issuedAt") or "",
        "moneda": (payout.get("net") or {}).get("currencyCode") or "USD",
        "monto_depositado": round(sign * _amount(payout.get("net")), 2),
        "comisiones": round(fees, 2),
        "retenciones": round(_amount(summ.get("reservedFundsGross")), 2),
        "reembolsos": round(abs(_amount(summ.get("refundsFeeGross"))), 2),
        "estado": PAYOUT_STATUS.get(payout.get("status") or "", ""),
    }


def payouts_denied(error: ShopifyError) -> bool:
    return _denied_field(error, "shopifyPaymentsAccount") or _denied_field(error, "payouts")


PAYOUT_SCOPES = "read_shopify_payments_payouts y read_shopify_payments_accounts"


# --- CLI --------------------------------------------------------------------------

def sync(client: ShopifyClient, since_days: int = 60) -> tuple[list[dict], list[dict]]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    routes = client.location_routes()
    listings = [r for p in client.iter_products()
                for r in product_to_listing_rows(p, now, routes)]
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    orders = [r for o in client.iter_orders(since) for r in order_to_rows(o, routes)]
    return listings, orders


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync Shopify into the workbook")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="print counts and samples only")
    group.add_argument("--to-json", metavar="DIR", help="write JSON files instead of the workbook")
    parser.add_argument("--days", type=int, default=60, help="orders updated in the last N days")
    args = parser.parse_args(argv)

    client = ShopifyClient.from_env()
    listings, orders = sync(client, args.days)
    unrouted = [o for o in orders if o["ruta_pod"] in ("desconocida", "manual")]
    print(f"Listados: {len(listings)}  Pedidos (líneas): {len(orders)}  "
          f"sin ruta POD clara: {len(unrouted)}")

    if args.dry_run:
        known = [o for o in orders if o["comision_canal"] != ""]
        print(f"Comisión Shopify Payments conocida en {len(known)} de {len(orders)} líneas")
        try:
            print(f"Pagos (payouts): {len(list(client.iter_payouts()))}")
        except ShopifyError as e:
            if not payouts_denied(e):
                raise
            print(f"Pagos: sin permiso ({PAYOUT_SCOPES})")
        for row in listings[:3] + orders[:3]:
            print(json.dumps(row, ensure_ascii=False))
        return 0
    if args.to_json:
        out = Path(args.to_json)
        out.mkdir(parents=True, exist_ok=True)
        (out / "shopify-listados.json").write_text(json.dumps(listings, ensure_ascii=False, indent=2))
        (out / "shopify-pedidos.json").write_text(json.dumps(orders, ensure_ascii=False, indent=2))
        print(f"wrote {out}/shopify-*.json (git-ignored; holds order data, never commit)")
        return 0

    from ..localbook import open_workbook
    from ..margen import recalcular

    wb = open_workbook()  # the Google Sheet when a key is configured, else data/libro/
    wb.upsert("Listados", listings)
    wb.upsert("Pedidos", orders)
    wb.stamp_source("shopify", rows=len(listings) + len(orders),
                    note=f"{len(unrouted)} líneas sin ruta POD clara" if unrouted else "")
    sync_payouts(client, wb)
    recalcular(wb)
    return 0


def sync_payouts(client: ShopifyClient, wb) -> int | None:
    """Upsert Shopify Payments payouts into ``Pagos``; None if the app lacks the scopes."""
    try:
        rows = [payout_to_row(p) for p in client.iter_payouts()]
    except ShopifyError as e:
        if not payouts_denied(e):
            raise
        wb.stamp_source("shopify-pagos", rows=0, estado="sin-conectar",
                        note=f"La app de Shopify no tiene los permisos {PAYOUT_SCOPES}.")
        print(f"Pagos: sin permiso ({PAYOUT_SCOPES}); no se sincronizaron.")
        return None
    if rows:
        wb.upsert("Pagos", rows)
    wb.stamp_source("shopify-pagos", rows=len(rows))
    print(f"Pagos (payouts): {len(rows)}")
    return len(rows)


if __name__ == "__main__":
    raise SystemExit(main())
