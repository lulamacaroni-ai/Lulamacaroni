"""Finanzas: what was sold, what it cost, what reached the bank, and what is still unknown.

Lorena's rules (requirements, sections 1, 13 and 14):

* The gross sale and the deposit are kept apart. A Shopify payout is the same sale, days
  later, with fees already taken out; adding both would count the money twice.
* Sales tax collected is shown, but it is not her income: it goes to the state.
* Three different numbers: margin per order, business profit (needs the accounting books)
  and cash flow (needs the bank). The last two stay "fuente no conectada" until QuickBooks
  exists. Never a zero.
* Each platform's own attribution is a separate view; nothing is added across platforms.
* US prints (USD) and Mexico originals (MXN) are never added together.

Every number is a :class:`metrics.Dato`. Pure functions over workbook rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html import escape

from . import metrics as m
from .alertas import SIN_CONEXION, gastos_mes

US, MX = "US-POD", "MX-original"
FUENTE_LIBRO_MX = "Pedidos (captura manual de ventas de originales)"
FUENTE_PAGOS = "Pagos de Shopify (payouts)"


# --- periods -----------------------------------------------------------------------------

@dataclass(frozen=True)
class PeriodoFin(m.Periodo):
    etiqueta: str = ""

    @property
    def texto(self) -> str:  # fin is exclusive; show the last day included
        ultimo = self.fin - timedelta(seconds=1)
        return f"{self.etiqueta}: {m.dia(self.inicio)} a {m.dia(ultimo)}, hora de CDMX"


PERIODOS = (("mes", "Este mes"), ("mes-ant", "Mes pasado"), ("7", "7 días"), ("30", "30 días"))


def _inicio_mes(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _mes_antes(inicio: datetime) -> datetime:
    return _inicio_mes(inicio - timedelta(days=1))


def periodo(clave: str, now: datetime) -> m.Periodo:
    local = now.astimezone(m.TZ)
    if clave == "mes":
        ini = _inicio_mes(local)
        prev = _mes_antes(ini)
        prev_fin = min(prev + (local - ini), ini)
        return PeriodoFin("mes", "Este mes", ini, local, prev, prev_fin,
                          "mismos días del mes anterior", "este mes")
    if clave == "mes-ant":
        fin = _inicio_mes(local)
        ini = _mes_antes(fin)
        return PeriodoFin("mes-ant", "Mes pasado", ini, fin, _mes_antes(ini), ini,
                          "el mes anterior", "mes pasado")
    return m.periodo(clave if clave in ("7", "30") else "30", now)


# --- helpers -----------------------------------------------------------------------------

def _vivos(rows: list[dict], linea: str) -> list[dict]:
    return [r for r in rows if r.get("estado") in m.VIVOS and (r.get("linea") or US) == linea]


def _en(rows: list[dict], per: m.Periodo, previo: bool = False) -> list[dict]:
    test = per.contiene_previo if previo else per.contiene
    return [r for r in rows if test(m.parse_dt(r.get("fecha")))]


def _suma(rows: list[dict], col: str) -> float:
    return round(sum(m.num(r.get(col)) or 0 for r in rows), 2)


def _canales(fuentes: dict[str, m.EstadoFuente]):
    shop, etsy = fuentes["shopify"], fuentes["etsy"]
    vivos = [f for f in (shop, etsy) if f.conectada]
    fuente = " + ".join(f.info.nombre for f in vivos) or "Shopify + Etsy"
    nota = "" if etsy.conectada else f"Etsy: {SIN_CONEXION} ({etsy.nota or etsy.info.fase})."
    act = min((f.actualizado for f in vivos if f.actualizado), default=None)
    return vivos, fuente, nota, act


# --- 1. the sale ---------------------------------------------------------------------------

VENTA = (
    ("Venta bruta", "venta_bruta", "Precio de los productos vendidos, antes de descuentos, sin "
     "impuestos ni envío. Pedidos creados en el periodo, sin cancelados ni de prueba."),
    ("Descuentos", "descuento", "Descuentos aplicados a esos pedidos."),
    ("Reembolsos", "reembolso", "Lo devuelto al cliente de esos pedidos (por fecha del pedido, "
     "no del reembolso)."),
)


def venta(pedidos_rows: list[dict], fuentes: dict[str, m.EstadoFuente],
          per: m.Periodo) -> list[m.Dato]:
    vivos, fuente, nota, act = _canales(fuentes)
    rows = _vivos(pedidos_rows, US)
    a, p = _en(rows, per), _en(rows, per, True)
    if not vivos:
        defs = [*VENTA, ("Ventas netas", "", ""), ("Envío cobrado", "", ""),
                ("Impuestos cobrados", "", "")]
        return [m.faltante(e, "Shopify + Etsy", per.texto, d or e, "Ningún canal de venta "
                           "conectado.", enlace="/fuentes") for e, _, d in defs]
    out = [m.Dato(e, _suma(a, c), "real", fuente, per.texto, d, act, "usd", _suma(p, c),
                  nota=nota, enlace="/pedidos") for e, c, d in VENTA]
    neto = round(sum(m.neto_linea(r) for r in a), 2)
    out.append(m.Dato(
        "Ventas netas", neto, "real", fuente, per.texto,
        "Venta bruta − descuentos − reembolsos. Es tu ingreso por producto, antes de costos.",
        act, "usd", round(sum(m.neto_linea(r) for r in p), 2),
        nota=f"{len({r['pedido_id'] for r in a})} pedido(s). {nota}".strip(), enlace="/pedidos"))
    out.append(m.Dato("Envío cobrado", _suma(a, "envio_cobrado"), "real", fuente, per.texto,
                      "Lo que el cliente pagó de envío. Se suma al ingreso del pedido.", act,
                      "usd", _suma(p, "envio_cobrado"), nota=nota))
    out.append(m.Dato("Impuestos cobrados", _suma(a, "impuesto_cobrado"), "real", fuente,
                      per.texto, "Impuesto sobre ventas cobrado al cliente. No es ingreso tuyo: "
                      "se entrega al estado (Etsy lo entrega por ti; el contador define el resto). "
                      "No entra en ventas ni en margen.", act, "usd",
                      _suma(p, "impuesto_cobrado"), nota=nota))
    return out


# --- 2. costs per order --------------------------------------------------------------------

COSTOS = (
    ("Comisiones del canal", "comision_canal", "comisión",
     "Comisión de cobro de Shopify Payments (2.9% + 30¢ por pedido en el plan Basic) y, "
     "cuando exista, la de Etsy."),
    ("Impresión (Prodigi)", "costo_pod", "coste de impresión",
     "Lo que Prodigi cobra por imprimir cada producto vendido."),
    ("Envío de la imprenta", "envio_pod", "envío de imprenta",
     "Lo que Prodigi cobra por enviar al cliente."),
)


def costos(pedidos_rows: list[dict], fuentes: dict[str, m.EstadoFuente],
           per: m.Periodo) -> list[m.Dato]:
    vivos, fuente, nota, act = _canales(fuentes)
    a = _en(_vivos(pedidos_rows, US), per)
    out = []
    for etiqueta, col, corto, definicion in COSTOS:
        src = ("Comisiones de Shopify Payments" if col == "comision_canal"
               else "Cargos de Prodigi")
        definicion = f"{definicion} Pedidos creados en el periodo."
        if not vivos:
            out.append(m.faltante(etiqueta, src, per.texto, definicion,
                                  "Ningún canal de venta conectado.", enlace="/fuentes"))
            continue
        sin = [r for r in a if m.num(r.get(col)) is None]
        if sin:
            out.append(m.faltante(etiqueta, src, per.texto, definicion,
                                  f"{len(sin)} de {len(a)} línea(s) sin {corto}: no se cuenta "
                                  "como cero.", enlace="/pedidos"))
            continue
        estimado = col != "comision_canal" and any(not r.get("pod_pedido_id") for r in a)
        out.append(m.Dato(etiqueta, _suma(a, col), "estimado" if estimado else "real", src,
                          per.texto, definicion, act, "usd",
                          nota=("Alguna línea usa precio de lista, no el cargo de Prodigi."
                                if estimado else nota), enlace="/pedidos"))
    return out


# --- 3. margin ----------------------------------------------------------------------------

def margen(pedidos_rows: list[dict], campanas: list[dict], fuentes: dict[str, m.EstadoFuente],
           per: m.Periodo, pagos: list[dict]) -> list[m.Dato]:
    """Margin before and after ads (same rules as Inicio), plus the per-order view."""
    us = [r for r in pedidos_rows if (r.get("linea") or US) == US]
    res = m.resumen(us, campanas, fuentes, per, pagos)
    by = {d.etiqueta: d for d in res.datos}
    antes, ventas = by["Margen antes de anuncios"], by["Ventas netas"]
    out = [antes]
    definicion = "Margen antes de anuncios ÷ ventas netas del periodo."
    if antes.calidad == "faltante" or ventas.calidad == "faltante" or not ventas.valor:
        out.append(m.faltante("Margen sobre ventas", antes.fuente, per.texto, definicion,
                              "Sin ventas en el periodo." if ventas.calidad != "faltante"
                              and antes.calidad != "faltante" else antes.nota, "pct"))
    else:
        out.append(m.Dato("Margen sobre ventas", round(antes.valor / ventas.valor * 100, 1),
                          antes.calidad, antes.fuente, per.texto, definicion, antes.actualizado,
                          "pct"))
    n = res.pedidos_periodo
    definicion = "Margen antes de anuncios ÷ número de pedidos del periodo."
    if antes.calidad == "faltante" or not n:
        out.append(m.faltante("Margen por pedido", antes.fuente, per.texto, definicion,
                              "Sin pedidos en el periodo." if antes.calidad != "faltante"
                              else antes.nota))
    else:
        out.append(m.Dato("Margen por pedido", round(antes.valor / n, 2), antes.calidad,
                          antes.fuente, per.texto, definicion, antes.actualizado, "usd",
                          nota=f"{n} pedido(s)"))
    out.append(by["Gasto publicitario"])
    despues = by["Margen de contribución"]
    despues.etiqueta = "Margen después de anuncios"
    out.append(despues)
    return out


# --- 4. deposits ---------------------------------------------------------------------------

def depositos(pagos: list[dict], fuentes: dict[str, m.EstadoFuente],
              per: m.Periodo) -> list[m.Dato]:
    f = fuentes.get("shopify-pagos")
    out: list[m.Dato] = []
    defs = (
        ("Depositado", "monto_depositado", "Pagos (payouts) de Shopify Payments ya pagados al "
         "banco, por fecha del pago. Ya vienen sin comisiones. Es la misma venta, días después: "
         "no se suma a las ventas."),
        ("Comisiones en depósitos", "comisiones", "Comisiones que Shopify descontó de los pagos "
         "del periodo."),
        ("Retenciones", "retenciones", "Dinero que Shopify retuvo como reserva en los pagos del "
         "periodo."),
    )
    if f is None or not f.conectada:
        nota = (f"{SIN_CONEXION.capitalize()}: falta dar a la app de Shopify los permisos de "
                "pagos." if f is None or f.estado == "sin-conectar" else "Los pagos tienen error.")
        out += [m.faltante(e, FUENTE_PAGOS, per.texto, d, nota, enlace="/fuentes")
                for e, _, d in defs]
    else:
        shop = [p for p in pagos if p.get("canal") == "shopify"]
        pagados = [p for p in shop if p.get("estado") == "pagado"]
        a, prev = _en(pagados, per), _en(pagados, per, True)
        for etiqueta, col, definicion in defs:
            out.append(m.Dato(etiqueta, _suma(a, col), "real", FUENTE_PAGOS, per.texto,
                              definicion, f.actualizado, "usd", _suma(prev, col),
                              nota=f"{len(a)} pago(s)" if col == "monto_depositado" else ""))
    out.append(m.por_recibir(pagos, fuentes))
    etsy = fuentes["etsy"]
    out.append(m.faltante("Depósitos de Etsy", "Etsy Payments", per.texto,
                          "Depósitos de Etsy al banco, con sus tarifas y reservas.",
                          f"{SIN_CONEXION.capitalize()} ({etsy.nota or etsy.info.fase}).",
                          enlace="/fuentes"))
    return out


@dataclass
class Pago:
    pago_id: str
    canal: str
    fecha: datetime | None
    estado: str
    monto: float | None
    comisiones: float | None
    retenciones: float | None
    conciliado: str


def lista_pagos(pagos: list[dict], n: int = 12) -> list[Pago]:
    out = [Pago(p.get("pago_id", ""), p.get("canal", ""), m.parse_dt(p.get("fecha")),
                p.get("estado", ""), m.num(p.get("monto_depositado")), m.num(p.get("comisiones")),
                m.num(p.get("retenciones")), p.get("conciliado") or "no") for p in pagos]
    out.sort(key=lambda p: p.fecha or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return out[:n]


# --- 5. accounting (QuickBooks) ------------------------------------------------------------

def contabilidad(gastos: list[dict], fuentes: dict[str, m.EstadoFuente], per: m.Periodo,
                 now: datetime) -> list[m.Dato]:
    qb = fuentes["quickbooks"]
    nota = f"{SIN_CONEXION.capitalize()} ({qb.nota or qb.info.fase})."
    out = [gastos_mes(gastos, fuentes, now)]
    if qb.conectada:  # only the books can say these; until then they stay missing
        nota = "Aún no se calcula desde QuickBooks."
    out.append(m.faltante(
        "Beneficio del negocio", "QuickBooks", per.texto,
        "Margen después de anuncios − gastos fijos y suscripciones (repartidos con un criterio "
        "explícito). Distinto del margen por pedido.", nota, enlace="/fuentes"))
    out.append(m.faltante(
        "Flujo de efectivo", "QuickBooks + banco (Chase)", per.texto,
        "Dinero que entró al banco − dinero que salió. Distinto del beneficio: un pago puede "
        "llegar semanas después de la venta.", nota, enlace="/fuentes"))
    out.append(m.faltante(
        "Diferencias de conciliación", "QuickBooks", per.texto,
        "Depósitos que no cuadran con sus ventas, comisiones, reembolsos y retenciones.",
        nota, "n", enlace="/fuentes"))
    return out


# --- 6. by channel and line ----------------------------------------------------------------

@dataclass
class FilaCanal:
    nombre: str
    moneda: str
    ventas: m.Dato
    margen: m.Dato
    deposito: m.Dato


def por_canal(pedidos_rows: list[dict], campanas: list[dict], pagos: list[dict],
              fuentes: dict[str, m.EstadoFuente], per: m.Periodo) -> list[FilaCanal]:
    filas = []
    shop, etsy = fuentes["shopify"], fuentes["etsy"]
    dep = depositos(pagos, fuentes, per)[0]
    for f, canal in ((shop, "shopify"), (etsy, "etsy")):
        rows = [r for r in pedidos_rows if r.get("canal") == canal
                and (r.get("linea") or US) == US]
        solo = {k: v for k, v in fuentes.items()}
        otro = etsy if canal == "shopify" else shop
        solo[otro.info.clave] = m.EstadoFuente(otro.info, "sin-conectar", None)
        if not f.conectada:
            nota = f"{SIN_CONEXION.capitalize()} ({f.nota or f.info.fase})."
            vacio = [m.faltante(e, f.info.nombre, per.texto, e, nota, enlace="/fuentes")
                     for e in ("Ventas netas", "Margen antes de anuncios", "Depositado")]
            filas.append(FilaCanal(f.info.nombre, "USD", *vacio))
            continue
        res = {d.etiqueta: d for d in m.resumen(rows, campanas, solo, per, pagos).datos}
        filas.append(FilaCanal(f.info.nombre, "USD", res["Ventas netas"],
                               res["Margen antes de anuncios"], dep))
    filas.append(FilaCanal("Originales México", "MXN", *originales_mx(pedidos_rows, per)))
    return filas


def originales_mx(pedidos_rows: list[dict], per: m.Periodo) -> list[m.Dato]:
    """Mexico originals are recorded by hand in Pedidos (linea MX-original), in MXN with IVA."""
    todas = [r for r in pedidos_rows if r.get("linea") == MX]
    definicion = ("Ventas de originales en México registradas en el libro (MXN, IVA incluido), "
                  "pedidos del periodo. Solo cuenta lo que se registró.")
    if not todas:
        nota = ("Aún no se registra ninguna venta de originales en el libro: falta el dato, no "
                "es cero.")
        return [m.faltante("Ventas netas", FUENTE_LIBRO_MX, per.texto, definicion, nota, "mxn"),
                m.faltante("Margen", FUENTE_LIBRO_MX, per.texto, "Venta − costos del original.",
                           "Los originales aún no llevan costo en el libro.", "mxn"),
                m.faltante("Depositado", FUENTE_LIBRO_MX, per.texto, "Cobros recibidos.",
                           "Fase 2 (cobro en MXN) aún no existe.", "mxn")]
    a = _en(_vivos(todas, MX), per)
    act = max((m.parse_dt(r.get("fecha")) for r in todas if m.parse_dt(r.get("fecha"))),
              default=None)
    ventas = m.Dato("Ventas netas", round(sum(m.neto_linea(r) for r in a), 2), "real",
                    FUENTE_LIBRO_MX, per.texto, definicion, act, "mxn",
                    nota=f"{len({r['pedido_id'] for r in a})} venta(s)")
    margenes = [m.num(r.get("margen_contribucion")) for r in a]
    if a and all(x is not None for x in margenes):
        mg = m.Dato("Margen", round(sum(margenes), 2), "estimado", FUENTE_LIBRO_MX, per.texto,
                    "Venta − costos del original registrados.", act, "mxn")
    elif not a:
        mg = m.Dato("Margen", 0.0, "real", FUENTE_LIBRO_MX, per.texto,
                    "Venta − costos del original registrados.", act, "mxn")
    else:
        mg = m.faltante("Margen", FUENTE_LIBRO_MX, per.texto,
                        "Venta − costos del original registrados.",
                        "Alguna venta no tiene su costo registrado.", "mxn")
    dep = m.faltante("Depositado", FUENTE_LIBRO_MX, per.texto, "Cobros recibidos.",
                     "Se cobra fuera del sistema (fase 2 pendiente).", "mxn")
    return [ventas, mg, dep]


# --- 7. attribution ------------------------------------------------------------------------

def atribucion_plataformas(campanas: list[dict], fuentes: dict[str, m.EstadoFuente],
                           per: m.Periodo) -> list[m.Dato]:
    """What each ad platform claims, one Dato each. Never added together."""
    out = []
    for clave, plat, nombre in (("meta", "meta", "Meta Ads"), ("pinterest", "pinterest",
                                                               "Pinterest Ads"),
                                ("etsy", "etsy-ads", "Etsy Ads")):
        f = fuentes[clave]
        definicion = (f"Ventas que {nombre} se atribuye con su propia ventana de atribución. "
                      "Vista aparte: no se suma a Shopify ni a otras plataformas.")
        if not f.conectada:
            out.append(m.faltante(f"Según {nombre}", nombre, per.texto, definicion,
                                  f"{SIN_CONEXION.capitalize()} ({f.nota or f.info.fase}).",
                                  enlace="/fuentes"))
            continue
        rows = [c for c in campanas if c.get("plataforma") == plat
                and per.contiene(m.parse_dt(c.get("fecha")))]
        out.append(m.Dato(f"Según {nombre}", _suma(rows, "valor_atribuido"), "estimado",
                          nombre, per.texto, definicion, f.actualizado, "usd",
                          nota=f"{int(_suma(rows, 'compras_atribuidas'))} compra(s) atribuidas"))
    return out


# --- the screen ----------------------------------------------------------------------------

@dataclass
class Finanzas:
    periodo: m.Periodo
    venta: list[m.Dato]
    costos: list[m.Dato]
    margen: list[m.Dato]
    depositos: list[m.Dato]
    pagos: list[Pago]
    contabilidad: list[m.Dato]
    canales: list[FilaCanal]
    origenes: list = field(default_factory=list)
    plataformas: list[m.Dato] = field(default_factory=list)


def calcular(d, clave: str = "mes") -> Finanzas:
    """Everything the Finanzas screen shows, from a :class:`screens.Datos`."""
    from .publicidad import atribucion

    per = periodo(clave, d.now)
    us = [r for r in d.pedidos_rows if (r.get("linea") or US) == US]
    return Finanzas(
        per, venta(d.pedidos_rows, d.fuentes, per), costos(d.pedidos_rows, d.fuentes, per),
        margen(d.pedidos_rows, d.campanas, d.fuentes, per, d.pagos),
        depositos(d.pagos, d.fuentes, per), lista_pagos(d.pagos),
        contabilidad(d.gastos, d.fuentes, per, d.now),
        por_canal(d.pedidos_rows, d.campanas, d.pagos, d.fuentes, per),
        atribucion(us, per) if d.fuentes["shopify"].conectada else [],
        atribucion_plataformas(d.campanas, d.fuentes, per))


ESTADO_PAGO = {"programado": ("amber", "Programado"), "en-transito": ("amber", "En camino"),
               "pagado": ("ok", "Pagado"), "fallido": ("warn", "Falló"),
               "cancelado": ("gray", "Cancelado")}


def render(f: Finanzas, fuentes: dict[str, m.EstadoFuente], now: datetime,
           banner: str = "") -> str:
    from . import views as v
    from .publicidad import ORIGEN

    per = f.periodo
    kpis = lambda ds: f'<div class="grid">{"".join(v._kpi(x, now) for x in ds)}</div>'  # noqa: E731
    chips = "".join(
        f'<a class="chip{" on" if k == per.clave else ""}" href="/finanzas?p={k}">{t}</a>'
        for k, t in PERIODOS)
    body = [
        '<h1>Finanzas</h1><p class="sub">Lo que vendiste, lo que costó y lo que llegó al '
        "banco. Solo lectura. La venta y el depósito van separados: el depósito es la misma "
        "venta, días después y sin comisiones, así que nunca se suman.</p>",
        f'<div class="chips">{chips}<span class="vs">vs {escape(per.comparacion)}</span></div>',
        f'<p class="meta">{escape(per.texto)} · Prints EUA en dólares. Los originales de México '
        "van aparte, en pesos.</p>",
        "<h2>1 · Venta (Prints EUA)</h2>", kpis(f.venta),
        "<h2>2 · Costos por pedido</h2>", kpis(f.costos),
        "<h2>3 · Margen</h2>", kpis(f.margen),
        "<h2>4 · Depósitos (lo que llega al banco)</h2>", kpis(f.depositos),
    ]
    if f.pagos:
        rows = []
        for p in f.pagos:
            cls, txt = ESTADO_PAGO.get(p.estado, ("gray", p.estado or "—"))
            dinero = lambda x: v.usd(x) if x is not None else "—"  # noqa: E731
            rows.append(
                f"<tr><td>{escape(v.fecha(p.fecha, hora=False))}<br><span class='meta'>"
                f"{escape(v.CANAL.get(p.canal, p.canal))}</span></td>"
                f"<td><span class='badge {cls}'>{escape(txt)}</span></td>"
                f"<td>{dinero(p.monto)}</td><td>{dinero(p.comisiones)}</td>"
                f"<td>{dinero(p.retenciones)}</td><td>{'sí' if p.conciliado == 'si' else 'no'}"
                "</td></tr>")
        body.append("<div class='tablebox'><table><thead><tr><th>Fecha</th><th>Estado</th>"
                    "<th>Depósito</th><th>Comisiones</th><th>Retenido</th><th>Conciliado</th>"
                    f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")
    elif fuentes["shopify-pagos"].conectada:
        body.append('<p class="empty">Shopify aún no ha hecho ningún pago (payout). Cero real.'
                    "</p>")
    body.append('<p class="legend">Conciliado = el depósito ya se cuadró contra sus ventas en '
                "contabilidad. Sin QuickBooks conectado, todos quedan en “no”.</p>")

    body += ["<h2>5 · Contabilidad (QuickBooks)</h2>", kpis(f.contabilidad)]

    rows = "".join(
        f"<tr><td><strong>{escape(c.nombre)}</strong><br><span class='meta'>{c.moneda}</span>"
        f"</td><td>{v._celda(c.ventas)}</td><td>{v._celda(c.margen)}</td>"
        f"<td>{v._celda(c.deposito)}</td></tr>" for c in f.canales)
    body.append("<h2>6 · Por canal</h2><div class='tablebox'><table><thead><tr><th>Canal</th>"
                "<th>Ventas netas</th><th>Margen antes de anuncios</th><th>Depositado</th>"
                f"</tr></thead><tbody>{rows}</tbody></table></div>"
                '<p class="legend">Pasa el dedo o el ratón por un número para ver fuente, '
                "periodo y definición. Dólares y pesos nunca se suman.</p>")

    body.append("<h2>7 · Atribución por plataforma</h2>")
    if not fuentes["shopify"].conectada:
        body.append('<p class="empty">Shopify no está conectado todavía.</p>')
    elif not f.origenes:
        body.append('<p class="empty">Sin pedidos de Shopify en el periodo. Cero real.</p>')
    else:
        rows = "".join(
            f"<tr><td><strong>{escape(ORIGEN[o.clave])}</strong></td><td>{o.pedidos}</td>"
            f"<td>{o.pedidos_anuncio if o.clave != 'sin-dato' else '—'}</td>"
            f"<td>{v.usd(o.ventas)}</td></tr>" for o in f.origenes)
        body.append("<div class='tablebox'><table><thead><tr><th>Origen (según Shopify)</th>"
                    "<th>Pedidos</th><th>De anuncio</th><th>Ventas netas</th></tr></thead>"
                    f"<tbody>{rows}</tbody></table></div>")
    body.append(kpis(f.plataformas))
    body.append('<p class="legend">Shopify: última visita antes del pedido (UTM y sitio que la '
                "refirió); cada pedido cuenta una vez. Lo que cada plataforma se atribuye va "
                "aparte y nunca se suma a Shopify ni entre plataformas. Una atribución no prueba "
                "que el anuncio causó la venta.</p>")
    body.append('<p class="legend"><a href="/fuentes">Fuentes</a>: 0 = cero real · — = falta '
                "el dato · ~ = estimado. Toca “¿De dónde sale?” en cualquier número. "
                '<a href="/semana">Ver resumen semanal</a>.</p>')
    return v.page("Finanzas", "/finanzas", "".join(body), banner)
