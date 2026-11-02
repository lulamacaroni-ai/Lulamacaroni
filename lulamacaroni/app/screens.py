"""Build each screen from the workbook (or its local stand-in) and the approvals store.

Kept apart from the HTTP server so tests can render every screen offline.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import alertas as al
from . import catalogo as cat
from . import contenido as cont
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
        self.variantes = book.read("Variantes")
        self.contenido = book.read("Contenido")
        self.pagos = book.read("Pagos")
        self.gastos = book.read("Gastos")
        self.fuentes_rows = book.read("Fuentes")
        self.fuentes = m.estado_fuentes(self.fuentes_rows, self.now)
        self.approvals = store.all()
        self.pedidos = m.agrupar_pedidos(self.pedidos_rows)
        self.productos = m.agrupar_catalogo(self.listados)
        self.fichas = cat.fichas(self.productos, self.listados, self.variantes, self.obras,
                                 self.pedidos_rows, self.now)
        self.piezas = cont.piezas(self.contenido, self.obras, self.approvals, self.now)

    @property
    def pendientes(self) -> int:
        return sum(1 for a in self.approvals if a.estado == "pendiente")


def render(path: str, params: dict[str, str], d: Datos, banner: str = "") -> str | None:
    """HTML for ``path``, or None if there is no such screen."""
    if path == "/":
        clave = params.get("p", "7")
        clave = clave if clave in m.PERIODOS else "7"
        res = m.resumen(d.pedidos_rows, d.campanas, d.fuentes, m.periodo(clave, d.now),
                        d.pagos)
        return views.inicio(res, al.resumen_dia(d), d.fuentes, d.now, banner=banner)
    if path == "/alertas":
        return views.alertas_view(al.resumen_dia(d).alertas, d.fuentes, d.now, banner)
    if path == "/pedidos":
        return views.pedidos(d.pedidos, d.fuentes, d.now, banner)
    if path == "/catalogo":
        origs = cat.originales(d.obras, d.variantes)
        return views.catalogo(d.fichas, origs, cat.resumen(d.fichas, origs, d.obras, d.fuentes,
                                                          d.now),
                              params.get("f", "todo"), d.fuentes, d.now, banner)
    if path == "/catalogo/producto":
        ficha = next((f for f in d.fichas if f.producto.canal == params.get("c")
                      and f.producto.id_producto == params.get("id")), None)
        return views.producto(ficha, d.fuentes, d.now, banner) if ficha else None
    if path == "/contenido":
        plat = params.get("pl", "")
        plat = plat if plat in cont.PLATAFORMA else ""
        ps = [p for p in d.piezas if not plat or p.plataforma == plat]
        return views.contenido_view(ps, cont.resumen(ps, d.fuentes, d.now), plat, d.now, banner)
    if path == "/fuentes":
        return views.fuentes_view(d.fuentes, d.now, banner)
    if path == "/aprobar":
        return views.aprobar(d.approvals, banner)
    return None
