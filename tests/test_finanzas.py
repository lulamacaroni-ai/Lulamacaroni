from datetime import datetime, timedelta, timezone

import pytest

from lulamacaroni.app import finanzas as fin
from lulamacaroni.app import semanal as sem
from lulamacaroni.app.demo import fill_demo
from lulamacaroni.app.screens import Datos, render
from lulamacaroni.approval import JsonStore
from lulamacaroni.localbook import LocalWorkbook

NOW = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)  # Monday, 14:00 CDMX


@pytest.fixture
def store(tmp_path):
    return JsonStore(tmp_path / "aprobaciones.json")


@pytest.fixture
def demo(tmp_path, store):
    b = LocalWorkbook(tmp_path / "libro")
    fill_demo(b, NOW)
    return b


def _iso(dt):
    return dt.replace(microsecond=0).isoformat()


def _fuentes(*claves):
    return [{"fuente": k, "ultima_actualizacion": _iso(NOW - timedelta(minutes=5)),
             "estado": "ok", "filas": 1} for k in claves]


def _linea(n, dias, precio=100.0, **over):
    r = {"linea_pedido_id": f"shopify-{n}-1", "pedido_id": f"shopify-{n}", "linea": "US-POD",
         "canal": "shopify", "fecha": _iso(NOW - timedelta(days=dias)), "moneda": "USD",
         "venta_bruta": precio, "descuento": 0, "impuesto_cobrado": 7.25, "envio_cobrado": 5,
         "reembolso": 0, "estado": "enviado", "comision_canal": 3.2, "costo_pod": 30,
         "envio_pod": 8, "pod_pedido_id": f"ord_{n}", "producto": f"Obra {n}"}
    r.update(over)
    return r


def _book(tmp_path, pedidos=(), pagos=(), fuentes=("shopify", "shopify-pagos"), extra=None):
    from lulamacaroni.margen import recalcular

    b = LocalWorkbook(tmp_path / "libro")
    b.upsert("Fuentes", _fuentes(*fuentes))
    if pedidos:
        b.upsert("Pedidos", list(pedidos))
        recalcular(b)
    if pagos:
        b.upsert("Pagos", list(pagos))
    for tab, rows in (extra or {}).items():
        b.upsert(tab, rows)
    return b


def _by(datos):
    return {d.etiqueta: d for d in datos}


def test_periods_are_calendar_months_in_cdmx():
    p = fin.periodo("mes", NOW)
    assert (p.inicio.day, p.inicio.month) == (1, 11)
    assert (p.previo_inicio.day, p.previo_inicio.month) == (1, 10)
    assert p.previo_fin - p.previo_inicio == p.fin - p.inicio
    a = fin.periodo("mes-ant", NOW)
    assert (a.inicio.month, a.fin.month, a.fin.day) == (10, 11, 1)
    assert "31 oct" in a.texto
    assert fin.periodo("raro", NOW).clave == "30"


def test_gross_sale_and_tax_are_separate_and_deposit_is_not_sales(tmp_path, store):
    b = _book(tmp_path, [_linea(1, 1), _linea(2, 1, descuento=10)], pagos=[
        {"pago_id": "p1", "linea": "US-POD", "canal": "shopify", "fecha": _iso(NOW - timedelta(hours=30)),
         "monto_depositado": 180.0, "comisiones": 6.4, "retenciones": 0, "estado": "pagado"}])
    f = fin.calcular(Datos(b, store, NOW), "7")
    v = _by(f.venta)
    assert v["Venta bruta"].valor == 200 and v["Descuentos"].valor == 10
    assert v["Ventas netas"].valor == 190
    assert v["Impuestos cobrados"].valor == 14.5          # shown, never inside sales
    assert v["Envío cobrado"].valor == 10
    dep = _by(f.depositos)
    assert dep["Depositado"].valor == 180 and dep["Depositado"].calidad == "real"
    assert v["Ventas netas"].valor != v["Ventas netas"].valor + dep["Depositado"].valor
    mg = _by(f.margen)
    # 190 + 10 shipping − 6.4 fees − 60 print − 16 print shipping
    assert mg["Margen antes de anuncios"].valor == pytest.approx(117.6)
    assert mg["Margen antes de anuncios"].calidad == "real"
    assert mg["Margen por pedido"].valor == pytest.approx(58.8)
    assert mg["Margen sobre ventas"].formato == "pct"


def test_missing_print_cost_is_missing_not_zero(tmp_path, store):
    b = _book(tmp_path, [_linea(1, 1), _linea(2, 1, costo_pod="", envio_pod="",
                                             pod_pedido_id="")])
    f = fin.calcular(Datos(b, store, NOW), "7")
    c = _by(f.costos)
    assert c["Impresión (Prodigi)"].calidad == "faltante"
    assert c["Impresión (Prodigi)"].valor is None
    assert "1 de 2" in c["Impresión (Prodigi)"].nota
    assert c["Comisiones del canal"].valor == 6.4
    assert _by(f.margen)["Margen antes de anuncios"].calidad == "faltante"


def test_price_list_cost_is_estimated(tmp_path, store):
    b = _book(tmp_path, [_linea(1, 1, pod_pedido_id="")])
    c = _by(fin.calcular(Datos(b, store, NOW), "7").costos)
    assert c["Impresión (Prodigi)"].calidad == "estimado"


def test_no_orders_is_a_real_zero(tmp_path, store):
    f = fin.calcular(Datos(_book(tmp_path), store, NOW), "mes")
    assert _by(f.venta)["Ventas netas"].es_cero
    assert _by(f.costos)["Impresión (Prodigi)"].es_cero
    assert _by(f.depositos)["Depositado"].es_cero


def test_unconnected_sources_are_never_zero(tmp_path, store):
    f = fin.calcular(Datos(_book(tmp_path, fuentes=()), store, NOW), "mes")
    for d in f.venta + f.costos + f.depositos + f.contabilidad + f.plataformas:
        assert d.valor is None and d.calidad == "faltante", d.etiqueta
    nombres = {d.etiqueta for d in f.contabilidad}
    assert {"Gastos del mes", "Beneficio del negocio", "Flujo de efectivo"} <= nombres
    assert all("no conectada" in d.nota.lower() for d in f.contabilidad)
    etsy = next(c for c in f.canales if c.nombre == "Etsy")
    assert etsy.ventas.calidad == "faltante" and "no conectada" in etsy.ventas.nota


def test_quickbooks_and_etsy_slots_say_not_connected_even_with_shopify(tmp_path, store):
    f = fin.calcular(Datos(_book(tmp_path, [_linea(1, 1)]), store, NOW), "7")
    dep = _by(f.depositos)
    assert dep["Depósitos de Etsy"].calidad == "faltante"
    assert "Fuente no conectada" in dep["Depósitos de Etsy"].nota
    plat = _by(f.plataformas)
    assert set(plat) == {"Según Meta Ads", "Según Pinterest Ads", "Según Etsy Ads"}
    assert all(d.calidad == "faltante" for d in plat.values())


def test_mexico_originals_never_mix_with_dollars(tmp_path, store):
    mx = {"linea_pedido_id": "mx-1-1", "pedido_id": "mx-1", "linea": "MX-original",
          "canal": "whatsapp", "fecha": _iso(NOW - timedelta(days=2)), "moneda": "MXN",
          "venta_bruta": 14500, "descuento": 0, "reembolso": 0, "estado": "entregado"}
    b = _book(tmp_path, [_linea(1, 1), mx])
    f = fin.calcular(Datos(b, store, NOW), "7")
    assert _by(f.venta)["Ventas netas"].valor == 100           # USD only
    fila = next(c for c in f.canales if c.nombre == "Originales México")
    assert fila.ventas.valor == 14500 and fila.ventas.formato == "mxn"
    assert fila.margen.calidad == "faltante"
    shop = next(c for c in f.canales if c.nombre == "Shopify")
    assert shop.ventas.valor == 100


def test_mexico_without_records_is_missing(tmp_path, store):
    f = fin.calcular(Datos(_book(tmp_path, [_linea(1, 1)]), store, NOW), "7")
    fila = next(c for c in f.canales if c.nombre == "Originales México")
    assert fila.ventas.calidad == "faltante"


def test_payout_scope_missing_shows_missing(tmp_path, store):
    f = fin.calcular(Datos(_book(tmp_path, [_linea(1, 1)], fuentes=("shopify",)), store, NOW))
    dep = _by(f.depositos)
    assert dep["Depositado"].calidad == "faltante"
    assert dep["Por recibir"].calidad == "faltante"


def test_finanzas_and_semana_screens_render(demo, store):
    d = Datos(demo, store, NOW)
    for clave in ("mes", "mes-ant", "7", "30", "nada"):
        html = render("/finanzas", {"p": clave}, d)
        assert "Finanzas" in html and "¿De dónde sale?" in html
        assert "nunca se suman" in html
    html = render("/finanzas", {}, d)
    assert "Fuente no conectada" in html and "QuickBooks" in html
    assert "Originales México" in html and "Según Meta Ads" in html
    for s in ("pasada", "actual"):
        html = render("/semana", {"s": s}, d)
        assert "Tu semana" in html and "Prioridades para la semana" in html
    assert 'href="/finanzas"' in html and 'href="/semana"' in html


def test_week_is_monday_to_sunday_cdmx():
    p = sem.periodo("pasada", NOW)
    assert p.inicio.weekday() == 0 and (p.fin - p.inicio).days == 7
    assert (p.inicio.day, p.inicio.month) == (26, 10)
    a = sem.periodo("actual", NOW)
    assert a.inicio.day == 2 and a.fin == NOW.astimezone(a.fin.tzinfo)


def test_weekly_summary_results_and_volume_rule(tmp_path, store):
    b = _book(tmp_path, [_linea(i, 3 + i * 0.1) for i in range(1, 4)])
    r = sem.calcular(Datos(b, store, NOW), "pasada")
    by = _by(r.resultados)
    assert by["Ventas netas"].valor == 300 and by["Pedidos"].valor == 3
    assert "semana pasada" in by["Ventas netas"].periodo.lower()
    assert by["Gasto publicitario"].calidad == "faltante"
    assert "no hay volumen" in r.hipotesis[0]
    assert any(x.titulo == "Lo más vendido" for x in r.destacados)
    assert "Resumen semanal" in sem.texto(r)


def test_weekly_hypotheses_need_volume_and_say_correlation(tmp_path, store):
    lineas = [_linea(i, 3 + i * 0.1, origen_estado="ok", origen_fuente="instagram",
                     utm_fuente="instagram", utm_medio="paid_social") for i in range(1, 7)]
    r = sem.calcular(Datos(_book(tmp_path, lineas), store, NOW), "pasada")
    assert any("correlación" in h for h in r.hipotesis)


def test_weekly_tests_and_decisions(tmp_path, store):
    dec = [{"decision_id": "d1", "fecha": _iso(NOW - timedelta(days=4)),
            "decision": "Subir precio del 18x24", "razon": "margen bajo", "responsable": "Lore",
            "resultado": ""},
           {"decision_id": "d2", "fecha": _iso(NOW - timedelta(days=30)),
            "decision": "Probar pins de Harbor", "razon": "tráfico", "responsable": "Lore",
            "resultado": ""},
           {"decision_id": "d3", "fecha": _iso(NOW - timedelta(days=30)),
            "decision": "Prueba cerrada", "resultado": "sin efecto"}]
    r = sem.calcular(Datos(_book(tmp_path, extra={"Decisiones": dec}), store, NOW), "pasada")
    assert [x.decision for x in r.decididas] == ["Subir precio del 18x24"]
    assert [x.decision for x in r.abiertas] == ["Probar pins de Harbor"]
    html = sem.render(r, NOW)
    assert "Pruebas abiertas" in html and "Subir precio" in html
