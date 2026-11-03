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

NAV = (("/", "Inicio"), ("/alertas", "Alertas"), ("/aprobar", "Aprobar"),
       ("/catalogo", "Catálogo"), ("/contenido", "Contenido"), ("/publicidad", "Anuncios"),
       ("/pedidos", "Pedidos"), ("/clientes", "Clientes"), ("/finanzas", "Finanzas"),
       ("/semana", "Semana"), ("/investigacion", "Investigación"), ("/fuentes", "Fuentes"))

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
.card.aviso{border-color:var(--amber);background:var(--amber-bg)}
.card.info{border-style:dashed}
.counts{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}
.slots{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
@media (min-width:720px){.slots{grid-template-columns:repeat(3,1fr)}}
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
display:flex;overflow-x:auto;text-align:center;font-size:.7rem;z-index:5}
nav.bottom a{flex:1 0 auto;padding:14px 8px;color:var(--muted);min-height:48px}
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
    if d.formato == "usd":
        text = usd(d.valor)
    elif d.formato == "x":
        text = f"{d.valor:,.2f}×"
    elif d.formato == "pct":
        text = f"{d.valor:,.1f}%"
    elif d.formato == "mxn":
        text = ("−" if d.valor < 0 else "") + f"MX${abs(d.valor):,.2f}"
    elif d.formato == "fecha":
        text = fecha(datetime.fromtimestamp(d.valor, TZ), hora=False)
    else:
        text = f"{d.valor:,.0f}"
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


def _alerta_meta(a, now: datetime) -> str:
    cuando = f"{fecha(a.actualizado)} ({hace(a.actualizado, now)})" if a.actualizado else "—"
    return f"Fuente: {a.fuente} · actualizado: {cuando}"


def inicio(res: Resumen, rd, fuentes: dict[str, EstadoFuente], now: datetime,
           nombre: str = "Lore", banner: str = "") -> str:
    """Home: the daily summary first, then the period numbers."""
    from .alertas import ATENCION, URGENTE

    per = res.periodo
    chips = "".join(
        f'<a class="chip{" on" if k == per.clave else ""}" href="/?p={k}">{t}</a>'
        for k, t in (("hoy", "Hoy"), ("7", "7 días"), ("30", "30 días")))
    acc = "".join(f'<li><a href="{escape(a.enlace)}">{escape(a.accion)}</a></li>'
                  for a in rd.acciones)
    acc = f"<ol>{acc}</ol>" if acc else "<p>Nada urgente. 🎨</p>"
    urg, ate = rd.cuenta(URGENTE), rd.cuenta(ATENCION)
    counts = (
        (f'<a href="/alertas" class="badge warn">{urg} urgente(s)</a>' if urg else "")
        + (f'<a href="/alertas" class="badge amber">{ate} aviso(s)</a>' if ate else "")
        or '<span class="badge ok">Nada pendiente</span>')
    body = (
        f'<div class="row"><div><p class="sub">Resumen del día · {fecha(now, hora=False)}</p>'
        f"<h1>Hola, {escape(nombre)}</h1></div></div>"
        f'<div class="card summary"><p><strong>Qué pasó:</strong> {escape(rd.que_paso)}</p>'
        f'<p><strong>Qué requiere tu atención:</strong></p><div class="counts">{counts}'
        '<a href="/alertas" class="chip">Ver alertas</a></div>'
        f"<p><strong>Tus 3 acciones de hoy</strong></p>{acc}"
        '<p class="meta">Sale de reglas fijas sobre los datos conectados; Claude lo redactará '
        "cuando el Asistente esté listo.</p></div>"
        "<h2>Hoy por canal y contabilidad</h2>"
        f'<div class="slots">{"".join(_kpi(d, now) for d in rd.ranuras)}</div>'
        f'<div class="chips">{chips}<span class="vs">vs {escape(per.comparacion)}</span></div>'
        f'<div class="grid">{"".join(_kpi(d, now) for d in res.datos)}</div>'
        '<p class="legend"><a href="/fuentes">Fuentes</a>: 0 = cero real · — = falta el dato · '
        "~ = estimado. Toca “¿De dónde sale?” en cualquier número.</p>"
    )
    return page("Inicio", "/", body, banner)


# --- Alertas ----------------------------------------------------------------------------------

def alertas_view(lista, fuentes: dict[str, EstadoFuente], now: datetime,
                 banner: str = "") -> str:
    from .alertas import NIVEL_NOMBRE, NIVELES

    clase = {"urgente": "alert", "atencion": "aviso", "info": "info"}
    body = ['<h1>Alertas</h1><p class="sub">Lo que necesita a una persona, lo más importante '
            "primero. Solo lectura: los arreglos se hacen en la tienda o pasan por Aprobar.</p>"]
    for nivel in NIVELES:
        items = [a for a in lista if a.nivel == nivel]
        if nivel == "info" and not items:
            continue
        h = " warn" if nivel == "urgente" else ""
        body.append(f'<h2 class="{h.strip()}">{escape(NIVEL_NOMBRE[nivel])} ({len(items)})</h2>')
        if not items:
            body.append('<p class="empty">Ninguna.</p>')
        for a in items:
            accion = (f'<div class="m"><strong>Qué hacer:</strong> {escape(a.accion)}</div>'
                      if a.accion else "")
            body.append(
                f'<div class="card {clase[nivel]}"><div class="t">'
                f'<a href="{escape(a.enlace)}">{escape(a.titulo)}</a></div>'
                f'<div class="m">{escape(a.detalle)}</div>{accion}'
                f'<div class="m">{escape(_alerta_meta(a, now))}</div></div>')
    sin = [f.info.nombre for f in fuentes.values() if f.estado == "sin-conectar"]
    if sin:
        body.append(f'<p class="legend">Fuentes aún no conectadas: {escape(", ".join(sin))}. '
                    "Sus números se muestran como “—”, nunca como cero.</p>")
    return page("Alertas", "/alertas", "".join(body), banner)


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
        f'<div class="r">{usd(p.neto)}<div class="m">neto</div>{_margen(p)}</div></div></div>'
    )


FALTA_TXT = {"comision_canal": "comisión", "costo_pod": "coste de impresión",
             "envio_pod": "envío de imprenta"}


def _margen(p: Pedido) -> str:
    if p.calidad_margen == "faltante" or p.margen is None:
        falta = ", ".join(FALTA_TXT.get(c, c) for c in p.faltan) or "costos"
        return (f'<div class="m" title="Falta: {escape(falta)}">margen —</div>'
                f'<div class="m">falta {escape(falta)}</div>')
    text = usd(p.margen)
    if p.calidad_margen == "estimado":
        return f'<div class="m">margen ~{text}</div><div class="m">estimado</div>'
    return f'<div class="m">margen {text}</div>'



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
                "app. Los pedidos de prueba no se cuentan. Margen = neto + envío cobrado − "
                "comisión de Shopify Payments − coste y envío de Prodigi, sin impuestos ni "
                "anuncios. “—” = falta un costo (nunca se cuenta como cero); “~” = estimado.</p>")
    return page("Pedidos", "/pedidos", "".join(body), banner)


# --- Catálogo ---------------------------------------------------------------------------------

ARCHIVO = {"ideal": ("ok", "archivo ideal"), "aceptable": ("ok", "archivo aceptable"),
           "baja-resolucion": ("warn", "resolución baja"), "no-apto": ("warn", "no sirve"),
           "sin-revisar": ("gray", "sin revisar")}
RUTA_CORTA = {"prodigi-app": "Prodigi", "frame-it-easy-app": "Frame It Easy",
              "prodigi-api": "Prodigi (API)", "manual": "Manual", "desconocida": "no está claro",
              "varias": "dos imprentas"}


def _precio(p: Producto) -> str:
    if p.precio_min is None:
        return "—"
    if p.precio_min == p.precio_max:
        return usd(p.precio_min)
    return f"{usd(p.precio_min)}–{usd(p.precio_max)}"


def _rutas(rutas) -> str:
    if not rutas:
        return "—"
    return ", ".join(RUTA_CORTA.get(r, r) for r in sorted(rutas))


def _ficha_avisos(f) -> list[str]:
    a = list(f.producto.avisos)
    p = f.producto
    if p.estado == "publicado":
        if "varias" in p.rutas or {"prodigi-app", "frame-it-easy-app"} <= p.rutas:
            a.append("Está en dos imprentas: un pedido podría imprimirse dos veces")
        elif p.rutas & {"manual", "desconocida"}:
            a.append("Ninguna imprenta recibe sus pedidos (ubicación “Manual”)")
        if f.archivos_mal:
            a.append(f"{f.archivos_mal} variante(s) con archivo que no sirve para su tamaño")
    return a


def catalogo(fichas: list, originales: list, datos: list[Dato], filtro: str, fuentes,
             now: datetime, banner: str = "") -> str:
    filtros = (("todo", "Todo"), ("venta", "En venta"), ("avisos", "Con avisos"),
               ("ocultos", "Ocultos o borrador"), ("mx", "Originales MX"))
    filtro = filtro if filtro in dict(filtros) else "todo"
    tabs = "".join(f'<a class="chip{" on" if k == filtro else ""}" href="/catalogo?f={k}">{t}</a>'
                   for k, t in filtros)
    badge = {"publicado": "ok", "en-aprobacion": "amber", "borrador": "gray", "pausado": "gray",
             "retirado": "gray"}
    sel = {
        "venta": [f for f in fichas if f.producto.estado == "publicado"],
        "avisos": [f for f in fichas if _ficha_avisos(f)],
        "ocultos": [f for f in fichas if f.producto.estado in ("pausado", "borrador")],
        "mx": [],
    }.get(filtro, fichas)
    rows = []
    for f in sel:
        p = f.producto
        avisos = _ficha_avisos(f)
        link = f"/catalogo/producto?c={escape(p.canal)}&amp;id={escape(p.id_producto)}"
        obra = (f" · obra {escape(f.obras[0].get('obra_id', ''))}" if f.obras
                else " · sin ligar a una obra")
        rows.append(
            f'<div class="card{" alert" if avisos else ""}"><div class="row"><div>'
            f'<div class="t"><a href="{link}">{escape(p.titulo)}</a></div>'
            f'<div class="m"><span class="tag">{escape(LINEA.get(p.linea, p.linea))}</span>'
            f"{escape(CANAL.get(p.canal, p.canal))} · {p.variantes} variante(s) · {_precio(p)}</div>"
            f'<div class="m">Imprime: {escape(_rutas(p.rutas))} · coste en {f.con_costo} de '
            f"{p.variantes} · archivo sin revisar en {f.archivos_sin}{obra}</div>"
            + "".join(f'<div class="m w">{escape(a)}</div>' for a in avisos)
            + f'</div><span class="badge {badge.get(p.estado, "gray")}">'
            f"{escape(ESTADO_LISTADO.get(p.estado, p.estado))}</span></div></div>")
    if filtro in ("todo", "mx"):
        rows.append("<h2>Originales México</h2>")
        if not originales:
            rows.append('<div class="card info"><div class="m">Aún no hay originales en la hoja. '
                        "Se cargan en las pestañas Obras y Variantes (línea MX-original, tipo "
                        "original). Mientras tanto se muestran como “—”, nunca como cero.</div></div>")
        for o in originales:
            ob = o.obra
            med = (f"{ob.get('ancho_cm')} × {ob.get('alto_cm')} cm"
                   if ob.get("ancho_cm") and ob.get("alto_cm") else "medidas —")
            precio = (f"MX${o.precio_mxn:,.0f} con IVA" if o.precio_mxn is not None
                      else "precio —")
            est = ob.get("estado") or "—"
            rows.append(
                f'<div class="card"><div class="row"><div><div class="t">'
                f"{escape(ob.get('titulo_es') or ob.get('titulo') or ob.get('obra_id', ''))}</div>"
                f'<div class="m"><span class="tag">Original MX</span>{escape(ob.get("tecnica") or "técnica —")}'
                f" · {escape(med)} · {escape(precio)}</div></div>"
                f'<span class="badge {"ok" if est == "activa" else "gray"}">{escape(est)}</span>'
                "</div></div>")
    shop = fuentes["shopify"]
    body = (
        '<h1>Catálogo</h1><p class="sub">Productos de la tienda con sus variantes, quién los '
        f"imprime, coste y archivo. Shopify actualizado {hace(shop.actualizado, now)}; "
        "la hoja se lee al abrir esta pantalla.</p>"
        f'<div class="grid">{"".join(_kpi(d, now) for d in datos)}</div>'
        f'<div class="tabs">{tabs}</div>'
        + ("".join(rows) or '<p class="empty">Nada en este filtro.</p>')
        + '<p class="legend">Solo lectura. Cambios de precio y publicaciones pasan por Aprobar. '
        "Nunca se recorta, estira ni regenera una obra: la revisión de archivo solo avisa.</p>"
    )
    return page("Catálogo", "/catalogo", body, banner)


def _celda(d: Dato) -> str:
    title = f"{d.fuente} · {d.periodo} · {d.definicion}" + (f" · {d.nota}" if d.nota else "")
    return f'<span title="{escape(title)}">{escape(valor(d))}</span> {calidad(d)}'


def producto(f, fuentes, now: datetime, banner: str = "") -> str:
    p = f.producto
    shop = fuentes["shopify"]
    rows = []
    for v in f.variantes:
        real = (f' · real {usd(v.margen_real)} en {v.ventas} venta(s)'
                if v.margen_real is not None else "")
        cls, txt = ARCHIVO[v.archivo.estado]
        ruta_cls = "warn" if v.ruta in ("manual", "desconocida", "varias") else "gray"
        rows.append(
            f'<div class="card"><div class="row"><div><div class="t">{escape(v.etiqueta)}</div>'
            f'<div class="m">{escape(v.sku) or "sin SKU"} · imprime '
            f'<span class="badge {ruta_cls}">{escape(RUTA_CORTA.get(v.ruta, v.ruta) or "—")}</span></div>'
            f'<div class="m">Coste {_celda(v.costo)} · Margen {_celda(v.margen)}{real}</div>'
            f'<div class="m">Archivo <span class="badge {cls}">{txt}</span> '
            f"{escape(v.archivo.motivo)}</div></div>"
            f'<div class="r">{usd(v.precio) if v.precio is not None else "—"}</div></div></div>')
    obras = "".join(
        f'<div class="card"><div class="t">Obra {escape(o.get("obra_id", ""))}: '
        f'{escape(o.get("titulo") or o.get("titulo_es") or "—")}</div>'
        f'<div class="m">Colección {escape(o.get("coleccion") or "—")} · '
        f'{escape(o.get("orientacion") or "orientación —")} · versión aprobada '
        f'{escape(o.get("version_aprobada") or "—")}</div></div>' for o in f.obras
    ) or ('<div class="card info"><div class="m">Sin ligar a una obra: ninguna variante tiene '
          "fila en Variantes con obra_id.</div></div>")
    avisos = "".join(f'<div class="card alert"><div class="m w">{escape(a)}</div></div>'
                     for a in _ficha_avisos(f))
    tienda = (f' · <a href="{escape(p.url)}" rel="noopener">ver en la tienda</a>' if p.url else "")
    body = (
        f'<p class="sub"><a href="/catalogo">← Catálogo</a></p><h1>{escape(p.titulo)}</h1>'
        f'<p class="sub">{escape(LINEA.get(p.linea, p.linea))} · {escape(CANAL.get(p.canal, p.canal))}'
        f" · {escape(ESTADO_LISTADO.get(p.estado, p.estado))}{tienda}. "
        f"Shopify actualizado {fecha(shop.actualizado)} ({hace(shop.actualizado, now)}).</p>"
        f"{avisos}<h2>Obra</h2>{obras}<h2>Variantes ({len(f.variantes)})</h2>"
        f"{''.join(rows)}"
        '<p class="legend">Precio e imprenta: Shopify (ubicación de inventario de cada variante). '
        "Coste: cotización en Variantes.costo_usd (impresión + envío a EUA), estimado. Margen "
        "estimado = precio − comisión estimada 2.9% + 30¢ − coste; sin descuentos, impuestos ni "
        "anuncios. “real” = promedio de ventas con costos reales de Prodigi. Archivo: "
        "resolución y proporción del archivo de impresión para el tamaño; nunca se recorta ni "
        "se estira. “—” = falta el dato.</p>"
    )
    return page(p.titulo, "/catalogo", body, banner)


# --- Contenido --------------------------------------------------------------------------------

GATE_BADGE = {"ok": ("ok", "Aprobado"), "pendiente": ("amber", "Por aprobar"),
              "no-hace-falta": ("gray", "Sin pedir")}


def _pieza(p, now: datetime, con_fecha: bool = True) -> str:
    from .contenido import PLATAFORMA

    r = p.row
    meta = [PLATAFORMA.get(p.plataforma, p.plataforma or "—"), r.get("formato") or "formato —",
            {"en": "inglés", "es": "español"}.get(r.get("idioma") or "", "idioma —")]
    if con_fecha:
        meta.append(fecha(p.fecha) if p.fecha else "sin fecha")
    if p.obra:
        meta.append(f"obra {p.obra}")
    texto = (f'<details><summary>Texto</summary><pre>{escape(r.get("texto"))}</pre></details>'
             if r.get("texto") else "")
    archivo = (f'<div class="m">Imagen: {escape(r.get("archivo"))} (original, sin recortar)</div>'
               if r.get("archivo") else "")
    if p.estado == "publicado":
        res = r.get("resultado") or "—"
        url = (f' · <a href="{escape(r.get("url"))}" rel="noopener">ver publicación</a>'
               if r.get("url") else " · sin enlace")
        archivo += f'<div class="m">Resultado: {escape(res)}{url}</div>'
    cls, corto = (("warn", "Sin aprobación válida") if p.gate.alerta
                  else GATE_BADGE.get(p.gate.estado, ("gray", "Revisar")))
    w = " w" if p.gate.alerta else ""
    return (f'<div class="card{" alert" if p.gate.alerta else ""}"><div class="row"><div>'
            f'<div class="t">{escape(p.titulo)}</div>'
            f'<div class="m">{escape(" · ".join(meta))}</div>'
            f'<div class="m{w}">{escape(p.gate.texto)}</div>{archivo}{texto}</div>'
            f'<span class="badge {cls}">{corto}</span></div></div>')


def contenido_view(ps: list, datos: list[Dato], plataforma: str, now: datetime,
                   banner: str = "") -> str:
    from .contenido import ESTADO, calendario

    chips = "".join(
        f'<a class="chip{" on" if k == plataforma else ""}" href="/contenido{"?pl=" + k if k else ""}">'
        f"{t}</a>" for k, t in (("", "Todas"), ("instagram", "Instagram"),
                                ("pinterest", "Pinterest")))
    body = ['<h1>Contenido</h1><p class="sub">Calendario y cola de publicaciones por plataforma, '
            "de la pestaña Contenido (se lee al abrir). Solo lectura: nada se publica sin tu "
            "aprobación del texto e imagen exactos.</p>",
            f'<div class="grid">{"".join(_kpi(d, now) for d in datos)}</div>',
            f'<div class="tabs">{chips}</div>']
    if not ps:
        body.append('<div class="card info"><div class="m">Aún no hay piezas en la pestaña '
                    "Contenido. Cada fila es una publicación, reel, story o pin: plataforma, "
                    "formato, idioma, texto, archivo de imagen y fecha.</div></div>")
    cal = calendario(ps, now)
    body.append("<h2>Próximos 14 días</h2>")
    if not cal:
        body.append('<p class="empty">Nada con fecha en los próximos 14 días.</p>')
    for dia_, items in cal:
        body.append(f'<p class="meta"><strong>{fecha(dia_, hora=False)}</strong></p>')
        body.append("".join(_pieza(p, now) for p in items))
    for estado, titulo in ESTADO.items():
        items = [p for p in ps if p.estado == estado]
        if estado == "publicado":
            items = sorted(items, key=lambda p: p.fecha or now, reverse=True)[:20]
        if not items:
            continue
        body.append(f'<h2 class="{"warn" if estado == "fallido" else ""}">{titulo} ({len(items)})</h2>')
        body.append("".join(_pieza(p, now) for p in items))
    body.append('<p class="legend">Los textos para EUA van en inglés. Las imágenes son los '
                "archivos originales aprobados: nunca se recortan, estiran ni regeneran. "
                "Resultados “—” hasta conectar Instagram y Pinterest.</p>")
    return page("Contenido", "/contenido", "".join(body), banner)


# --- Publicidad -------------------------------------------------------------------------------

CAMP_BADGE = {"ok": ("ok", "Aprobada"), "pendiente": ("amber", "Por aprobar"),
              "sin-solicitud": ("amber", "Falta pedirla"), "no-hace-falta": ("gray", "Sin pedir"),
              "rechazado": ("gray", "Rechazada")}
DESTINO = {"shopify": "Shopify", "etsy": "Etsy", "sitio-mx": "Sitio MX",
           "instagram": "perfil de Instagram", "otro": "otro destino"}


def _dinero(v: float | None) -> str:
    return "—" if v is None else usd(v)


def _campana(c, now: datetime) -> str:
    from .publicidad import PLATAFORMA

    r = c.row
    meta = [PLATAFORMA.get(c.plataforma, c.plataforma or "plataforma —"),
            "a " + DESTINO.get(r.get("destino") or "", r.get("destino") or "destino —")]
    if c.obra:
        meta.append(f"obra {c.obra}")
    fechas = f"{r.get('inicio') or 'inicio —'} a {r.get('fin') or 'sin fin'}"
    plan = (f"Presupuesto {_dinero(c.diario)}/día · total {_dinero(c.total)} · {fechas}"
            + (f" · este mes hasta {usd(c.plan_mes)}" if c.plan_mes is not None else ""))
    extra = []
    if r.get("objetivo") or r.get("audiencia"):
        extra.append(f"Objetivo: {r.get('objetivo') or '—'} · audiencia: {r.get('audiencia') or '—'}")
    extra.append(f"utm_campaign: {r.get('utm_campana') or '—'}")
    texto = (f'<details><summary>Texto e imagen</summary><pre>{escape(r.get("texto") or "—")}'
             f'</pre><div class="m">Imagen: {escape(r.get("archivo") or "—")} (original, sin '
             "recortar ni regenerar)</div></details>")
    resultados = " · ".join(f"{escape(d.etiqueta)}: {_celda(d)}" for d in
                            [c.shopify] + c.plataforma_datos)
    alert = c.gate.alerta or c.excede
    cls, corto = (("warn", "Revisar") if alert
                  else CAMP_BADGE.get(c.gate.estado, ("gray", "Revisar")))
    avisos = "".join(f'<div class="m w">{escape(a)}</div>' for a in c.avisos
                     if a != c.gate.texto)
    return (f'<div class="card{" alert" if alert else ""}"><div class="row"><div>'
            f'<div class="t">{escape(c.nombre)}</div>'
            f'<div class="m">{escape(" · ".join(meta))}</div>'
            f'<div class="m">{escape(plan)}</div>'
            + "".join(f'<div class="m">{escape(x)}</div>' for x in extra)
            + f'<div class="m{" w" if c.gate.alerta else ""}">{escape(c.gate.texto)}</div>'
            f"{avisos}<div class=\"m\">Resultados: {resultados}</div>{texto}</div>"
            f'<span class="badge {cls}">{corto}</span></div></div>')


def _plan_celda(planeado: float, pasa: bool) -> str:
    text = "~" + usd(planeado)
    return f'<span class="badge warn">{text}</span><br><span class="meta">pasa el tope</span>' if pasa else text


def publicidad_view(cs: list, datos: list[Dato], filas_origen: list, plan: list,
                    per, fuentes: dict[str, EstadoFuente], now: datetime,
                    banner: str = "", faltan_tabs: list[str] | None = None) -> str:
    from .publicidad import ESTADO, ORIGEN, PLATAFORMA

    chips = "".join(
        f'<a class="chip{" on" if k == per.clave else ""}" href="/publicidad?p={k}">{t}</a>'
        for k, t in (("hoy", "Hoy"), ("7", "7 días"), ("30", "30 días")))
    body = ['<h1>Publicidad</h1><p class="sub">Campañas planeadas, topes de gasto y de dónde '
            "llegan los pedidos. Solo lectura: nada se lanza ni cambia de presupuesto sin tu "
            "aprobación, y desde aquí nunca se envía nada a Meta, Pinterest ni Google.</p>",
            f'<div class="chips">{chips}<span class="vs">{escape(per.texto)}</span></div>',
            f'<div class="grid">{"".join(_kpi(d, now) for d in datos)}</div>']
    if faltan_tabs:
        body.insert(1, '<div class="card alert"><div class="m w">La hoja aún no tiene la(s) '
                    f'pestaña(s) {escape(", ".join(faltan_tabs))}. Se crean con '
                    "<code>python -m lulamacaroni.setup_workbook</code> (solo agrega pestañas y "
                    "encabezados; no borra nada).</div></div>")

    body.append("<h2>Topes por plataforma</h2>")
    if not plan:
        body.append('<div class="card info"><div class="m">Aún no hay topes. Se definen en la '
                    "pestaña Topes: tope diario, tope mensual y cambio máximo de presupuesto "
                    "por plataforma. Sin tope no se pide aprobación para ninguna campaña.</div></div>")
    else:
        rows = []
        for pp in plan:
            t = pp.tope
            cambio = f"{t.cambio_pct:.0f}%" if t and t.cambio_pct is not None else "—"
            corto = {"meta": "Meta", "etsy-ads": "Etsy Ads"}.get(
                pp.plataforma, PLATAFORMA.get(pp.plataforma, pp.plataforma))
            rows.append(
                f"<tr><td><strong>{escape(corto)}</strong><br><span class='meta'>cambio máx. "
                f"{escape(cambio)}</span></td><td>{_dinero(t.diario if t else None)}</td>"
                f"<td>{_dinero(t.mensual if t else None)}</td>"
                f"<td>{_plan_celda(pp.aprobado, pp.pasa)}</td><td>~{usd(pp.propuesto)}</td></tr>")
        body.append("<div class='tablebox'><table><thead><tr><th>Plataforma</th><th>Tope diario"
                    "</th><th>Tope mensual</th><th>Aprobado este mes</th>"
                    "<th>Propuesto</th></tr>"
                    f"</thead><tbody>{''.join(rows)}</tbody></table></div>"
                    '<p class="legend">Topes: pestaña Topes, los fija Lore. Plan del mes '
                    "(estimado): presupuesto diario × días de este mes dentro de sus fechas, "
                    "con su total como límite. Aprobado = campañas aprobadas o activas con "
                    "aprobación válida; propuesto = las que esperan aprobación o aún no la piden. "
                    "Cambio máx.: el mayor cambio de presupuesto que se te propondrá de una "
                    "vez.</p>")

    if not cs:
        body.append('<h2>Campañas</h2><div class="card info"><div class="m">Aún no hay campañas en '
                    "la pestaña Publicidad. Cada fila es una campaña: plataforma, obra, texto, "
                    "imagen, destino, utm_campaign, presupuesto diario y total, fechas. Para "
                    "pedirte la aprobación: <code>python -m lulamacaroni.app.publicidad --pedir "
                    "ID</code>.</div></div>")
    for estado, titulo in ESTADO.items():
        items = [c for c in cs if c.estado == estado]
        if not items:
            continue
        warn = "warn" if any(c.alerta for c in items) else ""
        body.append(f'<h2 class="{warn}">{escape(titulo)} ({len(items)})</h2>')
        body.append("".join(_campana(c, now) for c in items))

    shop = fuentes["shopify"]
    body.append("<h2>¿De dónde llegan los pedidos? (Shopify)</h2>")
    if not shop.conectada:
        body.append('<p class="empty">Shopify no está conectado todavía.</p>')
    elif not filas_origen:
        body.append(f'<p class="empty">Sin pedidos de Shopify en el periodo ({escape(per.texto)}). '
                    "Cero real, no un dato faltante.</p>")
    else:
        rows = "".join(
            f"<tr><td><strong>{escape(ORIGEN[f.clave])}</strong></td>"
            f"<td>{f.pedidos}</td><td>{f.pedidos_anuncio if f.clave != 'sin-dato' else '—'}</td>"
            f"<td>{f.pedidos_organico if f.clave != 'sin-dato' else '—'}</td>"
            f"<td>{usd(f.ventas)}</td><td>—</td></tr>" for f in filas_origen)
        body.append("<div class='tablebox'><table><thead><tr><th>Origen</th><th>Pedidos</th>"
                    "<th>De anuncio</th><th>Orgánico</th><th>Ventas netas</th>"
                    f"<th>Según la plataforma</th></tr></thead><tbody>{rows}</tbody></table></div>")
    body.append(
        '<p class="legend">Origen: recorrido del cliente de Shopify (última visita antes del '
        f"pedido: UTM y sitio que la refirió). Shopify actualizado {hace(shop.actualizado, now)}. "
        "Cada pedido cuenta una vez. “Según la plataforma” es lo que Meta o Pinterest se "
        "atribuyen con su propia ventana; va aparte y nunca se suma a lo de Shopify (fuente no "
        "conectada: “—”). Etsy no comparte el origen de la visita: sus anuncios se medirán con "
        "los reportes de Etsy Ads. Una atribución no prueba que el anuncio causó la venta.</p>")
    return page("Publicidad", "/publicidad", "".join(body), banner)


# --- Clientes ---------------------------------------------------------------------------------

def _cliente(c, now: datetime) -> str:
    meta = [LINEA.get(c.linea, c.linea or "línea —"),
            CANAL.get(c.canal, c.canal or "canal —"), c.lugar, c.consentimiento]
    if c.desde:
        meta.append(f"cliente desde {fecha(c.desde, hora=False)}")
    origen = (f'<span title="{escape(c.origen.nota)}">{escape(c.origen.texto)}</span> '
              + ('<span class="q real">real</span>' if c.origen.calidad == "real"
                 else '<span class="q faltante">falta el dato</span>'))
    notas = "".join(
        f'<div class="m">📝 {escape(t)} <span class="meta">({escape(p)})</span></div>'
        for t, p in c.notas)
    seg = ""
    if c.seguimiento:
        s = c.seguimiento
        para = fecha(datetime.combine(s.para, datetime.min.time(), TZ), hora=False) \
            if s.para else "sin fecha"
        cls = "warn" if s.vencido else ("amber" if s.estado == "pendiente" else "gray")
        txt = "vencido" if s.vencido else s.estado
        seg = (f'<div class="m{" w" if s.vencido else ""}">Seguimiento: {escape(s.texto)} · '
               f'para {escape(para)} <span class="badge {cls}">{escape(txt)}</span></div>')
    rows = [("Pedidos", c.pedidos), ("Total", c.total), ("Último pedido", c.ultimo)]
    dl = "".join(
        f"<dt>{escape(k)}</dt><dd>{escape(d.fuente)} · {escape(d.periodo)} · "
        f"{escape(d.definicion)} · actualizado "
        f"{escape(hace(d.actualizado, now) if d.actualizado else '—')}"
        + (f" · {escape(d.nota)}" if d.nota else "") + "</dd>" for k, d in rows)
    alert = " alert" if c.vencido else ""
    return (f'<div class="card{alert}"><div class="row"><div>'
            f'<div class="t">{escape(c.nombre)}</div>'
            f'<div class="m">{escape(" · ".join(meta))}</div>'
            f'<div class="m">Pedidos {_celda(c.pedidos)} · Total {_celda(c.total)} · '
            f'Último {_celda(c.ultimo)}</div>'
            f'<div class="m">Cómo llegó: {origen}</div>{notas}{seg}'
            f'<details class="m"><summary>¿De dónde sale?</summary><dl>{dl}</dl></details>'
            f'</div><div class="r">{escape(valor(c.total))}</div></div></div>')


def clientes_view(cs: list, datos: list[Dato], origenes: list, filtro: str, per,
                  fuentes: dict[str, EstadoFuente], now: datetime, banner: str = "") -> str:
    from .clientes import FILTROS

    chips = "".join(
        f'<a class="chip{" on" if k == per.clave else ""}" '
        f'href="/clientes?p={k}&amp;f={escape(filtro)}">{t}</a>'
        for k, t in (("hoy", "Hoy"), ("7", "7 días"), ("30", "30 días")))
    tabs = "".join(
        f'<a class="chip{" on" if k == filtro else ""}" href="/clientes?f={k}">{escape(t)}</a>'
        for k, t in FILTROS.items())
    body = ['<h1>Clientes</h1><p class="sub">Quién compra, cada cuánto, desde dónde y qué '
            "seguimiento les debes. Solo lectura: notas y seguimientos se escriben en la "
            "pestaña Clientes. Sin correos, teléfonos ni direcciones: solo nombre corto, país "
            "y estado.</p>",
            f'<div class="chips">{chips}<span class="vs">{escape(per.texto)}</span></div>',
            f'<div class="grid">{"".join(_kpi(d, now) for d in datos)}</div>']
    if origenes:
        rows = "".join(f"<tr><td>{escape(k)}</td><td>{n}</td></tr>" for k, n in origenes)
        body.append("<h2>Cómo llegaron (primer pedido)</h2><div class='tablebox'><table>"
                    "<thead><tr><th>Origen</th><th>Clientes</th></tr></thead>"
                    f"<tbody>{rows}</tbody></table></div>")
    body.append(f'<div class="tabs">{tabs}</div>')
    body.append("".join(_cliente(c, now) for c in cs)
                or '<p class="empty">Nadie en este filtro.</p>')
    etsy = fuentes["etsy"]
    if not etsy.conectada:
        body.append('<div class="card info"><div class="t">Etsy</div><div class="m">Fuente no '
                    f"conectada ({escape(etsy.nota or etsy.info.fase)}). Sus compradores "
                    "aparecerán aquí con canal Etsy y nunca se mandan a una lista de correo "
                    "externa.</div></div>")
    sync = fuentes.get("shopify-clientes")
    body.append(
        '<p class="legend">EUA: clientes de Shopify; pedidos, total y último pedido son las '
        "cifras de Shopify para toda la historia del cliente (actualizado "
        f"{hace(sync.actualizado if sync else None, now)}). México: lo que Lore anota en la "
        "pestaña Clientes (linea MX-original), en pesos con IVA; si Pedidos tiene sus "
        "pedidos, cuentan esos. “Cómo llegó”: la última visita antes de su primer pedido "
        "según el recorrido de Shopify; cada cliente cuenta una vez y no prueba que el "
        "anuncio causó la compra. Notas: quién y cuándo, o “nota del cliente en Shopify”. "
        "— = falta el dato.</p>")
    return page("Clientes", "/clientes", "".join(body), banner)


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
