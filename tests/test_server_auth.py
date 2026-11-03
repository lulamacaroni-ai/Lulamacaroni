import base64
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from lulamacaroni.app import server as srv
from lulamacaroni.approval.store import JsonStore
from lulamacaroni.localbook import LocalWorkbook


@pytest.fixture
def running(tmp_path, monkeypatch):
    monkeypatch.setattr(srv.Handler, "book", LocalWorkbook(tmp_path / "libro"))
    monkeypatch.setattr(srv.Handler, "store", JsonStore(tmp_path / "a.json"))
    monkeypatch.setattr(srv.Handler, "password", "s3creta-ñ")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _get(url, password=None):
    req = urllib.request.Request(url)
    if password is not None:
        token = base64.b64encode(f"lore:{password}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers)


def test_every_page_asks_for_the_password(running):
    for path in ("/", "/fuentes", "/aprobar"):
        status, headers = _get(running + path)
        assert status == 401
        assert headers["WWW-Authenticate"].startswith("Basic")


def test_wrong_password_is_refused_right_one_opens(running):
    assert _get(running + "/", "nope")[0] == 401
    assert _get(running + "/", "s3creta-ñ")[0] == 200


def test_post_needs_the_password_too(running):
    req = urllib.request.Request(running + "/decidir", data=b"x=1", method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 401


def test_refuses_to_listen_publicly_without_a_password(monkeypatch):
    monkeypatch.delenv("LULA_APP_PASSWORD", raising=False)
    assert srv.main(["--host", "0.0.0.0", "--port", "0", "--demo"]) == 2
