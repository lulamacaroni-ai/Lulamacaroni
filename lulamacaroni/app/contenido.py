"""Contenido: the content queue and calendar per platform, with each piece's approval.

Lorena's requirements, section 3 and 11: keep a queue of ideas, drafts, approved,
scheduled and published pieces; nothing is published without her approval; keep the link
and result of each post. Rows live in the ``Contenido`` tab. Pinterest results come from the
read-only Pinterest sync (``Pines``, ``Tableros``, ``PinterestDiario``); Instagram is not
connected yet, so its results show "—".

The approval gate covers exactly :func:`contenido_aprobable`: platform, format, language,
text, image file and date. Any edit after approval changes the fingerprint and the piece
needs a new approval; the screen says so before anything tries to publish it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..approval.gate import fingerprint
from . import metrics as m

PLATAFORMA = {"instagram": "Instagram", "pinterest": "Pinterest", "otro": "Otro"}
ESTADO = {"idea": "Ideas", "borrador": "Borradores", "aprobado": "Aprobados",
          "programado": "Programados", "publicado": "Publicados", "fallido": "Fallidos"}
NECESITA_APROBACION = {"aprobado", "programado", "publicado"}
FUENTE = "Libro de datos (pestaña Contenido)"
CAMPOS_APROBADOS = ("contenido_id", "plataforma", "formato", "idioma", "texto", "archivo",
                    "programado_para")


def contenido_aprobable(row: dict) -> dict:
    """The exact content Lorena approves for a piece (what the publisher will send)."""
    return {"tipo": "contenido", **{k: str(row.get(k) or "") for k in CAMPOS_APROBADOS}}


@dataclass
class Gate:
    # ok | pendiente | cambio | rechazado | expirado | cancelado | sin-aprobacion |
    # no-hace-falta | perdida | usada
    estado: str
    texto: str
    alerta: bool = False


def gate(row: dict, approvals: dict, now: datetime) -> Gate:
    aid = row.get("aprobacion_id") or ""
    estado = row.get("estado") or ""
    if not aid:
        if estado in NECESITA_APROBACION:
            return Gate("sin-aprobacion", "Marcado como " + estado + " sin aprobación de Lore",
                        alerta=True)
        return Gate("no-hace-falta", "Aún no pide aprobación")
    a = approvals.get(aid)
    if a is None:
        return Gate("perdida", f"La aprobación {aid} no está en Aprobaciones", alerta=True)
    if a.tipo != "contenido":
        return Gate("perdida", f"{aid} aprueba “{a.tipo}”, no contenido", alerta=True)
    if a.estado == "pendiente":
        return Gate("pendiente", "Esperando tu aprobación")
    if a.estado in ("rechazado", "expirado", "cancelado"):
        return Gate(a.estado, {"rechazado": "Rechazado", "expirado": "Aprobación vencida",
                               "cancelado": "Solicitud cancelada"}[a.estado],
                    alerta=estado in NECESITA_APROBACION)
    if a.huella != fingerprint(contenido_aprobable(row)):
        return Gate("cambio", "Cambió después de aprobarse: necesita nueva aprobación",
                    alerta=estado != "publicado")
    if a.ejecutado_en and estado != "publicado":
        return Gate("usada", "La aprobación ya se usó para publicar", alerta=True)
    quien = a.decidido_por or "Lore"
    cuando = m.dia(m.parse_dt(a.decidido_en)) if a.decidido_en else ""
    return Gate("ok", f"Aprobado por {quien}" + (f" el {cuando}" if cuando else ""))


@dataclass
class Pieza:
    row: dict
    fecha: datetime | None
    obra: str
    gate: Gate

    @property
    def plataforma(self) -> str:
        return self.row.get("plataforma") or ""

    @property
    def estado(self) -> str:
        return self.row.get("estado") or ""

    @property
    def titulo(self) -> str:
        return (self.row.get("titulo") or (self.row.get("texto") or "")[:60]
                or self.row.get("contenido_id", ""))


def piezas(rows: list[dict], obras: list[dict], approvals: list, now: datetime,
           plataforma: str = "") -> list[Pieza]:
    titulos = {o.get("obra_id"): o.get("titulo") or o.get("titulo_es") or o.get("obra_id")
               for o in obras}
    by_id = {a.aprobacion_id: a for a in approvals}
    out = []
    for r in rows:
        if plataforma and r.get("plataforma") != plataforma:
            continue
        oid = r.get("obra_id") or ""
        out.append(Pieza(r, m.parse_dt(r.get("programado_para")),
                         titulos.get(oid, oid) if oid else "", gate(r, by_id, now)))
    out.sort(key=lambda p: (p.fecha is None, p.fecha or now))
    return out


def calendario(ps: list[Pieza], now: datetime, dias: int = 14) -> list[tuple[datetime, list[Pieza]]]:
    """Pieces with a date in the next ``dias`` days, grouped by day (CDMX)."""
    hoy = now.astimezone(m.TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for i in range(dias):
        d0 = hoy + timedelta(days=i)
        d1 = d0 + timedelta(days=1)
        del_dia = [p for p in ps if p.fecha and d0 <= p.fecha < d1
                   and p.estado not in ("idea", "fallido")]
        if del_dia:
            out.append((d0, del_dia))
    return out


def resumen(ps: list[Pieza], fuentes: dict[str, m.EstadoFuente], now: datetime) -> list[m.Dato]:
    semana = now + timedelta(days=7)
    mes = now - timedelta(days=30)
    nota = "Registrado en la hoja (lo que se marcó a mano)."
    datos = [
        m.Dato("Programadas 7 días", sum(1 for p in ps if p.estado in ("aprobado", "programado")
                                         and p.fecha and now <= p.fecha < semana),
               "real", FUENTE, "próximos 7 días",
               "Piezas aprobadas o programadas con fecha en los próximos 7 días.", now, "n",
               nota=nota),
        m.Dato("Esperan aprobación", sum(1 for p in ps if p.gate.estado == "pendiente"), "real",
               FUENTE + " + Aprobaciones", "a la fecha",
               "Piezas con una solicitud de aprobación pendiente.", now, "n", enlace="/aprobar"),
        m.Dato("Publicadas 30 días", sum(1 for p in ps if p.estado == "publicado" and p.fecha
                                         and mes <= p.fecha <= now),
               "real", FUENTE, "últimos 30 días",
               "Piezas marcadas como publicadas con fecha en los últimos 30 días.", now, "n",
               nota=nota),
    ]
    ig = fuentes.get("instagram")
    if not (ig and ig.conectada):
        datos.append(m.faltante(
            "Resultados de Instagram", "Instagram", "últimos 30 días",
            "Alcance, guardados, compartidos y clics de lo publicado, según Instagram.",
            "Instagram aún no está conectado.", "n", "/fuentes"))
    return datos


def alertas(ps: list[Pieza], now: datetime) -> list[Pieza]:
    """Pieces whose approval is missing, broken or changed, dated in the past or next 3 days."""
    limite = now + timedelta(days=3)
    return [p for p in ps if p.gate.alerta
            and (p.estado == "publicado" or p.fecha is None or p.fecha <= limite)]


# --- Pinterest results (read-only, from the Pinterest sync) ---------------------------------

FUENTE_PIN = "Pinterest (analítica de la cuenta)"
TABS_PINTEREST = ("PinterestDiario", "Pines", "Tableros")


@dataclass
class VistaPinterest:
    conectada: bool
    nota: str                  # why not, or the source note (account, token expiry)
    datos: list[m.Dato]
    pines: list[dict]          # most seen first
    tableros: list[dict]
    faltan_tabs: list[str]


def _suma(rows: list[dict], col: str) -> float | None:
    vals = [m.num(r.get(col)) for r in rows]
    return None if any(v is None for v in vals) else sum(vals)


def pinterest(diario: list[dict], pines: list[dict], tableros: list[dict],
              fuentes: dict[str, m.EstadoFuente], now: datetime,
              faltan_tabs: list[str] | None = None) -> VistaPinterest:
    """Account totals for the last 30 days of data, the pins ranked by impressions, boards.

    A day Pinterest is still processing makes the total ``estimado``; a day it can't report
    (or no rows at all) makes it ``faltante``. Never a zero for something unknown.
    """
    f = fuentes.get("pinterest")
    defs = (("Impresiones", "impresiones", "Veces que se vieron tus pines en Pinterest."),
            ("Guardados", "guardados", "Veces que alguien guardó uno de tus pines."),
            ("Clics al enlace", "clics_enlace",
             "Clics que salieron de Pinterest hacia el enlace del pin (la tienda)."),
            ("Clics en el pin", "clics_pin", "Clics para ver el pin en grande."))
    periodo = "últimos 30 días con datos (Pinterest reporta con 1–2 días de retraso)"
    if not f or not f.conectada:
        porque = ("Fuente no conectada" + (f" ({f.nota or f.info.fase})." if f else "."))
        if f and f.estado == "error":
            porque = f"La última sincronización falló ({f.nota})."
        return VistaPinterest(False, porque, [m.faltante(e, "Pinterest", periodo, d, porque, "n",
                                                         "/fuentes") for e, _, d in defs],
                              [], [], faltan_tabs or [])
    limite = (now - timedelta(days=31)).date().isoformat()
    filas = sorted((r for r in diario if (r.get("fecha") or "") >= limite),
                   key=lambda r: r.get("fecha") or "")
    calidades = {r.get("calidad_dato") for r in filas}
    datos = []
    for etiqueta, col, definicion in defs:
        total = _suma(filas, col)
        if not filas or total is None or "faltante" in calidades:
            datos.append(m.faltante(
                etiqueta, FUENTE_PIN, periodo, definicion,
                "Pinterest aún no reporta estos días." if not filas
                else "Pinterest no reporta algún día del periodo.", "n", "/fuentes"))
            continue
        calidad = "estimado" if "estimado" in calidades else "real"
        datos.append(m.Dato(
            etiqueta, total, calidad, FUENTE_PIN,
            f"{filas[0]['fecha']} a {filas[-1]['fecha']}", definicion, f.actualizado, "n",
            nota="Pinterest aún procesa algún día: puede subir." if calidad == "estimado" else ""))
    vistos = sorted(pines, key=lambda p: (m.num(p.get("impresiones")) is None,
                                          -(m.num(p.get("impresiones")) or 0)))
    tabs = sorted(tableros, key=lambda t: -(m.num(t.get("pines")) or 0))
    return VistaPinterest(True, f.nota, datos, vistos, tabs, faltan_tabs or [])
