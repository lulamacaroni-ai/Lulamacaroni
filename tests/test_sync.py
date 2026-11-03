import io
from datetime import datetime, timezone

from lulamacaroni import sync
from lulamacaroni.app import alertas as al
from lulamacaroni.app import metrics as m
from lulamacaroni.localbook import LocalWorkbook


class Boom(RuntimeError):
    pass


def _fail():
    raise Boom("respuesta con datos que no deben salir")


def test_one_failure_does_not_stop_the_rest_and_is_marked(tmp_path):
    wb = LocalWorkbook(tmp_path / "libro")
    wb.upsert("Fuentes", [{"fuente": "shopify", "ultima_actualizacion": "2026-11-01T10:00:00+00:00",
                           "estado": "ok", "filas": 672, "nota": ""}])
    ran = []
    steps = [("Shopify", lambda: "shopify", _fail),
             ("Prodigi", lambda: "prodigi", lambda: ran.append("prodigi"))]
    out = io.StringIO()
    assert sync.run(wb, steps, out) == 1
    assert ran == ["prodigi"]
    row = next(r for r in wb.read("Fuentes") if r["fuente"] == "shopify")
    assert row["estado"] == "error"
    assert row["ultima_actualizacion"] == "2026-11-01T10:00:00+00:00"  # last good time kept
    assert "Boom" in row["nota"] and "no deben salir" not in row["nota"]
    assert "no deben salir" not in out.getvalue()


def test_failed_sync_shows_as_error_without_update_time(tmp_path):
    wb = LocalWorkbook(tmp_path / "libro")
    sync.run(wb, [("Shopify", lambda: "shopify", _fail)], io.StringIO())
    now = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)
    fuentes = m.estado_fuentes(wb.read("Fuentes"), now)
    assert fuentes["shopify"].estado == "error"
    assert fuentes["shopify"].actualizado is None  # never synced: no fake update time


def test_all_ok(tmp_path):
    wb = LocalWorkbook(tmp_path / "libro")
    assert sync.run(wb, [("A", lambda: "a", lambda: None)], io.StringIO()) == 0
    assert wb.read("Fuentes") == []


def test_prodigi_source_key_follows_env(monkeypatch):
    monkeypatch.setattr(sync.config, "get", lambda k, d=None: "live" if k == "PRODIGI_ENV" else d)
    assert sync._prodigi_fuente() == "prodigi"
    monkeypatch.setattr(sync.config, "get", lambda k, d=None: d)
    assert sync._prodigi_fuente() == "prodigi-sandbox"
