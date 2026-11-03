import pytest

from lulamacaroni.approval import JsonStore, NotApproved, decide, request_approval
from lulamacaroni.connectors.shopify import (
    ShopifyClient, ShopifyError, order_to_rows, product_to_listing_rows, route_for,
)
from lulamacaroni.schema import validate_row


class Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.text = str(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def post(self, url, **kw):
        self.calls.append((url, kw))
        return self.responses.pop(0)


TOKEN = Resp(200, {"access_token": "tok-1", "expires_in": 86399, "scope": "read_products"})


def client(*responses):
    return ShopifyClient(store_domain="https://lula-test.myshopify.com/", client_id="cid",
                         client_secret="csecret", session=FakeSession(responses),
                         sleep=lambda s: None)


def page(path, nodes, has_next=False, cursor=None):
    return Resp(200, {"data": {path: {"nodes": nodes,
                                      "pageInfo": {"hasNextPage": has_next, "endCursor": cursor}}}})


def test_domain_must_be_myshopify():
    with pytest.raises(ValueError):
        ShopifyClient(store_domain="lulamacaroni.com", client_id="a", client_secret="b")


def test_client_credentials_exchange_then_cached_token():
    c = client(TOKEN, page("products", [PRODUCT]), page("products", []))
    list(c.iter_products())
    list(c.iter_products())
    token_call, gql_call = c.session.calls[0], c.session.calls[1]
    assert token_call[0] == "https://lula-test.myshopify.com/admin/oauth/access_token"
    assert token_call[1]["data"]["grant_type"] == "client_credentials"
    assert gql_call[1]["headers"]["X-Shopify-Access-Token"] == "tok-1"
    assert sum("access_token" in u for u, _ in c.session.calls) == 1  # cached


def test_401_renews_token_once():
    new_token = Resp(200, {"access_token": "tok-2", "expires_in": 86399})
    c = client(TOKEN, Resp(401, {}), new_token, page("products", []))
    assert list(c.iter_products()) == []
    assert c.session.calls[-1][1]["headers"]["X-Shopify-Access-Token"] == "tok-2"


def test_throttle_retries_then_succeeds():
    throttled = Resp(200, {"errors": [{"message": "Throttled", "extensions": {"code": "THROTTLED"}}]})
    c = client(TOKEN, throttled, Resp(429, {}), page("products", []))
    assert list(c.iter_products()) == []


def test_token_failure_does_not_leak_secret():
    c = client(Resp(400, {"error": "invalid_client"}))
    with pytest.raises(ShopifyError) as exc:
        c.token()
    assert "csecret" not in str(exc.value)


def test_paging_follows_cursor():
    c = client(TOKEN, page("products", [PRODUCT], True, "c1"), page("products", [PRODUCT]))
    assert len(list(c.iter_products())) == 2
    assert c.session.calls[2][1]["json"]["variables"]["after"] == "c1"


def test_graphql_errors_raise():
    c = client(TOKEN, Resp(200, {"errors": [{"message": "Field 'x' doesn't exist"}]}))
    with pytest.raises(ShopifyError):
        list(c.iter_products())


PRODUCT = {
    "id": "gid://shopify/Product/1", "legacyResourceId": "1", "title": "Sunlit Garden",
    "handle": "sunlit-garden", "status": "ACTIVE", "onlineStoreUrl": "https://lulamacaroni.com/products/sunlit-garden",
    "variants": {"nodes": [
        {"id": "gid://shopify/ProductVariant/11", "legacyResourceId": "11", "sku": "LM-001-12x16",
         "title": "12x16", "price": "95.00", "inventoryQuantity": 0},
        {"id": "gid://shopify/ProductVariant/12", "legacyResourceId": "12", "sku": None,
         "title": "18x24", "price": "125.00", "inventoryQuantity": None},
    ]},
}


def test_product_to_listing_rows_are_valid():
    rows = product_to_listing_rows(PRODUCT, "2026-11-02T19:00:00+00:00")
    assert [r["listado_ref"] for r in rows] == ["shopify-11", "shopify-12"]
    assert rows[0]["estado"] == "publicado" and rows[0]["linea"] == "US-POD"
    assert rows[0]["titulo_en_canal"] == "Sunlit Garden / 12x16"
    assert rows[1]["inventario"] == ""  # unknown stays empty, not zero
    for r in rows:
        assert validate_row("Listados", r) == []


def _money(x):
    return {"shopMoney": {"amount": str(x)}}


def _order(**over):
    order = {
        "id": "gid://shopify/Order/500", "legacyResourceId": "500", "name": "#1001",
        "createdAt": "2026-11-14T10:00:00Z", "updatedAt": "2026-11-14T10:00:00Z",
        "cancelledAt": None, "test": False, "displayFinancialStatus": "PAID",
        "displayFulfillmentStatus": "UNFULFILLED", "currencyCode": "USD",
        "totalRefundedSet": _money(0), "shippingLine": {"originalPriceSet": _money(8)},
        "lineItems": {"nodes": [
            {"id": "gid://shopify/LineItem/1", "sku": "LM-001-12x16", "quantity": 1, "name": "x",
             "originalTotalSet": _money(95), "totalDiscountSet": _money(5),
             "taxLines": [{"priceSet": _money(6.3)}]},
            {"id": "gid://shopify/LineItem/2", "sku": "LM-002-FRAMED", "quantity": 2, "name": "y",
             "originalTotalSet": _money(240), "totalDiscountSet": _money(0), "taxLines": []},
            {"id": "gid://shopify/LineItem/3", "sku": "LM-OTHER", "quantity": 1, "name": "z",
             "originalTotalSet": _money(20), "totalDiscountSet": _money(0), "taxLines": []},
        ]},
        "fulfillmentOrders": {"nodes": [
            {"status": "OPEN", "assignedLocation": {"name": "Prodigi Global Print on Demand"},
             "lineItems": {"nodes": [{"lineItem": {"id": "gid://shopify/LineItem/1"}}]}},
            {"status": "OPEN", "assignedLocation": {"name": "Frame It Easy"},
             "lineItems": {"nodes": [{"lineItem": {"id": "gid://shopify/LineItem/2"}}]}},
        ]},
        "fulfillments": [],
    }
    order.update(over)
    return order


def test_order_rows_tag_route_so_app_orders_are_not_resent():
    rows = order_to_rows(_order())
    assert [r["ruta_pod"] for r in rows] == ["prodigi-app", "frame-it-easy-app", "desconocida"]
    for r in rows:
        assert validate_row("Pedidos", r) == []


def test_order_amounts_counted_once_and_costs_marked_missing():
    rows = order_to_rows(_order())
    assert rows[0]["venta_bruta"] == 95 and rows[0]["descuento"] == 5
    assert rows[0]["impuesto_cobrado"] == 6.3
    assert [r["envio_cobrado"] for r in rows] == [8, 0, 0]
    # Prodigi cost and margin belong to other syncs: a Shopify re-sync must not wipe them
    for col in ("costo_pod", "envio_pod", "pod_pedido_id", "margen_contribucion", "calidad_dato"):
        assert all(col not in r for r in rows)
    assert [r["comision_canal"] for r in rows] == [0.0, 0.0, 0.0]  # nothing paid: real zero fee
    assert rows[0]["numero_canal"] == "#1001"
    assert rows[0]["linea_pedido_id"] == "shopify-500-1"


def test_order_states_tracking_and_test_orders():
    shipped = _order(displayFulfillmentStatus="FULFILLED", fulfillments=[{
        "trackingInfo": [{"number": "1Z999"}],
        "fulfillmentLineItems": {"nodes": [{"lineItem": {"id": "gid://shopify/LineItem/1"}}]}}])
    rows = order_to_rows(shipped)
    assert rows[0]["estado"] == "enviado" and rows[0]["tracking"] == "1Z999"
    assert order_to_rows(_order(cancelledAt="2026-11-15T00:00:00Z"))[0]["estado"] == "cancelado"
    assert order_to_rows(_order(test=True)) == []


def test_route_for():
    assert route_for("Prodigi Global Print on Demand") == "prodigi-app"
    assert route_for("Lula studio") == "manual"
    assert route_for(None) == "desconocida"


def test_create_draft_requires_approval(tmp_path):
    store = JsonStore(tmp_path / "a.json")
    product = {"title": "Sunlit Garden", "productType": "Art print"}
    rec = request_approval(store, tipo="listado", linea="US-POD", resumen="Nuevo producto",
                           contenido=product, creado_por="Listados")
    created = Resp(200, {"data": {"productCreate": {
        "product": {"id": "gid://shopify/Product/9", "legacyResourceId": "9", "status": "DRAFT",
                    "title": "Sunlit Garden"}, "userErrors": []}}})
    c = client(TOKEN, created)
    with pytest.raises(NotApproved):
        c.create_draft_product(product, approval=rec)
    assert c.session.calls == []
    rec = decide(store, rec.aprobacion_id, aprobar=True, decidido_por="Lorena")
    assert c.create_draft_product(product, approval=rec)["status"] == "DRAFT"
    sent = c.session.calls[-1][1]["json"]["variables"]["product"]
    assert sent["status"] == "DRAFT"


def test_route_for_fie_fulfillment_service_name():
    # Frame It Easy registers itself in the store as "FIE Fulfillment".
    assert route_for("FIE Fulfillment") == "frame-it-easy-app"


def test_unlisted_product_maps_to_pausado():
    rows = product_to_listing_rows({**PRODUCT, "status": "UNLISTED"}, "2026-11-02T19:00:00+00:00")
    assert rows[0]["estado"] == "pausado"
    assert validate_row("Listados", rows[0]) == []


def _with_variant_location(line, location_id):
    return {**line, "variant": {"inventoryItem": {"inventoryLevels": {"nodes": [
        {"location": {"id": location_id}}]}}}}


def test_orders_fall_back_to_variant_location_without_fulfillment_order_scopes():
    denied = Resp(200, {"errors": [{"message": "Access denied for fulfillmentOrders field.",
                                    "path": ["orders", "nodes", 0, "fulfillmentOrders"],
                                    "extensions": {"code": "ACCESS_DENIED"}}]})
    base = _order()
    lines = base["lineItems"]["nodes"]
    order = {**base, "fulfillmentOrders": None, "lineItems": {"nodes": [
        _with_variant_location(lines[0], "L-prodigi"),
        _with_variant_location(lines[1], "L-fie"),
        _with_variant_location(lines[2], "L-manual")]}}
    services = Resp(200, {"data": {"shop": {"fulfillmentServices": [
        {"serviceName": "Manual", "location": {"id": "L-manual"}},
        {"serviceName": "FIE Fulfillment", "location": {"id": "L-fie"}},
        {"serviceName": "Prodigi", "location": {"id": "L-prodigi"}}]}}})
    c = client(TOKEN, services, denied, page("orders", [order]))
    routes = c.location_routes()
    orders = list(c.iter_orders())
    assert "fulfillmentOrders" not in c.session.calls[-1][1]["json"]["query"]
    rows = order_to_rows(orders[0], routes)
    assert [r["ruta_pod"] for r in rows] == ["prodigi-app", "frame-it-easy-app", "manual"]


def test_other_graphql_errors_are_not_swallowed_by_fallback():
    c = client(TOKEN, Resp(200, {"errors": [{"message": "boom"}]}))
    with pytest.raises(ShopifyError):
        list(c.iter_orders())


def test_listing_route_from_stock_locations():
    from lulamacaroni.connectors.shopify import listing_route

    routes = {"L-prodigi": "prodigi-app", "L-fie": "frame-it-easy-app"}

    def v(*locs):
        return {"inventoryItem": {"inventoryLevels": {"nodes": [{"location": {"id": x}}
                                                                 for x in locs]}}}
    assert listing_route(v("L-prodigi"), routes) == "prodigi-app"
    assert listing_route(v("L-manual"), routes) == "manual"
    assert listing_route(v("L-prodigi", "L-fie"), routes) == "varias"
    assert listing_route(v("L-prodigi", "L-manual"), routes) == "desconocida"
    assert listing_route(v(), routes) == "desconocida"
    assert listing_route(v("L-prodigi"), None) == ""
    rows = product_to_listing_rows({**PRODUCT, "variants": {"nodes": [
        {**PRODUCT["variants"]["nodes"][0], **v("L-fie")}]}}, "2026-11-02T19:00:00+00:00", routes)
    assert rows[0]["ruta_pod"] == "frame-it-easy-app"


# --- attribution (customer journey) -----------------------------------------------------------

def _journey(**visit):
    base = {"source": "instagram", "sourceType": "AD",
            "referrerUrl": "https://l.instagram.com/?u=https%3A%2F%2Fshop&e=private",
            "utmParameters": {"source": "Instagram", "medium": "paid_social",
                              "campaign": "garden-otono"}}
    return {"ready": True, "lastVisit": {**base, **visit}}


def test_order_origin_keeps_utm_and_referrer_domain_only():
    from lulamacaroni.connectors.shopify import order_origin

    o = order_origin(_order(customerJourneySummary=_journey()))
    assert o == {"origen_estado": "ok", "origen_fuente": "instagram", "origen_tipo": "ad",
                 "utm_fuente": "instagram", "utm_medio": "paid_social",
                 "utm_campana": "garden-otono", "referente": "l.instagram.com"}
    assert order_origin(_order(customerJourneySummary=None))["origen_estado"] == "sin-recorrido"
    assert order_origin(_order(customerJourneySummary={"ready": False}))["origen_estado"] == "pendiente"
    # field not requested: say so, and don't blank what an earlier sync stored
    assert order_origin(_order()) == {"origen_estado": "sin-permiso"}
    rows = order_to_rows(_order(customerJourneySummary=_journey()))
    assert all(r["utm_campana"] == "garden-otono" for r in rows)
    assert all(validate_row("Pedidos", r) == [] for r in rows)


def test_orders_drop_the_journey_block_if_shopify_denies_it():
    denied = Resp(200, {"errors": [{"message": "Access denied for customerJourneySummary field.",
                                    "path": ["orders", "nodes", 0, "customerJourneySummary"],
                                    "extensions": {"code": "ACCESS_DENIED"}}]})
    c = client(TOKEN, denied, page("orders", [_order()]))
    orders = list(c.iter_orders())
    assert len(orders) == 1
    assert "customerJourneySummary" in c.session.calls[1][1]["json"]["query"]
    last = c.session.calls[-1][1]["json"]["query"]
    assert "customerJourneySummary" not in last and "fulfillmentOrders" in last
