"""HTML for the Investigación screen (kept apart from views.py; same helpers and style)."""

from __future__ import annotations

from datetime import datetime
from html import escape

from .metrics import MESES, Dato, EstadoFuente, parse_dt
from .views import _celda, _kpi, fecha, page


ESTADO_KEYWORD = {"a-probar": ("a probar", "amber"), "probando": ("probando", "amber"),
                  "en-uso": ("en uso", "ok"), "descartada": ("descartada", "gray")}
TENDENCIA = {"sube": "ok", "baja": "warn", "pico": "amber", "estable": "gray",
             "sin-historial": "gray"}


def _exp(e) -> str:
    d = e.fecha
    cuando = f"{d.day} {MESES[d.month - 1]} {d.year}" if d else "fecha —"
    return f"{e.archivo} · export {cuando}"


def _kw_fila(k) -> str:
    comp = (f'{escape(k.competencia_texto)} <span class="q estimado">estimado</span>'
            if k.competencia_texto else _celda(k.competencia))
    archivo = f" · el archivo dice: {escape(k.tendencia_archivo)}" if k.tendencia_archivo else ""
    hist = " → ".join(f"{v:,.0f}" for _, v in k.historial[-4:])
    mercado = f'<span class="tag">{escape(k.mercado)}</span>' if k.mercado else ""
    return (f"<tr><td><strong>{escape(k.texto)}</strong><br>"
            f'<span class="tag">{escape(_cat(k.categoria))}</span>{mercado}</td>'
            f"<td>{_celda(k.busquedas)}</td><td>{comp}</td>"
            f'<td><span class="badge {TENDENCIA[k.tendencia]}">{escape(k.tendencia_texto)}'
            f'</span><br><span class="meta">{escape(hist)}{archivo}</span></td>'
            f'<td class="meta">{escape(_exp(k.export))}</td></tr>')


def _cat(c: str) -> str:
    from .investigacion import CATEGORIA
    return CATEGORIA.get(c, c or "—")


def _sugerencia(s, now: datetime) -> str:
    lista = "".join(
        f'<div class="m">{escape(str(r.get("keyword") or ""))} '
        f'<span class="badge {ESTADO_KEYWORD.get(r.get("estado"), ("", "gray"))[1]}">'
        f'{escape(ESTADO_KEYWORD.get(r.get("estado"), (r.get("estado") or "sin estado",))[0])}'
        "</span>"
        + (f' · desde {escape(str(r.get("desde"))[:10])}' if r.get("desde") else "")
        + (f' · hasta {escape(str(r.get("hasta"))[:10])}' if r.get("hasta") else "")
        + (f' · resultado: {escape(str(r.get("resultado")))}' if r.get("resultado") else "")
        + "</div>" for r in s.lista)
    ideas = "".join(
        f'<div class="m">💡 {escape(k.texto)} · búsquedas {_celda(k.busquedas)} · '
        f'<span class="meta">{escape(why)} · {escape(k.export.texto)}</span></div>'
        for k, why in s.ideas)
    if not lista and not ideas:
        ideas = ('<div class="m meta">— Ninguna keyword importada coincide con el título, '
                 "tema, colores o colección de esta obra.</div>")
    return (f'<div class="card"><div class="t">{escape(s.titulo)}</div>'
            + (f'<div class="m"><strong>Tu lista (pestaña Keywords)</strong></div>{lista}'
               if lista else "")
            + (f'<div class="m"><strong>Sugeridas</strong></div>{ideas}' if s.ideas else ideas)
            + "</div>")


def investigacion_view(inv, datos: list[Dato], categoria: str, fuentes: dict[str, EstadoFuente],
                       now: datetime, banner: str = "") -> str:
    from .investigacion import AVISO, CATEGORIA, DEMANDA_MIN, ORIGEN_FECHA, filtrar

    chips = (f'<a class="chip{" on" if not categoria else ""}" href="/investigacion">Todo</a>'
             + "".join(f'<a class="chip{" on" if k == categoria else ""}" '
                       f'href="/investigacion?c={k}">{escape(t)}</a>'
                       for k, t in CATEGORIA.items()))
    body = ['<h1>Investigación</h1><p class="sub">Keywords, tendencias y precios de la '
            "competencia a partir de los exports mensuales de eRank y EverBee. Solo lectura: "
            "nada se publica ni cambia desde aquí.</p>",
            f'<div class="grid">{"".join(_kpi(d, now) for d in datos)}</div>']
    if inv.faltan_tabs:
        body.append('<div class="card aviso"><div class="t">Faltan pestañas en la hoja</div>'
                    f'<div class="m">{escape(", ".join(inv.faltan_tabs))}. Se crean con '
                    "python -m lulamacaroni.setup_workbook; hasta entonces aquí todo sale "
                    "como “—”.</div></div>")
    if not inv.exports:
        body.append(
            '<div class="card info"><div class="t">Aún no hay exports importados</div>'
            '<div class="m">Cada mes: exporta el CSV en eRank o EverBee, déjalo en la carpeta '
            "de Drive “LulaMacaroni Investigación” y corre la importación. Los pasos están en "
            "docs/setup/investigacion-es.md. Mientras tanto todo sale como “—”: no hay datos "
            "de ejemplo.</div></div>")

    ks = filtrar(inv.keywords, categoria)
    body.append(f"<h2>Keywords y tendencias</h2><div class='chips'>{chips}</div>")
    if ks:
        body.append("<div class='tablebox'><table><thead><tr><th>Keyword</th><th>Búsquedas/mes"
                    "</th><th>Competencia</th><th>Tendencia</th><th>Archivo</th></tr></thead>"
                    f"<tbody>{''.join(_kw_fila(k) for k in ks[:50])}</tbody></table></div>")
        if len(ks) > 50:
            body.append(f'<p class="legend">Se muestran 50 de {len(ks)}; todas están en la '
                        "pestaña Investigacion.</p>")
    else:
        body.append('<p class="empty">— Sin keywords importadas'
                    + (" en esta categoría" if categoria and inv.keywords else "") + ".</p>")

    ops = [k for k in inv.oportunidades if not categoria or k.categoria == categoria]
    body.append("<h2>Oportunidades para revisar</h2>")
    if ops:
        body.append("".join(
            f'<div class="card"><div class="row"><div><div class="t">{escape(k.texto)}</div>'
            f'<div class="m">{escape(_cat(k.categoria))} · búsquedas {_celda(k.busquedas)} · '
            f"competencia {_celda(k.competencia)} · {escape(k.tendencia_texto)}</div>"
            f'<div class="m meta">{escape(_exp(k.export))}</div></div>'
            f'<div class="r">{k.puntaje * 100:,.1f}<br><span class="meta">búsquedas por<br>'
            "100 listings</span></div>"
            "</div></div>" for k in ops))
    else:
        body.append(f'<p class="empty">— Ninguna keyword con {DEMANDA_MIN}+ búsquedas y '
                    "competencia numérica en el último export.</p>")
    body.append(f'<p class="legend">{escape(AVISO)}</p>')

    pr = [p for p in inv.precios if not categoria or p.categoria == categoria]
    body.append("<h2>Precios de la competencia (USD)</h2>")
    if pr:
        rows = "".join(
            f"<tr><td><strong>{escape(_cat(p.categoria))}</strong><br>"
            f'<span class="meta">{p.n} producto(s)</span></td><td>{_celda(p.minimo)}</td>'
            f"<td>{_celda(p.mediana)}</td><td>{_celda(p.maximo)}</td><td>{_celda(p.ventas)}</td>"
            f'<td class="meta">{escape(p.fuentes)}</td></tr>' for p in pr)
        body.append("<div class='tablebox'><table><thead><tr><th>Tipo</th><th>Mínimo</th>"
                    "<th>Mediana</th><th>Máximo</th><th>Ventas/mes (mediana)</th><th>Archivo"
                    f"</th></tr></thead><tbody>{rows}</tbody></table></div>")
        body.append('<p class="legend">Precio: lo que la herramienta vio publicado el día del '
                    "export. Ventas: estimación de la herramienta, no de las tiendas. Lo que "
                    "observamos no dice cuánto ganan ni cuánto invierten.</p>")
    else:
        body.append('<p class="empty">— Sin export de productos de la competencia'
                    + (" en esta categoría" if categoria and inv.precios else "") + ".</p>")

    body.append("<h2>Keywords sugeridas por obra</h2>")
    if inv.sugerencias:
        body.append("".join(_sugerencia(s, now) for s in inv.sugerencias[:30]))
        body.append('<p class="legend">Sugeridas: keywords importadas que comparten palabras '
                    "con el título, tema, colores o colección de la obra (pestaña Obras), de "
                    "más a menos búsquedas por listing. Para probar una, anótala en la pestaña "
                    "Keywords con la obra y el estado; ahí queda su historial.</p>")
    else:
        body.append('<p class="empty">— Aún no hay obras en la pestaña Obras.</p>')

    body.append("<h2>Archivos importados</h2>")
    if inv.importaciones:
        color = {"ok": "ok", "parcial": "amber", "error": "warn"}
        rows = "".join(
            f"<tr><td><strong>{escape(str(r.get('archivo') or ''))}</strong><br>"
            f"<span class='meta'>{escape(str(r.get('fuente') or '?'))} · "
            f"{escape(str(r.get('tipo') or ''))}</span></td>"
            f"<td>{escape(str(r.get('fecha_export') or '—'))}<br><span class='meta'>"
            f"{escape(ORIGEN_FECHA.get(r.get('fecha_export_origen'), ''))}</span></td>"
            f"<td>{escape(fecha(parse_dt(r.get('importado_en'))))}</td>"
            f"<td>{escape(str(r.get('filas', '')))}</td>"
            f"<td><span class='badge {color.get(r.get('estado'), 'gray')}'>"
            f"{escape(str(r.get('estado') or ''))}</span>"
            + (f"<br><span class='meta'>{escape(str(r.get('nota')))}</span>"
               if r.get("nota") else "")
            + (f"<br><span class='meta'>ignoradas: {escape(str(r.get('columnas_ignoradas')))}"
               "</span>" if r.get("columnas_ignoradas") else "")
            + "</td></tr>" for r in inv.importaciones[:24])
        body.append("<div class='tablebox'><table><thead><tr><th>Archivo</th><th>Export</th>"
                    "<th>Importado</th><th>Filas</th><th>Estado</th></tr></thead>"
                    f"<tbody>{rows}</tbody></table></div>")
    else:
        body.append('<p class="empty">— Ningún archivo importado todavía.</p>')
    body.append('<p class="legend">Cada número dice de qué archivo sale y la fecha del export '
                "(toca “¿De dónde sale?” o pasa el dedo sobre la cifra). ~ = estimado por la "
                "herramienta. — = falta el dato.</p>")
    return page("Investigación", "/investigacion", "".join(body), banner)
