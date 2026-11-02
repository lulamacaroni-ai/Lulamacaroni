import pytest

from lulamacaroni.approval import JsonStore, NotApproved, decide, request_approval
from lulamacaroni.connectors.prodigi import BASE_URLS, ProdigiClient, ProdigiError, product_is_available


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body, self.reason, self.text = status, body, "x", ""

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def request(self, method, url, headers=None, timeout=None, **kw):
        self.calls.append((method, url, headers, kw))
        return self.responses.pop(0)


def client(*responses):
    return ProdigiClient(api_key="test-key", env="sandbox", session=FakeSession(responses))


def test_sandbox_url_and_header():
    c = client(FakeResponse(200, {"order": {"id": "ord_1"}}))
    assert c.get_order("ord_1")["id"] == "ord_1"
    method, url, headers, _ = c.session.calls[0]
    assert url == BASE_URLS["sandbox"] + "/orders/ord_1"
    assert headers["X-API-Key"] == "test-key"


def test_rejects_unknown_env():
    with pytest.raises(ValueError):
        ProdigiClient(api_key="k", env="prod")


def test_paging():
    c = client(FakeResponse(200, {"orders": [{"id": 1}, {"id": 2}], "hasMore": True}),
               FakeResponse(200, {"orders": [{"id": 3}], "hasMore": False}))
    assert [o["id"] for o in c.iter_orders(page_size=2)] == [1, 2, 3]
    assert c.session.calls[1][3]["params"]["skip"] == 2


def test_errors_and_availability():
    c = client(FakeResponse(404, {"statusText": "NotFound"}))
    assert product_is_available(c, "GONE") is False
    c = client(FakeResponse(500, {"statusText": "boom"}))
    with pytest.raises(ProdigiError):
        product_is_available(c, "X")


def test_manual_order_needs_matching_approval(tmp_path):
    store = JsonStore(tmp_path / "a.json")
    order = {"shippingMethod": "Standard", "recipient": {"name": "Test"}, "items": []}
    rec = request_approval(store, tipo="pedido-manual", linea="US-POD", resumen="Reimpresión",
                           contenido=order, creado_por="Operaciones")
    c = client(FakeResponse(200, {"order": {"id": "ord_9"}}))
    with pytest.raises(NotApproved):
        c.create_order(order, approval=rec)
    assert c.session.calls == []  # nothing sent while pending
    rec = decide(store, rec.aprobacion_id, aprobar=True, decidido_por="Lorena")
    assert c.create_order(order, approval=rec)["id"] == "ord_9"
    sent = c.session.calls[0][3]["json"]
    assert sent["merchantReference"] == rec.aprobacion_id
    assert "merchantReference" not in order  # caller's dict untouched


def test_from_env_picks_the_key_for_the_environment(monkeypatch):
    from lulamacaroni.connectors.prodigi import ProdigiClient

    monkeypatch.setenv("PRODIGI_SANDBOX_API_KEY", "sbx")
    monkeypatch.setenv("PRODIGI_API_KEY", "live-key")
    monkeypatch.delenv("PRODIGI_ENV", raising=False)
    c = ProdigiClient.from_env()
    assert c.env == "sandbox" and c.api_key == "sbx"
    monkeypatch.setenv("PRODIGI_ENV", "live")
    c = ProdigiClient.from_env()
    assert c.env == "live" and c.api_key == "live-key"


def test_sandbox_never_falls_back_to_the_live_key(monkeypatch):
    import pytest as _pytest

    from lulamacaroni.config import MissingSetting
    from lulamacaroni.connectors.prodigi import ProdigiClient

    monkeypatch.delenv("PRODIGI_SANDBOX_API_KEY", raising=False)
    monkeypatch.setenv("PRODIGI_API_KEY", "live-key")
    monkeypatch.setenv("PRODIGI_ENV", "sandbox")
    with _pytest.raises(MissingSetting):
        ProdigiClient.from_env()
