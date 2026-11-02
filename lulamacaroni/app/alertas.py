"""Alerts and the daily summary ("Resumen del día": qué pasó, qué requiere atención, 3 acciones).

Lorena's requirements, section 1: a daily summary of what happened, what needs her
attention and the three priority actions, and an alerts view. Every alert says where it
comes from and when that source was last updated, like every number in the app.

Rules only for now. When the Asistente (Claude) is connected it gets the same alert list
as input and writes the summary in prose; the rules stay as the safety net.

Pure functions over workbook rows: no network, no writes. ``python -m
lulamacaroni.app.alertas`` prints today's summary as plain text (read-only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from . import metrics as m

URGENTE, ATENCION, INFO = "urgente", "atencion", "info"
NIVELES = (URGENTE, ATENCION, INFO)
NIVEL_NOMBRE = {URGENTE: "Urgente", ATENCION: "Requiere atención", INFO: "Para saber"}
SIN_CONEXION = "fuente no conectada"

# Sources that have a slot on the summary before they are connected. Each plugs in by
# stamping its row in Fuentes (and, for a sales channel, writing Pedidos rows with its
# ``canal``): the slot then switches from "—" to the real number with no other change.
CANALES_VENTA = (("shopify", "shopify"), ("etsy", "etsy"))   # (fuente, Pedidos.canal)
FUENTE_CONTABLE = "quickbooks"


@dataclass
class Alerta:
    nivel: str
    area: str            # tienda | pedidos | aprobaciones | fuentes | finanzas | contenido
                         # | publicidad | clientes
    titulo: str
    detalle: str
    fuente: str
    actualizado: datetime | None
    enlace: str
    accion: str = ""     # imperative line for "tus 3 acciones"; "" = not an action
    prioridad: int = 50  # lower first
    items: list[str] = field(default_factory=list)


def _act(fuentes: dict[str, m.EstadoFuente], clave: str) -> datetime | None:
    f = fuentes.get(clave)
    return f.actualizado if f else None


def _lista(items: list[str], n: int = 3) -> str:
    shown = ", ".join(f"“{t}”" for t in items[:n])
    return shown + (f" y {len(items) - n} más" if len(items) > n else "")


def calcular(pedidos_rows: list[dict], pedidos: list[m.Pedido], productos: list[m.Producto],
             fuentes: dict[str, m.EstadoFuente], excepciones: list[dict],
             pendientes: int, fuentes_rows: list[dict] | None = None) -> list[Alerta]:
    """Every alert that applies right now, most important first."""
    out: list[Alerta] = []
    shop = fuentes["shopify"]
    shop_act = shop.actualizado

    # -- store setup: who prints what (from each variant's stock locations) ------------
    en_venta = [p for p in productos if p.estado == "publicado" and p.canal == "shopify"]
    dobles = [p for p in en_venta
              if "varias" in p.rutas or {"prodigi-app", "frame-it-easy-app"} <= p.rutas]
    sin_imprenta = [p for p in en_venta if p not in dobles
                    and p.rutas & {"manual", "desconocida"}]
    if dobles:
        out.append(Alerta(
            URGENTE, "tienda",
            f"{len(dobles)} producto(s) en venta con dos imprentas",
            "Sus variantes están en la ubicación de Prodigi y en la de Frame It Easy a la vez. "
            f"Un pedido podría imprimirse y cobrarse dos veces: {_lista([p.titulo for p in dobles])}.",
            "Shopify (productos y ubicaciones de inventario)", shop_act, "/catalogo?f=avisos",
            "Deja cada producto en una sola imprenta en Shopify", 5,
            [p.titulo for p in dobles]))
    if sin_imprenta:
        variantes = sum(p.variantes for p in sin_imprenta)
        out.append(Alerta(
            URGENTE, "tienda",
            f"{len(sin_imprenta)} producto(s) en venta que ninguna imprenta recibe",
            f"{variantes} variante(s) están en la ubicación “Manual” de Shopify (o sin ubicación "
            "clara), así que un pedido no le llega a Prodigi ni a Frame It Easy. Puede ser "
            f"también por qué la tienda los muestra agotados: {_lista([p.titulo for p in sin_imprenta])}.",
            "Shopify (productos y ubicaciones de inventario)", shop_act, "/catalogo?f=avisos",
            "Asigna una imprenta a los productos en venta que están en “Manual”", 6,
            [p.titulo for p in sin_imprenta]))
    sin_sku = [p for p in en_venta if p.sin_sku]
    if sin_sku:
        out.append(Alerta(
            ATENCION, "tienda",
            f"{len(sin_sku)} producto(s) en venta con variantes sin SKU",
            "Sin SKU no se pueden ligar a una obra, a su archivo de impresión ni a los costos de "
            f"Prodigi: {_lista([p.titulo for p in sin_sku])}.",
            "Shopify (variantes)", shop_act, "/catalogo?f=avisos",
            "Pon SKU a las variantes de los productos en venta", 35,
            [p.titulo for p in sin_sku]))

    # -- orders ---------------------------------------------------------------------------
    for p in pedidos:
        if p.atencion:
            out.append(Alerta(
                URGENTE, "pedidos", f"Pedido #{p.numero} ({p.canal.capitalize()})",
                p.atencion + ".", m.FUENTE_BY_KEY.get(p.canal, m.FUENTE_BY_KEY["shopify"]).nombre,
                _act(fuentes, p.canal), "/pedidos",
                f"Revisa el pedido #{p.numero}: {p.atencion.lower()}", 8))
    abiertas = [e for e in excepciones if e.get("estado") in ("abierta", "en-curso")]
    if abiertas:
        out.append(Alerta(
            ATENCION, "pedidos", f"{len(abiertas)} excepción(es) abierta(s)",
            "; ".join(f"{e.get('tipo') or 'excepción'} {e.get('referencia') or ''}".strip()
                      for e in abiertas[:5]) + ".",
            "Libro de datos (Excepciones)", None, "/pedidos",
            f"Resuelve {len(abiertas)} excepción(es) abierta(s)", 25))
    reales = {r["pedido_id"] for r in pedidos_rows if r.get("estado") != "cancelado"}
    if shop.conectada and not reales:
        out.append(Alerta(
            ATENCION, "pedidos", "Aún no hay pedidos reales",
            "Shopify no tiene pedidos en los últimos 60 días, sin contar los de prueba ni los "
            "cancelados. Antes de abrir conviene un pedido de prueba completo: que llegue a la "
            "imprenta correcta y que el correo de confirmación le llegue al comprador.",
            "Shopify (pedidos, últimos 60 días)", shop_act, "/pedidos",
            "Haz un pedido de prueba completo antes del lanzamiento", 40))

    # -- approvals ------------------------------------------------------------------------
    if pendientes:
        out.append(Alerta(
            ATENCION, "aprobaciones", f"{pendientes} cosa(s) esperan tu aprobación",
            "Nada se publica, gasta ni reembolsa sin tu aprobación.",
            "Aprobaciones", None, "/aprobar", f"Aprueba o rechaza {pendientes} pendiente(s)", 10))

    # -- sources --------------------------------------------------------------------------
    for f in fuentes.values():
        if f.estado == "error":
            out.append(Alerta(
                ATENCION, "fuentes", f"{f.info.nombre}: la última sincronización falló",
                f.nota or "Los números de esta fuente pueden estar incompletos.",
                f.info.nombre, f.actualizado, "/fuentes",
                f"Revisa la conexión de {f.info.nombre}", 20))
        elif f.estado == "atrasada":
            out.append(Alerta(
                ATENCION, "fuentes", f"{f.info.nombre}: datos atrasados",
                f"No se actualiza desde {m.dia(f.actualizado) if f.actualizado else 'nunca'}; "
                "los números que salen de aquí pueden no estar al día.",
                f.info.nombre, f.actualizado, "/fuentes",
                f"Vuelve a sincronizar {f.info.nombre}", 20))
    pagos = fuentes.get("shopify-pagos")
    if shop.conectada and pagos and pagos.estado == "sin-conectar":
        out.append(Alerta(
            ATENCION, "finanzas", "Pagos de Shopify sin conectar",
            "Sin los pagos (payouts) no se sabe cuánto dinero está por llegar al banco.",
            pagos.info.nombre, None, "/fuentes", "", 45))
    for r in fuentes_rows or []:
        if r.get("fuente") in ("prodigi", "prodigi-sandbox") and "sin pedido de canal" in (
                r.get("nota") or ""):
            out.append(Alerta(
                ATENCION, "pedidos", "Pedidos de Prodigi que no se ligan a una venta",
                f"{r.get('nota')}. Su costo no entra en el margen hasta ligarlos.",
                "Prodigi" + (" (sandbox)" if r.get("fuente") == "prodigi-sandbox" else ""),
                m.parse_dt(r.get("ultima_actualizacion")), "/pedidos",
                "Revisa los pedidos de Prodigi sin venta", 22))

    # -- slots waiting for a source (never shown as zero) ------------------------------------
    for clave, que in (("etsy", "Las ventas, comisiones y pedidos de Etsy"),
                       (FUENTE_CONTABLE, "Gastos, utilidad del negocio y conciliación")):
        f = fuentes.get(clave)
        if f and not f.conectada:
            out.append(Alerta(
                INFO, "fuentes", f"{f.info.nombre}: {SIN_CONEXION}",
                f"{que} aparecen como “—” hasta que se conecte ({f.nota or f.info.fase}). "
                "No se cuentan como cero.",
                f.info.nombre, None, "/fuentes", "", 90))

    out.sort(key=lambda a: (NIVELES.index(a.nivel), a.prioridad))
    return out


def catalogo_y_contenido(fichas, piezas, fuentes: dict[str, m.EstadoFuente],
                         now: datetime) -> list[Alerta]:
    """Print files that can't print a live size, and content whose approval is not valid."""
    from .catalogo import avisos_archivo
    from .contenido import alertas as contenido_alertas

    out = []
    malos = avisos_archivo(fichas)
    if malos:
        n = sum(k for _, k in malos)
        out.append(Alerta(
            URGENTE, "tienda", f"{n} variante(s) en venta con archivo que no sirve para su tamaño",
            "Proporción distinta o resolución por debajo del mínimo. No se recorta ni se estira: "
            f"hace falta un archivo para ese tamaño o quitar el tamaño: {_lista([t for t, _ in malos])}.",
            "Libro de datos (Variantes) + Shopify", _act(fuentes, "shopify"), "/catalogo?f=avisos",
            "Revisa los archivos de impresión que no sirven para su tamaño", 7,
            [t for t, _ in malos]))
    for p in contenido_alertas(piezas, now):
        cuando = m.dia(p.fecha) if p.fecha else "sin fecha"
        out.append(Alerta(
            URGENTE if p.estado in ("aprobado", "programado") else ATENCION, "contenido",
            f"{p.titulo} ({p.plataforma.capitalize() or 'contenido'}, {cuando})",
            p.gate.texto + ". Nada se publica sin tu aprobación del texto e imagen exactos.",
            "Libro de datos (Contenido + Aprobaciones)", now, "/contenido",
            f"Revisa la aprobación de “{p.titulo}”", 9))
    return out


def publicidad(cs, now: datetime) -> list[Alerta]:
    """Campaigns over a spend limit, or approved/running without a valid approval."""
    from .publicidad import PLATAFORMA, alertas as pub_alertas

    out = []
    for c in pub_alertas(cs):
        out.append(Alerta(
            URGENTE if c.estado in ("aprobada", "activa") else ATENCION, "publicidad",
            f"Campaña “{c.nombre}” ({PLATAFORMA.get(c.plataforma, c.plataforma or 'anuncios')})",
            "; ".join(c.avisos) + ". Ningún anuncio se lanza ni cambia de presupuesto sin tu "
            "aprobación del plan exacto.",
            "Libro de datos (Publicidad + Topes + Aprobaciones)", now, "/publicidad",
            f"Revisa la campaña “{c.nombre}”", 8))
    return out


def clientes(cs, fuentes: dict[str, m.EstadoFuente], now: datetime) -> list[Alerta]:
    """Customer follow-ups whose date has passed (Clientes.seguimiento)."""
    from .clientes import vencidos

    out = []
    for c in vencidos(cs):
        s = c.seguimiento
        out.append(Alerta(
            ATENCION, "clientes", f"Seguimiento vencido: {c.nombre}",
            f"“{s.texto}”, para el {m.dia(datetime.combine(s.para, datetime.min.time(), m.TZ))}.",
            "Libro de datos (Clientes)", now, "/clientes?f=seguimiento",
            f"Atiende el seguimiento de {c.nombre}", 12))
    return out


def acciones(alertas: list[Alerta], n: int = 3) -> list[Alerta]:
    """The day's priority actions: the first ``n`` alerts that ask for something."""
    return [a for a in alertas if a.accion and a.nivel != INFO][:n]


# --- slots: sales by channel and accounting ----------------------------------------------------

def ventas_canal(pedidos_rows: list[dict], fuentes: dict[str, m.EstadoFuente],
                 clave: str, canal: str, per: m.Periodo) -> m.Dato:
    f = fuentes[clave]
    nombre = f.info.nombre
    definicion = ("Venta bruta − descuentos − reembolsos de los pedidos creados en el periodo, "
                  "sin impuestos ni envío. Sin cancelados ni pedidos de prueba.")
    if not f.conectada:
        return m.faltante(f"Ventas {nombre}", nombre, per.texto, definicion,
                          f"{SIN_CONEXION.capitalize()} ({f.nota or f.info.fase}).",
                          enlace="/fuentes")
    rows = [r for r in pedidos_rows if r.get("canal") == canal and r.get("estado") in m.VIVOS]
    act = [r for r in rows if per.contiene(m.parse_dt(r.get("fecha")))]
    prev = [r for r in rows if per.contiene_previo(m.parse_dt(r.get("fecha")))]
    n = len({r["pedido_id"] for r in act})
    return m.Dato(f"Ventas {nombre}", round(sum(m.neto_linea(r) for r in act), 2), "real",
                  nombre, per.texto, definicion, f.actualizado, "usd",
                  round(sum(m.neto_linea(r) for r in prev), 2), nota=f"{n} pedido(s)",
                  enlace="/pedidos")


def gastos_mes(gastos: list[dict], fuentes: dict[str, m.EstadoFuente], now: datetime) -> m.Dato:
    f = fuentes[FUENTE_CONTABLE]
    local = now.astimezone(m.TZ)
    inicio = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    periodo = f"{m.dia(inicio)} a {m.dia(local)}, hora de CDMX"
    definicion = ("Gastos del negocio registrados en contabilidad este mes (suscripciones, "
                  "publicidad, imprenta, etc.). No incluye el costo por pedido.")
    if not f.conectada:
        return m.faltante("Gastos del mes", f.info.nombre, periodo, definicion,
                          f"{SIN_CONEXION.capitalize()} ({f.nota or f.info.fase}).",
                          enlace="/fuentes")
    rows = [g for g in gastos if (d := m.parse_dt(g.get("fecha"))) and inicio <= d <= local]
    return m.Dato("Gastos del mes", round(sum(m.num(g.get("monto")) or 0 for g in rows), 2),
                  "real", f.info.nombre, periodo, definicion, f.actualizado, "usd",
                  nota=f"{len(rows)} gasto(s)", enlace="/fuentes")


# --- the daily summary -----------------------------------------------------------------------

@dataclass
class ResumenDia:
    hoy: m.Resumen
    alertas: list[Alerta]
    acciones: list[Alerta]
    ranuras: list[m.Dato]

    def cuenta(self, nivel: str) -> int:
        return sum(1 for a in self.alertas if a.nivel == nivel)

    @property
    def que_paso(self) -> str:
        ventas = self.hoy.datos[0]
        if ventas.calidad == "faltante":
            return "Aún no hay canales de venta conectados."
        from .views import usd  # formatting lives with the views
        texto = (f"Hoy: {self.hoy.pedidos_periodo} pedido(s), {usd(ventas.valor)} netos "
                 f"({ventas.fuente}).")
        if ventas.previo is not None:
            texto += f" Mismo día la semana pasada: {usd(ventas.previo)}."
        if self.hoy.mas_vendido:
            texto += f" Lo más vendido: “{self.hoy.mas_vendido}”."
        return texto


def resumen_dia(d, now: datetime | None = None) -> ResumenDia:
    """Build the summary from a :class:`lulamacaroni.app.screens.Datos`."""
    now = now or d.now
    per = m.periodo("hoy", now)
    hoy = m.resumen(d.pedidos_rows, d.campanas, d.fuentes, per, d.pagos)
    lista = calcular(d.pedidos_rows, d.pedidos, d.productos, d.fuentes, d.excepciones,
                     d.pendientes, d.fuentes_rows)
    lista += catalogo_y_contenido(getattr(d, "fichas", []), getattr(d, "piezas", []),
                                  d.fuentes, now)
    lista += publicidad(getattr(d, "campanas_plan", []), now)
    lista += clientes(getattr(d, "clientes", []), d.fuentes, now)
    lista.sort(key=lambda a: (NIVELES.index(a.nivel), a.prioridad))
    ranuras = [ventas_canal(d.pedidos_rows, d.fuentes, f, c, per) for f, c in CANALES_VENTA]
    ranuras.append(gastos_mes(d.gastos, d.fuentes, now))
    return ResumenDia(hoy, lista, acciones(lista), ranuras)


def texto(r: ResumenDia, now: datetime) -> str:
    """Plain-text summary (for a terminal now; WhatsApp or email later, after approval)."""
    from .views import valor

    lines = [f"Resumen del día · {m.dia(now)}", "", f"Qué pasó: {r.que_paso}", ""]
    lines.append(f"Requiere atención: {r.cuenta(URGENTE)} urgente(s), "
                 f"{r.cuenta(ATENCION)} aviso(s).")
    lines.append("Tus 3 acciones de hoy:")
    lines += [f"  {i}. {a.accion}" for i, a in enumerate(r.acciones, 1)] or ["  Nada urgente."]
    lines += ["", "Por canal y contabilidad:"]
    for dato in r.ranuras:
        extra = f" · {dato.nota}" if dato.nota else ""
        lines.append(f"  {dato.etiqueta}: {valor(dato)}{extra}")
    lines += ["", "Alertas:"]
    for a in r.alertas:
        cuando = m.dia(a.actualizado) if a.actualizado else "—"
        lines.append(f"  [{NIVEL_NOMBRE[a.nivel]}] {a.titulo}. {a.detalle} "
                     f"(fuente: {a.fuente}; actualizado: {cuando})")
    return "\n".join(lines)


def main() -> int:
    from ..approval.store import SheetsStore, open_store
    from ..localbook import open_workbook
    from ..workbook import Workbook
    from .screens import Datos

    book = open_workbook()
    store = SheetsStore(book) if isinstance(book, Workbook) else open_store()
    d = Datos(book, store)
    print(texto(resumen_dia(d), d.now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
