"""Serve the back office app.

    python -m lulamacaroni.app.server            # http://127.0.0.1:8770, real data
    python -m lulamacaroni.app.server --demo     # sample data, clearly marked, nothing real

Real data comes from the workbook: the Google Sheet when a Google key is configured,
otherwise the local files that ``python -m lulamacaroni.connectors.shopify`` writes to
``data/libro/``. Approvals come from the approval store.

It binds to 127.0.0.1 only and is read-only, except for Aprobar/Rechazar, which records
Lorena's decision through the approval gate. To use it from her phone it gets hosted
behind Cloudflare Access (login required); never expose it without that.
"""

from __future__ import annotations

import argparse
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import config
from ..approval.gate import decide
from ..approval.store import JsonStore, SheetsStore, open_store
from ..localbook import LocalWorkbook, open_workbook
from ..workbook import Workbook
from .screens import Datos, render

APPROVER = config.get("LULA_APPROVER", "Lorena")
TEXT = "text/plain; charset=utf-8"


class Handler(BaseHTTPRequestHandler):
    book = None
    store = None
    banner = ""

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

    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            html = render(url.path, params, Datos(self.book, self.store), self.banner)
        except Exception as exc:  # show a readable error instead of a dropped connection
            return self._send(500, f"No se pudo leer el libro de datos: {type(exc).__name__}", TEXT)
        if html is None:
            return self._send(404, "No encontrado", TEXT)
        self._send(200, html)

    def do_POST(self):  # noqa: N802
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
    parser.add_argument("--port", type=int, default=int(config.get("LULA_APP_PORT", "8770")))
    parser.add_argument("--demo", action="store_true",
                        help="sample data in a temporary folder; nothing real is read or written")
    args = parser.parse_args(argv)

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
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Back office en http://127.0.0.1:{args.port}  (Ctrl+C para salir)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
