"""Publicidad: planned campaigns, spend limits, approvals and where orders came from.

Lorena's requirements, sections 4, 11 and 14:

* she approves every new ad and every budget change, at first with no exceptions;
* daily, monthly and per-platform limits, and a maximum size for a budget change;
* results per platform kept as separate views, never added up as if they were different
  orders; uncertain attribution is labelled as such;
* ads sent to Shopify and to Etsy are told apart (Etsy does not share the visit's origin).

No ad platform is connected yet, so nothing here talks to Meta, Pinterest or Google, and
nothing is ever sent to a platform. Campaigns are rows in the ``Publicidad`` tab (a plan),
limits are rows in ``Topes``, and platform results (``Campanas``) show "—" until a source is
connected. What Shopify can say today comes from the order's customer journey (UTM tags
and the referring site), synced into ``Pedidos`` by the Shopify connector.

The approval covers exactly :func:`campana_aprobable`: creative, text, destination,
audience, budget and dates. Any edit after approval changes the fingerprint and the
campaign needs a new approval before anyone launches or changes it on the platform.

    python -m lulamacaroni.app.publicidad --pedir CAMPANA_ID   # ask Lore to approve a campaign

That command only writes the request into Aprobaciones and its id into the campaign row.
"""

from __future__ import annotations

import argparse
import re
import sys
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..approval.gate import fingerprint, request_approval
from . import metrics as m
from .contenido import Gate

PLATAFORMA = {"meta": "Meta (Instagram y Facebook)", "pinterest": "Pinterest",
              "google": "Google", "etsy-ads": "Etsy Ads", "otro": "Otra"}
# Which Fuentes row reports each platform's own results (None: no connector planned yet)
FUENTE_PLATAFORMA = {"meta": "meta", "pinterest": "pinterest", "etsy-ads": "etsy",
                     "google": None, "otro": None}
ESTADO = {"por-aprobar": "Esperan tu aprobación", "aprobada": "Aprobadas, sin lanzar",
          "activa": "Activas", "pausada": "Pausadas", "borrador": "Borradores",
          "idea": "Ideas", "terminada": "Terminadas", "rechazada": "Rechazadas"}
NECESITA_APROBACION = {"aprobada", "activa", "pausada", "terminada"}
EN_PLAN = {"por-aprobar", "aprobada", "activa"}   # count against the limits
TIPOS_VALIDOS = ("anuncio", "presupuesto")
FUENTE = "Libro de datos (pestaña Publicidad)"
CAMPOS_APROBADOS = ("campana_id", "linea", "plataforma", "obra_id", "objetivo", "audiencia",
                    "destino", "url_destino", "utm_campana", "texto", "archivo",
                    "presupuesto_diario_usd", "presupuesto_total_usd", "inicio", "fin")
DINERO = {"presupuesto_diario_usd", "presupuesto_total_usd"}


def _campo(row: dict, k: str) -> str:
    v = row.get(k)
    if k in DINERO:
        n = m.num(v)
        return "" if n is None else f"{n:.2f}"   # "10", 10 and "10.0" approve the same
    return str(v if v is not None else "").strip()


def campana_aprobable(row: dict) -> dict:
    """The exact plan Lorena approves (what someone would set up on the platform)."""
    return {"objeto": "campana", **{k: _campo(row, k) for k in CAMPOS_APROBADOS}}


def gate(row: dict, approvals: dict, now: datetime) -> Gate:
    aid = row.get("aprobacion_id") or ""
    estado = row.get("estado") or ""
    if not aid:
        if estado in NECESITA_APROBACION:
            return Gate("sin-aprobacion", f"Marcada como {estado} sin aprobación de Lore",
                        alerta=True)
        if estado == "por-aprobar":
            return Gate("sin-solicitud", "Aún no se te pide: falta crear la solicitud",
                        alerta=False)
        return Gate("no-hace-falta", "Aún no pide aprobación")
    a = approvals.get(aid)
    if a is None:
        return Gate("perdida", f"La aprobación {aid} no está en Aprobaciones", alerta=True)
    if a.tipo not in TIPOS_VALIDOS:
        return Gate("perdida", f"{aid} aprueba “{a.tipo}”, no un anuncio ni un presupuesto",
                    alerta=True)
    if a.estado == "pendiente":
        expira = m.parse_dt(a.expira_en)
        if expira and now > expira:
            return Gate("expirado", "La solicitud venció sin decisión",
                        alerta=estado in NECESITA_APROBACION)
        return Gate("pendiente", "Esperando tu aprobación")
    if a.estado in ("rechazado", "expirado", "cancelado"):
        return Gate(a.estado, {"rechazado": "Rechazada", "expirado": "Aprobación vencida",
                               "cancelado": "Solicitud cancelada"}[a.estado],
                    alerta=estado in NECESITA_APROBACION)
    if a.huella != fingerprint(campana_aprobable(row)):
        return Gate("cambio", "Cambió después de aprobarse (texto, destino, fechas o "
                    "presupuesto): necesita nueva aprobación",
                    alerta=estado not in ("terminada", "rechazada"))
    quien = a.decidido_por or "Lore"
    cuando = m.dia(m.parse_dt(a.decidido_en)) if a.decidido_en else ""
    return Gate("ok", f"Aprobada por {quien}" + (f" el {cuando}" if cuando else ""))


# --- limits ---------------------------------------------------------------------------------

@dataclass
class Tope:
    plataforma: str
    diario: float | None
    mensual: float | None
    cambio_pct: float | None
    actualizado: datetime | None
    definido_por: str = ""


def topes(rows: list[dict]) -> dict[str, Tope]:
    return {r["plataforma"]: Tope(r["plataforma"], m.num(r.get("tope_diario_usd")),
                                  m.num(r.get("tope_mensual_usd")),
                                  m.num(r.get("cambio_max_pct")),
                                  m.parse_dt(r.get("actualizado")), r.get("definido_por") or "")
            for r in rows if r.get("plataforma")}


def _mes(now: datetime) -> tuple[datetime, datetime]:
    local = now.astimezone(m.TZ)
    ini = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fin = ini + timedelta(days=monthrange(ini.year, ini.month)[1])
    return ini, fin


def _fecha_local(value, fin: bool = False) -> datetime | None:
    """A date cell ("2026-11-05") as the start of that day in CDMX; ``fin`` = end of it."""
    dt = m.parse_dt(value)
    if dt is None:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value).strip()):
        dt = dt.replace(tzinfo=m.TZ)
    return dt + timedelta(days=1) if fin else dt


def plan_mes(row: dict, now: datetime) -> float | None:
    """Most this campaign can spend this calendar month by its plan (daily × days, capped).

    None when the daily budget is missing: the plan can't be checked against the limit.
    """
    diario = m.num(row.get("presupuesto_diario_usd"))
    if diario is None:
        return None
    mes_ini, mes_fin = _mes(now)
    ini = max(_fecha_local(row.get("inicio")) or mes_ini, mes_ini)
    fin = min(_fecha_local(row.get("fin"), fin=True) or mes_fin, mes_fin)
    dias = max(0, round((fin - ini).total_seconds() / 86400))
    total = m.num(row.get("presupuesto_total_usd"))
    gasto = diario * dias
    return round(min(gasto, total) if total is not None else gasto, 2)


# --- where orders came from (Shopify customer journey) --------------------------------------

ORIGEN = {"meta": "Instagram / Facebook", "pinterest": "Pinterest", "google": "Google",
          "etsy": "Etsy", "correo": "Correo", "directo": "Directo (sin referente)",
          "otro": "Otro sitio", "sin-dato": "Sin dato de origen"}
PAGADO_MEDIO = {"cpc", "ppc", "paid", "paid_social", "paidsocial", "paid-social", "cpm",
                "ads", "ad", "display", "paid_search", "paidsearch", "retargeting"}
PAGADO_TIPO = {"ad", "retargeting", "display"}


# The store's own pages and Shopify's admin are not an origin: the visit came from inside.
DOMINIOS_PROPIOS = tuple(d.strip().lower() for d in m.config.get(
    "LULA_DOMINIOS_PROPIOS", "lulamacaroni.com,myshopify.com,shopify.com").split(",") if d.strip())


def _interno(value: str | None) -> bool:
    v = (value or "").lower()
    host = re.sub(r"^[a-z]+://", "", v).split("/")[0].removeprefix("www.")
    return bool(host) and any(host == d or host.endswith("." + d) for d in DOMINIOS_PROPIOS)


def _tokens(*values: str) -> set[str]:
    return {t for v in values for t in re.split(r"[^a-z0-9]+", (v or "").lower()) if t}


def origen(row: dict) -> tuple[str, bool | None]:
    """(origin key, came from an ad?) for one Pedidos row. None = can't tell."""
    if row.get("origen_estado") != "ok":
        return "sin-dato", None
    ref = "" if _interno(row.get("referente")) else (row.get("referente") or "")
    fuente = "" if _interno(row.get("origen_fuente")) else (row.get("origen_fuente") or "")
    toks = _tokens(row.get("utm_fuente"), fuente, ref)
    if toks & {"facebook", "fb", "instagram", "ig", "meta"}:
        clave = "meta"
    elif "pinterest" in toks or "pin" in toks and "it" in toks:
        clave = "pinterest"
    elif toks & {"google", "googleadservices", "googlesyndication"}:
        clave = "google"
    elif "etsy" in toks:
        clave = "etsy"
    elif (toks & {"email", "newsletter", "klaviyo", "mail"}
          or row.get("origen_tipo") in ("newsletter", "transactional")):
        clave = "correo"
    elif not ref and not row.get("utm_fuente") and fuente in ("", "direct"):
        clave = "directo"
    else:
        clave = "otro"
    pagado = ((row.get("utm_medio") or "") in PAGADO_MEDIO
              or (row.get("origen_tipo") or "") in PAGADO_TIPO or "ads" in toks)
    return clave, pagado


@dataclass
class FilaOrigen:
    clave: str
    pedidos_anuncio: int = 0
    pedidos_organico: int = 0
    pedidos_sin_saber: int = 0
    ventas: float = 0.0

    @property
    def pedidos(self) -> int:
        return self.pedidos_anuncio + self.pedidos_organico + self.pedidos_sin_saber


def _pedidos_vivos(pedidos_rows: list[dict]) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = defaultdict(list)
    for r in pedidos_rows:
        if r.get("estado") in m.VIVOS and r.get("canal") == "shopify":
            by[r["pedido_id"]].append(r)
    return by


def atribucion(pedidos_rows: list[dict], per: m.Periodo) -> list[FilaOrigen]:
    """Shopify orders created in the period, one row per origin, each order counted once."""
    filas: dict[str, FilaOrigen] = {}
    for lines in _pedidos_vivos(pedidos_rows).values():
        first = lines[0]
        if not per.contiene(m.parse_dt(first.get("fecha"))):
            continue
        clave, pagado = origen(first)
        f = filas.setdefault(clave, FilaOrigen(clave))
        if pagado is None:
            f.pedidos_sin_saber += 1
        elif pagado:
            f.pedidos_anuncio += 1
        else:
            f.pedidos_organico += 1
        f.ventas = round(f.ventas + sum(m.neto_linea(r) for r in lines), 2)
    orden = list(ORIGEN)
    return sorted(filas.values(), key=lambda f: orden.index(f.clave))


# --- campaigns -------------------------------------------------------------------------------

@dataclass
class Campana:
    row: dict
    gate: Gate
    obra: str
    diario: float | None
    total: float | None
    plan_mes: float | None
    tope: Tope | None
    shopify: m.Dato
    plataforma_datos: list[m.Dato]
    avisos: list[str] = field(default_factory=list)

    @property
    def campana_id(self) -> str:
        return self.row.get("campana_id") or ""

    @property
    def plataforma(self) -> str:
        return self.row.get("plataforma") or ""

    @property
    def estado(self) -> str:
        return self.row.get("estado") or ""

    @property
    def nombre(self) -> str:
        return self.row.get("nombre") or self.campana_id

    @property
    def alerta(self) -> bool:
        return bool(self.avisos) and (self.gate.alerta or self.excede)

    excede: bool = False


def _resultado_shopify(row: dict, por_utm: dict[str, list[list[dict]]],
                       fuentes: dict[str, m.EstadoFuente]) -> m.Dato:
    utm = (row.get("utm_campana") or "").strip().lower()
    definicion = ("Pedidos de Shopify cuya última visita llegó con esta utm_campaign, según "
                  "el recorrido del cliente de Shopify. Es la vista de Shopify, no la de la "
                  "plataforma; no se suman entre sí.")
    shop = fuentes["shopify"]
    if row.get("destino") == "etsy":
        return m.faltante("Pedidos (Shopify)", "Shopify", "desde el inicio", definicion,
                          "El destino es Etsy: Etsy no comparte de dónde llegó la visita.", "n")
    if not shop.conectada:
        return m.faltante("Pedidos (Shopify)", "Shopify", "desde el inicio", definicion,
                          "Shopify no está conectado.", "n")
    if not utm:
        return m.faltante("Pedidos (Shopify)", "Shopify", "desde el inicio", definicion,
                          "Sin utm_campana: sus ventas no se pueden ligar a la campaña.", "n")
    pedidos = por_utm.get(utm, [])
    ventas = round(sum(m.neto_linea(r) for lines in pedidos for r in lines), 2)
    return m.Dato("Pedidos (Shopify)", len(pedidos), "real", "Shopify (recorrido del cliente)",
                  "desde el inicio", definicion, shop.actualizado, "n",
                  nota=f"Ventas netas US${ventas:,.2f}" if pedidos else "")


def _resultados_plataforma(row: dict, dias: list[dict],
                           fuentes: dict[str, m.EstadoFuente]) -> list[m.Dato]:
    plat = row.get("plataforma") or ""
    clave = FUENTE_PLATAFORMA.get(plat)
    f = fuentes.get(clave) if clave else None
    nombre = f.info.nombre if f else PLATAFORMA.get(plat, plat or "Plataforma")
    defs = (("Gasto", "gasto", "usd", "Lo que la plataforma dice que se gastó."),
            ("Clics", "clics", "n", "Clics que reporta la plataforma."),
            ("Compras según la plataforma", "compras_atribuidas", "n",
             "Compras que la plataforma se atribuye con su propia ventana. Pueden coincidir "
             "con pedidos que Shopify atribuye a otro origen: no se suman."))
    if f is None or not f.conectada:
        porque = (f"Fuente no conectada ({f.nota or f.info.fase})." if f
                  else "Fuente no conectada (no hay conector para esta plataforma).")
        return [m.faltante(et, nombre, "desde el inicio", d, porque, fmt)
                for et, _, fmt, d in defs]
    filas = [d for d in dias if d.get("campana_id") == row.get("campana_id")]
    out = []
    for et, col, fmt, d in defs:
        vals = [m.num(x.get(col)) for x in filas]
        if not filas or any(v is None for v in vals):
            out.append(m.faltante(et, nombre, "desde el inicio", d,
                                  "La plataforma aún no reporta esta campaña.", fmt))
        else:
            out.append(m.Dato(et, round(sum(vals), 2), "real", nombre, "desde el inicio", d,
                              f.actualizado, fmt))
    return out


def campanas(rows: list[dict], obras: list[dict], approvals: list, topes_rows: list[dict],
             pedidos_rows: list[dict], dias: list[dict], fuentes: dict[str, m.EstadoFuente],
             now: datetime) -> list[Campana]:
    titulos = {o.get("obra_id"): o.get("titulo") or o.get("titulo_es") or o.get("obra_id")
               for o in obras}
    by_id = {a.aprobacion_id: a for a in approvals}
    tps = topes(topes_rows)
    por_utm: dict[str, list[list[dict]]] = defaultdict(list)
    for lines in _pedidos_vivos(pedidos_rows).values():
        if lines[0].get("origen_estado") == "ok" and lines[0].get("utm_campana"):
            por_utm[lines[0]["utm_campana"].strip().lower()].append(lines)
    out = []
    for r in rows:
        oid = r.get("obra_id") or ""
        c = Campana(r, gate(r, by_id, now), titulos.get(oid, oid) if oid else "",
                    m.num(r.get("presupuesto_diario_usd")), m.num(r.get("presupuesto_total_usd")),
                    plan_mes(r, now), tps.get(r.get("plataforma") or ""),
                    _resultado_shopify(r, por_utm, fuentes),
                    _resultados_plataforma(r, dias, fuentes))
        if c.gate.alerta:
            c.avisos.append(c.gate.texto)
        if c.estado in EN_PLAN:
            if c.diario is None:
                c.avisos.append("Falta el presupuesto diario")
            if c.tope is None:
                c.avisos.append("No hay tope para esta plataforma en la pestaña Topes")
            elif c.tope.diario is not None and c.diario is not None and c.diario > c.tope.diario:
                c.avisos.append(f"Presupuesto diario US${c.diario:,.2f} pasa el tope de "
                                f"US${c.tope.diario:,.2f}")
                c.excede = True
            if not (r.get("utm_campana") or "").strip() and r.get("destino") != "etsy":
                c.avisos.append("Sin utm_campana: Shopify no podrá ligar ventas a la campaña")
        out.append(c)
    # monthly limit per platform: what is already approved, plus each proposal on top of it
    for plat, tope in tps.items():
        if tope.mensual is None:
            continue
        aprobado = sum(c.plan_mes or 0 for c in out if c.plataforma == plat and _vigente(c))
        nombre = PLATAFORMA.get(plat, plat)
        for c in out:
            if c.plataforma != plat or c.estado not in EN_PLAN:
                continue
            if _vigente(c) and aprobado > tope.mensual:
                c.avisos.append(f"Lo aprobado en {nombre} suma US${aprobado:,.2f} este mes; "
                                f"el tope mensual es US${tope.mensual:,.2f}")
                c.excede = True
            elif not _vigente(c) and aprobado + (c.plan_mes or 0) > tope.mensual:
                c.avisos.append(f"Con lo ya aprobado en {nombre} (US${aprobado:,.2f}) esta "
                                f"campaña llevaría el mes a US${aprobado + (c.plan_mes or 0):,.2f}; "
                                f"el tope mensual es US${tope.mensual:,.2f}")
                c.excede = True
    orden = list(ESTADO)
    out.sort(key=lambda c: (orden.index(c.estado) if c.estado in orden else 99,
                            c.row.get("inicio") or ""))
    return out


def _vigente(c: Campana) -> bool:
    """Approved or running with a valid approval: it counts as committed spend."""
    return c.estado in ("aprobada", "activa") and c.gate.estado == "ok"


@dataclass
class PlanPlataforma:
    plataforma: str
    aprobado: float      # this month, approved or running campaigns with a valid approval
    propuesto: float     # this month, everything else in the plan (waiting or not asked)
    tope: Tope | None

    @property
    def pasa(self) -> bool:
        return bool(self.tope and self.tope.mensual is not None
                    and self.aprobado > self.tope.mensual)


def plan_por_plataforma(cs: list[Campana], tps: dict[str, Tope]) -> list[PlanPlataforma]:
    plats = sorted({c.plataforma for c in cs if c.estado in EN_PLAN} | set(tps))
    out = []
    for p in plats:
        mias = [c for c in cs if c.plataforma == p and c.estado in EN_PLAN]
        out.append(PlanPlataforma(
            p, round(sum(c.plan_mes or 0 for c in mias if _vigente(c)), 2),
            round(sum(c.plan_mes or 0 for c in mias if not _vigente(c)), 2), tps.get(p)))
    return out


# --- headline numbers ------------------------------------------------------------------------

def resumen(cs: list[Campana], pedidos_rows: list[dict], dias: list[dict],
            fuentes: dict[str, m.EstadoFuente], per: m.Periodo, now: datetime) -> list[m.Dato]:
    datos: list[m.Dato] = []
    # 1. real spend, only from the platforms themselves
    ads = [f for f in (fuentes["meta"], fuentes["pinterest"]) if f.conectada]
    def_gasto = "Gasto reportado por cada plataforma de anuncios en el periodo."
    if not ads:
        datos.append(m.faltante("Gasto publicitario", "Meta Ads + Pinterest Ads", per.texto,
                                def_gasto, "Fuente no conectada: Meta y Pinterest aún no "
                                "están conectados."))
    else:
        g = sum(m.num(c.get("gasto")) or 0 for c in dias if per.contiene(m.parse_dt(c.get("fecha"))))
        datos.append(m.Dato("Gasto publicitario", round(g, 2), "real",
                            " + ".join(f.info.nombre for f in ads), per.texto, def_gasto,
                            min((f.actualizado for f in ads if f.actualizado), default=None),
                            "usd"))
    # 2. approved plan
    vigentes = [c for c in cs if c.estado in ("aprobada", "activa") and c.gate.estado == "ok"]
    datos.append(m.Dato(
        "Presupuesto diario aprobado", round(sum(c.diario or 0 for c in vigentes), 2), "real",
        FUENTE + " + Aprobaciones", "a la fecha",
        "Suma del presupuesto diario de las campañas aprobadas o activas con aprobación "
        "válida. Es el plan, no lo gastado.", now, "usd",
        nota=f"{len(vigentes)} campaña(s)"))
    planes = [c.plan_mes for c in vigentes]
    mes_ini, _ = _mes(now)
    if any(p is None for p in planes):
        datos.append(m.faltante("Plan del mes", FUENTE, f"mes de {m.MESES[mes_ini.month - 1]}",
                                "Lo más que pueden gastar este mes las campañas aprobadas, "
                                "según su presupuesto diario, fechas y total.",
                                "Alguna campaña aprobada no tiene presupuesto diario."))
    else:
        datos.append(m.Dato("Plan del mes", round(sum(planes), 2), "estimado", FUENTE,
                            f"mes de {m.MESES[mes_ini.month - 1]}",
                            "Lo más que pueden gastar este mes las campañas aprobadas, según "
                            "su presupuesto diario, fechas y total. Cálculo nuestro, no gasto.",
                            now, "usd"))
    datos.append(m.Dato("Esperan tu aprobación", sum(1 for c in cs if c.gate.estado == "pendiente"),
                        "real", FUENTE + " + Aprobaciones", "a la fecha",
                        "Campañas con una solicitud de aprobación pendiente.", now, "n",
                        enlace="/aprobar"))
    # 3. what Shopify attributes to ads
    shop = fuentes["shopify"]
    def_anuncio = ("Pedidos de Shopify creados en el periodo cuya última visita llegó de un "
                   "anuncio (utm_medium de pago o tipo de visita “anuncio”), según el "
                   "recorrido del cliente de Shopify. Atribución de último clic de Shopify.")
    if not shop.conectada:
        datos.append(m.faltante("Pedidos desde anuncios", "Shopify", per.texto, def_anuncio,
                                "Shopify no está conectado.", "n"))
    else:
        filas = atribucion(pedidos_rows, per)
        sin = sum(f.pedidos_sin_saber for f in filas)
        datos.append(m.Dato("Pedidos desde anuncios", sum(f.pedidos_anuncio for f in filas),
                            "real", "Shopify (recorrido del cliente)", per.texto, def_anuncio,
                            shop.actualizado, "n",
                            nota=f"{sin} pedido(s) sin dato de origen" if sin else ""))
    datos.append(roas_equilibrio(pedidos_rows, per, shop))
    return datos


def roas_equilibrio(pedidos_rows: list[dict], per: m.Periodo, shop: m.EstadoFuente) -> m.Dato:
    """Break-even ROAS = ventas netas / margen antes de anuncios (requirements, section 14)."""
    definicion = ("Ventas que un dólar de anuncios debe traer para no perder: ventas netas ÷ "
                  "margen antes de anuncios de los pedidos del periodo. Si el margen es 40% "
                  "de las ventas, el equilibrio es 2.5. Antes de gastos fijos y ganancia.")
    fuente = "Pedidos (Shopify) + comisiones + costos de Prodigi"
    vivos = [r for lines in _pedidos_vivos(pedidos_rows).values()
             if per.contiene(m.parse_dt(lines[0].get("fecha"))) for r in lines]
    if not shop.conectada or not vivos:
        return m.faltante("ROAS de equilibrio", fuente, per.texto, definicion,
                          "Sin pedidos en el periodo." if shop.conectada
                          else "Shopify no está conectado.", "n")
    if any(r.get("calidad_dato") not in ("real", "estimado") for r in vivos):
        return m.faltante("ROAS de equilibrio", fuente, per.texto, definicion,
                          "Algún pedido del periodo no tiene todos sus costos.", "n")
    ventas = sum(m.neto_linea(r) for r in vivos)
    margen = sum(m.num(r.get("margen_contribucion")) or 0 for r in vivos)
    if ventas <= 0 or margen <= 0:
        return m.faltante("ROAS de equilibrio", fuente, per.texto, definicion,
                          "Sin margen positivo en el periodo: ningún anuncio sería rentable.",
                          "n")
    return m.Dato("ROAS de equilibrio", round(ventas / margen, 2), "estimado", fuente,
                  per.texto, definicion, shop.actualizado, "x",
                  nota=f"margen {margen / ventas:.0%} de las ventas")


def alertas(cs: list[Campana]) -> list[Campana]:
    """Campaigns that are over a limit, or running/approved without a valid approval."""
    return [c for c in cs if c.alerta]


# --- asking for approval ---------------------------------------------------------------------

def solicitar(book, store, campana_id: str, creado_por: str = "Publicidad",
              now: datetime | None = None):
    """Create the approval request for a campaign and write its id into the row.

    Refuses when the plan breaks a limit or has no limit: Lorena sets the limits first.
    A campaign that was approved before asks for a ``presupuesto`` approval (a change);
    a new one asks for ``anuncio``. Nothing is sent to any platform.
    """
    from datetime import timezone

    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    rows = book.read("Publicidad")
    row = next((r for r in rows if r.get("campana_id") == campana_id), None)
    if row is None:
        raise KeyError(f"No hay campaña {campana_id!r} en la pestaña Publicidad")
    todas = campanas(rows, book.read("Obras"), store.all(), book.read("Topes"), [], [],
                     {k: m.EstadoFuente(m.FUENTE_BY_KEY[k], "sin-conectar", None)
                      for k in m.FUENTE_BY_KEY}, now)
    c = next(x for x in todas if x.campana_id == campana_id)
    if c.diario is None:
        raise ValueError("Falta presupuesto_diario_usd")
    if c.tope is None:
        raise ValueError(f"No hay tope para {c.plataforma or 'esta plataforma'} en la pestaña "
                         "Topes: Lore lo define antes de aprobar campañas")
    if c.tope.diario is not None and c.diario > c.tope.diario:
        raise ValueError(f"US${c.diario:,.2f}/día pasa el tope diario de US${c.tope.diario:,.2f}")
    if c.tope.mensual is not None:
        aprobado = sum(x.plan_mes or 0 for x in todas
                       if x.plataforma == c.plataforma and _vigente(x) and x is not c)
        if aprobado + (c.plan_mes or 0) > c.tope.mensual:
            raise ValueError(f"Con lo ya aprobado (US${aprobado:,.2f}) el mes llegaría a "
                             f"US${aprobado + (c.plan_mes or 0):,.2f}; el tope mensual es "
                             f"US${c.tope.mensual:,.2f}")
    if c.gate.estado in ("ok", "pendiente"):
        raise ValueError(f"Ya tiene una aprobación {c.gate.estado}: {row.get('aprobacion_id')}")
    previa = row.get("estado") in ("activa", "pausada") or c.gate.estado == "cambio"
    antes = _diario_aprobado(store, row.get("aprobacion_id"))
    if antes and c.tope.cambio_pct is not None:
        cambio = abs(c.diario - antes) / antes * 100
        if cambio > c.tope.cambio_pct + 1e-9:
            raise ValueError(f"El presupuesto diario cambia {cambio:.0f}% (de US${antes:,.2f} a "
                             f"US${c.diario:,.2f}); el cambio máximo es {c.tope.cambio_pct:.0f}%")
    monto = c.total if c.total is not None else (c.plan_mes or 0.0)
    rec = request_approval(
        store, tipo="presupuesto" if previa else "anuncio", linea=row.get("linea") or "US-POD",
        creado_por=creado_por, monto_usd=monto, now=now,
        resumen=(f"{'Cambio en' if previa else 'Nueva'} campaña de "
                 f"{PLATAFORMA.get(c.plataforma, c.plataforma)}: “{c.nombre}”, "
                 f"US${c.diario:,.2f}/día" + (f", máx. US${c.total:,.2f}" if c.total else "")),
        contenido=campana_aprobable(row))
    cambios = {"campana_id": campana_id, "linea": row.get("linea") or "US-POD",
               "aprobacion_id": rec.aprobacion_id}
    if row.get("estado") in ("idea", "borrador", "", None):
        cambios["estado"] = "por-aprobar"
    book.upsert("Publicidad", [cambios])
    return rec


def _diario_aprobado(store, aprobacion_id: str | None) -> float | None:
    """Daily budget of the campaign's last approved plan, if there is one."""
    if not aprobacion_id:
        return None
    try:
        a = store.get(aprobacion_id)
    except KeyError:
        return None
    if a.estado != "aprobado":
        return None
    try:
        return m.num(a.contenido.get("presupuesto_diario_usd"))
    except (ValueError, AttributeError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pedir a Lore que apruebe una campaña")
    parser.add_argument("--pedir", metavar="CAMPANA_ID", required=True)
    args = parser.parse_args(argv)
    from ..approval.store import SheetsStore, open_store
    from ..localbook import open_workbook
    from ..workbook import Workbook

    book = open_workbook()
    store = SheetsStore(book) if isinstance(book, Workbook) else open_store()
    try:
        rec = solicitar(book, store, args.pedir)
    except (KeyError, ValueError) as e:
        print(f"No se pidió: {e}", file=sys.stderr)
        return 1
    print(f"Solicitud {rec.aprobacion_id} creada ({rec.tipo}, US${rec.monto_usd}). "
          "Lore la ve en Aprobar. No se envió nada a ninguna plataforma.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
