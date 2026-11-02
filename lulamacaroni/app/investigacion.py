"""Investigación: keywords, trends, competitor prices and keyword ideas per artwork.

Lorena's requirements, sections 7 and 8. The data are the monthly eRank and EverBee CSV
exports that ``python -m lulamacaroni.connectors.investigacion`` writes into the
Investigacion tab (one Importaciones row per file). Rules kept here:

* Every number names its file, the export date and what it measures. Search volume,
  competition, sales and revenue are the tool's estimates (``estimado``); a competitor's
  price is what the tool saw published that day.
* Nothing imported means "—" with the reason, never a zero or sample data.
* A trend is called sustained only after three monthly exports in a row; one jump is a
  peak. High demand with low competition is an opportunity to look at, never a promise
  of sales, and only Lorena decides whether it fits Lula.
* Suggested keywords are matches between imported keywords and the artwork's own words
  (Obras: título, tema, colores, colección). Read-only: nothing is published or changed.

Pure functions over workbook rows: no network, no writes.
"""

from __future__ import annotations

import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from . import metrics as m
from ..connectors.investigacion import FUENTE_NOMBRE, _norm

CATEGORIA = {"print": "Prints", "enmarcado": "Enmarcados", "descargable": "Descargables",
             "cojin": "Cojines", "wallpaper": "Wallpaper", "otro": "Otros"}
ORIGEN_FECHA = {"nombre-archivo": "fecha del nombre del archivo",
                "archivo": "fecha del archivo (no venía en el nombre)",
                "dia-importacion": "día en que se importó (el archivo no traía fecha)"}
DEMANDA_MIN = 100          # searches per month below which a keyword is not an opportunity
EXPORT_MAX_DIAS = 35       # a monthly export older than this is due again
MESES_SOSTENIDA = 3
PICO = 1.5                 # last month this many times the previous best = a peak
STOP = {"the", "and", "with", "for", "from", "your", "this", "that", "wall", "para", "con",
        "del", "las", "los", "una", "uno", "print", "prints", "art", "arte", "obra", "serie",
        "coleccion", "collection", "decor", "gift", "home"}
AVISO = ("Las cifras de eRank y EverBee son estimaciones de cada herramienta. Mucha "
         "demanda con poca competencia no garantiza ventas; solo tú decides si encaja con Lula.")


@dataclass(eq=False)
class Export:
    row: dict
    fuente: str
    tipo: str
    archivo: str
    fecha: date | None
    origen: str
    importado: datetime | None

    @property
    def texto(self) -> str:
        return f"{FUENTE_NOMBRE.get(self.fuente, self.fuente)} · {self.archivo}"


@dataclass
class Keyword:
    texto: str
    fuente: str
    categoria: str
    mercado: str
    busquedas: m.Dato
    competencia: m.Dato
    competencia_texto: str       # a level like "Low" when the tool gives no number
    ctr: m.Dato
    tendencia_archivo: str
    tendencia: str               # sube | baja | pico | estable | sin-historial
    tendencia_texto: str
    historial: list[tuple[date, float]]
    export: Export

    @property
    def puntaje(self) -> float | None:
        b, c = self.busquedas.valor, self.competencia.valor
        if b is None or c is None or b < DEMANDA_MIN:
            return None
        return b / max(c, 1)


@dataclass
class Precios:
    categoria: str
    n: int
    minimo: m.Dato
    mediana: m.Dato
    maximo: m.Dato
    ventas: m.Dato
    fuentes: str


@dataclass
class Sugerencia:
    obra_id: str
    titulo: str
    ideas: list[tuple[Keyword, str]] = field(default_factory=list)   # (keyword, why)
    lista: list[dict] = field(default_factory=list)                   # Lore's Keywords rows


@dataclass
class Investigacion:
    exports: dict[str, Export]           # "erank-keyword" -> latest export
    keywords: list[Keyword]
    productos: list[dict]
    precios: list[Precios]
    importaciones: list[dict]
    sugerencias: list[Sugerencia]
    faltan_tabs: list[str] = field(default_factory=list)

    def ultimo(self, fuente: str) -> Export | None:
        es = [e for k, e in self.exports.items() if e.fuente == fuente]
        return max(es, key=_orden_export) if es else None

    @property
    def oportunidades(self) -> list[Keyword]:
        ks = [k for k in self.keywords if k.puntaje is not None and k.tendencia != "baja"]
        return sorted(ks, key=lambda k: -k.puntaje)[:10]

    @property
    def sostenidas(self) -> list[Keyword]:
        return [k for k in self.keywords if k.tendencia == "sube"]


def _fecha(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _orden_export(e: Export):
    return (e.fecha or date.min, e.importado or datetime.min.replace(tzinfo=m.TZ))


def exports(importaciones: list[dict]) -> dict[str, Export]:
    """The latest successful import per (fuente, tipo)."""
    out: dict[str, Export] = {}
    for r in importaciones:
        if r.get("estado") not in ("ok", "parcial") or not r.get("fuente"):
            continue
        e = Export(r, r["fuente"], r.get("tipo") or "", r.get("archivo") or "",
                   _fecha(r.get("fecha_export")), r.get("fecha_export_origen") or "",
                   m.parse_dt(r.get("importado_en")))
        k = f"{e.fuente}-{e.tipo}"
        if k not in out or _orden_export(e) > _orden_export(out[k]):
            out[k] = e
    return out


def _periodo(e: Export) -> str:
    d = e.fecha
    cuando = f"{d.day} {m.MESES[d.month - 1]} {d.year}" if d else "fecha —"
    return f"export del {cuando} (promedio mensual según {FUENTE_NOMBRE.get(e.fuente, e.fuente)})"


def _dato(etiqueta: str, value, calidad: str, e: Export, definicion: str,
          formato: str = "n") -> m.Dato:
    v = m.num(value)
    if v is None:
        return m.faltante(etiqueta, e.texto, _periodo(e), definicion,
                          "El archivo no trae esta columna o la celda está vacía.", formato)
    return m.Dato(etiqueta, v, calidad, e.texto, _periodo(e), definicion, e.importado, formato)


def _serie(puntos: list[tuple[date, float]]) -> list[tuple[date, float]]:
    """One value per month (the latest export of each month), oldest first."""
    por_mes: dict[tuple[int, int], tuple[date, float]] = {}
    for d, v in sorted(puntos):
        por_mes[(d.year, d.month)] = (d, v)
    return [por_mes[k] for k in sorted(por_mes)]


def tendencia(puntos: list[tuple[date, float]]) -> tuple[str, str]:
    s = [v for _, v in _serie(puntos)]
    if len(s) < 2:
        return "sin-historial", "un solo export; la tendencia se ve desde el segundo mes"
    ult = s[-MESES_SOSTENIDA:]
    if len(ult) == MESES_SOSTENIDA and all(a < b for a, b in zip(ult, ult[1:])):
        return "sube", f"sube {MESES_SOSTENIDA} meses seguidos"
    if len(ult) == MESES_SOSTENIDA and all(a > b for a, b in zip(ult, ult[1:])):
        return "baja", f"baja {MESES_SOSTENIDA} meses seguidos"
    if s[-1] > PICO * max(s[:-1]):
        return "pico", "pico del último mes (aún no es tendencia)"
    return "estable", f"sin cambio sostenido en {len(s)} meses"


def keywords(rows: list[dict], ex: dict[str, Export]) -> list[Keyword]:
    imp_vigente = {e.row["importacion_id"]: e for k, e in ex.items() if e.tipo == "keyword"}
    fechas = {r.get("importacion_id"): _fecha(r.get("fecha_export")) for r in rows}
    hist: dict[tuple, list[tuple[date, float]]] = defaultdict(list)
    for r in rows:
        if r.get("tipo") != "keyword":
            continue
        b, d = m.num(r.get("busquedas")), fechas.get(r.get("importacion_id"))
        if b is not None and d:
            hist[(r.get("fuente"), _norm(r.get("keyword")), r.get("mercado") or "")].append((d, b))
    out = []
    for r in rows:
        e = imp_vigente.get(r.get("importacion_id"))
        if not e or r.get("tipo") != "keyword":
            continue
        clave = (r.get("fuente"), _norm(r.get("keyword")), r.get("mercado") or "")
        t, tt = tendencia(hist.get(clave, []))
        comp = r.get("competencia")
        comp_txt = "" if m.num(comp) is not None else str(comp or "")
        out.append(Keyword(
            str(r.get("keyword")), e.fuente, r.get("categoria") or "otro",
            r.get("mercado") or "",
            _dato("Búsquedas", r.get("busquedas"), "estimado", e,
                  "Búsquedas por mes que estima la herramienta para esta keyword."),
            _dato("Competencia", comp, "estimado", e,
                  "Listings que compiten por esta keyword según la herramienta."),
            comp_txt,
            _dato("CTR", r.get("ctr"), "estimado", e,
                  "Porcentaje de búsquedas que terminan en clic, según la herramienta."),
            str(r.get("tendencia") or ""), t, tt, _serie(hist.get(clave, [])), e))
    return sorted(out, key=lambda k: -(k.busquedas.valor or -1))


def precios(rows: list[dict], ex: dict[str, Export]) -> list[Precios]:
    vigentes = {e.row["importacion_id"]: e for e in ex.values() if e.tipo == "producto"}
    prods = [r for r in rows if r.get("importacion_id") in vigentes]
    por: dict[str, list[dict]] = defaultdict(list)
    for r in prods:
        if (r.get("moneda") or "USD") == "USD" and m.num(r.get("precio")) is not None:
            por[r.get("categoria") or "otro"].append(r)
    out = []
    for cat in sorted(por, key=lambda c: list(CATEGORIA).index(c) if c in CATEGORIA else 99):
        rs = por[cat]
        es = sorted({vigentes[r["importacion_id"]] for r in rs}, key=_orden_export,
                    reverse=True)
        e = es[0]
        txt = " + ".join(x.texto for x in es)
        ps = [m.num(r["precio"]) for r in rs]
        defin = f"Precio publicado de {len(rs)} producto(s) de la competencia, en USD."
        vs = [v for r in rs if (v := m.num(r.get("ventas_mes"))) is not None]

        def d(etq, v, calidad="real", formato="usd", definicion=defin):
            return m.Dato(etq, round(v, 2), calidad, txt, _periodo(e), definicion,
                          e.importado, formato)
        ventas = (d("Ventas/mes (mediana)", statistics.median(vs), "estimado", "n",
                    "Mediana de las ventas mensuales que la herramienta estima para estos "
                    "competidores. Es una estimación, no un dato de sus tiendas.")
                  if vs else m.faltante("Ventas/mes (mediana)", txt, _periodo(e),
                                        "Ventas mensuales estimadas.",
                                        "El archivo no trae ventas estimadas.", "n"))
        out.append(Precios(cat, len(rs), d("Mínimo", min(ps)),
                           d("Mediana", statistics.median(ps)), d("Máximo", max(ps)),
                           ventas, txt))
    return out


def _palabras(texto: str) -> set[str]:
    out = set()
    for w in re.split(r"[\s,;/|·\-]+", str(texto or "")):
        n = _norm(w)
        if len(n) >= 4 and n not in STOP:
            out.add(n[:-1] if n.endswith("s") and len(n) > 4 else n)
    return out


def sugerencias(obras: list[dict], ks: list[Keyword], lista: list[dict],
                n: int = 5) -> list[Sugerencia]:
    por_obra: dict[str, list[dict]] = defaultdict(list)
    for r in lista:
        por_obra[str(r.get("obra_id") or "")].append(r)
    out = []
    for o in obras:
        if o.get("estado") == "archivada" or not o.get("obra_id"):
            continue
        oid = str(o["obra_id"])
        ya = {_norm(r.get("keyword")) for r in por_obra.get(oid, [])}
        campos = {"título": f"{o.get('titulo', '')} {o.get('titulo_es', '')}",
                  "tema": o.get("tema"), "colores": o.get("colores"),
                  "colección": o.get("coleccion")}
        palabras = {campo: _palabras(t) for campo, t in campos.items()}
        ideas = []
        for k in ks:
            if _norm(k.texto) in ya:
                continue
            kw = _palabras(k.texto)
            for campo, ps in palabras.items():
                comun = sorted(ps & kw)
                if comun:
                    ideas.append((k, f"coincide con {campo}: {', '.join(comun)}"))
                    break
        ideas.sort(key=lambda kv: (-(kv[0].puntaje or 0), -(kv[0].busquedas.valor or 0)))
        vistos, unicas = set(), []
        for k, why in ideas:
            if _norm(k.texto) not in vistos:
                vistos.add(_norm(k.texto))
                unicas.append((k, why))
        out.append(Sugerencia(oid, str(o.get("titulo") or o.get("titulo_es") or oid),
                              unicas[:n], por_obra.get(oid, [])))
    return sorted(out, key=lambda s: (not s.lista, not s.ideas, s.titulo))


def investigacion(rows: list[dict], importaciones: list[dict], lista: list[dict],
                  obras: list[dict], faltan_tabs: list[str] | None = None) -> Investigacion:
    ex = exports(importaciones)
    ks = keywords(rows, ex)
    vig = {e.row["importacion_id"] for e in ex.values() if e.tipo == "producto"}
    prods = [r for r in rows if r.get("importacion_id") in vig]
    imps = sorted(importaciones, key=lambda r: str(r.get("importado_en") or ""), reverse=True)
    return Investigacion(ex, ks, prods, precios(rows, ex), imps,
                         sugerencias(obras, ks, lista), list(faltan_tabs or []))


def filtrar(ks: list[Keyword], categoria: str) -> list[Keyword]:
    return [k for k in ks if k.categoria == categoria] if categoria in CATEGORIA else ks


# --- summary numbers -------------------------------------------------------------------------

def _export_dato(inv: Investigacion, fuente: str, fuentes: dict[str, m.EstadoFuente],
                 now: datetime) -> m.Dato:
    nombre = FUENTE_NOMBRE[fuente]
    etq = f"Último export {nombre}"
    defin = "Fecha del export más reciente que se importó."
    e = inv.ultimo(fuente)
    if not e or not e.fecha:
        f = fuentes.get(fuente)
        return m.faltante(etq, f"{nombre} (CSV mensual)", "—", defin,
                          f"Aún no se importa ningún archivo de {nombre}."
                          + (" La hoja aún no tiene la pestaña Investigacion."
                             if "Investigacion" in inv.faltan_tabs else ""), "fecha",
                          "/fuentes" if f else "")
    ts = datetime.combine(e.fecha, datetime.min.time(), m.TZ)
    nota = ORIGEN_FECHA.get(e.origen, "")
    if (now.astimezone(m.TZ).date() - e.fecha).days > EXPORT_MAX_DIAS:
        nota = f"tiene más de {EXPORT_MAX_DIAS} días: toca exportar de nuevo. " + nota
    return m.Dato(etq, ts.timestamp(), "real" if e.origen == "nombre-archivo" else "estimado",
                  e.texto, "—", defin + " " + ORIGEN_FECHA.get(e.origen, ""), e.importado,
                  "fecha", nota=nota)


def resumen(inv: Investigacion, fuentes: dict[str, m.EstadoFuente], now: datetime) -> list[m.Dato]:
    datos = [_export_dato(inv, "erank", fuentes, now), _export_dato(inv, "everbee", fuentes, now)]
    kex = [e for e in inv.exports.values() if e.tipo == "keyword"]
    pex = [e for e in inv.exports.values() if e.tipo == "producto"]
    txt = lambda es: " + ".join(e.texto for e in es)  # noqa: E731
    act = lambda es: max((e.importado for e in es if e.importado), default=None)  # noqa: E731
    if kex:
        datos.append(m.Dato("Keywords", len(inv.keywords), "real", txt(kex),
                            "último export de cada herramienta",
                            "Keywords en el export más reciente de keywords.", act(kex), "n"))
        meses = max((len(k.historial) for k in inv.keywords), default=0)
        if meses < MESES_SOSTENIDA:
            datos.append(m.faltante(
                "Suben 3 meses seguidos", txt(kex), f"{meses} mes(es) de exports",
                "Keywords cuyas búsquedas estimadas suben en 3 exports mensuales seguidos.",
                f"Hacen falta {MESES_SOSTENIDA} meses de exports; hay {meses}.", "n"))
        else:
            datos.append(m.Dato("Suben 3 meses seguidos", len(inv.sostenidas), "estimado",
                                txt(kex), f"últimos {MESES_SOSTENIDA} exports mensuales",
                                "Keywords cuyas búsquedas estimadas suben en 3 exports "
                                "mensuales seguidos.", act(kex), "n"))
        datos.append(m.Dato("Oportunidades", len(inv.oportunidades), "estimado", txt(kex),
                            "último export",
                            f"Keywords con {DEMANDA_MIN}+ búsquedas estimadas al mes, "
                            "ordenadas por búsquedas por cada listing que compite (máx. 10). "
                            "No garantiza ventas.", act(kex), "n"))
    else:
        for etq in ("Keywords", "Oportunidades"):
            datos.append(m.faltante(etq, "eRank / EverBee (CSV mensual)", "—",
                                    "Keywords del export más reciente.",
                                    "Aún no se importa ningún export de keywords.", "n"))
    datos.append(m.Dato("Productos de la competencia", len(inv.productos), "real", txt(pex),
                        "último export", "Productos en el export más reciente de productos.",
                        act(pex), "n") if pex else
                 m.faltante("Productos de la competencia", "EverBee (CSV mensual)", "—",
                            "Productos de la competencia en el último export.",
                            "Aún no se importa ningún export de productos.", "n"))
    return datos


def avisos(inv: Investigacion, now: datetime) -> list[tuple[str, str, str, datetime | None]]:
    """(nivel, título, detalle, actualizado) for the alerts view."""
    out = []
    for fuente in ("erank", "everbee"):
        e = inv.ultimo(fuente)
        if e and e.fecha and (now.astimezone(m.TZ).date() - e.fecha) > timedelta(
                days=EXPORT_MAX_DIAS):
            out.append(("atencion", f"Toca el export mensual de {FUENTE_NOMBRE[fuente]}",
                        f"El último es del {e.fecha.isoformat()} ({e.archivo}).", e.importado))
    sube = inv.sostenidas
    if sube:
        nombres = ", ".join(f"“{k.texto}”" for k in sube[:3]) + (
            f" y {len(sube) - 3} más" if len(sube) > 3 else "")
        out.append(("info", f"{len(sube)} keyword(s) suben {MESES_SOSTENIDA} meses seguidos",
                    f"{nombres}. {AVISO}", max(k.export.importado for k in sube
                                                if k.export.importado) if any(
                        k.export.importado for k in sube) else None))
    return out
