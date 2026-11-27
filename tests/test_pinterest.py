"""Pinterest connector (read-only) and its place in Contenido, Fuentes and alerts. Offline."""

from datetime import date, datetime, timedelta, timezone

import pytest

from lulamacaroni import sync
from lulamacaroni.app import alertas as al
from lulamacaroni.app import contenido as cont
from lulamacaroni.app import metrics as m
from lulamacaroni.app.screens import Datos, render
from lulamacaroni.approval import JsonStore
from lulamacaroni.connectors import pinterest as pt
from lulamacaroni.localbook import LocalWorkbook

NOW = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)
HOY = NOW.date()


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.reason = "x"

    def json(self):
        return self._body


class FakeSession:
    """Answers by path; records every call (method, path, params, headers)."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def request(self, method, url, params=None, headers=None, timeout=None):
        path = url.removeprefix(pt.BASE_URL)
        self.calls.append((method, path, dict(params or {}), headers))
        ans = self.routes.get(path)
        if callable(ans):
            ans = ans(params or {})
        if ans is None:
            return FakeResponse(404, {"message": "not found"})
        return ans if isinstance(ans, FakeResponse) else FakeResponse(200, ans)


def _dia(d, status="READY", imp=10):
    return {"date": d.isoformat(), "data_status": status,
            "metrics": {"IMPRESSION": imp, "SAVE": 1, "PIN_CLICK": 2, "OUTBOUND_CLICK": 1,
                        "ENGAGEMENT": 3}}


def _routes(**extra):
    boards_p1 = {"items": [{"id": "b1", "name": "Garden", "privacy": "PUBLIC", "pin_count": 2,
                            "follower_count": 5}], "bookmark": "next"}
    boards_p2 = {"items": [{"id": "b2", "name": "Secret", "privacy": "SECRET", "pin_count": 0}],
                 "bookmark": None}
    routes = {
        "/user_account": {"username": "lulamacaroni", "account_type": "BUSINESS",
                          "follower_count": 53},
        "/boards": lambda p: boards_p2 if p.get("bookmark") == "next" else boards_p1,
        "/pins": {"items": [
            {"id": "p1", "title": "Old", "board_id": "b1", "created_at": "2026-01-01T00:00:00",
             "link": "https://lulamacaroni.com/products/garden-print?utm_source=pinterest",
             "media": {"media_type": "image", "images": {"600x": {"url": "https://i.pinimg.com/a.jpg"}}}},
            {"id": "p2", "title": "New", "board_id": "b1", "created_at": "2026-10-30T00:00:00",
             "link": "", "media": {"media_type": "video"}},
        ], "bookmark": None},
        "/pins/p1/analytics": {"all": {"summary_metrics": {"IMPRESSION": 120, "SAVE": 4,
                                                           "PIN_CLICK": 6, "OUTBOUND_CLICK": 2},
                                       "daily_metrics": [_dia(HOY)]}},
        "/pins/p2/analytics": {"all": {"daily_metrics": [_dia(HOY - timedelta(days=1)),
                                                         _dia(HOY, "PROCESSING")]}},
        "/user_account/analytics": {"all": {"daily_metrics": [
            _dia(HOY - timedelta(days=3)), _dia(HOY - timedelta(days=2)),
            _dia(HOY - timedelta(days=1), "PROCESSING")]}},
        "/ad_accounts": {"items": [], "bookmark": None},
    }
    routes.update(extra)
    return routes


def client(**extra):
    s = FakeSession(_routes(**extra))
    return pt.PinterestClient("tok-test", session=s), s


LISTADOS = [{"listado_ref": "shopify-1", "url": "https://lulamacaroni.com/products/garden-print",
             "id_producto_canal": "777", "titulo_en_canal": "Garden Print / 8x10"}]


# --- client ---------------------------------------------------------------------------------

def test_bearer_token_paging_and_get_only():
    c, s = client()
    boards = list(c.iter_boards())
    assert [b["id"] for b in boards] == ["b1", "b2"]
    assert all(call[0] == "GET" for call in s.calls)
    assert s.calls[0][3]["Authorization"] == "Bearer tok-test"
    assert s.calls[1][2]["bookmark"] == "next" and s.calls[0][2]["page_size"] == 100


def test_expired_token_says_what_to_do_and_never_echoes_it():
    c, _ = client(**{"/user_account": FakeResponse(401, {"message": "Authentication failed"})})
    with pytest.raises(pt.PinterestError) as e:
        c.user_account()
    assert e.value.status == 401 and "docs/setup/pinterest.md" in str(e.value)
    assert "tok-test" not in str(e.value)


def test_from_env_requires_the_token(monkeypatch):
    from lulamacaroni.config import MissingSetting

    monkeypatch.delenv("PINTEREST_ACCESS_TOKEN", raising=False)
    with pytest.raises(MissingSetting):
        pt.PinterestClient.from_env()


# --- transforms --------------------------------------------------------------------------------

def test_missing_and_processing_are_not_zero():
    vals, q = pt.resumen_metricas(None)
    assert q == "faltante" and set(vals.values()) == {""}
    vals, q = pt.resumen_metricas({"all": {"daily_metrics": [_dia(HOY), _dia(HOY, "PROCESSING")]}})
    assert q == "estimado" and vals["impresiones"] == 10   # only the final day is summed
    rows = pt.daily_rows({"all": {"daily_metrics": [
        _dia(HOY), _dia(HOY, "PROCESSING"), _dia(HOY, "BEFORE_BUSINESS_CREATED")]}}, "t")
    assert [r["calidad_dato"] for r in rows] == ["real", "estimado", "faltante"]
    assert rows[2]["impresiones"] == "" and rows[0]["linea"] == "US-POD"


def test_pin_links_to_its_shopify_product():
    assert pt.handle_producto("https://x.com/products/garden-print?v=1") == "garden-print"
    assert pt.handle_producto("https://x.com/collections/all") == ""
    assert pt.handle_producto("") == ""
    pin = {"id": "p1", "board_id": "b1", "link": "https://lulamacaroni.com/products/Garden-Print"}
    row = pt.pin_to_row(pin, {"b1": "Garden"}, pt.productos_por_handle(LISTADOS), None, "p", "t")
    assert row["producto"] == "Garden Print" and row["id_producto_canal"] == "777"
    assert row["tablero"] == "Garden" and row["calidad_dato"] == "faltante"


def test_ad_rows_land_in_campanas_in_dollars():
    rows = pt.campaign_rows([{"CAMPAIGN_ID": 55, "DATE": "2026-11-01", "SPEND_IN_DOLLAR": 3.5,
                              "TOTAL_IMPRESSION": 900, "TOTAL_CLICKTHROUGH": 12,
                              "TOTAL_CHECKOUT": 1,
                              "TOTAL_CHECKOUT_VALUE_IN_MICRO_DOLLAR": 79_000_000},
                             {"DATE": "2026-11-01"}])
    assert len(rows) == 1
    r = rows[0]
    assert r["campana_id"] == "pinterest-55" and r["gasto"] == 3.5 and r["valor_atribuido"] == 79
    assert r["plataforma"] == "pinterest" and r["linea"] == "US-POD" and r["calidad_dato"] == "real"


def test_token_expiry_note(monkeypatch):
    monkeypatch.setenv("PINTEREST_TOKEN_VENCE", "2026-11-30")
    assert "vence el 2026-11-30 (en 26 días)" in pt.nota_vence(HOY)
    assert "haz uno nuevo" in pt.nota_vence(date(2026, 11, 25))
    assert "venció" in pt.nota_vence(date(2026, 12, 2))
    monkeypatch.delenv("PINTEREST_TOKEN_VENCE")
    assert "desconocida" in pt.nota_vence(HOY)


# --- sync ------------------------------------------------------------------------------------

def test_sync_writes_tabs_and_marks_ads_unconnected(tmp_path, monkeypatch):
    monkeypatch.setenv("PINTEREST_TOKEN_VENCE", "2026-12-01")
    c, s = client()
    wb = LocalWorkbook(tmp_path)
    r = pt.leer(c, LISTADOS, hoy=HOY)
    pt.escribir(wb, r)
    assert {t["tablero_id"]: t["privacidad"] for t in wb.read("Tableros")} == {
        "b1": "publico", "b2": "secreto"}
    pines = {p["pin_id"]: p for p in wb.read("Pines")}
    assert pines["p1"]["impresiones"] == 120 and pines["p1"]["calidad_dato"] == "real"
    assert pines["p1"]["producto"] == "Garden Print"
    assert pines["p2"]["calidad_dato"] == "estimado"
    assert len(wb.read("PinterestDiario")) == 3
    fuentes = {f["fuente"]: f for f in wb.read("Fuentes")}
    assert fuentes["pinterest"]["estado"] == "ok" and "@lulamacaroni" in fuentes["pinterest"]["nota"]
    assert "vence el 2026-12-01" in fuentes["pinterest"]["nota"]
    assert fuentes["pinterest-ads"]["estado"] == "sin-conectar"
    assert wb.read("Campanas") == []
    # newest pin first; the period ends yesterday (Pinterest's data lags)
    pin_calls = [x for x in s.calls if x[1].startswith("/pins/")]
    assert pin_calls[0][1] == "/pins/p2/analytics"
    assert pin_calls[0][2]["end_date"] == (HOY - timedelta(days=1)).isoformat()


def test_pin_analytics_cap_and_per_pin_failure(tmp_path):
    c, _ = client(**{"/pins/p2/analytics": FakeResponse(403, {"message": "no"})})
    r = pt.leer(c, [], hoy=HOY, max_pines=1)
    by = {p["pin_id"]: p for p in r.pines}
    assert by["p2"]["calidad_dato"] == "faltante" and by["p1"]["calidad_dato"] == "faltante"
    assert any("p2" in a for a in r.avisos) and any("más viejos" in a for a in r.avisos)


def test_ad_account_spend_is_synced(tmp_path):
    c, _ = client(**{
        "/ad_accounts": {"items": [{"id": "A1"}], "bookmark": None},
        "/ad_accounts/A1/campaigns": {"items": [{"id": "55"}], "bookmark": None},
        "/ad_accounts/A1/campaigns/analytics": [
            {"CAMPAIGN_ID": "55", "DATE": "2026-11-02", "SPEND_IN_DOLLAR": 0}],
    })
    wb = LocalWorkbook(tmp_path)
    pt.escribir(wb, pt.leer(c, [], hoy=HOY))
    assert wb.read("Campanas")[0]["gasto"] == 0          # a real zero from Pinterest
    f = {x["fuente"]: x for x in wb.read("Fuentes")}["pinterest-ads"]
    assert f["estado"] == "ok" and "1 cuenta" in f["nota"]


def test_no_ads_permission_is_not_an_error(tmp_path):
    c, _ = client(**{"/ad_accounts": FakeResponse(403, {"message": "scope"})})
    r = pt.leer(c, [], hoy=HOY)
    assert r.campanas is None and "ads:read" in r.nota_ads


def test_daily_sync_runs_pinterest_only_with_a_token(monkeypatch):
    monkeypatch.delenv("PINTEREST_ACCESS_TOKEN", raising=False)
    assert "Pinterest" not in [n for n, _, _ in sync.pasos()]
    monkeypatch.setenv("PINTEREST_ACCESS_TOKEN", "x")
    assert "Pinterest" in [n for n, _, _ in sync.pasos()]


# --- app -------------------------------------------------------------------------------------

def _book(tmp_path, monkeypatch, **extra):
    monkeypatch.setenv("PINTEREST_TOKEN_VENCE", "2026-12-01")
    c, _ = client(**extra)
    wb = LocalWorkbook(tmp_path / "libro")
    pt.escribir(wb, pt.leer(c, LISTADOS, hoy=HOY))
    return wb


def test_contenido_shows_pinterest_numbers_with_their_quality(tmp_path, monkeypatch):
    wb = _book(tmp_path, monkeypatch)
    d = Datos(wb, JsonStore(tmp_path / "a.json"), NOW)
    vp = d.pinterest()
    imp = next(x for x in vp.datos if x.etiqueta == "Impresiones")
    assert vp.conectada and imp.valor == 30 and imp.calidad == "estimado"   # one day processing
    assert [p["pin_id"] for p in vp.pines] == ["p1", "p2"]                 # most seen first
    html = render("/contenido", {"pl": "pinterest"}, d)
    assert "Pines más vistos (2)" in html and "Garden Print" in html and "Tableros (2)" in html
    assert "https://www.pinterest.com/pin/p1/" in html
    assert "render(" not in html and "nunca se publica" in html


def test_contenido_without_pinterest_shows_missing_not_zero(tmp_path):
    wb = LocalWorkbook(tmp_path)
    vp = cont.pinterest([], [], [], m.estado_fuentes([], NOW), NOW)
    assert not vp.conectada and all(x.calidad == "faltante" and x.valor is None
                                    for x in vp.datos)
    html = render("/contenido", {}, Datos(wb, JsonStore(tmp_path / "a.json"), NOW))
    assert "PINTEREST_ACCESS_TOKEN" in html
    assert "Pines más vistos" not in render("/contenido", {"pl": "instagram"},
                                             Datos(wb, JsonStore(tmp_path / "b.json"), NOW))


def test_connected_pinterest_without_ads_keeps_ad_spend_missing(tmp_path, monkeypatch):
    wb = _book(tmp_path, monkeypatch)
    f = m.estado_fuentes(wb.read("Fuentes"), NOW)
    assert f["pinterest"].conectada and not f["pinterest-ads"].conectada
    res = m.resumen([], [], f, m.periodo("30", NOW), [])
    assert next(x for x in res.datos if x.etiqueta == "Gasto publicitario").calidad == "faltante"


def test_token_expiry_alert(monkeypatch):
    hoy = datetime.now(m.TZ).date()
    for dias, sale in ((3, True), (20, False), (-1, True)):
        nota = f"@x; el permiso vence el {(hoy + timedelta(days=dias)).isoformat()}"
        fuentes = m.estado_fuentes([{"fuente": "pinterest", "estado": "ok", "nota": nota,
                                     "ultima_actualizacion": NOW.isoformat()},
                                    {"fuente": "shopify", "estado": "ok",
                                     "ultima_actualizacion": NOW.isoformat()}], NOW)
        out = al.calcular([], [], [], fuentes, [], 0)
        hits = [a for a in out if a.titulo.startswith("Pinterest: el permiso")]
        assert bool(hits) == sale, dias
    assert al.pinterest_vence("sin fecha") is None
