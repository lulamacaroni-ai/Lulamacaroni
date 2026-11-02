"""Resumen semanal: results, what the numbers suggest, tests and decisions, next priorities.

Requirements, section 1: "Entregar un resumen semanal con resultados, hipótesis, pruebas y
prioridades". Built from fixed rules over the connected data, like the daily summary; the
assistant will write it in prose later. Hypotheses only appear with enough orders behind
them (section 14: minimum volume, correlation is not cause).

    python -m lulamacaroni.app.semanal            # last full week (Monday to Sunday)
    python -m lulamacaroni.app.semanal --actual   # this week so far
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from html import escape

from . import metrics as m
from .alertas import ATENCION, URGENTE, resumen_dia
from .finanzas import US, depositos

MIN_PEDIDOS = 5   # below this, no hypothesis is drawn from the week


def periodo(clave: str, now: datetime) -> m.Periodo:
    """``pasada`` = last full Monday–Sunday week (CDMX); ``actual`` = this week so far."""
    local = now.astimezone(m.TZ)
    lunes = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0,
                                                              microsecond=0)
    semana = timedelta(days=7)
    if clave == "actual":
        return m.Periodo("actual", "Esta semana", lunes, local, lunes - semana,
                         local - semana, "mismos días de la semana anterior")
    return m.Periodo("pasada", "Semana pasada", lunes - semana, lunes, lunes - 2 * semana,
                     lunes - semana, "la semana anterior")


def texto_periodo(per: m.Periodo) -> str:
    return (f"{per.nombre}: lunes {m.dia(per.inicio)} a "
            f"{m.dia(per.fin - timedelta(seconds=1))}, hora de CDMX")


@dataclass
class Destacado:
    titulo: str
    detalle: str
    fuente: str


@dataclass
class Decision:
    fecha: datetime | None
    decision: str
    razon: str
    responsable: str
    resultado: str


@dataclass
class ResumenSemana:
    periodo: m.Periodo
    resultados: list[m.Dato]
    destacados: list[Destacado]
    hipotesis: list[str]
    decididas: list[Decision]
    abiertas: list[Decision]
    prioridades: list
    urgentes: int
    avisos: int
    sin_conectar: list[str] = field(default_factory=list)


def _contenido(contenido: list[dict], per: m.Periodo) -> m.Dato:
    rows = [c for c in contenido if c.get("estado") == "publicado"
            and per.contiene(m.parse_dt(c.get("programado_para")))]
    return m.Dato("Contenido publicado", len(rows), "real",
                  "Libro de datos (pestaña Contenido)", texto_periodo(per),
                  "Piezas marcadas como publicadas con fecha en la semana. Instagram y "
                  "Pinterest aún no están conectados: cuenta lo que se marcó en el libro.",
                  None, "n", len([c for c in contenido if c.get("estado") == "publicado"
                                  and per.contiene_previo(m.parse_dt(c.get("programado_para")))]),
                  enlace="/contenido")


def _destacados(us: list[dict], per: m.Periodo, act) -> list[Destacado]:
    vivos = [r for r in us if r.get("estado") in m.VIVOS and per.contiene(m.parse_dt(r.get("fecha")))]
    out = []
    ventas, margen, completo = defaultdict(float), defaultdict(float), defaultdict(lambda: True)
    for r in vivos:
        k = r.get("producto") or r.get("sku") or "sin nombre"
        ventas[k] += m.neto_linea(r)
        mg = m.num(r.get("margen_contribucion"))
        if r.get("calidad_dato") in ("real", "estimado") and mg is not None:
            margen[k] += mg
        else:
            completo[k] = False
    if ventas:
        k, v = max(ventas.items(), key=lambda kv: kv[1])
        if v > 0:
            from .views import usd
            out.append(Destacado("Lo más vendido", f"“{k}”: {usd(v)} netos",
                                 "Pedidos (Shopify)"))
    con_margen = {k: v for k, v in margen.items() if completo[k]}
    if con_margen:
        from .views import usd
        k, v = max(con_margen.items(), key=lambda kv: kv[1])
        out.append(Destacado("Lo que más margen dejó", f"“{k}”: {usd(v)} antes de anuncios",
                             "Pedidos + comisiones + cargos de Prodigi"))
    elif vivos:
        out.append(Destacado("Lo que más margen dejó", "— falta el dato: ningún producto de la "
                             "semana tiene todos sus costos.", "Pedidos + cargos de Prodigi"))
    return out


def _hipotesis(datos: dict[str, m.Dato], pedidos: int, origenes: list) -> list[str]:
    if pedidos < MIN_PEDIDOS:
        return [f"Con {pedidos} pedido(s) no hay volumen para sacar conclusiones (mínimo "
                f"{MIN_PEDIDOS} por semana). Se sigue midiendo."]
    out = []
    v = datos.get("Ventas netas")
    if v and v.cambio_pct is not None and abs(v.cambio_pct) >= 20:
        sentido = "subieron" if v.cambio_pct > 0 else "bajaron"
        out.append(f"Las ventas netas {sentido} {abs(v.cambio_pct):.0f}% contra la semana "
                   "anterior. Hipótesis por probar: revisa qué cambió (contenido, anuncios, "
                   "precios) antes de atribuirlo a algo.")
    total = sum(o.pedidos for o in origenes)
    conocidos = [o for o in origenes if o.clave != "sin-dato"]
    if total and conocidos:
        top = max(conocidos, key=lambda o: o.pedidos)
        from .publicidad import ORIGEN
        out.append(f"{ORIGEN[top.clave]} trajo {top.pedidos} de {total} pedidos según Shopify "
                   "(último clic). Es correlación, no prueba que ese canal causó la venta.")
    return out or ["Sin cambios grandes contra la semana anterior."]


def _decisiones(rows: list[dict], per: m.Periodo) -> tuple[list[Decision], list[Decision]]:
    todas = [Decision(m.parse_dt(r.get("fecha")), r.get("decision", ""), r.get("razon", ""),
                      r.get("responsable", ""), r.get("resultado", "")) for r in rows
             if r.get("decision")]
    decididas = [x for x in todas if per.contiene(x.fecha)]
    abiertas = [x for x in todas if not x.resultado and x.fecha and x.fecha < per.fin
                and x not in decididas]
    return decididas, abiertas


def calcular(d, clave: str = "pasada") -> ResumenSemana:
    from .publicidad import atribucion

    per = periodo(clave, d.now)
    us = [r for r in d.pedidos_rows if (r.get("linea") or US) == US]
    res = m.resumen(us, d.campanas, d.fuentes, per, d.pagos)
    resultados = []
    for x in res.datos:
        x.periodo = texto_periodo(per) if x.periodo == per.texto else x.periodo
        resultados.append(x)
    dep = depositos(d.pagos, d.fuentes, per)[0]
    dep.periodo = texto_periodo(per)
    resultados.append(dep)
    resultados.append(_contenido(getattr(d, "contenido", []), per))
    by = {x.etiqueta: x for x in resultados}
    rd = resumen_dia(d)
    origenes = atribucion(us, per) if d.fuentes["shopify"].conectada else []
    decididas, abiertas = _decisiones(getattr(d, "decisiones", []), per)
    return ResumenSemana(
        per, resultados, _destacados(us, per, d.fuentes["shopify"].actualizado),
        _hipotesis(by, res.pedidos_periodo, origenes), decididas, abiertas, rd.acciones,
        rd.cuenta(URGENTE), rd.cuenta(ATENCION),
        [f.info.nombre for f in d.fuentes.values() if f.estado == "sin-conectar"])


# --- output -------------------------------------------------------------------------------

def _decision_html(x: Decision, fecha) -> str:
    extra = " · ".join(t for t in (f"por {x.responsable}" if x.responsable else "",
                                   f"resultado: {x.resultado}" if x.resultado else
                                   "sin resultado aún") if t)
    return (f'<div class="card"><div class="t">{escape(x.decision)}</div>'
            f'<div class="m">{escape(x.razon)}</div>'
            f'<div class="m">{escape(fecha(x.fecha, hora=False))} · {escape(extra)}</div></div>')


def render(r: ResumenSemana, now: datetime, banner: str = "") -> str:
    from . import views as v

    per = r.periodo
    chips = "".join(
        f'<a class="chip{" on" if k == per.clave else ""}" href="/semana?s={k}">{t}</a>'
        for k, t in (("pasada", "Semana pasada"), ("actual", "Esta semana")))
    body = [
        f'<p class="sub">Resumen semanal · {escape(texto_periodo(per))}</p><h1>Tu semana</h1>',
        f'<div class="chips">{chips}<span class="vs">vs {escape(per.comparacion)}</span></div>',
        "<h2>Resultados</h2>",
        f'<div class="grid">{"".join(v._kpi(x, now) for x in r.resultados)}</div>',
    ]
    if r.destacados:
        body.append("<h2>Destacados</h2>")
        body += [f'<div class="card"><div class="t">{escape(x.titulo)}</div>'
                 f'<div class="m">{escape(x.detalle)}</div>'
                 f'<div class="m">Fuente: {escape(x.fuente)}</div></div>' for x in r.destacados]
    body.append("<h2>Lo que sugieren los datos (hipótesis)</h2><div class='card summary'>"
                + "".join(f"<p>{escape(h)}</p>" for h in r.hipotesis) + "</div>")
    body.append("<h2>Pruebas y decisiones</h2>")
    if not r.decididas and not r.abiertas:
        body.append('<div class="card info"><div class="m">No hay decisiones ni pruebas '
                    "registradas en la pestaña Decisiones. Cada prueba (por ejemplo, un precio "
                    "nuevo o un anuncio) se anota ahí con su razón y, al terminar, su resultado."
                    "</div></div>")
    if r.decididas:
        body.append(f"<p class='meta'>Decididas esta semana ({len(r.decididas)})</p>")
        body += [_decision_html(x, v.fecha) for x in r.decididas]
    if r.abiertas:
        body.append(f"<p class='meta'>Pruebas abiertas, sin resultado ({len(r.abiertas)})</p>")
        body += [_decision_html(x, v.fecha) for x in r.abiertas]
    acc = "".join(f'<li><a href="{escape(a.enlace)}">{escape(a.accion)}</a></li>'
                  for a in r.prioridades)
    body.append("<h2>Prioridades para la semana</h2><div class='card summary'>"
                + (f"<ol>{acc}</ol>" if acc else "<p>Nada urgente. 🎨</p>")
                + f'<p class="meta">{r.urgentes} urgente(s) y {r.avisos} aviso(s) abiertos. '
                '<a href="/alertas">Ver alertas</a></p></div>')
    if r.sin_conectar:
        body.append(f'<p class="legend">Fuentes aún no conectadas: '
                    f'{escape(", ".join(r.sin_conectar))}. Sus números salen “—”, nunca cero.</p>')
    body.append('<p class="legend">Sale de reglas fijas sobre los datos conectados; Claude lo '
                'redactará cuando el Asistente esté listo. <a href="/finanzas">Ver finanzas</a>.'
                "</p>")
    return v.page("Resumen semanal", "/semana", "".join(body), banner)


def texto(r: ResumenSemana) -> str:
    """Plain text (terminal now; email or WhatsApp later, after approval)."""
    from .views import valor

    lines = [f"Resumen semanal · {texto_periodo(r.periodo)}", "", "Resultados:"]
    for x in r.resultados:
        extra = f" · {x.nota}" if x.nota else ""
        lines.append(f"  {x.etiqueta}: {valor(x)} ({x.calidad}; fuente: {x.fuente}){extra}")
    if r.destacados:
        lines += ["", "Destacados:"] + [f"  {x.titulo}: {x.detalle}" for x in r.destacados]
    lines += ["", "Lo que sugieren los datos:"] + [f"  - {h}" for h in r.hipotesis]
    lines += ["", "Pruebas y decisiones:"]
    if not r.decididas and not r.abiertas:
        lines.append("  Ninguna registrada en la pestaña Decisiones.")
    lines += [f"  [decidida] {x.decision} ({x.resultado or 'sin resultado aún'})"
              for x in r.decididas]
    lines += [f"  [abierta] {x.decision}" for x in r.abiertas]
    lines += ["", f"Prioridades ({r.urgentes} urgente(s), {r.avisos} aviso(s)):"]
    lines += [f"  {i}. {a.accion}" for i, a in enumerate(r.prioridades, 1)] or ["  Nada urgente."]
    if r.sin_conectar:
        lines += ["", f"Sin conectar (se muestran como —): {', '.join(r.sin_conectar)}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    from ..approval.store import SheetsStore, open_store
    from ..localbook import open_workbook
    from ..workbook import Workbook
    from .screens import Datos

    parser = argparse.ArgumentParser(description="Resumen semanal (solo lectura)")
    parser.add_argument("--actual", action="store_true", help="esta semana en lugar de la pasada")
    args = parser.parse_args(argv)
    book = open_workbook()
    store = SheetsStore(book) if isinstance(book, Workbook) else open_store()
    d = Datos(book, store)
    print(texto(calcular(d, "actual" if args.actual else "pasada")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
