"""Serve the back office app.

    python -m lulamacaroni.app.server            # http://127.0.0.1:8770, real data
    python -m lulamacaroni.app.server --demo     # sample data, clearly marked, nothing real

Real data comes from the workbook: the Google Sheet when a Google key is configured,
otherwise the local files that ``python -m lulamacaroni.connectors.shopify`` writes to
``data/libro/``. Approvals come from the approval store.

It binds to 127.0.0.1 and is read-only, except for Aprobar/Rechazar, which records
Lorena's decision through the approval gate. Hosted (docs/hosting.md) it listens on
``--host 0.0.0.0`` and the host's ``PORT``, and then it refuses to start unless
``LULA_APP_PASSWORD`` is set: every page asks for that password first.
"""

from __future__ import annotations

import argparse
import base64
import hmac
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import config
from ..approval.gate import decide
from ..approval.store import JsonStore, SheetsStore, open_store
from ..localbook import LocalWorkbook, open_workbook
from ..workbook import Workbook
from . import views
from .arte import ARCHIVOS as ARTE
from .screens import PERRITO, PORTADA, Datos, es_portada, render

APPROVER = config.get("LULA_APPROVER", "Lorena")
TEXT = "text/plain; charset=utf-8"
IMAGENES = {"/portada.png": PORTADA, "/perrito.png": PERRITO, **ARTE}


LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class Handler(BaseHTTPRequestHandler):
    book = None
    store = None
    banner = ""
    password = None  # set when hosted; every request must carry it (HTTP Basic auth)

    def log_message(self, fmt, *args):  # keep request logs free of query strings
        pass

    def _send(self, status: int, body: str, content_type: str = "text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin") or self.headers.get("Referer")
        return bool(origin) and urlparse(origin).netloc == self.headers.get("Host")

    def _authorized(self) -> bool:
        if not self.password:
            return True
        header = self.headers.get("Authorization") or ""
        if header.startswith("Basic "):
            try:
                _, _, given = base64.b64decode(header[6:]).decode("utf-8").partition(":")
            except Exception:  # noqa: BLE001
                given = ""
            if hmac.compare_digest(given.encode("utf-8"), self.password.encode("utf-8")):
                return True
        data = "Se necesita la contraseña.".encode("utf-8")
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Lula Macaroni", charset="UTF-8"')
        self.send_header("Content-Type", TEXT)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
        return False

    def do_GET(self):  # noqa: N802
        if not self._authorized():
            return
        url = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path in IMAGENES:  # Lore's art, served as-is
            archivo = IMAGENES[url.path]
            if not archivo.is_file():
                return self._send(404, "No encontrado", TEXT)
            data = archivo.read_bytes()
            self.send_response(200)
            tipo = "image/jpeg" if archivo.suffix == ".jpg" else "image/png"
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "private, max-age=86400")
            self.end_headers()
            self.wfile.write(data)
            return
        if es_portada(url.path, params):  # no workbook read: the welcome page opens at once
            return self._send(200, views.portada(PORTADA.is_file(), self.banner))
        try:
            html = render(url.path, params, Datos(self.book, self.store), self.banner)
        except Exception as exc:  # show a readable error instead of a dropped connection
            return self._send(500, f"No se pudo leer el libro de datos: {type(exc).__name__}", TEXT)
        if html is None:
            return self._send(404, "No encontrado", TEXT)
        self._send(200, html)

    def do_POST(self):  # noqa: N802
        if not self._authorized():
            return
        if urlparse(self.path).path != "/decidir":
            return self._send(404, "No encontrado", TEXT)
        if not self._same_origin():
            return self._send(403, "Origen no permitido", TEXT)
        length = min(int(self.headers.get("Content-Length") or 0), 20_000)
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        aprobacion_id = (form.get("aprobacion_id") or [""])[0]
        decision = (form.get("decision") or [""])[0]
        nota = (form.get("nota") or [""])[0][:500]
        if decision not in ("aprobar", "rechazar"):
            return self._send(400, "Decisión no válida", TEXT)
        try:
            decide(self.store, aprobacion_id, aprobar=decision == "aprobar",
                   decidido_por=APPROVER, nota=nota)
        except (KeyError, ValueError) as exc:
            return self._send(409, f"No se pudo registrar: {exc}", TEXT)
        self.send_response(303)
        self.send_header("Location", "/aprobar")
        self.end_headers()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Back office app (local)")
    parser.add_argument("--port", type=int,
                        default=int(config.get("PORT") or config.get("LULA_APP_PORT", "8770")))
    parser.add_argument("--host", default=config.get("LULA_APP_HOST", "127.0.0.1"),
                        help="0.0.0.0 when hosted; then LULA_APP_PASSWORD is required")
    parser.add_argument("--demo", action="store_true",
                        help="sample data in a temporary folder; nothing real is read or written")
    parser.add_argument("--open", action="store_true",
                        help="open the app in the default browser once it is listening")
    args = parser.parse_args(argv)

    Handler.password = config.get("LULA_APP_PASSWORD")
    if args.host not in LOOPBACK and not Handler.password:
        print("LULA_APP_PASSWORD is not set. Refusing to listen on "
              f"{args.host} without a password (see docs/hosting.md).")
        return 2

    if args.demo:
        from ..approval.server import seed_demo
        from .demo import fill_demo, seed_publicidad

        tmp = Path(tempfile.mkdtemp(prefix="lula-demo-"))
        Handler.book = LocalWorkbook(tmp / "libro")
        Handler.store = JsonStore(tmp / "aprobaciones.json")
        fill_demo(Handler.book)
        seed_demo(Handler.store)
        seed_publicidad(Handler.book, Handler.store)
        Handler.banner = "Datos de ejemplo: nada de esto es real."
    else:
        Handler.book = open_workbook()
        # one connection and one cache for both: an approval shows up on the next screen
        Handler.store = (SheetsStore(Handler.book) if isinstance(Handler.book, Workbook)
                         else open_store())
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Back office en {url}  (Ctrl+C para salir)")
    if args.open:
        import threading
        import webbrowser

        threading.Timer(0.5, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
