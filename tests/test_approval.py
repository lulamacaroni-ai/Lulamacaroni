from datetime import datetime, timedelta, timezone

import pytest

from lulamacaroni.approval import (
    JsonStore, NotApproved, assert_approved, decide, fingerprint, mark_executed, request_approval,
)
from lulamacaroni.approval.page import render

T0 = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)
LISTING = {"canal": "etsy", "sku": "LM-001-12x16", "titulo": "Sunlit garden print", "precio_usd": 95}


@pytest.fixture
def store(tmp_path):
    return JsonStore(tmp_path / "aprobaciones.json")


def _approved(store):
    rec = request_approval(store, tipo="listado", linea="US-POD", resumen="Nuevo listado",
                           contenido=LISTING, creado_por="Listados", now=T0)
    return decide(store, rec.aprobacion_id, aprobar=True, decidido_por="Lorena", now=T0)


def test_fingerprint_ignores_key_order():
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})
    assert fingerprint({"a": 1}) != fingerprint({"a": 2})


def test_pending_is_not_enough(store):
    rec = request_approval(store, tipo="listado", linea="US-POD", resumen="x",
                           contenido=LISTING, creado_por="Listados", now=T0)
    with pytest.raises(NotApproved):
        assert_approved(rec, tipo="listado", contenido=LISTING, now=T0)


def test_approved_exact_content_passes(store):
    rec = _approved(store)
    assert_approved(store.get(rec.aprobacion_id), tipo="listado", contenido=LISTING, now=T0)


def test_edit_after_approval_needs_new_approval(store):
    rec = _approved(store)
    changed = dict(LISTING, precio_usd=80)
    with pytest.raises(NotApproved, match="contenido cambió"):
        assert_approved(rec, tipo="listado", contenido=changed, now=T0)


def test_wrong_type_rejected(store):
    rec = _approved(store)
    with pytest.raises(NotApproved):
        assert_approved(rec, tipo="reembolso", contenido=LISTING, now=T0)


def test_expired_rejected(store):
    rec = _approved(store)
    with pytest.raises(NotApproved, match="expiró"):
        assert_approved(rec, tipo="listado", contenido=LISTING, now=T0 + timedelta(days=8))


def test_approval_used_once(store):
    rec = _approved(store)
    mark_executed(store, rec, now=T0)
    with pytest.raises(NotApproved, match="ya se usó"):
        assert_approved(store.get(rec.aprobacion_id), tipo="listado", contenido=LISTING, now=T0)


def test_rejected_and_none(store):
    rec = request_approval(store, tipo="listado", linea="US-POD", resumen="x",
                           contenido=LISTING, creado_por="Listados", now=T0)
    decide(store, rec.aprobacion_id, aprobar=False, decidido_por="Lorena", nota="otro título", now=T0)
    with pytest.raises(NotApproved):
        assert_approved(store.get(rec.aprobacion_id), tipo="listado", contenido=LISTING, now=T0)
    with pytest.raises(NotApproved):
        assert_approved(None, tipo="listado", contenido=LISTING, now=T0)


def test_cannot_decide_twice(store):
    rec = _approved(store)
    with pytest.raises(ValueError):
        decide(store, rec.aprobacion_id, aprobar=False, decidido_por="Lorena", now=T0)


def test_deciding_after_expiry_marks_expired(store):
    rec = request_approval(store, tipo="listado", linea="US-POD", resumen="x",
                           contenido=LISTING, creado_por="Listados", now=T0)
    out = decide(store, rec.aprobacion_id, aprobar=True, decidido_por="Lorena",
                 now=T0 + timedelta(days=30))
    assert out.estado == "expirado"


def test_budget_needs_amount_and_line_is_validated(store):
    with pytest.raises(ValueError):
        request_approval(store, tipo="presupuesto", linea="US-POD", resumen="x",
                         contenido={}, creado_por="Pulso")
    with pytest.raises(ValueError):
        request_approval(store, tipo="listado", linea="US", resumen="x",
                         contenido={}, creado_por="Listados")


def test_page_escapes_and_shows_pending(store):
    request_approval(store, tipo="listado", linea="MX-original", resumen="<script>x</script>",
                     contenido={"t": "<b>"}, creado_por="Catálogo", now=T0)
    html = render(store.all())
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html
    assert "1 pendiente(s)" in html
    assert "México · originales" in html
