"""The store's HTML, in English for US buyers. No JavaScript is needed to buy.

Photos are always shown whole (``object-fit: contain`` inside a neutral mat), so the page
never crops or stretches the art. Colours and type follow the back office palette.
"""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from urllib.parse import urlparse

from .ajustes import Ajustes
from .catalogo import Producto

POLITICAS = {"shipping": "Shipping", "returns": "Returns and refunds",
             "privacy": "Privacy policy", "terms": "Terms of service"}
CARPETA_POLITICAS = Path(__file__).with_name("politicas")

CSS = """
:root{--fondo:#f6f1e7;--papel:#fffdf8;--tinta:#2b2522;--suave:#6f655e;--linea:#e3d9c8;
--cereza:#9C0F0C;--olivo:#364422;--ocre:#CC842E;--enlace:#8A4F12}
@media (prefers-color-scheme:dark){:root{--fondo:#1d1b17;--papel:#26231e;--tinta:#ece5d8;
--suave:#b0a693;--linea:#3d382f;--cereza:#e0625c;--enlace:#e0a868}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--fondo);color:var(--tinta);
font:16px/1.6 "DM Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--enlace)}img{display:block}
.env{max-width:1120px;margin:0 auto;padding:0 16px}
header.sitio{border-bottom:1px solid var(--linea)}
header.sitio .env{display:flex;align-items:center;gap:16px;padding-top:16px;padding-bottom:14px}
.marca{font-size:24px;font-weight:600;color:var(--cereza);text-decoration:none;letter-spacing:.01em}
nav.menu{margin-left:auto;display:flex;gap:18px;font-size:15px}
nav.menu a{color:var(--tinta);text-decoration:none}
nav.menu a.carrito{font-weight:600}
main{padding:28px 0 56px}
h1{font-size:30px;line-height:1.2;margin:0 0 10px;font-weight:600}
h2{font-size:20px;margin:28px 0 8px}
.intro{color:var(--suave);max-width:640px;margin:0 0 26px}
.rejilla{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:30px 24px}
.tarjeta{text-decoration:none;color:inherit}
.cuadro{background:var(--papel);border:1px solid var(--linea);aspect-ratio:1/1;display:flex;
align-items:center;justify-content:center;padding:16px}
.cuadro img{max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain}
.tarjeta h3{font-size:17px;font-weight:600;margin:10px 0 0}
.precio{color:var(--suave);margin:2px 0 0;font-size:15px}
.ficha{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:40px;align-items:start}
.ficha .cuadro{aspect-ratio:auto;min-height:320px}
.ficha .cuadro img{max-height:78vh}
.miniaturas{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.miniaturas a{display:block;width:84px;height:84px;background:var(--papel);border:1px solid var(--linea);
padding:6px}
.miniaturas img{width:100%;height:100%;object-fit:contain}
label{display:block;font-weight:600;margin:18px 0 6px}
select,input[type=number]{font:inherit;padding:10px 12px;border:1px solid var(--linea);border-radius:8px;
background:var(--papel);color:var(--tinta);width:100%}
input[type=number]{width:96px}
button,.boton{font:600 16px "DM Sans",system-ui,sans-serif;background:var(--cereza);color:#fff;border:0;
border-radius:999px;padding:13px 26px;margin-top:20px;cursor:pointer;text-decoration:none;
display:inline-block}
button.quitar{background:none;color:var(--enlace);padding:0;margin:0;font-weight:400;font-size:14px;
text-decoration:underline}
.nota{color:var(--suave);font-size:14px}
.aviso{border:1px solid var(--ocre);background:var(--papel);padding:12px 14px;border-radius:8px}
.descripcion{white-space:pre-line}
table.carrito{width:100%;border-collapse:collapse}
table.carrito td{border-bottom:1px solid var(--linea);padding:14px 8px;vertical-align:middle}
table.carrito img{width:72px;height:72px;object-fit:contain;background:var(--papel)}
.total{font-size:18px;font-weight:600;text-align:right}
footer.sitio{border-top:1px solid var(--linea);color:var(--suave);font-size:14px;padding:22px 0 36px}
footer.sitio nav{display:flex;flex-wrap:wrap;gap:8px 18px;margin-bottom:8px}
footer.sitio a{color:var(--suave)}
@media (max-width:760px){.ficha{grid-template-columns:1fr;gap:22px}h1{font-size:25px}
nav.menu{gap:12px}}
"""


def usd(v: float) -> str:
    return f"${v:,.0f}" if float(v).is_integer() else f"${v:,.2f}"


def _img(url: str, alt: str, carga: str = "lazy") -> str:
    if not url:
        return f'<span class="nota">{escape(alt)}</span>'
    return f'<img src="{escape(url)}" alt="{escape(alt)}" loading="{carga}" decoding="async">'


def pagina(a: Ajustes, titulo: str, cuerpo: str, *, en_carrito: int = 0, descripcion: str = "",
           ruta: str = "/", extra_head: str = "", aviso: str = "") -> str:
    n = f" ({en_carrito})" if en_carrito else ""
    canonica = f"{a.url}{ruta}"
    desc = escape(descripcion or "Fine art prints by Lorena Vazquez, made to order and shipped in the US.")
    aviso_html = f'<p class="aviso">{escape(aviso)}</p>' if aviso else ""
    enlaces = "".join(f'<a href="/policies/{k}">{escape(v)}</a>' for k, v in POLITICAS.items())
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(titulo)}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{escape(canonica)}">
<meta property="og:title" content="{escape(titulo)}"><meta property="og:description" content="{desc}">
<meta property="og:url" content="{escape(canonica)}"><meta property="og:type" content="website">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600&display=swap">
<style>{CSS}</style>{extra_head}</head>
<body><header class="sitio"><div class="env"><a class="marca" href="/">{escape(a.marca)}</a>
<nav class="menu"><a href="/">Shop</a><a href="/policies/shipping">Shipping</a>
<a class="carrito" href="/cart">Cart{n}</a></nav></div></header>
<main><div class="env">{aviso_html}{cuerpo}</div></main>
<footer class="sitio"><div class="env"><nav>{enlaces}<a href="mailto:{escape(a.soporte)}">Contact</a></nav>
<p>© Lorena Vazquez. Prints made to order and shipped within the US. Secure payment by Stripe.</p></div></footer>
</body></html>"""


def _tarjeta(p: Producto) -> str:
    return (f'<a class="tarjeta" href="/products/{escape(p.slug)}"><div class="cuadro">'
            f'{_img(p.imagen, p.titulo)}</div><h3>{escape(p.titulo)}</h3>'
            f'<p class="precio">From {usd(p.desde)}</p></a>')


def inicio(a: Ajustes, productos: list[Producto], en_carrito: int = 0) -> str:
    if productos:
        cuerpo = ('<h1>Framed fine art prints</h1><p class="intro">Original paintings by Lorena '
                  'Vazquez, printed on archival paper and framed to order in the US.</p>'
                  f'<div class="rejilla">{"".join(_tarjeta(p) for p in productos)}</div>')
    else:
        cuerpo = ('<h1>New prints are on their way</h1><p class="intro">The shop is being '
                  f'restocked. Write to <a href="mailto:{escape(a.soporte)}">{escape(a.soporte)}</a> '
                  'and we\'ll let you know when it opens.</p>')
    return pagina(a, f"{a.marca} · Framed fine art prints", cuerpo, en_carrito=en_carrito)


def _jsonld(a: Ajustes, p: Producto) -> str:
    datos = {
        "@context": "https://schema.org", "@type": "Product", "name": p.titulo,
        "image": p.imagenes[:5], "description": re.sub(r"\s+", " ", p.descripcion)[:500],
        "brand": {"@type": "Brand", "name": a.marca},
        "offers": [{"@type": "Offer", "sku": o.sku, "name": o.etiqueta, "priceCurrency": "USD",
                    "price": f"{o.precio:.2f}", "availability": "https://schema.org/InStock",
                    "url": f"{a.url}/products/{p.slug}?sku={o.sku}"} for o in p.opciones],
    }
    texto = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{texto}</script>'


def producto(a: Ajustes, p: Producto, *, elegido: str = "", en_carrito: int = 0,
             foto: int = 0) -> str:
    foto = foto if 0 <= foto < len(p.imagenes) else 0
    principal = p.imagenes[foto] if p.imagenes else ""
    minis = "".join(
        f'<a href="/products/{escape(p.slug)}?foto={i}" aria-label="Photo {i + 1}">{_img(u, f"{p.titulo}, photo {i + 1}")}</a>'
        for i, u in enumerate(p.imagenes)) if len(p.imagenes) > 1 else ""
    opciones = "".join(
        f'<option value="{escape(o.sku)}"{" selected" if o.sku == elegido else ""}>'
        f'{escape(o.etiqueta)} · {usd(o.precio)}</option>' for o in p.opciones)
    cuerpo = f"""<div class="ficha"><div><div class="cuadro">{_img(principal, p.titulo, "eager")}</div>
<div class="miniaturas">{minis}</div></div>
<div><h1>{escape(p.titulo)}</h1><p class="precio">From {usd(p.desde)}</p>
<form method="post" action="/cart/add">
<label for="sku">Size and frame</label><select id="sku" name="sku">{opciones}</select>
<label for="qty">Quantity</label><input id="qty" name="qty" type="number" min="1" max="10" value="1">
<button type="submit">Add to cart</button></form>
<p class="nota">{escape(p.tipo)}: archival fine art paper, box frame with acrylic glaze, ready to hang.
Made to order in 2 to 5 business days, then shipped within the US.</p>
<h2>About this piece</h2><p class="descripcion">{escape(p.descripcion)}</p></div></div>"""
    return pagina(a, f"{p.titulo} · {a.marca}", cuerpo, en_carrito=en_carrito,
                  descripcion=p.descripcion[:155], ruta=f"/products/{p.slug}",
                  extra_head=_jsonld(a, p))


def carrito(a: Ajustes, lineas: list[dict], aviso: str = "", abierta: bool = True) -> str:
    """``lineas``: {sku, producto: Producto, opcion: Opcion, cantidad}."""
    if not lineas:
        cuerpo = '<h1>Your cart is empty</h1><p><a href="/">Browse the prints</a></p>'
        return pagina(a, f"Cart · {a.marca}", cuerpo, ruta="/cart", aviso=aviso)
    filas, subtotal = [], 0.0
    for li in lineas:
        p, o, n = li["producto"], li["opcion"], li["cantidad"]
        subtotal += o.precio * n
        filas.append(
            f'<tr><td>{_img(p.imagen, p.titulo)}</td><td><a href="/products/{escape(p.slug)}">'
            f'{escape(p.titulo)}</a><br><span class="nota">{escape(o.etiqueta)}</span></td>'
            f'<td><form method="post" action="/cart/update"><input type="hidden" name="sku" '
            f'value="{escape(o.sku)}"><input aria-label="Quantity" name="qty" type="number" '
            f'min="0" max="10" value="{n}"> '
            f'<button class="quitar" name="qty" value="0">Remove</button></form></td>'
            f'<td style="text-align:right">{usd(o.precio * n)}</td></tr>')
    envio = "Free US shipping" if a.envio_usd <= 0 else f"Shipping {usd(a.envio_usd)}"
    boton = ('<form method="post" action="/checkout"><button type="submit">Check out securely</button>'
             '</form>' if abierta else '<p class="aviso">Checkout opens soon.</p>')
    cuerpo = (f'<h1>Your cart</h1><table class="carrito">{"".join(filas)}</table>'
              f'<p class="total">Subtotal {usd(subtotal)}</p>'
              f'<p class="nota" style="text-align:right">{envio}. Sales tax, if any, is added at checkout.</p>'
              f'<div style="text-align:right">{boton}</div>')
    return pagina(a, f"Cart · {a.marca}", cuerpo, en_carrito=sum(l["cantidad"] for l in lineas),
                  ruta="/cart", aviso=aviso)


def gracias(a: Ajustes, numero: str = "") -> str:
    ref = f" <b>{escape(numero)}</b>" if numero else ""
    cuerpo = (f"<h1>Thank you!</h1><p>Your order{ref} is confirmed and a receipt is on its way to "
              "your inbox. Your print is made just for you: production takes 2 to 5 business days, "
              "then we email you the tracking number.</p><p><a href=\"/\">Back to the shop</a></p>")
    return pagina(a, f"Thank you · {a.marca}", cuerpo, ruta="/thank-you")


def no_encontrada(a: Ajustes) -> str:
    return pagina(a, f"Not found · {a.marca}",
                  '<h1>We couldn\'t find that page</h1><p><a href="/">Browse the prints</a></p>')


# --- policies: small Markdown files with {placeholders} ------------------------------------

def _md(texto: str) -> str:
    """The subset the policy files use: #/## headings, paragraphs, '- ' lists, **bold**."""
    def linea(t: str) -> str:
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape(t))

    out, lista = [], []
    def cerrar():
        if lista:
            out.append("<ul>" + "".join(f"<li>{x}</li>" for x in lista) + "</ul>")
            lista.clear()
    for bloque in texto.split("\n"):
        b = bloque.rstrip()
        if b.startswith("- "):
            lista.append(linea(b[2:]))
            continue
        cerrar()
        if b.startswith("## "):
            out.append(f"<h2>{linea(b[3:])}</h2>")
        elif b.startswith("# "):
            out.append(f"<h1>{linea(b[2:])}</h1>")
        elif b:
            out.append(f"<p>{linea(b)}</p>")
    cerrar()
    return "".join(out)


def texto_politica(a: Ajustes, clave: str) -> str:
    envio = ("Shipping is free on every order within the US." if a.envio_usd <= 0 else
             f"Shipping is a flat {usd(a.envio_usd)} per order within the US, shown at checkout.")
    valores = {"marca": a.marca, "soporte": a.soporte, "razon_social": a.texto(a.razon_social),
               "domicilio": a.texto(a.domicilio), "estado": a.texto(a.estado_constitucion),
               "envio": envio, "dominio": urlparse(a.url).netloc or a.url}
    crudo = (CARPETA_POLITICAS / f"{clave}.md").read_text(encoding="utf-8")
    return re.sub(r"\{(\w+)\}", lambda m: valores.get(m.group(1), m.group(0)), crudo)


def politica(a: Ajustes, clave: str, en_carrito: int = 0) -> str:
    return pagina(a, f"{POLITICAS[clave]} · {a.marca}", _md(texto_politica(a, clave)),
                  en_carrito=en_carrito, ruta=f"/policies/{clave}")


def sitemap(a: Ajustes, productos: list[Producto]) -> str:
    rutas = ["/", *[f"/products/{p.slug}" for p in productos], *[f"/policies/{k}" for k in POLITICAS]]
    urls = "".join(f"<url><loc>{escape(a.url + r)}</loc></url>" for r in rutas)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
