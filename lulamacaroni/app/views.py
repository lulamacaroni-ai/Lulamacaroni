"""HTML for the back office screens (Mexican Spanish, phone first, works on desktop).

Pure functions: data in, one HTML string out. Everything shown is escaped. Layout and
colors follow the UX map (cream ground, ink text, amber accent, Space Grotesk titles).
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from ..approval.page import render_cards
from .metrics import MESES, TZ, Dato, EstadoFuente, Pedido, Producto, Resumen

CANAL = {"shopify": "Shopify", "etsy": "Etsy", "sitio-mx": "Sitio MX", "whatsapp": "WhatsApp",
         "instagram": "Instagram", "pinterest": "Pinterest", "otro": "Otro"}
LINEA = {"US-POD": "Prints EUA", "MX-original": "Original MX"}
ESTADO_PEDIDO = {
    "recibido": "Recibido", "enviado-a-pod": "Enviado a imprenta", "en-produccion": "En producción",
    "enviado": "Enviado", "entregado": "Entregado", "cancelado": "Cancelado",
    "reembolsado": "Reembolsado", "excepcion": "Excepción",
}
RUTA = {"prodigi-app": "app de Prodigi", "frame-it-easy-app": "app de Frame It Easy",
        "prodigi-api": "Prodigi (API)", "manual": "manual (ninguna imprenta)",
        "desconocida": "desconocida"}
ESTADO_LISTADO = {"publicado": "En venta", "pausado": "Oculto", "borrador": "Borrador",
                  "en-aprobacion": "Por aprobar", "retirado": "Retirado"}
ESTADO_FUENTE = {"ok": "al día", "atrasada": "atrasada", "error": "con error",
                 "sin-conectar": "sin conectar"}

NAV = (("/", "Inicio"), ("/aprobar", "Aprobar"), ("/catalogo", "Catálogo"),
       ("/pedidos", "Pedidos"), ("/fuentes", "Fuentes"))

CSS = """
:root{--bg:#FBF8F3;--card:#FFFFFF;--ink:#1C1C1E;--muted:#4A4A50;--line:#E0D6C8;
--accent:#8A4B00;--accent-ink:#FFFFFF;--warn:#8A1C0C;--warn-bg:#FBEAE6;--ok:#1E6A3E;
--ok-bg:#EAF5EE;--amber-bg:#FCE8B2;--amber:#5C4000;--chip:#F2F2F4;--no:#9b2c2c}
@media (prefers-color-scheme:dark){:root{--bg:#171513;--card:#211E1B;--ink:#F1ECE6;
--muted:#B5ACA2;--line:#3A332C;--accent:#E7A35A;--accent-ink:#1C1C1E;--warn:#F0A090;
--warn-bg:#3A201B;--ok:#86C99A;--ok-bg:#1D3326;--amber-bg:#3D3115;--amber:#F2D58A;
--chip:#2C2824;--no:#e58b8b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.45 Inter,system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
main{max-width:980px;margin:0 auto;padding:16px 16px 96px}
h1{font-family:"Space Grotesk",system-ui,sans-serif;font-size:1.6rem;margin:4px 0}
h2{font-size:.78rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:22px 0 8px}
h2.warn{color:var(--warn)}
.sub{color:var(--muted);font-size:.85rem;margin:0}
.banner{background:var(--amber-bg);color:var(--amber);border-radius:10px;padding:8px 12px;
font-size:.85rem;margin-bottom:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:8px 0}
.summary p{margin:4px 0}.summary ol{margin:6px 0 0;padding-left:20px}.summary li{margin:4px 0}
.chips{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:12px 0 4px}
.chip{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;
padding:8px 14px;font-size:.85rem;min-height:40px;display:inline-flex;align-items:center}
.chip.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.chips .vs{margin-left:auto;color:var(--muted);font-size:.78rem}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
@media (min-width:720px){.grid{grid-template-columns:repeat(3,1fr)}}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;
display:flex;flex-direction:column;gap:2px;min-width:0}
.kpi .lbl{font-size:.75rem;color:var(--muted)}
.kpi .val{font-size:1.3rem;font-weight:600;font-variant-numeric:tabular-nums}
.kpi .val.missing{color:var(--muted)}
.kpi .foot{font-size:.75rem;color:var(--muted)}
.kpi details{font-size:.75rem;color:var(--muted);margin-top:4px}
.kpi details summary{cursor:pointer;color:var(--accent);min-height:24px}
.kpi dl{margin:6px 0 0}
.kpi dt{font-weight:600;margin-top:4px}.kpi dd{margin:0}
.q{display:inline-block;font-size:.7rem;font-weight:600;border-radius:999px;padding:1px 7px}
.q.real{background:var(--ok-bg);color:var(--ok)}.q.cero{background:var(--chip);color:var(--muted)}
.q.faltante{background:var(--warn-bg);color:var(--warn)}.q.estimado{background:var(--amber-bg);color:var(--amber)}
.legend{font-size:.78rem;color:var(--muted);margin:10px 0 0}
.row{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.row .t{font-weight:600}.row .m{font-size:.85rem;color:var(--muted)}
.row .r{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.card.alert{border-color:var(--warn);background:var(--warn-bg)}
.card.alert .m.w{color:var(--warn)}
.badge{font-size:.72rem;font-weight:600;border-radius:999px;padding:3px 8px;white-space:nowrap}
.badge.ok{background:var(--ok-bg);color:var(--ok)}.badge.amber{background:var(--amber-bg);color:var(--amber)}
.badge.gray{background:var(--chip);color:var(--muted)}.badge.warn{background:var(--warn-bg);color:var(--warn)}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th{text-align:left;font-size:.72rem;color:var(--muted);font-weight:600;padding:6px 8px}
td{padding:9px 8px;border-top:1px solid var(--line);vertical-align:top}
.tablebox{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow-x:auto}
.empty{color:var(--muted);text-align:center;padding:20px}
nav.bottom{position:fixed;left:0;right:0;bottom:0;background:var(--card);border-top:1px solid var(--line);
display:grid;grid-template-columns:repeat(5,1fr);text-align:center;font-size:.78rem;z-index:5}
nav.bottom a{padding:14px 2px;color:var(--muted);min-height:48px}
nav.bottom a.on{color:var(--ink);font-weight:700}
.tag{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:1px 8px;margin-right:6px;font-size:.8rem}
.meta{color:var(--muted);font-size:.85rem}
details pre{white-space:pre-wrap;word-break:break-word;font-size:.8rem;background:var(--bg);padding:8px;border-radius:8px}
form{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
input[type=text]{flex:1 1 100%;padding:10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink)}
button{flex:1;padding:12px;border:0;border-radius:8px;font-weight:600;color:#fff;cursor:pointer;font:inherit;font-weight:600}
button.ok{background:#2f6b3a}button.no{background:#9b2c2c}
"""


# --- formatting ---------------------------------------------------------------------------

def fecha(dt: datetime | None, hora: bool = True) -> str:
    if dt is None:
        return "—"
    d = dt.astimezone(TZ)
    base = f"{d.day} {MESES[d.month - 1]}"
    return f"{base} {d:%H:%M}" if hora else base


def hace(dt: datetime | None, now: datetime) -> str:
    if dt is None:
        return "nunca"
    s = (now - dt).total_seconds()
    if s < 90:
        return "hace un momento"
    if s < 3600:
        return f"hace {int(s // 60)} min"
    if s < 86400 * 2:
        return f"hace {int(s // 3600)} h"
    return f"hace {int(s // 86400)} días"


def usd(v: float) -> str:
    sign = "−" if v < 0 else ""
    return f"{sign}US${abs(v):,.2f}"


def valor(d: Dato) -> str:
    if d.calidad == "faltante" or d.valor is None:
        return "—"
    text = usd(d.valor) if d.formato == "usd" else f"{d.valor:,.0f}"
    return ("~" + text) if d.calidad == "estimado" else text


def calidad(d: Dato) -> str:
    if d.es_cero:
        return '<span class="q cero">cero real</span>'
    label = {"real": "real", "faltante": "falta el dato", "estimado": "estimado"}[d.calidad]
    return f'<span class="q {d.calidad}">{label}</span>'


def page(titulo: str, activo: str, body: str, banner: str = "") -> str:
    nav = "".join(f'<a href="{h}" class="{"on" if h == activo else ""}">{escape(t)}</a>'
                  for h, t in NAV)
    ban = f'<div class="banner">{escape(banner)}</div>' if banner else ""
    return (
        "<!doctype html><html lang='es-MX'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex'>"
        f"<title>{escape(titulo)} · Lula Macaroni</title><style>{CSS}</style></head>"
        f"<body><main>{ban}{body}</main><nav class='bottom'>{nav}</nav></body></html>"
    )


# --- Inicio -----------------------------------------------------------------------------------

def _kpi(d: Dato, now: datetime) -> str:
    if d.cambio_pct is not None:
        foot = f"{d.cambio_pct:+.0f}% vs periodo anterior"
    elif d.calidad == "real" and d.previo is not None:
        prev = usd(d.previo) if d.formato == "usd" else f"{d.previo:,.0f}"
        foot = f"antes: {prev}"
    else:
        foot = d.nota or ""
    lbl = escape(d.etiqueta)
    head = f'<a href="{escape(d.enlace)}" class="lbl">{lbl}</a>' if d.enlace else f'<span class="lbl">{lbl}</span>'
    rows = [("Fuente", d.fuente), ("Periodo", d.periodo), ("Qué mide", d.definicion),
            ("Actualizado", f"{fecha(d.actualizado)} ({hace(d.actualizado, now)})"
             if d.actualizado else "—")]
    if d.nota and foot != d.nota:
        rows.append(("Nota", d.nota))
    dl = "".join(f"<dt>{escape(k)}</dt><dd>{escape(v)}</dd>" for k, v in rows)
    missing = " missing" if d.calidad == "faltante" else ""
    return (f'<div class="kpi">{head}<span class="val{missing}">{escape(valor(d))}</span>'
            f'<span class="foot">{calidad(d)} {escape(foot)}</span>'
            f"<details><summary>¿De dónde sale?</summary><dl>{dl}</dl></details></div>")


def inicio(res: Resumen, acciones, fuentes: dict[str, EstadoFuente], now: datetime,
           nombre: str = "Lore", banner: str = "") -> str:
    per = res.periodo
    chips = "".join(
        f'<a class="chip{" on" if k == per.clave else ""}" href="/?p={k}">{t}</a>'
        for k, t in (("hoy", "Hoy"), ("7", "7 días"), ("30", "30 días")))
    ventas = res.datos[0]
    if ventas.calidad == "faltante":
        que_paso = "Aún no hay canales de venta conectados."
    else:
        que_paso = (f"{res.pedidos_periodo} pedido(s), {usd(ventas.valor)} netos "
                    f"({per.nombre.lower()}, {escape(ventas.fuente)}).")
        if res.mas_vendido:
            que_paso += f" Lo más vendido: “{escape(res.mas_vendido)}”."
        if ventas.nota:
            que_paso += f" {escape(ventas.nota)}"
    acc = "".join(f'<li><a href="{escape(a.enlace)}">{escape(a.texto)}</a></li>' for a in acciones)
    acc = f"<ol>{acc}</ol>" if acc else "<p>Nada urgente. 🎨</p>"
    alertas = sum(1 for f in fuentes.values() if f.estado in ("error", "atrasada"))
    body = (
        f'<div class="row"><div><p class="sub">Resumen del día · {fecha(now, hora=False)}</p>'
        f"<h1>Hola, {escape(nombre)}</h1></div>"
        + (f'<a href="/fuentes" class="badge warn">{alertas} fuente(s) con aviso</a>' if alertas else "")
        + "</div>"
        f'<div class="card summary"><p><strong>Qué pasó:</strong> {que_paso}</p>'
        f"<p><strong>Tus 3 acciones de hoy</strong></p>{acc}"
        '<p class="meta">Por ahora este resumen sale de reglas fijas; Claude lo redactará cuando '
        "el Asistente esté listo.</p></div>"
        f'<div class="chips">{chips}<span class="vs">vs {escape(per.comparacion)}</span></div>'
        f'<div class="grid">{"".join(_kpi(d, now) for d in res.datos)}</div>'
        '<p class="legend"><a href="/fuentes">Fuentes</a>: 0 = cero real · — = falta el dato · '
        "~ = estimado. Toca “¿De dónde sale?” en cualquier número.</p>"
    )
    return page("Inicio", "/", body, banner)


# --- Pedidos ----------------------------------------------------------------------------------

def _pedido(p: Pedido) -> str:
    rutas = ", ".join(RUTA.get(r, r) for r in sorted(p.rutas))
    prods = "; ".join(dict.fromkeys(r.get("producto") or r.get("sku") or "sin nombre"
                                    for r in p.lineas))
    alert = " alert" if p.atencion else ""
    extra = f'<div class="m w">{escape(p.atencion)}</div>' if p.atencion else ""
    track = f" · tracking {escape(p.tracking)}" if p.tracking else ""
    return (
        f'<div class="card{alert}"><div class="row"><div><div class="t">#{escape(p.numero)} · '
        f"{escape(CANAL.get(p.canal, p.canal))}</div>"
        f'<div class="m">{escape(prods)}</div>'
        f'<div class="m">{fecha(p.fecha)} · {escape(ESTADO_PEDIDO.get(p.estado, p.estado))} · '
        f"imprime: {escape(rutas)}{track}</div>{extra}</div>"
        f'<div class="r">{usd(p.neto)}<div class="m">neto</div></div></div></div>'
    )


def pedidos(lista: list[Pedido], fuentes: dict[str, EstadoFuente], now: datetime,
            banner: str = "") -> str:
    secciones = (("atencion", "Necesitan atención", "warn"), ("camino", "En curso", ""),
                 ("cerrado", "Cerrados, cancelados o reembolsados", ""))
    shop = fuentes["shopify"]
    body = ['<h1>Pedidos</h1><p class="sub">Shopify (y Etsy cuando se conecte), un pedido por '
            f"tarjeta. Shopify actualizado {hace(shop.actualizado, now)}. Sin datos de compradores "
            "en esta vista.</p>"]
    if not shop.conectada:
        body.append('<p class="empty">Shopify no está conectado todavía.</p>')
    for key, title, cls in secciones:
        items = [p for p in lista if p.grupo == key]
        if key == "cerrado":
            items = items[:20]
        body.append(f'<h2 class="{cls}">{escape(title)} ({len(items)})</h2>')
        body.append("".join(_pedido(p) for p in items) or '<p class="empty">Ninguno.</p>')
    body.append('<p class="legend">Shopify solo comparte los últimos 60 días de pedidos con esta '
                "app. Los pedidos de prueba no se cuentan. Coste de Prodigi y comisiones aparecen "
                "cuando se conecten Prodigi y los pagos.</p>")
    return page("Pedidos", "/pedidos", "".join(body), banner)


# --- Catálogo ---------------------------------------------------------------------------------

def _precio(p: Producto) -> str:
    if p.precio_min is None:
        return "—"
    if p.precio_min == p.precio_max:
        return usd(p.precio_min)
    return f"{usd(p.precio_min)}–{usd(p.precio_max)}"


def catalogo(productos: list[Producto], obras: int, filtro: str, fuentes, now: datetime,
             banner: str = "") -> str:
    filtros = (("todo", "Todo"), ("venta", "En venta"), ("avisos", "Con avisos"),
               ("ocultos", "Ocultos o borrador"))
    tabs = "".join(f'<a class="chip{" on" if k == filtro else ""}" href="/catalogo?f={k}">{t}</a>'
                   for k, t in filtros)
    sel = {
        "todo": productos,
        "venta": [p for p in productos if p.estado == "publicado"],
        "avisos": [p for p in productos if p.avisos],
        "ocultos": [p for p in productos if p.estado in ("pausado", "borrador")],
    }.get(filtro, productos)
    badge = {"publicado": "ok", "en-aprobacion": "amber", "borrador": "gray", "pausado": "gray",
             "retirado": "gray"}
    rows = []
    for p in sel:
        avisos = "".join(f'<div class="m w">{escape(a)}</div>' for a in p.avisos)
        title = (f'<a href="{escape(p.url)}" rel="noopener">{escape(p.titulo)}</a>' if p.url
                 else escape(p.titulo))
        rows.append(
            f'<div class="card{" alert" if p.avisos else ""}"><div class="row"><div>'
            f'<div class="t">{title}</div>'
            f'<div class="m">{escape(LINEA.get(p.linea, p.linea))} · {escape(CANAL.get(p.canal, p.canal))}'
            f" · {p.variantes} variante(s) · {_precio(p)}</div>{avisos}</div>"
            f'<span class="badge {badge.get(p.estado, "gray")}">'
            f"{escape(ESTADO_LISTADO.get(p.estado, p.estado))}</span></div></div>")
    en_venta = sum(1 for p in productos if p.estado == "publicado")
    body = (
        f'<h1>Catálogo</h1><p class="sub">{len(productos)} producto(s) en canales, {en_venta} en '
        f"venta. Obras en el catálogo maestro: {obras}"
        + (" (se cargan en el paso de catálogo)" if not obras else "") + ". "
        f"Shopify actualizado {hace(fuentes['shopify'].actualizado, now)}.</p>"
        f'<div class="tabs">{tabs}</div>'
        + ("".join(rows) or '<p class="empty">Nada en este filtro.</p>')
        + '<p class="legend">Solo lectura. Cambios de precio y publicaciones pasan por Aprobar. '
        "Nunca se recorta, estira ni regenera una obra.</p>"
    )
    return page("Catálogo", "/catalogo", body, banner)


# --- Fuentes ----------------------------------------------------------------------------------

def fuentes_view(fuentes: dict[str, EstadoFuente], now: datetime, banner: str = "") -> str:
    color = {"ok": "ok", "atrasada": "warn", "error": "warn", "sin-conectar": "gray"}
    rows = []
    for f in fuentes.values():
        cuando = f"{fecha(f.actualizado)}<br><span class='meta'>{hace(f.actualizado, now)}</span>" \
            if f.actualizado else "—"
        rows.append(
            f"<tr><td><strong>{escape(f.info.nombre)}</strong>"
            + (f"<br><span class='meta'>{escape(f.nota)}</span>" if f.nota else "")
            + f"</td><td>{escape(f.info.como)}</td><td>{cuando}</td>"
            f"<td><span class='badge {color[f.estado]}'>{ESTADO_FUENTE[f.estado]}</span></td></tr>")
    body = (
        '<h1>Fuentes de datos</h1><p class="sub">De dónde sale cada número y cuándo se actualizó.</p>'
        '<div class="card"><span class="q real">real</span> dato de la fuente · '
        '<span class="q cero">cero real</span> la fuente dice 0 · '
        '<span class="q faltante">falta el dato</span> la fuente no está conectada o no lo da · '
        '<span class="q estimado">estimado</span> cálculo nuestro</div>'
        "<div class='tablebox'><table><thead><tr><th>Fuente</th><th>Cómo</th><th>Actualizado</th>"
        f"<th>Estado</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        '<p class="legend">Lo que una API no permita queda como tarea manual o importación, '
        "nunca como sincronización falsa.</p>"
    )
    return page("Fuentes", "/fuentes", body, banner)


# --- Aprobar ----------------------------------------------------------------------------------

def aprobar(approvals, banner: str = "") -> str:
    return page("Aprobar", "/aprobar", render_cards(approvals), banner)
