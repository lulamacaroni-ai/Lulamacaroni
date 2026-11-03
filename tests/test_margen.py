from datetime import datetime, timedelta, timezone

from lulamacaroni.app import metrics as m
from lulamacaroni.app.demo import fill_demo
from lulamacaroni.app.screens import Datos, render
from lulamacaroni.approval import JsonStore
from lulamacaroni.connectors.shopify import (
    ShopifyError, order_fee, order_to_rows, payout_to_row, payouts_denied, split_fee,
)
from lulamacaroni.localbook import LocalWorkbook
from lulamacaroni.margen import calcular, faltan, recalcular
from lulamacaroni.schema import validate_row

NOW = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)


def _tx(kind="CAPTURE", gateway="shopify_payments", fee="2.50", status="SUCCESS"):
    return {"kind": kind, "status": status, "gateway": gateway,
            "fees": [{"amount": {"amount": fee}, "type": "processing_fee"}] if fee else []}


# --- Shopify Payments fees -----------------------------------------------------------

def test_fee_sums_successful_transactions_and_keeps_it_after_refund():
    order = {"transactions": [_tx("AUTHORIZATION", fee=None), _tx(fee="2.50"),
                              _tx("REFUND", fee=None), _tx(status="FAILURE", fee="9")]}
    assert order_fee(order) == 2.5


def test_fee_unknown_for_other_gateways_and_zero_when_unpaid():
    assert order_fee({"transactions": [_tx("SALE", gateway="paypal", fee=None)]}) is None
    assert order_fee({"transactions": []}) == 0.0
    assert order_fee({"transactions": [_tx("SALE", gateway="gift_card", fee=None)]}) == 0.0


def test_fee_split_by_sale_share_adds_up_to_the_cent():
    parts = split_fee(10.0, [90, 240, 20])
    assert sum(parts) == 10.0 and parts[1] > parts[0] > parts[2]
    assert split_fee(None, [1, 2]) == ["", ""]


def _line(n, gross):
    return {"id": f"gid://shopify/LineItem/{n}", "sku": f"S{n}", "quantity": 1, "name": "x",
            "originalTotalSet": {"shopMoney": {"amount": str(gross)}},
            "totalDiscountSet": {"shopMoney": {"amount": "0"}}, "taxLines": []}


def test_order_rows_carry_real_fee():
    order = {"legacyResourceId": "500", "name": "#1001", "createdAt": "2026-11-14T10:00:00Z",
             "test": False, "currencyCode": "USD", "displayFinancialStatus": "PAID",
             "lineItems": {"nodes": [_line(1, 90), _line(2, 240), _line(3, 20)]},
             "transactions": [_tx(fee="10.00")]}
    rows = order_to_rows(order)
    assert round(sum(r["comision_canal"] for r in rows), 2) == 10.0
    for r in rows:
        assert validate_row("Pedidos", r) == []


# --- payouts -------------------------------------------------------------------------

PAYOUT = {
    "legacyResourceId": "77", "issuedAt": "2026-11-20T00:00:00Z", "status": "IN_TRANSIT",
    "transactionType": "DEPOSIT", "net": {"amount": "180.40", "currencyCode": "USD"},
    "summary": {"chargesFee": {"amount": "6.10"}, "refundsFee": {"amount": "0.00"},
                "adjustmentsFee": {"amount": "0"}, "reservedFundsFee": {"amount": "0"},
                "retriedPayoutsFee": {"amount": "0"}, "refundsFeeGross": {"amount": "-20.00"},
                "reservedFundsGross": {"amount": "0"}},
}


def test_payout_row_is_valid_and_kept_apart_from_sales():
    row = payout_to_row(PAYOUT)
    assert row["pago_id"] == "shopify-payout-77" and row["estado"] == "en-transito"
    assert row["monto_depositado"] == 180.4 and row["comisiones"] == 6.1
    assert row["reembolsos"] == 20.0
    assert validate_row("Pagos", row) == []
    assert payout_to_row({**PAYOUT, "transactionType": "WITHDRAWAL"})["monto_depositado"] == -180.4


def test_payout_scope_missing_is_detected():
    err = ShopifyError("x", {"errors": [{"extensions": {"code": "ACCESS_DENIED"},
                                         "path": ["shopifyPaymentsAccount"]}]})
    assert payouts_denied(err)


# --- margin ----------------------------------------------------------------------------

LINE = {"linea_pedido_id": "shopify-1-1", "linea": "US-POD", "venta_bruta": 100,
        "descuento": 10, "reembolso": 0, "envio_cobrado": 8, "comision_canal": 3.2,
        "costo_pod": 35, "envio_pod": 7.5, "pod_pedido_id": "ord_1"}


def test_margin_real_estimated_and_missing():
    assert calcular(LINE) == {"margen_contribucion": 52.3, "calidad_dato": "real"}
    assert calcular({**LINE, "pod_pedido_id": ""})["calidad_dato"] == "estimado"
    missing = calcular({**LINE, "costo_pod": ""})
    assert missing == {"margen_contribucion": "", "calidad_dato": "faltante"}
    assert faltan({**LINE, "comision_canal": "", "envio_pod": None}) == ["comision_canal", "envio_pod"]
    # a real zero cost is a cost, not a missing one
    assert calcular({**LINE, "envio_pod": 0})["margen_contribucion"] == 59.8


def test_recalcular_updates_workbook(tmp_path):
    b = LocalWorkbook(tmp_path)
    b.upsert("Pedidos", [{**LINE, "costo_pod": ""}])
    assert recalcular(b) == 1 and b.read("Pedidos")[0]["calidad_dato"] == "faltante"
    b.upsert("Pedidos", [{"linea_pedido_id": "shopify-1-1", "linea": "US-POD", "costo_pod": 35}])
    assert recalcular(b) == 1
    assert b.read("Pedidos")[0]["margen_contribucion"] == 52.3
    assert recalcular(b) == 0


# --- screens ------------------------------------------------------------------------------

def _datos(tmp_path):
    b = LocalWorkbook(tmp_path / "libro")
    fill_demo(b, NOW)
    return Datos(b, JsonStore(tmp_path / "a.json"), NOW)


def test_margin_before_ads_is_missing_while_any_line_lacks_cost(tmp_path):
    d = _datos(tmp_path)
    res = m.resumen(d.pedidos_rows, [], d.fuentes, m.periodo("7", NOW), d.pagos)
    antes = next(x for x in res.datos if x.etiqueta == "Margen antes de anuncios")
    # orders 1001 and 1003 have no Prodigi charge yet
    assert antes.calidad == "faltante" and "coste de impresión" in antes.nota
    assert next(x for x in res.datos if x.etiqueta == "Margen de contribución").valor is None


def test_margin_before_ads_real_when_all_costs_known(tmp_path):
    d = _datos(tmp_path)
    rows = [r for r in d.pedidos_rows if r["calidad_dato"] == "real"]
    res = m.resumen(rows, [], d.fuentes, m.periodo("30", NOW), d.pagos)
    antes = next(x for x in res.datos if x.etiqueta == "Margen antes de anuncios")
    assert antes.calidad == "real"
    assert antes.valor == round(sum(r["margen_contribucion"] for r in rows), 2)


def test_por_recibir_from_payouts_or_missing_without_scope(tmp_path):
    d = _datos(tmp_path)
    assert m.por_recibir(d.pagos, d.fuentes).valor == 77.38
    sin = m.estado_fuentes([{"fuente": "shopify-pagos", "estado": "sin-conectar",
                             "ultima_actualizacion": NOW.isoformat()}], NOW)
    falta = m.por_recibir([], sin)
    assert falta.calidad == "faltante" and "permisos" in falta.nota


def test_pedidos_screen_shows_margin_or_what_is_missing(tmp_path):
    d = _datos(tmp_path)
    html = render("/pedidos", {}, d)
    assert "margen US$" in html and "falta coste de impresión" in html
    p1002 = next(p for p in d.pedidos if p.numero == "1002")
    assert p1002.calidad_margen == "real" and p1002.margen is not None
