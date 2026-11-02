"""Build each screen from the workbook (or its local stand-in) and the approvals store.

Kept apart from the HTTP server so tests can render every screen offline.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import metrics as m
from . import views


class Datos:
    """Everything the screens read, loaded once per request."""

    def __init__(self, book, store, now: datetime | None = None):
        self.now = now or datetime.now(timezone.utc)
        self.pedidos_rows = book.read("Pedidos")
        self.listados = book.read("Listados")
        self.campanas = book.read("Campanas")
        self.excepciones = book.read("Excepciones")
        self.obras = book.read("Obras")
        self.fuentes = m.estado_fuentes(book.read("Fuentes"), self.now)
        self.approvals = store.all()
        self.pedidos = m.agrupar_pedidos(self.pedidos_rows)
        self.productos = m.agrupar_catalogo(self.listados)

    @property
    def pendientes(self) -> int:
        return sum(1 for a in self.approvals if a.estado == "pendiente")


def render(path: str, params: dict[str, str], d: Datos, banner: str = "") -> str | None:
    """HTML for ``path``, or None if there is no such screen."""
    if path == "/":
        clave = params.get("p", "7")
        clave = clave if clave in m.PERIODOS else "7"
        res = m.resumen(d.pedidos_rows, d.campanas, d.fuentes, m.periodo(clave, d.now))
        acciones = m.acciones_del_dia(d.pendientes, d.pedidos, d.productos, d.fuentes,
                                      d.excepciones)
        return views.inicio(res, acciones, d.fuentes, d.now, banner=banner)
    if path == "/pedidos":
        return views.pedidos(d.pedidos, d.fuentes, d.now, banner)
    if path == "/catalogo":
        return views.catalogo(d.productos, len(d.obras), params.get("f", "todo"), d.fuentes,
                              d.now, banner)
    if path == "/fuentes":
        return views.fuentes_view(d.fuentes, d.now, banner)
    if path == "/aprobar":
        return views.aprobar(d.approvals, banner)
    return None
