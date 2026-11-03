"""Build each screen from the workbook (or its local stand-in) and the approvals store.

Kept apart from the HTTP server so tests can render every screen offline.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import alertas as al
from . import catalogo as cat
from . import clientes as cli
from . import contenido as cont
from . import investigacion as inv
from .investigacion_view import investigacion_view
from . import finanzas as fin
from . import metrics as m
from . import publicidad as pub
from . import semanal as sem
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
        self.decisiones = book.read("Decisiones")
        self.fuentes_rows = book.read("Fuentes")
        self.fuentes = m.estado_fuentes(self.fuentes_rows, self.now)
        self.approvals = store.all()
        self.pedidos = m.agrupar_pedidos(self.pedidos_rows)
        self.productos = m.agrupar_catalogo(self.listados)
        self.fichas = cat.fichas(self.productos, self.listados, self.variantes, self.obras,
                                 self.pedidos_rows, self.now)
        self.piezas = cont.piezas(self.contenido, self.obras, self.approvals, self.now)
        # tabs added after the first setup: a sheet without them still opens every screen
        self.faltan_tabs: list[str] = []
        self.publicidad = self._opcional(book, "Publicidad")
        self.topes = self._opcional(book, "Topes")
        self.clientes_rows = book.read("Clientes")
        self.clientes = cli.clientes(self.clientes_rows, self.pedidos_rows, self.fuentes,
                                     self.now)
        faltan = len(self.faltan_tabs)
        self.investigacion_rows = self._opcional(book, "Investigacion")
        self.importaciones = self._opcional(book, "Importaciones")
        self.keywords = self._opcional(book, "Keywords")
        self.investigacion = inv.investigacion(self.investigacion_rows, self.importaciones,
                                               self.keywords, self.obras,
                                               self.faltan_tabs[faltan:])
        self.campanas_plan = pub.campanas(self.publicidad, self.obras, self.approvals,
                                          self.topes, self.pedidos_rows, self.campanas,
                                          self.fuentes, self.now)

    def _opcional(self, book, nombre: str) -> list[dict]:
        from ..workbook import GoogleSetupError

        try:
            return book.read(nombre)
        except GoogleSetupError:
            self.faltan_tabs.append(nombre)
            return []

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
    if path == "/publicidad":
        clave = params.get("p", "30")
        per = m.periodo(clave if clave in m.PERIODOS else "30", d.now)
        datos = pub.resumen(d.campanas_plan, d.pedidos_rows, d.campanas, d.fuentes, per, d.now)
        if "Publicidad" in d.faltan_tabs:  # no tab is a missing number, not a zero
            datos = [x if x.fuente.startswith(("Meta", "Shopify", "Pedidos")) else
                     m.faltante(x.etiqueta, x.fuente, x.periodo, x.definicion,
                                "La hoja aún no tiene la pestaña Publicidad.", x.formato)
                     for x in datos]
        return views.publicidad_view(
            d.campanas_plan, datos,
            pub.atribucion(d.pedidos_rows, per),
            pub.plan_por_plataforma(d.campanas_plan, pub.topes(d.topes)), per, d.fuentes,
            d.now, banner, d.faltan_tabs)
    if path == "/clientes":
        clave = params.get("p", "30")
        per = m.periodo(clave if clave in m.PERIODOS else "30", d.now)
        filtro = params.get("f", "todo")
        filtro = filtro if filtro in cli.FILTROS else "todo"
        return views.clientes_view(
            cli.filtrar(d.clientes, filtro),
            cli.resumen(d.clientes, d.pedidos_rows, d.fuentes, per, d.now),
            cli.origenes(d.clientes), filtro, per, d.fuentes, d.now, banner)
    if path == "/investigacion":
        categoria = params.get("c", "")
        categoria = categoria if categoria in inv.CATEGORIA else ""
        return investigacion_view(d.investigacion, inv.resumen(d.investigacion,
                                                                     d.fuentes, d.now),
                                        categoria, d.fuentes, d.now, banner)
    if path == "/finanzas":
        clave = params.get("p", "mes")
        clave = clave if clave in dict(fin.PERIODOS) else "mes"
        return fin.render(fin.calcular(d, clave), d.fuentes, d.now, banner)
    if path == "/semana":
        clave = "actual" if params.get("s") == "actual" else "pasada"
        return sem.render(sem.calcular(d, clave), d.now, banner)
    if path == "/fuentes":
        return views.fuentes_view(d.fuentes, d.now, banner)
    if path == "/aprobar":
        return views.aprobar(d.approvals, banner)
    return None
