"""Serve the approval page locally.

    python -m lulamacaroni.approval.server            # http://127.0.0.1:8765
    python -m lulamacaroni.approval.server --demo     # seed sample requests first

It binds to 127.0.0.1 only. For Lorena to approve from her phone it gets hosted
behind Cloudflare Access (login required) — see docs/approval-gate.md. Never expose
this server to the internet without that login in front of it.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import config
from .gate import decide, request_approval
from .page import render
from .store import open_store

APPROVER = config.get("LULA_APPROVER", "Lorena")


class Handler(BaseHTTPRequestHandler):
    store = None  # set in main()

    def _send(self, status: int, body: str, content_type: str = "text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _same_origin(self) -> bool:
        origin = self.headers.get("Origin") or self.headers.get("Referer")
        if not origin:
            return False
        return urlparse(origin).netloc == self.headers.get("Host")

    def do_GET(self):  # noqa: N802
        if urlparse(self.path).path != "/":
            return self._send(404, "No encontrado", "text/plain; charset=utf-8")
        self._send(200, render(self.store.all()))

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != "/decidir":
            return self._send(404, "No encontrado", "text/plain; charset=utf-8")
        if not self._same_origin():
            return self._send(403, "Origen no permitido", "text/plain; charset=utf-8")
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        aprobacion_id = (form.get("aprobacion_id") or [""])[0]
        decision = (form.get("decision") or [""])[0]
        nota = (form.get("nota") or [""])[0]
        if decision not in ("aprobar", "rechazar"):
            return self._send(400, "Decisión no válida", "text/plain; charset=utf-8")
        try:
            decide(self.store, aprobacion_id, aprobar=decision == "aprobar",
                   decidido_por=APPROVER, nota=nota)
        except (KeyError, ValueError) as exc:
            return self._send(409, f"No se pudo registrar: {exc}", "text/plain; charset=utf-8")
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


def seed_demo(store) -> None:
    request_approval(
        store, tipo="listado", linea="US-POD", creado_por="Listados",
        resumen="Nuevo listado en Etsy: 'Sample artwork' print 12×16 in",
        contenido={"canal": "etsy", "sku": "DEMO-001-12x16", "titulo": "Sample artwork print",
                   "precio_usd": 95.0, "tags": ["wall art", "botanical print"]},
    )
    request_approval(
        store, tipo="presupuesto", linea="US-POD", creado_por="Pulso", monto_usd=10.0,
        resumen="Subir presupuesto diario de Meta Ads de US$5 a US$10 por 7 días",
        contenido={"plataforma": "meta", "campana": "DEMO", "de": 5, "a": 10, "dias": 7},
    )
    request_approval(
        store, tipo="listado", linea="MX-original", creado_por="Catálogo",
        resumen="Agregar obra original al catálogo del sitio México",
        contenido={"canal": "sitio-mx", "obra_id": "DEMO-002", "precio_mxn_con_iva": 12000},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local approval page")
    parser.add_argument("--port", type=int, default=int(config.get("LULA_APPROVAL_PORT", "8765")))
    parser.add_argument("--demo", action="store_true", help="add three sample requests")
    args = parser.parse_args(argv)
    Handler.store = open_store()
    if args.demo:
        seed_demo(Handler.store)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Aprobaciones en http://127.0.0.1:{args.port}  (Ctrl+C para salir)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
