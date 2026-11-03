from datetime import datetime, timedelta, timezone

import pytest

from lulamacaroni.app import alertas as al
from lulamacaroni.app import metrics as m
from lulamacaroni.app.demo import fill_demo
from lulamacaroni.app.screens import Datos, render
from lulamacaroni.approval import JsonStore, request_approval
from lulamacaroni.localbook import LocalWorkbook

NOW = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path):
    return JsonStore(tmp_path / "aprobaciones.json")


def _book(tmp_path, listados=(), pedidos=(), fuentes=None):
    b = LocalWorkbook(tmp_path / "libro")
    if fuentes is None:
        fuentes = [{"fuente": "shopify", "ultima_actualizacion": (NOW - timedelta(minutes=5)).isoformat(),
                    "estado": "ok", "filas": 1}]
    b.upsert("Fuentes", fuentes)
    if listados:
        b.upsert("Listados", list(listados))
    if pedidos:
        b.upsert("Pedidos", list(pedidos))
    return b


def _lst(ref, pid, title, ruta, sku="S", estado="publicado"):
    return {"listado_ref": ref, "sku": sku, "linea": "US-POD", "canal": "shopify",
            "id_producto_canal": pid, "titulo_en_canal": f"{title} / 8x10", "estado": estado,
            "precio": 50, "ruta_pod": ruta}


def _titles(alerts, nivel=None):
    return [a.titulo for a in alerts if nivel is None or a.nivel == nivel]


def test_known_store_problems_are_urgent(tmp_path, store):
    b = _book(tmp_path, listados=[
        _lst("1", "p1", "Garden", "prodigi-app"),
        _lst("2", "p2", "Harbor", "manual", sku=""),
        _lst("3", "p2", "Harbor", "manual", sku=""),
        _lst("4", "p3", "Owl", "prodigi-app"),
        _lst("5", "p3", "Owl", "frame-it-easy-app"),
        _lst("6", "p4", "Moon", "varias"),
        _lst("7", "p5", "Hidden dup", "manual", estado="pausado"),
    ])
    rd = al.resumen_dia(Datos(b, store, NOW))
    urg = [a for a in rd.alertas if a.nivel == al.URGENTE]
    dobles = next(a for a in urg if "dos imprentas" in a.titulo)
    assert sorted(dobles.items) == ["Moon", "Owl"]
    manual = next(a for a in urg if "ninguna imprenta" in a.titulo)
    assert manual.items == ["Harbor"]           # the hidden duplicate is not for sale
    assert "Shopify" in manual.fuente and manual.actualizado is not None
    assert any("sin SKU" in t for t in _titles(rd.alertas, al.ATENCION))
    # urgent store fixes lead the three actions
    assert rd.acciones[0].prioridad == 5 and len(rd.acciones) == 3


def test_no_real_orders_is_flagged_only_when_shopify_is_connected(tmp_path, store):
    rd = al.resumen_dia(Datos(_book(tmp_path), store, NOW))
    assert "Aún no hay pedidos reales" in _titles(rd.alertas)
    rd = al.resumen_dia(Datos(_book(tmp_path / "x", fuentes=[]), store, NOW))
    assert "Aún no hay pedidos reales" not in _titles(rd.alertas)


def test_cancelled_orders_do_not_count_as_real(tmp_path, store):
    row = {"linea_pedido_id": "shopify-1-1", "pedido_id": "shopify-1", "linea": "US-POD",
           "canal": "shopify", "fecha": NOW.isoformat(), "estado": "cancelado"}
    rd = al.resumen_dia(Datos(_book(tmp_path, pedidos=[row]), store, NOW))
    assert "Aún no hay pedidos reales" in _titles(rd.alertas)


def test_etsy_and_accounting_slots_are_missing_never_zero(tmp_path, store):
    rd = al.resumen_dia(Datos(_book(tmp_path), store, NOW))
    by = {d.etiqueta: d for d in rd.ranuras}
    assert by["Ventas Shopify"].calidad == "real" and by["Ventas Shopify"].es_cero
    for label in ("Ventas Etsy", "Gastos del mes"):
        assert by[label].calidad == "faltante" and by[label].valor is None
        assert "Fuente no conectada" in by[label].nota
    info = _titles(rd.alertas, al.INFO)
    assert "Etsy: fuente no conectada" in info and "QuickBooks: fuente no conectada" in info
    assert all(a.nivel != al.INFO for a in rd.acciones)


def test_slots_plug_in_once_the_source_is_stamped(tmp_path, store):
    fuentes = [{"fuente": k, "ultima_actualizacion": NOW.isoformat(), "estado": "ok"}
               for k in ("shopify", "etsy", "quickbooks")]
    pedido = {"linea_pedido_id": "etsy-9-1", "pedido_id": "etsy-9", "linea": "US-POD",
              "canal": "etsy", "fecha": (NOW - timedelta(hours=1)).isoformat(),
              "estado": "recibido", "venta_bruta": 70}
    b = _book(tmp_path, pedidos=[pedido], fuentes=fuentes)
    b.upsert("Gastos", [{"gasto_id": "g1", "linea": "compartido", "fecha": NOW.isoformat(),
                         "monto": 12.5}])
    by = {d.etiqueta: d for d in al.resumen_dia(Datos(b, store, NOW)).ranuras}
    assert by["Ventas Etsy"].valor == 70 and by["Ventas Etsy"].calidad == "real"
    assert by["Gastos del mes"].valor == 12.5


def test_pending_approval_and_order_without_printer_are_actions(tmp_path, store):
    b = LocalWorkbook(tmp_path / "libro")
    fill_demo(b, NOW)
    request_approval(store, tipo="precio", linea="US-POD", resumen="x", contenido={"a": 1},
                     creado_por="test")
    rd = al.resumen_dia(Datos(b, store, NOW))
    textos = [a.accion for a in rd.acciones]
    assert any("#1003" in t for t in textos)
    assert any("pendiente" in a.accion for a in rd.alertas)


def test_stale_and_failed_sources_alert(tmp_path, store):
    old = (NOW - timedelta(hours=40)).isoformat()
    b = _book(tmp_path, fuentes=[
        {"fuente": "shopify", "ultima_actualizacion": old, "estado": "ok"},
        {"fuente": "shopify-pagos", "ultima_actualizacion": NOW.isoformat(), "estado": "error",
         "nota": "boom"},
        {"fuente": "prodigi-sandbox", "ultima_actualizacion": NOW.isoformat(), "estado": "ok",
         "nota": "2 pedido(s) Prodigi sin pedido de canal"}])
    t = _titles(al.resumen_dia(Datos(b, store, NOW)).alertas)
    assert "Shopify: datos atrasados" in t
    assert any("falló" in x for x in t)
    assert "Pedidos de Prodigi que no se ligan a una venta" in t


def test_alerts_page_and_home_show_source_and_escape(tmp_path, store):
    b = _book(tmp_path, listados=[_lst("1", "p1", "<b>x</b>", "manual")])
    d = Datos(b, store, NOW)
    html = render("/alertas", {}, d)
    assert "Fuente: Shopify" in html and "&lt;b&gt;" in html and "<b>x</b>" not in html
    assert "Fuentes aún no conectadas" in html
    home = render("/", {}, d)
    assert "Qué requiere tu atención" in home and "Hoy por canal y contabilidad" in home
    assert "Ventas Etsy" in home and "falta el dato" in home


def test_plain_text_summary(tmp_path, store):
    d = Datos(_book(tmp_path, listados=[_lst("1", "p1", "Owl", "manual")]), store, NOW)
    out = al.texto(al.resumen_dia(d), NOW)
    assert "Tus 3 acciones de hoy:" in out and "Ventas Etsy: —" in out
    assert "ninguna imprenta" in out
