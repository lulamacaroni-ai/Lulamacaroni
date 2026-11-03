"""HTML for the back office screens (Mexican Spanish, phone first, works on desktop).

Pure functions: data in, one HTML string out. Everything shown is escaped. Layout and
colors come from Lore's artwork in the store; DM Sans, the storefront's font.
"""

from __future__ import annotations

import re
from datetime import datetime
from html import escape

from ..approval.page import render_cards
from . import arte
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

# Left-hand menu, grouped. Each entry: (path, label, icon key).
NAV_GRUPOS = (
    ("Hoy", (("/inicio", "Inicio", "casa"), ("/alertas", "Alertas", "campana"),
             ("/aprobar", "Aprobar", "check"))),
    ("Tienda", (("/catalogo", "Catálogo", "cuadros"), ("/pedidos", "Pedidos", "caja"),
                ("/clientes", "Clientes", "personas"))),
    ("Promoción", (("/contenido", "Contenido", "calendario"), ("/publicidad", "Anuncios", "megafono"),
                   ("/investigacion", "Investigación", "lupa"))),
    ("Números", (("/finanzas", "Finanzas", "dinero"), ("/semana", "Semana", "grafica"),
                 ("/fuentes", "Fuentes", "enchufe"))),
)
NAV = tuple((h, t) for _, items in NAV_GRUPOS for h, t, _ in items)

# Small stroke icons (24×24 viewBox), drawn in the current text color.
ICONOS = {
    "casa": "M3 11l9-7 9 7M5 10v10h5v-6h4v6h5V10",
    "campana": "M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 21h4",
    "check": "M4 12l5 5L20 6",
    "cuadros": "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
    "caja": "M3 7l9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10",
    "personas": "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21a7 7 0 0 1 14 0M17 3.5a4 4 0 0 1 0 7.5M22 21a7 7 0 0 0-4-6.3",
    "calendario": "M4 5h16v16H4zM4 10h16M8 3v4M16 3v4",
    "megafono": "M3 10v4h4l7 5V5L7 10zM18 8a5 5 0 0 1 0 8",
    "lupa": "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-5-5",
    "dinero": "M3 6h18v12H3zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 9v.01M18 15v.01",
    "grafica": "M4 20V4M4 20h16M8 16v-4M12 16V8M16 16v-6",
    "enchufe": "M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4",
    "menu": "M4 6h16M4 12h16M4 18h16",
    "cerrar": "M6 6l12 12M18 6L6 18",
}


def icono(nombre: str) -> str:
    return (f'<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="{ICONOS[nombre]}"/>'
            "</svg>")


CSS = """
:root{
/* Palette taken from Lore's artwork in the Shopify store (cherry red, olive, ochre, parchment, teal).
   Links use deep ochre so cherry red stays for the brand and warnings read as warnings. */
--cereza:#9C0F0C;--olivo:#364422;--ocre:#CC842E;--pergamino:#E8D2B2;--azulejo:#1F5C5E;
--bg:#F6EFE3;--card:#FFFDF8;--ink:#2B1A12;--muted:#6A5644;--line:#E6D8C2;
--accent:#8A4F12;--accent-soft:#F4E4CC;--accent-ink:#FFFFFF;--warn:#8E120E;--warn-bg:#F9E2DC;
--ok:#3F5221;--ok-bg:#E8EDD9;--amber-bg:#F7E5C4;--amber:#6E4710;--chip:#EFE6D6;--no:#8E120E;
--side:#2C3520;--side-ink:#F2EADB;--side-muted:#B8B096;--side-hover:#38432A;--side-on:#435032;
--side-mark:var(--ocre);
--shadow:0 1px 2px rgba(43,26,18,.05),0 2px 8px rgba(43,26,18,.05);--r:14px;--sidew:236px}
@media (prefers-color-scheme:dark){:root{--bg:#16120D;--card:#201A14;--ink:#F3EBDD;
--muted:#BDAE98;--line:#3A3026;--accent:#E0A85A;--accent-soft:#3A2C18;--accent-ink:#1C1C1E;
--warn:#F29A8C;--warn-bg:#3B1D18;--ok:#A9C27E;--ok-bg:#27311A;--amber-bg:#3A2C14;--amber:#EBC27A;
--chip:#2B241C;--no:#F29A8C;--side:#151A10;--side-hover:#222919;--side-on:#2E3722;--side-mark:#E0A85A;
--shadow:none}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 "DM Sans",system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
img{max-width:100%;height:auto}
.ico{width:18px;height:18px;flex:none;fill:none;stroke:currentColor;stroke-width:1.8;
stroke-linecap:round;stroke-linejoin:round}

/* --- layout: left menu + content --------------------------------------------------- */
.layout{min-height:100vh}
.side{position:fixed;top:0;left:0;bottom:0;width:var(--sidew);background:var(--side);
color:var(--side-ink);display:flex;flex-direction:column;overflow-y:auto;z-index:20}
.brand{display:flex;align-items:center;gap:10px;padding:20px 18px 14px;color:var(--side-ink)}
.brand:hover{text-decoration:none}
.brand .mark{width:34px;height:34px;border-radius:10px;background:var(--cereza);color:#fff;
display:grid;place-items:center;font:700 15px/1 "DM Sans",system-ui,sans-serif}
.brand .name{font:700 1.05rem/1.1 "DM Sans",system-ui,sans-serif;letter-spacing:-.01em}
.brand .name small{display:block;font:500 .7rem/1.3 "DM Sans",system-ui,sans-serif;color:var(--side-muted);
letter-spacing:.02em}
.side nav{padding:4px 10px 16px;flex:1}
.side .grp{font-size:.66rem;font-weight:600;letter-spacing:.09em;text-transform:uppercase;
color:var(--side-muted);margin:16px 10px 6px}
.side nav a{display:flex;align-items:center;gap:11px;padding:9px 10px;border-radius:9px;
color:var(--side-ink);opacity:.82;font-size:.9rem;font-weight:500;min-height:40px}
.side nav a:hover{background:var(--side-hover);opacity:1;text-decoration:none}
.side nav a.on{background:var(--side-on);opacity:1;font-weight:600;box-shadow:inset 3px 0 0 var(--side-mark)}
.side nav a.on .ico{color:var(--side-mark)}
.side .foot{padding:14px 18px 18px;font-size:.72rem;color:var(--side-muted);border-top:1px solid var(--side-hover)}
.top{display:none}
.side .close{display:none;position:absolute;top:14px;right:10px;width:40px;height:40px;place-items:center;
border-radius:10px;cursor:pointer;color:var(--side-ink)}
#menu{position:absolute;opacity:0;pointer-events:none}
.veil{display:none}
.content{margin-left:var(--sidew);min-width:0}
main{max-width:1120px;margin:0 auto;padding:28px 32px 56px}
@media (max-width:900px){
 .top{display:flex;position:sticky;top:0;z-index:15;align-items:center;gap:10px;height:56px;
 padding:0 12px;background:var(--side);color:var(--side-ink)}
 .top .brand{padding:0}.top .brand .mark{width:30px;height:30px;font-size:13px}
 .top .here{margin-left:auto;font-size:.85rem;color:var(--side-muted);white-space:nowrap;
 overflow:hidden;text-overflow:ellipsis}
 .burger{display:grid;place-items:center;width:44px;height:44px;border-radius:10px;cursor:pointer;
 color:var(--side-ink)}
 .burger:hover{background:var(--side-hover)}.burger .ico{width:22px;height:22px}
 .side{transform:translateX(-100%);transition:transform .2s ease;width:min(84vw,280px)}
 #menu:checked~.side{transform:none;box-shadow:0 0 40px rgba(0,0,0,.35)}
 #menu:checked~.veil{display:block;position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:19}
 #menu:focus-visible~.top .burger{outline:2px solid var(--accent)}
 .side .close{display:grid}
 .content{margin-left:0}
 main{padding:18px 16px 40px}
}
@media (prefers-reduced-motion:reduce){.side{transition:none}}
html.entrada .layout{animation:entra .7s ease both}
@keyframes entra{from{opacity:0}to{opacity:1}}
@media (prefers-reduced-motion:reduce){html.entrada .layout{animation:none}}

/* --- type ----------------------------------------------------------------------------- */
h1{font-family:"DM Sans",system-ui,sans-serif;font-size:1.85rem;line-height:1.15;
letter-spacing:-.02em;margin:2px 0 6px}
h2{font-size:.72rem;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);
font-weight:700;margin:30px 0 10px;display:flex;align-items:center;gap:10px}
h2::after{content:"";flex:1;height:1px;background:var(--line)}
h2.warn{color:var(--warn)}
h1+p,.sub{color:var(--muted)}
.sub{font-size:.85rem;margin:0}
h1+.sub{margin-bottom:16px}
.banner{background:var(--amber-bg);color:var(--amber);border-radius:10px;padding:9px 14px;
font-size:.85rem;font-weight:500;margin-bottom:18px;border:1px solid rgba(92,64,0,.12)}

/* --- cards ----------------------------------------------------------------------------- */
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:14px 16px;
margin:10px 0;box-shadow:var(--shadow)}
.summary{padding:18px 20px}
.summary p{margin:6px 0}.summary ol{margin:6px 0 4px;padding-left:22px}.summary li{margin:6px 0}
.chips{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:16px 0 8px}
.chip{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;
padding:7px 15px;font-size:.85rem;font-weight:500;min-height:38px;display:inline-flex;align-items:center}
.chip:hover{border-color:var(--accent);text-decoration:none}
.chip.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.chips .vs{margin-left:auto;color:var(--muted);font-size:.78rem}
.grid,.slots{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px}
@media (min-width:720px){.grid,.slots{grid-template-columns:repeat(3,1fr)}}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:14px 16px;
display:flex;flex-direction:column;gap:3px;min-width:0;box-shadow:var(--shadow)}
.kpi .lbl{font-size:.78rem;color:var(--muted);font-weight:500}
.kpi .val{font:600 1.55rem/1.2 "DM Sans",system-ui,sans-serif;letter-spacing:-.01em;
font-variant-numeric:tabular-nums;margin:2px 0}
.kpi .val.missing{color:var(--muted)}
.kpi .foot{font-size:.76rem;color:var(--muted)}
.kpi details{font-size:.76rem;color:var(--muted);margin-top:auto;padding-top:6px}
.kpi details summary{cursor:pointer;color:var(--accent);min-height:24px;font-weight:500}
.kpi details[open]{background:var(--bg);border-radius:10px;padding:6px 10px 8px;margin-top:8px}
.kpi dl{margin:6px 0 0}
.kpi dt{font-weight:600;margin-top:5px;color:var(--ink)}.kpi dd{margin:0}
.q{display:inline-block;font-size:.7rem;font-weight:600;border-radius:999px;padding:1px 8px;line-height:1.6}
.q.real{background:var(--ok-bg);color:var(--ok)}.q.cero{background:var(--chip);color:var(--muted)}
.q.faltante{background:var(--warn-bg);color:var(--warn)}.q.estimado{background:var(--amber-bg);color:var(--amber)}
.legend{font-size:.78rem;color:var(--muted);margin:12px 0 0}
.row{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
.row .t{font-weight:600}.row .m{font-size:.85rem;color:var(--muted)}
.row .r{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.card .t+.m,.card .m+.m{margin-top:2px}
.card.alert{border-color:color-mix(in srgb,var(--warn) 35%,var(--line));background:var(--warn-bg);
box-shadow:inset 4px 0 0 var(--warn)}
.card.alert .m.w,.m.w{color:var(--warn)}
.card.aviso{border-color:color-mix(in srgb,var(--amber) 30%,var(--line));background:var(--amber-bg);
box-shadow:inset 4px 0 0 var(--amber)}
.card.info{border-style:dashed;box-shadow:none;background:transparent}
.counts{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0}
.badge{display:inline-flex;align-items:center;font-size:.72rem;font-weight:600;border-radius:999px;
padding:3px 10px;white-space:nowrap;line-height:1.5}
.badge:hover{text-decoration:none}
.badge.ok{background:var(--ok-bg);color:var(--ok)}.badge.amber{background:var(--amber-bg);color:var(--amber)}
.badge.gray{background:var(--chip);color:var(--muted)}.badge.warn{background:var(--warn-bg);color:var(--warn)}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}

/* --- tables ---------------------------------------------------------------------------- */
.tablebox{background:var(--card);border:1px solid var(--line);border-radius:var(--r);overflow-x:auto;
box-shadow:var(--shadow);margin:10px 0}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th{text-align:left;font-size:.7rem;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);
font-weight:600;padding:10px 12px;background:var(--bg);border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:11px 12px;border-top:1px solid var(--line);vertical-align:top;font-variant-numeric:tabular-nums}
tr:first-child td{border-top:0}
tbody tr:hover td{background:color-mix(in srgb,var(--accent-soft) 45%,transparent)}
.empty{color:var(--muted);text-align:center;padding:24px}
.tag{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:1px 9px;margin-right:6px;
font-size:.78rem;background:var(--bg)}
.meta{color:var(--muted);font-size:.85rem}
details pre{white-space:pre-wrap;word-break:break-word;font-size:.8rem;background:var(--bg);padding:10px;border-radius:8px}
form{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
input[type=text]{flex:1 1 100%;padding:10px 12px;border:1px solid var(--line);border-radius:10px;
background:var(--bg);color:var(--ink);font:inherit}
input[type=text]:focus{outline:2px solid var(--accent);outline-offset:1px}
button{flex:1;padding:12px;border:0;border-radius:10px;color:#fff;cursor:pointer;font:inherit;font-weight:600}
button:hover{filter:brightness(1.08)}
button.ok{background:#4A5E2A}button.no{background:var(--cereza)}
a:focus-visible,summary:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:6px}
.pr{display:flex;gap:10px;align-items:flex-start;min-width:0}
.ph{flex:0 0 auto;width:72px;height:72px;border-radius:8px;background:var(--chip);
display:flex;align-items:center;justify-content:center;overflow:hidden;color:var(--muted);
font-size:.65rem;text-align:center;line-height:1.1}
.ph img{max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain;display:block}
.ph.sm{width:52px;height:52px}
.ph.md{width:96px;height:96px;padding:4px}
.gal{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}

/* --- Catálogo: the art first, large and whole (scaled to fit, never cropped) -------------- */
.galeria{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,400px),1fr));gap:18px;
margin:14px 0}
.pieza{background:var(--card);border:1px solid var(--line);border-radius:var(--r);overflow:hidden;
box-shadow:var(--shadow);display:flex;flex-direction:column;min-width:0}
.pieza.alert{border-color:color-mix(in srgb,var(--warn) 35%,var(--line));box-shadow:inset 0 4px 0 var(--warn)}
.pieza .foto{display:block}
.ph.xl{width:100%;height:auto;aspect-ratio:1/1;border-radius:0;padding:22px;font-size:.9rem;
background:color-mix(in srgb,var(--pergamino) 45%,var(--card))}
.ph.xl img{max-height:100%;filter:drop-shadow(0 6px 14px rgba(43,26,18,.22))}
.pieza .foto:hover .ph.xl img{transform:scale(1.015)}
.ph.xl img{transition:transform .25s ease}
@media (prefers-reduced-motion:reduce){.ph.xl img{transition:none}}
.pieza .info{padding:14px 16px 16px;display:flex;flex-direction:column;gap:3px}
.pieza .info .t{font-size:1.08rem}
.pieza.alert .info{background:var(--warn-bg)}
@media (prefers-color-scheme:dark){.ph.xl{background:#2A2219}}

/* --- product page: a large cover, whole ----------------------------------------------------- */
.cubierta{margin:16px 0 8px}
.ph.cover{width:100%;height:min(82vh,820px);padding:20px;border-radius:var(--r);font-size:.95rem;
background:color-mix(in srgb,var(--pergamino) 45%,var(--card));border:1px solid var(--line)}
.ph.cover img{max-height:100%;filter:drop-shadow(0 8px 20px rgba(43,26,18,.25))}
@media (prefers-color-scheme:dark){.ph.cover{background:#2A2219}}
@media (max-width:600px){.ph.cover{height:auto;aspect-ratio:1/1;padding:10px}.ph.xl{padding:14px}}

/* --- details of Lore's paintings: one per screen, a row of stamps at the foot ---------------- */
.cab{display:flex;align-items:flex-start;justify-content:space-between;gap:28px;margin-bottom:10px}
.cab-t{flex:1;min-width:0}
.obra{flex:none;margin:0;width:118px;display:flex;flex-direction:column;align-items:center;gap:6px}
.obra img{display:block;width:118px;height:148px;border-radius:999px 999px 12px 12px;
border:4px solid var(--card);box-shadow:0 2px 4px rgba(43,26,18,.12),0 8px 22px rgba(43,26,18,.14)}
.obra figcaption{font-size:.68rem;line-height:1.3;color:var(--muted);text-align:center}
@media (max-width:600px){.cab{gap:14px;align-items:flex-start}.obra{width:78px}
 .obra img{width:78px;height:98px;border-width:3px}.obra figcaption{display:none}}
.sellos{display:flex;justify-content:center;flex-wrap:wrap;gap:10px;margin:44px 0 0;padding-top:22px;
border-top:1px solid var(--line)}
.sellos img{display:block;width:40px;height:40px;border-radius:50%;border:2px solid var(--card);
box-shadow:0 1px 4px rgba(43,26,18,.18);opacity:.92}
.empty::before{content:"";display:block;width:56px;height:56px;margin:0 auto 10px;border-radius:50%;
background:var(--motivo) center/contain no-repeat;box-shadow:0 1px 4px rgba(43,26,18,.18)}
.card.info{position:relative;padding-left:68px;min-height:64px}
.card.info::before{content:"";position:absolute;left:16px;top:14px;width:38px;height:38px;
border-radius:50%;background:var(--motivo) center/contain no-repeat;opacity:.95}
.desc p{margin:6px 0}

/* --- the puppy (Lore's art, cut out of its background, never cropped or stretched) ------ */
.perrito{position:fixed;top:0;left:0;z-index:19;pointer-events:none;width:var(--perro,76px)}
.perrito img{display:block;width:100%;height:auto;filter:drop-shadow(0 2px 3px rgba(43,26,18,.25))}
@media (prefers-reduced-motion:reduce){.perrito{display:none}}
"""


# --- formatting ---------------------------------------------------------------------------

def _cdn(url: str, ancho: int) -> str:
    """Ask Shopify's CDN for a smaller copy: it scales proportionally, never crops."""
    if not url.startswith("https://cdn.shopify.com/") or "width=" in url:
        return url
    return f"{url}{'&' if '?' in url else '?'}width={ancho}"


def imagen(url: str, alt: str, clase: str = "", ancho: int = 240) -> str:
    """A product image shown whole (scaled to fit its box, never cropped or stretched).

    Only https links are shown; anything else in the sheet becomes the "sin imagen" box.
    The image stays on the channel's CDN: nothing is copied or changed.
    """
    url = (url or "").strip()
    cls = f"ph {clase}".strip()
    if not url.startswith("https://"):
        return f'<div class="{cls}">sin imagen</div>'
    return (f'<div class="{cls}"><img src="{escape(_cdn(url, ancho))}" alt="{escape(alt)}" '
            'loading="lazy" referrerpolicy="no-referrer"></div>')


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


# The puppy: now and then, on Inicio, a dog pillow appears next to "Hola, Lore"; the puppy walks
# out from behind the menu, turns round on the pillow twice, lies down facing forward and stays.
# The animation lives in static/perrito.js and, like the image, only loads on the visits when it
# plays. Decoration only: it never blocks a click, is hidden from screen readers and skips people
# who turn motion off. Add ?perrito=1 to Inicio to see it.
PERRITO_CADA_MIN = 20     # at most once per this many minutes per browser
PERRITO_PROBABILIDAD = 0.35  # chance on a visit once that wait has passed (the first visit always plays)
PERRITO_JS = (
    "(function(){var W=window,D=document;"
    "if(!W.matchMedia||!D.body.animate)return;"
    "if(W.matchMedia('(prefers-reduced-motion: reduce)').matches)return;if(!/^\\/(inicio)?$/.test(location.pathname))return;"
    "var forzar=/[?&]perrito=1/.test(location.search),ahora=Date.now(),ultimo=0;"
    "try{ultimo=+localStorage.getItem('lula-perrito')||0}catch(e){}"
    "if(!forzar){if(D.documentElement.classList.contains('entrada'))return;"
    f"if(ultimo&&(ahora-ultimo<{PERRITO_CADA_MIN}*60000||Math.random()>{PERRITO_PROBABILIDAD}))return;}}"
    "try{localStorage.setItem('lula-perrito',String(ahora))}catch(e){}"
    "function go(){if(D.hidden)return;var s=D.createElement('script');s.src='/perrito.js';s.async=true;"
    "D.body.appendChild(s)}"
    "function listo(){setTimeout(go,forzar?600:2500)}"
    "if(D.readyState==='complete')listo();else W.addEventListener('load',listo);})();"
)


# A screen's heading: an optional kicker line, the <h1>, and the line under it.
_CABECERA = re.compile(r"""^((?:<p class=["']sub["']>.*?</p>)?<h1>.*?</h1>"""
                       r"""(?:<p class=["'](?:sub|meta)["']>.*?</p>)?)""", re.S)


def _con_arte(body: str, activo: str) -> str:
    """Put the screen's art detail beside its heading, without touching the data below."""
    deco = arte.detalle(activo)
    m = _CABECERA.match(body)
    if not deco or not m:
        return body
    return (f'<header class="cab"><div class="cab-t">{m.group(1)}</div>{deco}</header>'
            + body[m.end():])


def page(titulo: str, activo: str, body: str, banner: str = "", decorar: bool = True) -> str:
    grupos = []
    aqui = ""
    for grupo, items in NAV_GRUPOS:
        links = []
        for h, t, ico in items:
            on = h == activo
            if on:
                aqui = t
            cur = ' class="on" aria-current="page"' if on else ""
            links.append(f'<a href="{h}"{cur}>{icono(ico)}<span>{escape(t)}</span></a>')
        grupos.append(f'<div class="grp">{escape(grupo)}</div>{"".join(links)}')
    ban = f'<div class="banner">{escape(banner)}</div>' if banner else ""
    marca = ('<a class="brand" href="/inicio"><span class="mark">LM</span>'
             '<span class="name">Lula Macaroni<small>Oficina</small></span></a>')
    return (
        "<!doctype html><html lang='es-MX'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex'>"
        "<link rel='preconnect' href='https://fonts.googleapis.com'>"
        "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
        "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=DM+Sans:"
        "ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap'>"
        f"<title>{escape(titulo)} · Lula Macaroni</title><style>{CSS}</style>"
        "<script>try{if(sessionStorage.getItem('lula-entrada')){sessionStorage.removeItem('lula-entrada');"
        "document.documentElement.classList.add('entrada')}}catch(e){}</script></head>"
        "<body><div class='layout'>"
        "<input type='checkbox' id='menu' aria-label='Abrir menú'>"
        f"<header class='top'><label for='menu' class='burger' title='Menú'>{icono('menu')}</label>"
        f"{marca}<span class='here'>{escape(aqui)}</span></header>"
        f"<aside class='side'><label for='menu' class='close' title='Cerrar menú'>{icono('cerrar')}</label>"
        f"{marca}<nav aria-label='Menú principal'>{''.join(grupos)}</nav>"
        "<div class='foot'>Solo lectura · lo que se publica o gasta pasa por Aprobar.</div></aside>"
        "<label for='menu' class='veil' aria-hidden='true'></label>"
        f"<div class='content'><main style='--motivo:url({arte.motivo(activo)})'>{ban}"
        f"{_con_arte(body, activo) if decorar else body}{arte.sellos()}</main></div>"
        f"</div><script>{PERRITO_JS}</script></body></html>"
    )


# --- Portada (landing page) ------------------------------------------------------------------

PORTADA_CSS = """
:root{--paper:#F4EBD9;--ink:#2B1A12;--muted:#6A5644;--red:#9C0F0C}
@media (prefers-color-scheme:dark){:root{--paper:#16120D;--ink:#F3EBDD;--muted:#BDAE98;--red:#EE7A6A}}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--paper);color:var(--ink);
font:15px/1.5 "DM Sans",system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
.portada{min-height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;
gap:22px;padding:24px 16px 32px;text-align:center}
.portada .banner{background:#F7E5C4;color:#6E4710;border-radius:10px;padding:8px 14px;font-size:.85rem}
.portada figure{margin:0;display:flex;justify-content:center;width:100%}
/* the art is shown whole: never cropped, never stretched */
.portada img{display:block;width:auto;height:auto;max-width:min(100%,560px);max-height:72vh;
object-fit:contain;border-radius:6px;box-shadow:0 10px 40px rgba(60,30,10,.18)}
.portada .marca{font:700 1.35rem/1.1 "DM Sans",system-ui,sans-serif;letter-spacing:-.01em;margin:0}
.portada .marca small{display:block;font:500 .78rem/1.4 "DM Sans",system-ui,sans-serif;color:var(--muted);margin-top:4px}
.portada .entrar{display:inline-flex;align-items:center;gap:10px;background:var(--red);color:#fff;
padding:13px 26px;border-radius:999px;font-weight:600;font-size:1rem;text-decoration:none;
box-shadow:0 4px 14px rgba(158,27,34,.28);min-height:48px}
.portada .entrar:hover{filter:brightness(1.08)}
.portada .entrar:focus-visible{outline:3px solid var(--ink);outline-offset:3px}
@media (prefers-color-scheme:dark){.portada .entrar{color:#1C1C1E}}
/* the welcome page fades out on its own, then Inicio fades in */
.portada{transition:opacity .9s ease}
body.salir .portada{opacity:0}
.portada img{animation:aparece .8s ease both}
@keyframes aparece{from{opacity:0;transform:scale(.985)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.portada,.portada img{transition:none;animation:none}}
"""

# Seconds the welcome art stays before fading into Inicio; a tap or key skips it.
PORTADA_ESPERA_MS = 2600
PORTADA_FUNDIDO_MS = 900


def portada(con_imagen: bool, banner: str = "") -> str:
    """Welcome page shown on entering the app; one button into Inicio."""
    ban = f'<div class="banner">{escape(banner)}</div>' if banner else ""
    img = ('<figure><img src="/portada.png" alt="Oh, the places you\'ll go!" '
           'width="1070" height="1470"></figure>') if con_imagen else ""
    return (
        "<!doctype html><html lang='es-MX'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex'>"
        "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=DM+Sans:"
        "opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=swap'>"
        f"<title>Bienvenida · Lula Macaroni</title><style>{PORTADA_CSS}</style></head>"
        f"<body><main class='portada'>{ban}{img}"
        "<p class='marca'>Lula Macaroni<small>Oficina del estudio</small></p>"
        "<a class='entrar' href='/inicio'>Entrar →</a></main>"
        "<script>(function(){var ido=false;function ir(){if(ido)return;ido=true;"
        "try{sessionStorage.setItem('lula-entrada','1')}catch(e){}"
        "var quieto=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;"
        "document.body.classList.add('salir');"
        f"setTimeout(function(){{location.replace('/inicio')}},quieto?0:{PORTADA_FUNDIDO_MS});}}"
        f"setTimeout(ir,{PORTADA_ESPERA_MS});"
        "document.addEventListener('click',function(e){e.preventDefault();ir()});"
        "document.addEventListener('keydown',ir);})();</script>"
        "</body></html>"
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
        f'<a class="chip{" on" if k == per.clave else ""}" href="/inicio?p={k}">{t}</a>'
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
        f'<p class="sub">Resumen del día · {fecha(now, hora=False)}</p>'
        f"<h1>Hola, {escape(nombre)}</h1>"
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
    return page("Inicio", "/inicio", body, banner)


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
    foto = next(((r.get("imagen_url"), r.get("producto") or "") for r in p.lineas
                 if r.get("imagen_url")), ("", ""))
    return (
        f'<div class="card{alert}"><div class="row"><div class="pr">'
        f'{imagen(str(foto[0]), str(foto[1]), "sm", 160)}<div>'
        f'<div class="t">#{escape(p.numero)} · '
        f"{escape(CANAL.get(p.canal, p.canal))}</div>"
        f'<div class="m">{escape(prods)}</div>'
        f'<div class="m">{fecha(p.fecha)} · {escape(ESTADO_PEDIDO.get(p.estado, p.estado))} · '
        f"imprime: {escape(rutas)}{track}</div>{extra}</div></div>"
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
    piezas = []
    for f in sel:
        p = f.producto
        avisos = _ficha_avisos(f)
        link = f"/catalogo/producto?c={escape(p.canal)}&amp;id={escape(p.id_producto)}"
        obra = (f" · obra {escape(f.obras[0].get('obra_id', ''))}" if f.obras
                else " · sin ligar a una obra")
        piezas.append(
            f'<article class="pieza{" alert" if avisos else ""}">'
            f'<a class="foto" href="{link}" aria-hidden="true" tabindex="-1">'
            f'{imagen(p.imagen, p.titulo, "xl", 800)}</a><div class="info">'
            f'<div class="row"><div class="t"><a href="{link}">{escape(p.titulo)}</a></div>'
            f'<span class="badge {badge.get(p.estado, "gray")}">'
            f"{escape(ESTADO_LISTADO.get(p.estado, p.estado))}</span></div>"
            f'<div class="m"><span class="tag">{escape(LINEA.get(p.linea, p.linea))}</span>'
            f"{escape(CANAL.get(p.canal, p.canal))} · {p.variantes} variante(s) · {_precio(p)}</div>"
            f'<div class="m">Imprime: {escape(_rutas(p.rutas))} · coste en {f.con_costo} de '
            f"{p.variantes} · archivo sin revisar en {f.archivos_sin}{obra}</div>"
            + "".join(f'<div class="m w">{escape(a)}</div>' for a in avisos)
            + "</div></article>")
    rows = [f'<div class="galeria">{"".join(piezas)}</div>'] if piezas else []
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


def _parrafos(texto: str) -> str:
    partes = [t.strip() for t in texto.splitlines() if t.strip()]
    return "".join(f"<p>{escape(t)}</p>" for t in partes)


def _contenido_producto(p, actualizado: datetime | None) -> str:
    """Images, description, type and tags exactly as the store has them (read-only)."""
    origen = (f'<p class="meta">Fuente: Shopify (imágenes y texto del producto) · '
              f"actualizado {fecha(actualizado)}. Las imágenes se ven completas, sin recortar; "
              "se cambian en Shopify.</p>")
    if not (p.imagenes or p.descripcion or p.etiquetas or p.tipo):
        return ('<h2>En la tienda</h2><div class="card info"><div class="m">Aún no hay imagen ni '
                "descripción en la hoja: llegan con la próxima sincronización de Shopify."
                "</div></div>")
    desc = (f'<div class="desc">{_parrafos(p.descripcion)}</div>' if p.descripcion
            else '<p class="m">Sin descripción en Shopify.</p>')
    return (
        f'<h2>En la tienda</h2><div class="card">'
        f'{desc}<p class="m">Tipo: {escape(p.tipo or "—")} · Etiquetas: '
        f'{escape(p.etiquetas or "sin etiquetas en Shopify")}</p>{origen}</div>')


def _portada_producto(p) -> str:
    """The product's main image, large and whole, with the rest of its images below."""
    if not p.imagenes:
        return ""
    galeria = "".join(
        f'<a href="{escape(u)}" target="_blank" rel="noopener">'
        f'{imagen(u, f"{p.titulo}, imagen {i}", "md", 320)}</a>'
        for i, u in enumerate(p.imagenes, 1)) if len(p.imagenes) > 1 else ""
    return (f'<section class="cubierta">{imagen(p.imagen, p.titulo, "cover", 1600)}'
            + (f'<div class="gal">{galeria}</div>' if galeria else "") + "</section>")


def producto(f, fuentes, now: datetime, banner: str = "") -> str:
    p = f.producto
    shop = fuentes["shopify"]
    rows = []
    for v in f.variantes:
        real = (f' · real {usd(v.margen_real)} en {v.ventas} venta(s)'
                if v.margen_real is not None else "")
        cls, txt = ARCHIVO[v.archivo.estado]
        ruta_cls = "warn" if v.ruta in ("manual", "desconocida", "varias") else "gray"
        foto = str(v.listado.get("imagen_url") or "")
        foto = (imagen(foto, f"{p.titulo} / {v.etiqueta}", "sm", 160)
                if foto and foto != p.imagen else "")
        rows.append(
            f'<div class="card"><div class="row"><div class="pr">{foto}<div>'
            f'<div class="t">{escape(v.etiqueta)}</div>'
            f'<div class="m">{escape(v.sku) or "sin SKU"} · imprime '
            f'<span class="badge {ruta_cls}">{escape(RUTA_CORTA.get(v.ruta, v.ruta) or "—")}</span></div>'
            f'<div class="m">Coste {_celda(v.costo)} · Margen {_celda(v.margen)}{real}</div>'
            f'<div class="m">Archivo <span class="badge {cls}">{txt}</span> '
            f"{escape(v.archivo.motivo)}</div></div></div>"
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
    contenido = _contenido_producto(p, shop.actualizado)
    body = (
        f'<p class="sub"><a href="/catalogo">← Catálogo</a></p><h1>{escape(p.titulo)}</h1>'
        f'<p class="sub">{escape(LINEA.get(p.linea, p.linea))} · {escape(CANAL.get(p.canal, p.canal))}'
        f" · {escape(ESTADO_LISTADO.get(p.estado, p.estado))}{tienda}. "
        f"Shopify actualizado {fecha(shop.actualizado)} ({hace(shop.actualizado, now)}).</p>"
        f"{_portada_producto(p)}{avisos}{contenido}<h2>Obra</h2>{obras}<h2>Variantes ({len(f.variantes)})</h2>"
        f"{''.join(rows)}"
        '<p class="legend">Precio e imprenta: Shopify (ubicación de inventario de cada variante). '
        "Coste: cotización en Variantes.costo_usd (impresión + envío a EUA), estimado. Margen "
        "estimado = precio − comisión estimada 2.9% + 30¢ − coste; sin descuentos, impuestos ni "
        "anuncios. “real” = promedio de ventas con costos reales de Prodigi. Archivo: "
        "resolución y proporción del archivo de impresión para el tamaño; nunca se recorta ni "
        "se estira. “—” = falta el dato.</p>"
    )
    return page(p.titulo, "/catalogo", body, banner, decorar=False)


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
