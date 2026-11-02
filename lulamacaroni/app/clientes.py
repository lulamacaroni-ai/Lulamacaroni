"""Clientes: who buys, how often, from where, and what Lorena owes each of them.

Lorena's requirements: a clientes view (section 1), per-platform attribution that never
double counts (section 14), customer care continuity and follow-ups (section 10), and no
Etsy buyer sent to an outside marketing list (section 5).

Sources, each shown on every number:

* US: ``Clientes`` rows synced from Shopify customers (``canal_origen`` shopify). Order
  count, total and last order are Shopify's own lifetime figures. How the buyer found
  the store comes from ``Pedidos`` (Shopify's customer journey on their first order the
  sync has seen).
* Mexico: ``Clientes`` rows Lorena types herself (``linea`` MX-original). If ``Pedidos``
  has orders for that ``cliente_id`` they win; otherwise her typed numbers are shown as
  typed by hand.
* Etsy: no account yet, so a slot that says "fuente no conectada".

Personal data stays minimal: a short name, country and state. No email, phone or
address is read, stored or shown, and nothing here writes outside the workbook.

Pure functions over workbook rows: no network, no writes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

from . import metrics as m
from . import publicidad as pub

FUENTE_SHOPIFY = "shopify-clientes"
MANUAL = "Clientes (captura manual de Lore)"
FILTROS = {"todo": "Todos", "us": "EUA", "mx": "México", "seguimiento": "Seguimientos"}
PAISES = {"US": "EUA", "MX": "México", "CA": "Canadá"}
CONSENT = {"si": "acepta correos", "no": "no acepta correos", "desconocido": "consentimiento —"}


@dataclass
class Origen:
    clave: str                 # pub.ORIGEN key, or "" when unknown
    texto: str
    calidad: str               # real | faltante
    nota: str = ""


@dataclass
class Seguimiento:
    texto: str
    para: date | None
    estado: str
    vencido: bool


@dataclass
class Cliente:
    row: dict
    id: str
    linea: str
    canal: str
    nombre: str
    lugar: str
    consentimiento: str
    pedidos: m.Dato
    total: m.Dato
    ultimo: m.Dato
    desde: datetime | None
    origen: Origen
    notas: list[tuple[str, str]] = field(default_factory=list)   # (text, provenance)
    seguimiento: Seguimiento | None = None

    @property
    def pendiente(self) -> bool:
        return bool(self.seguimiento and self.seguimiento.estado == "pendiente")

    @property
    def vencido(self) -> bool:
        return bool(self.seguimiento and self.seguimiento.vencido)


def _dia(value) -> date | None:
    if not value:
        return None
    dt = m.parse_dt(value)
    if dt:
        return dt.astimezone(m.TZ).date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _lugar(row: dict) -> str:
    pais = (row.get("pais") or "").strip()
    region = (row.get("region") or "").strip()
    nombre = PAISES.get(pais.upper(), pais)
    return ", ".join(x for x in (region, nombre) if x) or "—"


def pedidos_por_cliente(pedidos_rows: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """cliente_id -> pedido_id -> its lines (live orders only)."""
    out: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in pedidos_rows:
        cid = r.get("cliente_id")
        if cid and r.get("estado") in m.VIVOS:
            out[cid][r["pedido_id"]].append(r)
    return out


def origen_cliente(pedidos: dict[str, list[dict]] | None) -> Origen:
    """How the buyer first came: the origin of their earliest order the sync has seen."""
    if not pedidos:
        return Origen("", "—", "faltante", "Sin pedidos ligados a este cliente en Pedidos.")
    primero = min(pedidos.values(), key=lambda ls: m.parse_dt(ls[0].get("fecha"))
                  or datetime.max.replace(tzinfo=m.TZ))[0]
    canal = primero.get("canal") or ""
    if canal != "shopify":
        from .views import CANAL
        return Origen(canal, CANAL.get(canal, canal or "—"), "real",
                      "Canal del pedido; ese canal no comparte la visita que lo trajo.")
    clave, pagado = pub.origen(primero)
    if clave == "sin-dato":
        estado = primero.get("origen_estado") or "sin dato"
        return Origen("", "—", "faltante", f"Shopify no tiene el recorrido ({estado}).")
    texto = pub.ORIGEN[clave] + (" · anuncio" if pagado else "")
    if primero.get("utm_campana"):
        texto += f" · campaña {primero['utm_campana']}"
    numero = primero.get("numero_canal") or primero.get("pedido_id") or ""
    return Origen(clave, texto, "real",
                  f"Última visita antes del pedido {numero} según Shopify.")


def _origen(row: dict, pedidos: dict[str, list[dict]] | None) -> Origen:
    canal = row.get("canal_origen") or ""
    if not pedidos and canal and canal != "shopify":
        from .views import CANAL
        return Origen(canal, CANAL.get(canal, canal), "real",
                      "Canal que Lore anotó en Clientes (canal_origen).")
    return origen_cliente(pedidos)


def _formato(moneda: str) -> str:
    return "mxn" if moneda.upper() == "MXN" else "usd"


def cliente(row: dict, pedidos: dict[str, list[dict]] | None,
            fuentes: dict[str, m.EstadoFuente], now: datetime) -> Cliente:
    canal = row.get("canal_origen") or ""
    moneda = (row.get("moneda") or ("MXN" if row.get("linea") == "MX-original" else "USD"))
    formato = _formato(moneda)
    sync = fuentes.get(FUENTE_SHOPIFY)
    if pedidos:
        # orders in Pedidos for this client: counted by us, period = what the sheet holds
        lineas = [r for ls in pedidos.values() for r in ls]
        fechas = [d for r in lineas if (d := m.parse_dt(r.get("fecha")))]
        fuente, act = "Pedidos", None
        periodo = "pedidos guardados en la hoja"
        n = m.Dato("Pedidos", len(pedidos), "real", fuente, periodo,
                   "Pedidos únicos de este cliente, sin cancelados ni de prueba.", act)
        total = m.Dato("Total", round(sum(m.neto_linea(r) for r in lineas), 2), "real",
                       fuente, periodo, "Venta bruta − descuentos − reembolsos de sus pedidos, "
                       "sin impuestos ni envío.", act, formato)
        ult = max(fechas) if fechas else None
        if canal == "shopify" and m.num(row.get("pedidos")) is not None:
            # Shopify's lifetime figures are complete (the sheet only holds 60 days)
            n, total, ult = _shopify(row, sync, formato)
    elif canal == "shopify":
        n, total, ult = _shopify(row, sync, formato)
    else:
        periodo = "según la captura"
        npd, tot = m.num(row.get("pedidos")), m.num(row.get("total"))
        nota = "" if row.get("nota_fecha") else "Sin fecha de captura (nota_fecha)."
        act = m.parse_dt(row.get("nota_fecha"))
        n = (m.Dato("Pedidos", npd, "real", MANUAL, periodo, "Compras que Lore anotó.", act,
                    nota=nota) if npd is not None else
             m.faltante("Pedidos", MANUAL, periodo, "Compras que Lore anotó.",
                        "Columna pedidos vacía.", "n"))
        total = (m.Dato("Total", tot, "real", MANUAL, periodo,
                        f"Lo que pagó en total, {moneda} (con IVA si es México).", act, formato,
                        nota=nota) if tot is not None else
                 m.faltante("Total", MANUAL, periodo, "Lo que pagó en total.",
                            "Columna total vacía.", formato))
        ult = m.parse_dt(row.get("ultimo_pedido")) or (
            datetime.combine(d, datetime.min.time(), m.TZ)
            if (d := _dia(row.get("ultimo_pedido"))) else None)
    if not isinstance(ult, m.Dato):
        ult = _fecha_dato(ult, n.fuente, n.periodo, n.actualizado)

    notas = []
    if (row.get("nota") or "").strip():
        quien = row.get("nota_por") or "sin autor"
        cuando = _dia(row.get("nota_fecha"))
        notas.append((row["nota"].strip(),
                      f"{quien}, {m.dia(datetime.combine(cuando, datetime.min.time(), m.TZ))}"
                      if cuando else f"{quien}, sin fecha"))
    if (row.get("nota_shopify") or "").strip():
        notas.append((row["nota_shopify"].strip(), "nota del cliente en Shopify"))

    seg = None
    if (row.get("seguimiento") or "").strip():
        para = _dia(row.get("seguimiento_para"))
        estado = row.get("seguimiento_estado") or "pendiente"
        hoy = now.astimezone(m.TZ).date()
        seg = Seguimiento(row["seguimiento"].strip(), para, estado,
                          estado == "pendiente" and para is not None and para < hoy)

    return Cliente(
        row, str(row.get("cliente_id")), row.get("linea") or "", canal,
        (row.get("nombre") or "").strip() or "Sin nombre", _lugar(row),
        CONSENT.get(row.get("consentimiento_email") or "desconocido", "consentimiento —"),
        n, total, ult, m.parse_dt(row.get("cliente_desde")), _origen(row, pedidos),
        notas, seg)


def _shopify(row: dict, sync: m.EstadoFuente | None, formato: str):
    act = sync.actualizado if sync else None
    fuente = "Shopify (clientes)"
    periodo = "toda la historia del cliente en la tienda"
    npd, tot = m.num(row.get("pedidos")), m.num(row.get("total"))
    n = (m.Dato("Pedidos", npd, "real", fuente, periodo,
                "Pedidos que Shopify cuenta para el cliente (numberOfOrders).", act)
         if npd is not None else m.faltante("Pedidos", fuente, periodo, "numberOfOrders",
                                            "Aún sin sincronizar.", "n"))
    total = (m.Dato("Total", tot, "real", fuente, periodo,
                    "Lo que Shopify dice que ha gastado (amountSpent): pedidos menos "
                    "reembolsos, con impuestos y envío.", act, formato)
             if tot is not None else m.faltante("Total", fuente, periodo, "amountSpent",
                                                "Aún sin sincronizar.", formato))
    ult = _fecha_dato(m.parse_dt(row.get("ultimo_pedido")), fuente, periodo, act)
    return n, total, ult


def _fecha_dato(dt: datetime | None, fuente: str, periodo: str, act) -> m.Dato:
    d = m.Dato("Último pedido", dt.timestamp() if dt else None, "real" if dt else "faltante",
               fuente, periodo, "Fecha del pedido más reciente.", act, "fecha")
    if not dt:
        d.nota = "Sin pedidos registrados."
    return d


def clientes(rows: list[dict], pedidos_rows: list[dict], fuentes: dict[str, m.EstadoFuente],
             now: datetime) -> list[Cliente]:
    por = pedidos_por_cliente(pedidos_rows)
    out = [cliente(r, por.get(str(r.get("cliente_id"))), fuentes, now) for r in rows]
    # follow-ups that are due first, then the most recent buyers
    def orden(c: Cliente):
        ult = c.ultimo.valor or 0
        return (not c.vencido, not c.pendiente, -ult, c.nombre)
    return sorted(out, key=orden)


def filtrar(cs: list[Cliente], filtro: str) -> list[Cliente]:
    if filtro == "us":
        return [c for c in cs if c.linea == "US-POD"]
    if filtro == "mx":
        return [c for c in cs if c.linea == "MX-original"]
    if filtro == "seguimiento":
        return [c for c in cs if c.pendiente]
    return cs


# --- summary numbers -------------------------------------------------------------------------

def resumen(cs: list[Cliente], pedidos_rows: list[dict], fuentes: dict[str, m.EstadoFuente],
            per: m.Periodo, now: datetime) -> list[m.Dato]:
    sync = fuentes.get(FUENTE_SHOPIFY)
    shop = fuentes["shopify"]
    us = [c for c in cs if c.canal == "shopify"]
    mx = [c for c in cs if c.linea == "MX-original"]
    datos: list[m.Dato] = []
    fuente_us = "Shopify (clientes)"
    if not sync or not sync.conectada:
        nota = (sync.nota if sync and sync.nota else "Los clientes de Shopify aún no se "
                "sincronizan (python -m lulamacaroni.connectors.shopify).")
        datos.append(m.faltante("Clientes EUA con compra", fuente_us, "toda la historia",
                                "Clientes de Shopify con al menos un pedido.", nota, "n",
                                "/clientes?f=us"))
    else:
        con = [c for c in us if (c.pedidos.valor or 0) > 0]
        datos.append(m.Dato("Clientes EUA con compra", len(con), "real", fuente_us,
                            "toda la historia", "Clientes de Shopify con al menos un pedido "
                            "(numberOfOrders ≥ 1).", sync.actualizado, "n",
                            nota=f"{len(us)} cliente(s) en Shopify en total",
                            enlace="/clientes?f=us"))

    # buyers in the period, from Pedidos (each order once; guests counted apart)
    definicion = ("Clientes distintos con un pedido de Shopify creado en el periodo, sin "
                  "cancelados ni de prueba.")
    if not shop.conectada:
        datos.append(m.faltante("Compraron en el periodo", "Pedidos (Shopify)", per.texto,
                                definicion, "Shopify no está conectado.", "n"))
        datos.append(m.faltante("Compraron otra vez", "Pedidos + Shopify (clientes)",
                                per.texto, "", "Shopify no está conectado.", "n"))
    else:
        vivos = [r for r in pedidos_rows if r.get("canal") == "shopify"
                 and r.get("estado") in m.VIVOS and per.contiene(m.parse_dt(r.get("fecha")))]
        sin_id = {r["pedido_id"] for r in vivos if not r.get("cliente_id")}
        ids = {r["cliente_id"] for r in vivos if r.get("cliente_id")}
        nota = (f"{len(sin_id)} pedido(s) sin cliente ligado (sin cuenta o anteriores a "
                "la columna cliente_id)." if sin_id else "")
        datos.append(m.Dato("Compraron en el periodo", len(ids), "real", "Pedidos (Shopify)",
                            per.texto, definicion, shop.actualizado, "n", nota=nota,
                            enlace="/pedidos"))
        by_id = {c.id: c for c in us}
        if not sync or not sync.conectada:
            datos.append(m.faltante("Compraron otra vez", "Pedidos + Shopify (clientes)",
                                    per.texto, "De quienes compraron en el periodo, los que "
                                    "ya tienen 2 o más pedidos en total.",
                                    "Faltan los clientes de Shopify.", "n"))
        else:
            rep = [i for i in ids if (by_id[i].pedidos.valor or 0) >= 2] if all(
                i in by_id for i in ids) else None
            if rep is None:
                datos.append(m.faltante(
                    "Compraron otra vez", "Pedidos + Shopify (clientes)", per.texto,
                    "De quienes compraron en el periodo, los que ya tienen 2 o más pedidos.",
                    "Hay pedidos de clientes que aún no están en Clientes; vuelve a "
                    "sincronizar Shopify.", "n"))
            else:
                datos.append(m.Dato(
                    "Compraron otra vez", len(rep), "real", "Pedidos + Shopify (clientes)",
                    per.texto, "De quienes compraron en el periodo, los que ya tienen 2 o más "
                    "pedidos en total según Shopify.", sync.actualizado, "n",
                    enlace="/clientes?f=us"))

    datos.append(m.Dato("Clientes México", len(mx), "real", MANUAL, "toda la historia",
                        "Compradores de obra original que Lore anotó en la pestaña Clientes "
                        "(linea MX-original).", None, "n",
                        nota="" if mx else "Aún no hay filas de México.",
                        enlace="/clientes?f=mx"))
    etsy = fuentes["etsy"]
    datos.append(m.faltante("Clientes Etsy", "Etsy", "toda la historia",
                            "Compradores de Etsy.",
                            f"Fuente no conectada ({etsy.nota or etsy.info.fase}).", "n",
                            "/fuentes")
                 if not etsy.conectada else
                 m.Dato("Clientes Etsy", len([c for c in cs if c.canal == "etsy"]), "real",
                        "Etsy", "toda la historia", "Compradores de Etsy.", etsy.actualizado,
                        "n"))
    pend = [c for c in cs if c.pendiente]
    venc = [c for c in pend if c.vencido]
    datos.append(m.Dato("Seguimientos pendientes", len(pend), "real",
                        "Clientes (columna seguimiento)", "hoy",
                        "Seguimientos con estado pendiente; vencidos = fecha ya pasó.", now, "n",
                        nota=f"{len(venc)} vencido(s)" if venc else "",
                        enlace="/clientes?f=seguimiento"))
    return datos


def origenes(cs: list[Cliente]) -> list[tuple[str, int]]:
    """Customers per first-order origin, each customer once."""
    cuenta: dict[str, int] = defaultdict(int)
    for c in cs:
        if (c.pedidos.valor or 0) > 0 or c.origen.calidad == "real":
            cuenta[c.origen.texto.split(" · ")[0] if c.origen.calidad == "real"
                   else "Sin dato de origen"] += 1
    return sorted(cuenta.items(), key=lambda kv: -kv[1])


def vencidos(cs: list[Cliente]) -> list[Cliente]:
    return [c for c in cs if c.vencido]
