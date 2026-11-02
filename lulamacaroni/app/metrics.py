"""Numbers for the back office, each one carrying where it came from.

Lorena's rule (requirements, section 1): every number shows its source, period,
definition and last update, and says whether it is a real zero, a missing value or an
estimate. So nothing here returns a bare float. Every metric is a :class:`Dato`.

All functions are pure: they take rows (as read from the workbook or the local JSON
files, so numbers may arrive as strings) and a ``now``, and never touch the network.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .. import config

TZ = ZoneInfo(config.get("LULA_TZ", "America/Mexico_City"))

# --- sources ------------------------------------------------------------------------

@dataclass(frozen=True)
class FuenteInfo:
    clave: str
    nombre: str
    como: str
    max_horas: int   # older than this -> "atrasada"
    fase: str        # when it gets connected, shown while it isn't


FUENTES = (
    FuenteInfo("shopify", "Shopify", "API", 26, "conectada"),
    FuenteInfo("etsy", "Etsy", "API", 26, "siguiente conector"),
    FuenteInfo("prodigi", "Prodigi", "API", 26, ""),  # text from prodigi_fase()
    FuenteInfo("quickbooks", "QuickBooks", "API", 48, "cuando exista la cuenta"),
    FuenteInfo("meta", "Meta Ads", "API", 26, "requiere revisión de app de Meta"),
    FuenteInfo("instagram", "Instagram", "API", 26, "requiere revisión de app de Meta"),
    FuenteInfo("pinterest", "Pinterest + Ads", "API", 26, "requiere aprobación de Pinterest"),
    FuenteInfo("erank", "eRank", "CSV mensual", 24 * 35, "importación mensual"),
    FuenteInfo("everbee", "EverBee", "CSV mensual", 24 * 35, "importación mensual"),
    FuenteInfo("gmail", "Correo info@", "Gmail", 26, "fase 4 (bandeja de clientes)"),
)
FUENTE_BY_KEY = {f.clave: f for f in FUENTES}


@dataclass
class EstadoFuente:
    info: FuenteInfo
    estado: str                    # ok | atrasada | error | sin-conectar
    actualizado: datetime | None
    filas: str = ""
    nota: str = ""

    @property
    def conectada(self) -> bool:
        return self.estado in ("ok", "atrasada")


def parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def prodigi_fase() -> str:
    """What Prodigi still needs, read from the same settings the connector uses."""
    from ..connectors.prodigi import KEY_VARS

    env = config.get("PRODIGI_ENV", "sandbox")
    var = KEY_VARS.get(env)
    if var is None:
        return f"PRODIGI_ENV no válido ({env})"
    if not config.get(var):
        return f"falta la llave de {env}"
    return f"llave de {env} lista; aún sin sincronizar costos"


def estado_fuentes(fuentes_rows: list[dict], now: datetime) -> dict[str, EstadoFuente]:
    by_key = {r.get("fuente"): r for r in fuentes_rows}
    out = {}
    for info in FUENTES:
        row = by_key.get(info.clave)
        if not row:
            fase = prodigi_fase() if info.clave == "prodigi" else info.fase
            out[info.clave] = EstadoFuente(info, "sin-conectar", None, nota=fase)
            continue
        when = parse_dt(row.get("ultima_actualizacion"))
        estado = row.get("estado") or "ok"
        if estado == "ok" and (when is None or now - when > timedelta(hours=info.max_horas)):
            estado = "atrasada"
        out[info.clave] = EstadoFuente(info, estado, when, str(row.get("filas", "")),
                                       row.get("nota", ""))
    return out


# --- the number type ------------------------------------------------------------------

@dataclass
class Dato:
    etiqueta: str
    valor: float | None              # None = missing
    calidad: str                     # real | estimado | faltante
    fuente: str
    periodo: str
    definicion: str
    actualizado: datetime | None = None
    formato: str = "n"               # n | usd
    previo: float | None = None
    nota: str = ""
    enlace: str = ""

    @property
    def es_cero(self) -> bool:
        return self.calidad == "real" and self.valor == 0

    @property
    def cambio_pct(self) -> float | None:
        if self.calidad != "real" or self.valor is None or not self.previo:
            return None
        return (self.valor - self.previo) / abs(self.previo) * 100


def faltante(etiqueta: str, fuente: str, periodo: str, definicion: str, nota: str,
             formato: str = "usd", enlace: str = "") -> Dato:
    return Dato(etiqueta, None, "faltante", fuente, periodo, definicion, None, formato,
                nota=nota, enlace=enlace)


# --- periods -------------------------------------------------------------------------

@dataclass(frozen=True)
class Periodo:
    clave: str
    nombre: str
    inicio: datetime
    fin: datetime
    previo_inicio: datetime
    previo_fin: datetime
    comparacion: str

    def contiene(self, dt: datetime | None) -> bool:
        return dt is not None and self.inicio <= dt < self.fin

    def contiene_previo(self, dt: datetime | None) -> bool:
        return dt is not None and self.previo_inicio <= dt < self.previo_fin

    @property
    def texto(self) -> str:
        if self.clave == "hoy":
            return f"hoy {dia(self.inicio)}, hora de CDMX"
        return f"{dia(self.inicio)} a {dia(self.fin)}, hora de CDMX"


PERIODOS = ("hoy", "7", "30")
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def dia(dt: datetime) -> str:
    d = dt.astimezone(TZ)
    return f"{d.day} {MESES[d.month - 1]}"


def periodo(clave: str, now: datetime) -> Periodo:
    local = now.astimezone(TZ)
    if clave == "hoy":
        inicio = local.replace(hour=0, minute=0, second=0, microsecond=0)
        semana = timedelta(days=7)
        return Periodo("hoy", "Hoy", inicio, local, inicio - semana, local - semana,
                       "mismo día de la semana pasada, hasta la misma hora")
    dias = int(clave)
    span = timedelta(days=dias)
    return Periodo(clave, f"{dias} días", local - span, local, local - 2 * span, local - span,
                   f"{dias} días anteriores")


# --- helpers over rows ------------------------------------------------------------------

def num(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _orden_num(pedido_id: str) -> str:
    return pedido_id.rsplit("-", 1)[-1]


VIVOS = {"recibido", "enviado-a-pod", "en-produccion", "enviado", "entregado", "excepcion",
         "reembolsado"}


def neto_linea(r: dict) -> float:
    return (num(r.get("venta_bruta")) or 0) - (num(r.get("descuento")) or 0) - (
        num(r.get("reembolso")) or 0)


@dataclass
class Resumen:
    periodo: Periodo
    datos: list[Dato]
    pedidos_periodo: int
    mas_vendido: str | None
    por_linea: dict[str, float] = field(default_factory=dict)


def resumen(pedidos: list[dict], campanas: list[dict], fuentes: dict[str, EstadoFuente],
            per: Periodo) -> Resumen:
    shop = fuentes["shopify"]
    etsy = fuentes["etsy"]
    canales_vivos = [f.info.nombre for f in (shop, etsy) if f.conectada]
    canales_faltan = [f.info.nombre for f in (shop, etsy) if not f.conectada]
    fuente_ventas = " + ".join(canales_vivos) or "ninguna"
    nota_canales = (f"Sin {', '.join(canales_faltan)}: aún no está conectado."
                    if canales_faltan else "")
    actualizado = min((f.actualizado for f in (shop, etsy) if f.conectada and f.actualizado),
                      default=None)

    def fecha(r):
        return parse_dt(r.get("fecha"))

    act = [r for r in pedidos if per.contiene(fecha(r))]
    prev = [r for r in pedidos if per.contiene_previo(fecha(r))]
    vivos_act = [r for r in act if r.get("estado") in VIVOS]
    vivos_prev = [r for r in prev if r.get("estado") in VIVOS]

    datos: list[Dato] = []
    if not canales_vivos:
        datos.append(faltante("Ventas netas", "Shopify + Etsy", per.texto,
                              "Venta bruta − descuentos − reembolsos, sin impuestos ni envío.",
                              "Ningún canal de venta conectado.", enlace="/pedidos"))
        datos.append(faltante("Pedidos", "Shopify + Etsy", per.texto,
                              "Pedidos únicos, sin cancelados ni de prueba.",
                              "Ningún canal de venta conectado.", "n", "/pedidos"))
    else:
        datos.append(Dato(
            "Ventas netas", round(sum(neto_linea(r) for r in vivos_act), 2), "real",
            fuente_ventas, per.texto,
            "Venta bruta − descuentos − reembolsos de los pedidos creados en el periodo, "
            "sin impuestos ni envío cobrado. No cuenta pedidos cancelados ni de prueba.",
            actualizado, "usd", round(sum(neto_linea(r) for r in vivos_prev), 2),
            nota=nota_canales, enlace="/pedidos"))
        datos.append(Dato(
            "Pedidos", len({r["pedido_id"] for r in vivos_act}), "real", fuente_ventas,
            per.texto, "Pedidos únicos creados en el periodo, sin cancelados ni de prueba.",
            actualizado, "n", len({r["pedido_id"] for r in vivos_prev}), nota=nota_canales,
            enlace="/pedidos"))

    # Ad spend: Campanas only fills once Meta / Pinterest are connected.
    ads = [f for f in (fuentes["meta"], fuentes["pinterest"]) if f.conectada]
    if not ads:
        datos.append(faltante("Gasto publicitario", "Meta Ads + Pinterest Ads", per.texto,
                              "Gasto reportado por cada plataforma de anuncios en el periodo.",
                              "Meta y Pinterest aún no están conectados."))
    else:
        gasto = sum(num(c.get("gasto")) or 0 for c in campanas if per.contiene(parse_dt(c.get("fecha"))))
        gasto_prev = sum(num(c.get("gasto")) or 0 for c in campanas
                         if per.contiene_previo(parse_dt(c.get("fecha"))))
        datos.append(Dato("Gasto publicitario", round(gasto, 2), "real",
                          " + ".join(f.info.nombre for f in ads), per.texto,
                          "Gasto reportado por cada plataforma de anuncios en el periodo.",
                          min((f.actualizado for f in ads if f.actualizado), default=None),
                          "usd", round(gasto_prev, 2)))

    # Contribution margin needs channel fees, Prodigi cost and ad spend for every line.
    sin_costos = [r for r in vivos_act if r.get("calidad_dato") != "real"]
    if not canales_vivos or sin_costos or not ads:
        motivo = []
        if sin_costos:
            motivo.append(f"{len(sin_costos)} línea(s) sin comisión o coste de Prodigi")
        if not ads:
            motivo.append("sin gasto publicitario")
        if not canales_vivos:
            motivo.append("sin canales de venta")
        datos.append(faltante(
            "Margen de contribución", "Pedidos + Prodigi + pagos + anuncios", per.texto,
            "Ventas netas − comisiones del canal − coste y envío de Prodigi − gasto publicitario.",
            "Falta: " + "; ".join(motivo) + "." if motivo else "", enlace="/pedidos"))
    else:
        margen = sum(num(r.get("margen_contribucion")) or 0 for r in vivos_act) - datos[2].valor
        datos.append(Dato("Margen de contribución", round(margen, 2), "real",
                          "Pedidos + Prodigi + pagos + anuncios", per.texto,
                          "Ventas netas − comisiones − coste y envío de Prodigi − publicidad.",
                          actualizado, "usd"))

    if canales_vivos:
        reemb = [r for r in act if (num(r.get("reembolso")) or 0) > 0]
        reemb_prev = [r for r in prev if (num(r.get("reembolso")) or 0) > 0]
        datos.append(Dato(
            "Devoluciones", round(sum(num(r["reembolso"]) for r in reemb), 2), "real",
            fuente_ventas, per.texto,
            "Monto reembolsado de los pedidos creados en el periodo (por fecha del pedido, "
            "no del reembolso). Incluye pedidos cancelados que se reembolsaron.",
            actualizado, "usd", round(sum(num(r["reembolso"]) for r in reemb_prev), 2),
            nota=f"{len({r['pedido_id'] for r in reemb})} pedido(s)" + (
                f". {nota_canales}" if nota_canales else ""), enlace="/pedidos"))
    else:
        datos.append(faltante("Devoluciones", "Shopify + Etsy", per.texto,
                              "Monto reembolsado de los pedidos del periodo.",
                              "Ningún canal de venta conectado.", enlace="/pedidos"))

    datos.append(faltante(
        "Por recibir", "Pagos de Shopify y Etsy", "a la fecha",
        "Ventas cobradas que aún no llegan como depósito al banco.",
        "Los pagos (payouts) aún no se sincronizan; la venta bruta y el depósito se "
        "llevan por separado."))

    ventas_por = Counter()
    for r in vivos_act:
        ventas_por[r.get("producto") or r.get("sku") or "sin nombre"] += neto_linea(r)
    mas = ventas_por.most_common(1)[0][0] if ventas_por and ventas_por.most_common(1)[0][1] > 0 else None
    por_linea = defaultdict(float)
    for r in vivos_act:
        por_linea[r.get("linea", "")] += neto_linea(r)
    return Resumen(per, datos, len({r["pedido_id"] for r in vivos_act}), mas, dict(por_linea))


# --- orders ------------------------------------------------------------------------------

SIN_IMPRENTA = {"manual", "desconocida"}
ABIERTOS = {"recibido", "enviado-a-pod", "en-produccion", "excepcion"}


@dataclass
class Pedido:
    pedido_id: str
    numero: str
    canal: str
    linea: str
    fecha: datetime | None
    estado: str
    lineas: list[dict]
    neto: float
    rutas: set[str]
    tracking: str

    @property
    def atencion(self) -> str:
        """Why this order needs a person, or "" if it doesn't."""
        if self.estado == "excepcion":
            return "Marcado como excepción"
        if self.estado in ABIERTOS and self.rutas & SIN_IMPRENTA:
            return "Ninguna imprenta lo recibe (ruta manual o desconocida); no se ha enviado"
        return ""

    @property
    def grupo(self) -> str:
        if self.atencion:
            return "atencion"
        if self.estado in ABIERTOS or self.estado == "enviado":
            return "camino"
        return "cerrado"


def agrupar_pedidos(pedidos_rows: list[dict]) -> list[Pedido]:
    by_order: dict[str, list[dict]] = defaultdict(list)
    for r in pedidos_rows:
        by_order[r["pedido_id"]].append(r)
    out = []
    for pid, lines in by_order.items():
        first = lines[0]
        estados = {r.get("estado") for r in lines}
        estado = "excepcion" if "excepcion" in estados else first.get("estado", "")
        out.append(Pedido(
            pid, _orden_num(pid), first.get("canal", ""), first.get("linea", ""),
            parse_dt(first.get("fecha")), estado, lines,
            round(sum(neto_linea(r) for r in lines), 2),
            {r.get("ruta_pod") or "desconocida" for r in lines},
            ", ".join(t for t in dict.fromkeys(r.get("tracking", "") for r in lines) if t)))
    out.sort(key=lambda p: p.fecha or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return out


# --- catalog -------------------------------------------------------------------------------

@dataclass
class Producto:
    canal: str
    id_producto: str
    titulo: str
    linea: str
    estado: str
    url: str
    variantes: int
    sin_sku: int
    precio_min: float | None
    precio_max: float | None

    @property
    def avisos(self) -> list[str]:
        a = []
        if self.estado == "publicado" and self.sin_sku:
            a.append(f"{self.sin_sku} de {self.variantes} variantes sin SKU: no se pueden "
                     "ligar a una obra ni a Prodigi")
        return a


def agrupar_catalogo(listados: list[dict]) -> list[Producto]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in listados:
        pid = str(r.get("id_producto_canal") or r.get("url") or
                  (r.get("titulo_en_canal") or "").split(" / ")[0])
        groups[(r.get("canal", ""), pid)].append(r)
    out = []
    for (canal, pid), rows in groups.items():
        precios = [p for p in (num(r.get("precio")) for r in rows) if p is not None]
        first = rows[0]
        out.append(Producto(
            canal, pid, (first.get("titulo_en_canal") or "").split(" / ")[0],
            first.get("linea", ""), first.get("estado", ""), first.get("url", ""), len(rows),
            sum(1 for r in rows if not r.get("sku")),
            min(precios) if precios else None, max(precios) if precios else None))
    orden = {"publicado": 0, "en-aprobacion": 1, "borrador": 2, "pausado": 3, "retirado": 4}
    out.sort(key=lambda p: (orden.get(p.estado, 9), p.titulo.lower()))
    return out


# --- the three actions of the day -------------------------------------------------------------

@dataclass
class Accion:
    texto: str
    enlace: str
    prioridad: int


def acciones_del_dia(pendientes: int, pedidos: list[Pedido], productos: list[Producto],
                     fuentes: dict[str, EstadoFuente], excepciones: list[dict]) -> list[Accion]:
    """Rule-based for now; the Asistente (Claude) writes this summary in a later slice."""
    acciones: list[Accion] = []
    if pendientes:
        acciones.append(Accion(f"Aprobar {pendientes} cosa(s) pendiente(s)", "/aprobar", 10))
    for p in pedidos:
        if p.grupo == "atencion":
            acciones.append(Accion(f"Revisar el pedido #{p.numero} ({p.canal.capitalize()}): {p.atencion.lower()}",
                                   "/pedidos", 20))
    abiertas = [e for e in excepciones if e.get("estado") in ("abierta", "en-curso")]
    if abiertas:
        acciones.append(Accion(f"Resolver {len(abiertas)} excepción(es) abierta(s)", "/pedidos", 25))
    for f in fuentes.values():
        if f.estado in ("error", "atrasada"):
            acciones.append(Accion(f"{f.info.nombre}: datos {'con error' if f.estado == 'error' else 'atrasados'}",
                                   "/fuentes", 30))
    sin_sku = [p for p in productos if p.avisos]
    if sin_sku:
        acciones.append(Accion(f"{len(sin_sku)} producto(s) publicados con variantes sin SKU",
                               "/catalogo", 40))
    for f in fuentes.values():
        if f.info.clave == "etsy" and not f.conectada:
            acciones.append(Accion("Conectar Etsy para ver todas las ventas de EUA", "/fuentes", 50))
    acciones.sort(key=lambda a: a.prioridad)
    return acciones[:3]
