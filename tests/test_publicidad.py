from datetime import datetime, timedelta, timezone

import pytest

from lulamacaroni.app import metrics as m
from lulamacaroni.app import publicidad as pub
from lulamacaroni.app.alertas import resumen_dia
from lulamacaroni.app.demo import fill_demo, seed_publicidad
from lulamacaroni.app.screens import Datos, render
from lulamacaroni.approval import JsonStore
from lulamacaroni.approval.gate import decide
from lulamacaroni.localbook import LocalWorkbook

NOW = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)


@pytest.fixture
def book(tmp_path):
    b = LocalWorkbook(tmp_path / "libro")
    fill_demo(b, NOW)
    return b


@pytest.fixture
def store(tmp_path):
    return JsonStore(tmp_path / "aprobaciones.json")


def _fuentes():
    return {k: m.EstadoFuente(m.FUENTE_BY_KEY[k], "sin-conectar", None) for k in m.FUENTE_BY_KEY}


def _row(**over):
    r = {"campana_id": "c1", "linea": "US-POD", "plataforma": "meta", "nombre": "Prueba",
         "destino": "shopify", "utm_campana": "prueba", "texto": "Ad copy",
         "archivo": "a.tif", "presupuesto_diario_usd": "10", "presupuesto_total_usd": "",
         "inicio": "2026-11-10", "fin": "2026-11-19", "estado": "borrador"}
    r.update(over)
    return r


TOPE = {"plataforma": "meta", "linea": "US-POD", "tope_diario_usd": 15,
        "tope_mensual_usd": 300, "cambio_max_pct": 20}


# --- what gets approved ---------------------------------------------------------------------

def test_approved_plan_ignores_number_formatting_but_not_content():
    a = pub.campana_aprobable(_row(presupuesto_diario_usd=10))
    assert a == pub.campana_aprobable(_row(presupuesto_diario_usd="10.0"))
    assert a != pub.campana_aprobable(_row(presupuesto_diario_usd="11"))
    assert a != pub.campana_aprobable(_row(texto="Other copy"))


def test_gate_states(tmp_path, store):
    b = LocalWorkbook(tmp_path / "l")
    b.upsert("Topes", [TOPE])
    b.upsert("Publicidad", [_row()])
    # running without approval is an alert
    g = pub.gate(_row(estado="activa"), {}, NOW)
    assert g.estado == "sin-aprobacion" and g.alerta
    assert pub.gate(_row(estado="por-aprobar"), {}, NOW).estado == "sin-solicitud"
    rec = pub.solicitar(b, store, "c1", now=NOW)
    assert rec.tipo == "anuncio" and rec.monto_usd == "100.00"
    row = b.read("Publicidad")[0]
    assert row["estado"] == "por-aprobar" and row["aprobacion_id"] == rec.aprobacion_id
    by_id = {a.aprobacion_id: a for a in store.all()}
    assert pub.gate(row, by_id, NOW).estado == "pendiente"
    decide(store, rec.aprobacion_id, aprobar=True, decidido_por="Lore", now=NOW)
    by_id = {a.aprobacion_id: a for a in store.all()}
    assert pub.gate({**row, "estado": "activa"}, by_id, NOW).estado == "ok"
    # any edit after approval (here the budget) needs a new approval
    g = pub.gate({**row, "estado": "activa", "presupuesto_diario_usd": "12"}, by_id, NOW)
    assert g.estado == "cambio" and g.alerta
    with pytest.raises(ValueError, match="Ya tiene una aprobación ok"):
        pub.solicitar(b, store, "c1", now=NOW)


def test_request_refuses_without_limits_or_over_them(tmp_path, store):
    b = LocalWorkbook(tmp_path / "l")
    b.upsert("Publicidad", [_row()])
    with pytest.raises(ValueError, match="No hay tope"):
        pub.solicitar(b, store, "c1", now=NOW)
    b.upsert("Topes", [TOPE])
    b.upsert("Publicidad", [_row(presupuesto_diario_usd="20")])
    with pytest.raises(ValueError, match="tope diario"):
        pub.solicitar(b, store, "c1", now=NOW)
    # monthly: an approved, running campaign already uses most of the month
    b.upsert("Publicidad", [_row(presupuesto_diario_usd="10", fin=""),
                            _row(campana_id="c0", estado="borrador", inicio="2026-11-01",
                                 fin="2026-11-30", presupuesto_diario_usd="9")])
    rec0 = pub.solicitar(b, store, "c0", now=NOW)
    decide(store, rec0.aprobacion_id, aprobar=True, decidido_por="Lore", now=NOW)
    b.upsert("Publicidad", [{"campana_id": "c0", "linea": "US-POD", "estado": "activa"}])
    with pytest.raises(ValueError, match="tope mensual"):
        pub.solicitar(b, store, "c1", now=NOW)   # 270 + 10 × 21 days > 300
    assert not store.get(rec0.aprobacion_id).ejecutado_en


def test_budget_change_on_running_campaign_is_a_presupuesto_approval_within_max_change(tmp_path, store):
    b = LocalWorkbook(tmp_path / "l")
    b.upsert("Topes", [TOPE])
    b.upsert("Publicidad", [_row()])
    rec = pub.solicitar(b, store, "c1", now=NOW)
    decide(store, rec.aprobacion_id, aprobar=True, decidido_por="Lore", now=NOW)
    b.upsert("Publicidad", [{"campana_id": "c1", "linea": "US-POD", "estado": "activa",
                             "presupuesto_diario_usd": "13"}])
    with pytest.raises(ValueError, match="cambio máximo es 20%"):
        pub.solicitar(b, store, "c1", now=NOW)
    b.upsert("Publicidad", [{"campana_id": "c1", "linea": "US-POD", "presupuesto_diario_usd": "12"}])
    rec2 = pub.solicitar(b, store, "c1", now=NOW)
    assert rec2.tipo == "presupuesto" and b.read("Publicidad")[0]["estado"] == "activa"


# --- limits and plan ------------------------------------------------------------------------

def test_plan_for_the_month_uses_dates_and_total():
    assert pub.plan_mes(_row(), NOW) == 100.0                       # 10 days × 10
    assert pub.plan_mes(_row(presupuesto_total_usd="60"), NOW) == 60.0
    assert pub.plan_mes(_row(fin="2026-12-20"), NOW) == 210.0       # Nov 10 to Nov 30
    assert pub.plan_mes(_row(inicio="2026-10-01", fin=""), NOW) == 300.0
    assert pub.plan_mes(_row(presupuesto_diario_usd=""), NOW) is None


def test_campaigns_flag_missing_limits_daily_limit_and_missing_utm():
    cs = pub.campanas([_row(estado="por-aprobar", utm_campana="")], [], [], [], [], [],
                      _fuentes(), NOW)
    assert any("No hay tope" in a for a in cs[0].avisos)
    assert any("utm_campana" in a for a in cs[0].avisos)
    cs = pub.campanas([_row(estado="por-aprobar", presupuesto_diario_usd="20")], [], [], [TOPE],
                      [], [], _fuentes(), NOW)
    assert cs[0].excede and cs[0].alerta
    # ideas and drafts are not checked against limits yet
    assert pub.campanas([_row(presupuesto_diario_usd="99")], [], [], [TOPE], [], [],
                        _fuentes(), NOW)[0].avisos == []


def test_platform_results_are_missing_until_the_source_is_connected():
    c = pub.campanas([_row()], [], [], [], [], [], _fuentes(), NOW)[0]
    assert all(d.calidad == "faltante" and "Fuente no conectada" in d.nota
               for d in c.plataforma_datos)
    assert c.shopify.calidad == "faltante"     # Shopify not connected either
    etsy = pub.campanas([_row(destino="etsy")], [], [], [], [], [], _fuentes(), NOW)[0]
    assert "Etsy no comparte" in etsy.shopify.nota


# --- attribution ----------------------------------------------------------------------------

def _o(pid, **origin):
    return {"pedido_id": pid, "linea_pedido_id": pid + "-1", "canal": "shopify",
            "estado": "recibido", "fecha": "2026-11-01T12:00:00Z", "venta_bruta": 100,
            "origen_estado": "ok", **origin}


@pytest.mark.parametrize("origin,expected", [
    ({"utm_fuente": "instagram", "utm_medio": "paid_social"}, ("meta", True)),
    ({"utm_fuente": "facebook", "utm_medio": "cpc"}, ("meta", True)),
    ({"referente": "l.instagram.com"}, ("meta", False)),
    ({"referente": "pinterest.com"}, ("pinterest", False)),
    ({"referente": "pin.it"}, ("pinterest", False)),
    ({"origen_fuente": "google", "origen_tipo": "ad"}, ("google", True)),
    ({"utm_fuente": "klaviyo", "utm_medio": "email"}, ("correo", False)),
    ({"origen_fuente": "direct"}, ("directo", False)),
    ({"referente": "someblog.com"}, ("otro", False)),
    ({"origen_estado": "sin-recorrido"}, ("sin-dato", None)),
    ({"origen_estado": ""}, ("sin-dato", None)),
])
def test_origin_classification(origin, expected):
    assert pub.origen(_o("x", **origin)) == expected


def test_attribution_counts_each_order_once_and_keeps_unknowns_apart():
    rows = [_o("a", utm_fuente="instagram", utm_medio="paid_social"),
            {**_o("a", utm_fuente="instagram", utm_medio="paid_social"), "linea_pedido_id": "a-2"},
            _o("b", referente="pinterest.com"),
            _o("c", origen_estado="pendiente"),
            {**_o("d"), "estado": "cancelado"}]
    filas = {f.clave: f for f in pub.atribucion(rows, m.periodo("30", NOW))}
    assert filas["meta"].pedidos == 1 and filas["meta"].pedidos_anuncio == 1
    assert filas["meta"].ventas == 200
    assert filas["pinterest"].pedidos_organico == 1
    assert filas["sin-dato"].pedidos_sin_saber == 1
    assert sum(f.pedidos for f in filas.values()) == 3


def test_break_even_roas():
    shop = m.EstadoFuente(m.FUENTE_BY_KEY["shopify"], "ok", NOW)
    per = m.periodo("30", NOW)
    rows = [{**_o("a"), "calidad_dato": "real", "margen_contribucion": 40}]
    d = pub.roas_equilibrio(rows, per, shop)
    assert d.valor == 2.5 and d.calidad == "estimado"
    assert pub.roas_equilibrio([_o("a")], per, shop).calidad == "faltante"
    assert pub.roas_equilibrio([], per, shop).calidad == "faltante"


# --- screen and daily summary ---------------------------------------------------------------

def test_publicidad_screen_on_demo_data(book, store):
    seed_publicidad(book, store, NOW)
    d = Datos(book, store, NOW)
    html = render("/publicidad", {}, d)
    assert "Publicidad" in html and "Topes por plataforma" in html
    assert "Fuente no conectada" in html and "nunca se envía nada" in html
    assert "Esperando tu aprobación" in html and "Garden otoño" in html
    assert "pasa el tope" in html                       # pub-3: 25/day over the 15 limit
    states = {c.campana_id: c.gate.estado for c in d.campanas_plan}
    assert states == {"pub-1": "ok", "pub-2": "pendiente", "pub-3": "sin-solicitud"}
    pub1 = next(c for c in d.campanas_plan if c.campana_id == "pub-1")
    assert pub1.shopify.valor == 2 and not pub1.excede
    titles = [a.titulo for a in resumen_dia(d).alertas]
    assert any("Owl prueba" in t for t in titles)
    assert not any("Garden otoño" in t for t in titles)
    assert render("/publicidad", {"p": "hoy"}, d) and render("/publicidad", {"p": "x"}, d)


def test_publicidad_screen_when_nothing_is_loaded(tmp_path, store):
    d = Datos(LocalWorkbook(tmp_path), store, NOW)
    html = render("/publicidad", {}, d)
    assert "Aún no hay campañas" in html and "Aún no hay topes" in html
    assert "US$0.00" not in html.split("Gasto publicitario")[1][:400]


@pytest.mark.parametrize("origin", [
    {"origen_fuente": "direct", "referente": "lulamacaroni.com"},
    {"origen_fuente": "https://admin.shopify.com/", "referente": "admin.shopify.com"},
    {"origen_fuente": "direct", "referente": "xve3fx-zk.myshopify.com"},
])
def test_store_own_pages_and_admin_count_as_direct(origin):
    assert pub.origen(_o("x", **origin)) == ("directo", False)


def test_screens_open_on_a_sheet_without_the_new_tabs(tmp_path, store):
    from lulamacaroni.workbook import GoogleSetupError

    class OldSheet(LocalWorkbook):
        def read(self, nombre):
            if nombre in ("Publicidad", "Topes"):
                raise GoogleSetupError(f"no tab {nombre}")
            return super().read(nombre)

    d = Datos(OldSheet(tmp_path), store, NOW)
    assert d.faltan_tabs == ["Publicidad", "Topes"]
    html = render("/publicidad", {}, d)
    assert "setup_workbook" in html and "cero real" not in html.split("Pedidos desde")[0]
    assert render("/", {}, d) and render("/catalogo", {}, d)
