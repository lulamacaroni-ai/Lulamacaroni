from datetime import datetime, timezone

import pytest

from lulamacaroni.app import clientes as cli
from lulamacaroni.app import metrics as m
from lulamacaroni.app.alertas import resumen_dia
from lulamacaroni.app.demo import fill_demo
from lulamacaroni.app.screens import Datos, render
from lulamacaroni.approval import JsonStore
from lulamacaroni.connectors import shopify as sh
from lulamacaroni.localbook import LocalWorkbook
from lulamacaroni.schema import validate_row

NOW = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)


@pytest.fixture
def datos(tmp_path):
    b = LocalWorkbook(tmp_path / "libro")
    fill_demo(b, NOW)
    return Datos(b, JsonStore(tmp_path / "a.json"), NOW)


def _fuentes(**estado):
    out = {k: m.EstadoFuente(m.FUENTE_BY_KEY[k], "sin-conectar", None) for k in m.FUENTE_BY_KEY}
    for k, v in estado.items():
        out[k.replace("_", "-")] = m.EstadoFuente(m.FUENTE_BY_KEY[k.replace("_", "-")], v, NOW)
    return out


# --- Shopify mapping ------------------------------------------------------------------------

CUSTOMER = {
    "id": "gid://shopify/Customer/77", "legacyResourceId": "77",
    "createdAt": "2026-10-01T10:00:00Z", "updatedAt": "2026-11-01T10:00:00Z",
    "numberOfOrders": "2", "amountSpent": {"amount": "180.5", "currencyCode": "USD"},
    "lastOrder": {"createdAt": "2026-10-30T10:00:00Z"}, "note": " VIP ",
    "emailMarketingConsent": {"marketingState": "SUBSCRIBED"},
    "firstName": "Maria Jose", "lastName": "garcia lopez",
    "defaultAddress": {"countryCodeV2": "US", "provinceCode": "CA"},
}


def test_customer_row_is_minimal_and_valid():
    row = sh.customer_to_row(CUSTOMER, "2026-11-02T00:00:00+00:00")
    assert row["cliente_id"] == "shopify-cliente-77"
    assert row["nombre"] == "Maria G."
    assert (row["pais"], row["region"]) == ("US", "CA")
    assert (row["pedidos"], row["total"], row["moneda"]) == (2, 180.5, "USD")
    assert row["consentimiento_email"] == "si"
    assert row["nota_shopify"] == "VIP"
    assert validate_row("Clientes", row) == []
    # Lorena's own columns are never written by the sync
    for col in ("nota", "nota_por", "seguimiento", "seguimiento_estado"):
        assert col not in row
    assert not any("@" in str(v) for v in row.values())


def test_customer_row_without_protected_fields_leaves_them_alone():
    c = {k: v for k, v in CUSTOMER.items() if k not in ("firstName", "lastName",
                                                        "defaultAddress")}
    row = sh.customer_to_row(c, "x")
    assert "nombre" not in row and "pais" not in row


class FakeClient:
    def __init__(self, deny=()):
        self.deny = set(deny)
        self.queries = []

    def paginate(self, query, path, variables=None, page_size=50):
        self.queries.append(query)
        for f in self.deny:
            if f in query:
                raise sh.ShopifyError("denied", {"errors": [
                    {"extensions": {"code": "ACCESS_DENIED"},
                     "path": ["customers", "nodes", 0, f]}]})
        yield {k: v for k, v in CUSTOMER.items()
               if k not in ("firstName", "lastName") or "firstName" in query}


def test_protected_fields_denied_are_dropped_not_fatal(tmp_path):
    client = FakeClient(deny=["firstName"])
    wb = LocalWorkbook(tmp_path / "l")
    assert sh.sync_customers(client, wb) == 1
    assert "firstName" not in client.queries[-1]
    rows = wb.read("Clientes")
    assert rows[0]["cliente_id"] == "shopify-cliente-77" and rows[0]["nombre"] == ""
    fuente = {r["fuente"]: r for r in wb.read("Fuentes")}["shopify-clientes"]
    assert fuente["estado"] == "ok" and "protegidos" in fuente["nota"]


def test_sync_keeps_lorenas_notes(tmp_path):
    wb = LocalWorkbook(tmp_path / "l")
    wb.upsert("Clientes", [{"cliente_id": "shopify-cliente-77", "linea": "US-POD",
                            "nota": "Regalo", "nota_por": "Lore",
                            "seguimiento": "Escribirle", "seguimiento_estado": "pendiente"}])
    sh.sync_customers(FakeClient(), wb)
    row = wb.read("Clientes")[0]
    assert (row["nota"], row["nota_por"], row["seguimiento"]) == ("Regalo", "Lore", "Escribirle")
    assert row["total"] == 180.5


def test_order_rows_carry_the_customer():
    order = {
        "legacyResourceId": "5", "name": "#1005", "createdAt": "2026-11-01T00:00:00Z",
        "currencyCode": "USD", "customer": {"legacyResourceId": "77"},
        "lineItems": {"nodes": [{"id": "gid://shopify/LineItem/1", "quantity": 1,
                                 "originalTotalSet": {"shopMoney": {"amount": "10"}},
                                 "totalDiscountSet": {"shopMoney": {"amount": "0"}}}]},
    }
    assert sh.order_to_rows(order)[0]["cliente_id"] == "shopify-cliente-77"
    order["customer"] = None
    assert sh.order_to_rows(order)[0]["cliente_id"] == ""


# --- the view -------------------------------------------------------------------------------

def test_demo_clients(datos):
    by = {c.id: c for c in datos.clientes}
    ana = by["shopify-cliente-901"]
    assert ana.pedidos.valor == 3 and ana.pedidos.fuente == "Shopify (clientes)"
    assert ana.origen.texto.startswith("Instagram / Facebook · anuncio")
    assert ana.notas == [("Pidió el 18x24 enmarcado para regalo (ejemplo).", "Lore, 30 oct")]
    ben = by["shopify-cliente-902"]
    assert ben.vencido and ben.notas[0][1] == "nota del cliente en Shopify"
    mx = by["mx-001"]
    assert mx.total.formato == "mxn" and mx.total.fuente == cli.MANUAL
    assert mx.origen.texto == "WhatsApp" and not mx.vencido and mx.pendiente
    # overdue follow-ups first
    assert datos.clientes[0].id == "shopify-cliente-902"


def test_missing_typed_numbers_are_missing_not_zero():
    row = {"cliente_id": "mx-9", "linea": "MX-original", "canal_origen": "sitio-mx",
           "nombre": "X"}
    c = cli.cliente(row, None, _fuentes(), NOW)
    assert c.pedidos.calidad == "faltante" and c.total.calidad == "faltante"
    assert c.ultimo.calidad == "faltante"


def test_pedidos_win_over_typed_numbers_for_mexico():
    row = {"cliente_id": "mx-1", "linea": "MX-original", "canal_origen": "sitio-mx",
           "pedidos": 9, "total": 1, "moneda": "MXN"}
    pedidos = {"p1": [{"pedido_id": "p1", "canal": "sitio-mx", "estado": "entregado",
                       "fecha": "2026-10-01T00:00:00Z", "venta_bruta": 14500,
                       "cliente_id": "mx-1"}]}
    c = cli.cliente(row, pedidos, _fuentes(), NOW)
    assert (c.pedidos.valor, c.total.valor, c.total.fuente) == (1, 14500, "Pedidos")
    assert c.origen.texto == "Sitio MX"


def test_summary_without_sources_is_missing(datos):
    per = m.periodo("30", NOW)
    datos_ = cli.resumen([], [], _fuentes(), per, NOW)
    by = {d.etiqueta: d for d in datos_}
    assert by["Clientes EUA con compra"].calidad == "faltante"
    assert by["Compraron en el periodo"].calidad == "faltante"
    assert by["Clientes Etsy"].calidad == "faltante"
    assert "no conectada" in by["Clientes Etsy"].nota
    assert by["Clientes México"].valor == 0 and by["Clientes México"].calidad == "real"


def test_summary_with_demo(datos):
    by = {d.etiqueta: d for d in cli.resumen(datos.clientes, datos.pedidos_rows,
                                              datos.fuentes, m.periodo("30", NOW), NOW)}
    assert by["Clientes EUA con compra"].valor == 3
    assert by["Compraron en el periodo"].valor == 3
    assert "1 pedido(s) sin cliente" in by["Compraron en el periodo"].nota
    assert by["Compraron otra vez"].valor == 2
    assert by["Seguimientos pendientes"].valor == 2


def test_screen_and_alert(datos):
    html = render("/clientes", {}, datos)
    assert "Ana E." in html and "Daniela R." in html and "MX$14,500.00" in html
    assert "Fuente no conectada" in html and "¿De dónde sale?" in html
    assert "@" not in html.split("</style>")[1]
    seg = render("/clientes", {"f": "seguimiento"}, datos)
    assert "Ben J." in seg and "Cleo K." not in seg
    mx = render("/clientes", {"f": "mx", "p": "nope"}, datos)
    assert "Daniela R." in mx and "Ana E." not in mx
    titulos = [a.titulo for a in resumen_dia(datos).alertas]
    assert "Seguimiento vencido: Ben J." in titulos


def test_screen_opens_on_a_sheet_without_clients(tmp_path):
    d = Datos(LocalWorkbook(tmp_path / "vacío"), JsonStore(tmp_path / "a.json"), NOW)
    html = render("/clientes", {}, d)
    assert "Nadie en este filtro" in html and "aún sin sincronizar" in html.lower()
