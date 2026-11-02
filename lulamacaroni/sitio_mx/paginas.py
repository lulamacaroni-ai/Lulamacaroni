"""HTML for the Mexico catalog site (Mexican Spanish, no JavaScript, no external requests).

Photos are shown whole: ``object-fit: contain`` with the photo's own width and height, so
the browser never crops or stretches them.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from urllib.parse import quote

from . import aviso
from .datos import Ajustes, Pieza

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")

CSS = """
:root{--fondo:#fbf8f3;--tinta:#2b2522;--suave:#6f655e;--linea:#e6ded3;--acento:#b5523b;
--marco:#fff;--wa:#1f7a4d}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--fondo);color:var(--tinta);
font:17px/1.55 Georgia,"Iowan Old Style","Palatino Linotype",serif}
a{color:var(--acento)}
.envoltura{max-width:1080px;margin:0 auto;padding:0 16px}
header.sitio{border-bottom:1px solid var(--linea);background:var(--fondo)}
header.sitio .envoltura{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 24px;
padding-top:18px;padding-bottom:14px}
.marca{font-size:26px;letter-spacing:.02em;color:var(--tinta);text-decoration:none}
.marca small{display:block;font:13px/1.3 system-ui,sans-serif;color:var(--suave);
letter-spacing:.08em;text-transform:uppercase}
nav.menu{display:flex;gap:18px;font:15px system-ui,sans-serif;margin-left:auto}
nav.menu a{color:var(--tinta);text-decoration:none}
nav.menu a[aria-current]{border-bottom:2px solid var(--acento)}
main{padding:28px 0 48px}
h1{font-weight:normal;font-size:32px;line-height:1.2;margin:0 0 10px}
h2{font-weight:normal;font-size:22px;margin:28px 0 8px}
.intro{color:var(--suave);max-width:640px;margin:0 0 22px}
.filtros{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px;font:14px system-ui,sans-serif}
.filtros a{padding:6px 12px;border:1px solid var(--linea);border-radius:999px;
text-decoration:none;color:var(--tinta);background:#fff}
.filtros a[aria-current]{background:var(--tinta);color:#fff;border-color:var(--tinta)}
.rejilla{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:28px 22px}
.tarjeta{text-decoration:none;color:inherit;display:block}
.cuadro{background:var(--marco);border:1px solid var(--linea);aspect-ratio:4/5;
display:flex;align-items:center;justify-content:center;padding:14px}
.cuadro img{max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain;display:block}
.tarjeta h3{font-weight:normal;font-size:18px;margin:10px 0 2px}
.dato{font:14px/1.45 system-ui,sans-serif;color:var(--suave);margin:0}
.precio{font:600 16px system-ui,sans-serif;margin:4px 0 0;color:var(--tinta)}
.precio small{font-weight:normal;color:var(--suave)}
.ficha{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:36px;align-items:start}
.ficha .cuadro{aspect-ratio:auto;padding:18px}
.ficha .cuadro img{max-height:78vh}
.ficha dl{font:15px/1.5 system-ui,sans-serif;display:grid;grid-template-columns:auto 1fr;
gap:6px 16px;margin:16px 0}
.ficha dt{color:var(--suave)}
.ficha dd{margin:0}
.ficha .precio{font-size:24px;margin:14px 0 2px}
.botones{display:flex;flex-direction:column;gap:10px;margin:20px 0 8px;max-width:360px}
.boton{display:block;text-align:center;padding:13px 16px;border-radius:6px;
font:600 16px system-ui,sans-serif;text-decoration:none}
.boton.wa{background:var(--wa);color:#fff}
.boton.correo{border:1px solid var(--tinta);color:var(--tinta)}
.nota{font:13px/1.45 system-ui,sans-serif;color:var(--suave)}
.texto{max-width:700px}
.texto li{margin:4px 0}
.fecha{font:14px system-ui,sans-serif;color:var(--suave)}
.vacio{padding:40px 0;color:var(--suave)}
footer{border-top:1px solid var(--linea);padding:22px 0 36px;font:13px/1.6 system-ui,sans-serif;
color:var(--suave)}
footer a{color:var(--suave)}
@media (max-width:720px){
 .ficha{grid-template-columns:1fr;gap:18px}
 h1{font-size:26px}
 nav.menu{margin-left:0;width:100%}
 .rejilla{grid-template-columns:repeat(2,minmax(0,1fr));gap:20px 12px}
 .cuadro{padding:8px}
 .tarjeta h3{font-size:16px}
}
"""


def fecha_larga(dt: datetime) -> str:
    return f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}"


def pesos(v: float) -> str:
    entero = round(v)
    return f"${entero:,} MXN" if abs(v - entero) < 0.005 else f"${v:,.2f} MXN"


def _precio(p: Pieza) -> str:
    if p.precio_mxn is None:
        return '<p class="precio">Precio a consultar</p>'
    return f'<p class="precio">{pesos(p.precio_mxn)} <small>IVA incluido</small></p>'


def _alt(p: Pieza) -> str:
    partes = [f"«{p.titulo}»", "obra original de Lula Macaroni"]
    if p.tecnica:
        partes.append(p.tecnica)
    return ", ".join(partes)


def _img(p: Pieza, raiz: str, carga: str = "lazy") -> str:
    return (f'<img src="{raiz}img/{escape(p.slug)}{p.foto.extension}" '
            f'width="{p.foto.ancho_px}" height="{p.foto.alto_px}" '
            f'alt="{escape(_alt(p))}" loading="{carga}" decoding="async">')


def _mensaje(p: Pieza) -> str:
    return (f"Hola, me interesa la obra «{p.titulo}» (ref. {p.obra_id}) "
            "que vi en el catálogo de Lula Macaroni. ¿Sigue disponible?")


def enlace_whatsapp(a: Ajustes, texto: str) -> str:
    return f"https://wa.me/{a.whatsapp}?text={quote(texto)}"


def enlace_correo(a: Ajustes, asunto: str, texto: str) -> str:
    return f"mailto:{a.correo}?subject={quote(asunto)}&body={quote(texto)}"


def pagina(titulo: str, cuerpo: str, a: Ajustes, ahora: datetime, *, raiz: str,
           activo: str = "", descripcion: str = "", ruta: str = "",
           imagen: str = "") -> str:
    def nav(href: str, nombre: str, clave: str) -> str:
        cur = ' aria-current="page"' if clave == activo else ""
        return f'<a href="{raiz}{href}"{cur}>{nombre}</a>'

    desc = escape(descripcion or "Obra original de Lula Macaroni a la venta en México. "
                                 "Precios en pesos, IVA incluido.")
    canon = f"{a.url}/{ruta}"
    og_img = f'<meta property="og:image" content="{escape(a.url)}/{escape(imagen)}">' if imagen else ""
    insta = (f' · <a href="https://www.instagram.com/{escape(a.instagram)}/">Instagram '
             f'@{escape(a.instagram)}</a>') if a.instagram else ""
    return (
        '<!doctype html><html lang="es-MX"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(titulo)}</title>"
        f'<meta name="description" content="{desc}">'
        f'<link rel="canonical" href="{escape(canon)}">'
        f'<meta property="og:title" content="{escape(titulo)}">'
        f'<meta property="og:description" content="{desc}">'
        '<meta property="og:locale" content="es_MX">'
        f'<meta property="og:url" content="{escape(canon)}">{og_img}'
        f'<link rel="stylesheet" href="{raiz}estilos.css"></head><body>'
        '<header class="sitio"><div class="envoltura">'
        f'<a class="marca" href="{raiz}index.html">Lula Macaroni<small>Obra original · México</small></a>'
        '<nav class="menu">'
        + nav("index.html", "Obras", "obras")
        + nav("como-comprar.html", "Cómo comprar", "comprar")
        + "</nav></div></header>"
        f'<main><div class="envoltura">{cuerpo}</div></main>'
        '<footer><div class="envoltura">'
        "Precios en pesos mexicanos (MXN), IVA incluido. "
        f"Catálogo actualizado el {fecha_larga(ahora)}.<br>"
        f'<a href="{raiz}aviso-de-privacidad.html">Aviso de privacidad</a>{insta}'
        "</div></footer></body></html>"
    )


def _tarjeta(p: Pieza, raiz: str) -> str:
    datos = " · ".join(x for x in (p.tecnica, p.medidas) if x)
    return (f'<a class="tarjeta" href="{raiz}obra/{escape(p.slug)}.html">'
            f'<div class="cuadro">{_img(p, raiz)}</div>'
            f"<h3>{escape(p.titulo)}</h3>"
            + (f'<p class="dato">{escape(datos)}</p>' if datos else "")
            + _precio(p) + "</a>")


def colecciones(piezas: list[Pieza]) -> list[tuple[str, str, int]]:
    """(slug, name, count) of the collections that have pieces, in order."""
    vistas: dict[str, tuple[str, int]] = {}
    for p in piezas:
        if p.coleccion:
            nombre, n = vistas.get(p.coleccion_slug, (p.coleccion, 0))
            vistas[p.coleccion_slug] = (nombre, n + 1)
    return [(s, n, c) for s, (n, c) in sorted(vistas.items(), key=lambda x: x[1][0].lower())]


def _filtros(piezas: list[Pieza], raiz: str, actual: str = "") -> str:
    cols = colecciones(piezas)
    if len(cols) < 2:
        return ""
    cur = ' aria-current="page"'
    out = [f'<a href="{raiz}index.html"{"" if actual else cur}>Todas ({len(piezas)})</a>']
    for s, nombre, n in cols:
        out.append(f'<a href="{raiz}coleccion/{escape(s)}.html"'
                   f'{cur if s == actual else ""}>{escape(nombre)} ({n})</a>')
    return '<nav class="filtros" aria-label="Colecciones">' + "".join(out) + "</nav>"


def inicio(piezas: list[Pieza], a: Ajustes, ahora: datetime) -> str:
    if piezas:
        rejilla = ('<div class="rejilla">' + "".join(_tarjeta(p, "") for p in piezas)
                   + "</div>")
    else:
        rejilla = ('<p class="vacio">Estamos preparando el catálogo. Muy pronto podrás ver '
                   "aquí las obras disponibles.</p>")
    cuerpo = ("<h1>Obra original disponible</h1>"
              '<p class="intro">Pinturas originales de Lula Macaroni, piezas únicas a la venta '
              "en México. Para comprar o preguntar por una obra, escríbenos: te respondemos "
              "personalmente.</p>" + _filtros(piezas, "") + rejilla)
    return pagina("Lula Macaroni · Obra original en México", cuerpo, a, ahora, raiz="",
                  activo="obras", ruta="")


def coleccion(slug: str, piezas: list[Pieza], a: Ajustes, ahora: datetime) -> str:
    propias = [p for p in piezas if p.coleccion_slug == slug]
    nombre = propias[0].coleccion
    cuerpo = (f"<h1>{escape(nombre)}</h1>" + _filtros(piezas, "../", slug)
              + '<div class="rejilla">' + "".join(_tarjeta(p, "../") for p in propias)
              + "</div>")
    return pagina(f"{nombre} · Lula Macaroni", cuerpo, a, ahora, raiz="../", activo="obras",
                  ruta=f"coleccion/{slug}.html",
                  descripcion=f"Colección {nombre}: obra original de Lula Macaroni.")


def obra(p: Pieza, a: Ajustes, ahora: datetime) -> str:
    filas = [("Técnica", p.tecnica), ("Medidas", p.medidas), ("Año", p.anio),
             ("Colección", p.coleccion), ("Referencia", p.obra_id)]
    dl = "".join(f"<dt>{t}</dt><dd>{escape(v)}</dd>" for t, v in filas if v)
    texto = _mensaje(p)
    botones = []
    if a.whatsapp:
        botones.append(f'<a class="boton wa" href="{escape(enlace_whatsapp(a, texto))}">'
                       "Preguntar por WhatsApp</a>")
    if a.correo:
        botones.append(f'<a class="boton correo" href="'
                       f'{escape(enlace_correo(a, f"Obra: {p.titulo}", texto))}">'
                       "Escribir por correo</a>")
    actualizado = ""
    if p.precio_mxn is not None and p.precio_actualizado:
        try:
            actualizado = (f'<p class="nota">Precio actualizado el '
                           f"{fecha_larga(datetime.fromisoformat(p.precio_actualizado[:10]))}.</p>")
        except ValueError:
            pass
    cuerpo = (
        '<article class="ficha">'
        f'<div class="cuadro">{_img(p, "../", "eager")}</div>'
        f"<div><h1>{escape(p.titulo)}</h1><p class=\"dato\">Obra original, pieza única</p>"
        + _precio(p) + actualizado
        + f"<dl>{dl}</dl>"
        + '<div class="botones">' + "".join(botones) + "</div>"
        + '<p class="nota">Te confirmamos disponibilidad, forma de pago y entrega. '
          '<a href="../como-comprar.html">Cómo comprar</a>.</p>'
        + "</div></article>")
    desc = f"«{p.titulo}», obra original de Lula Macaroni"
    if p.medidas:
        desc += f", {p.medidas}"
    if p.precio_mxn is not None:
        desc += f". {pesos(p.precio_mxn)}, IVA incluido"
    return pagina(f"{p.titulo} · Lula Macaroni", cuerpo, a, ahora, raiz="../",
                  activo="obras", ruta=f"obra/{p.slug}.html", descripcion=desc + ".",
                  imagen=f"img/{p.slug}{p.foto.extension}")


def como_comprar(a: Ajustes, ahora: datetime) -> str:
    contacto = []
    if a.whatsapp:
        contacto.append(f'<a href="{escape(enlace_whatsapp(a, "Hola, quiero información sobre una obra del catálogo de Lula Macaroni."))}">'
                        f"WhatsApp +{escape(a.whatsapp)}</a>")
    if a.correo:
        contacto.append(f'<a href="mailto:{escape(a.correo)}">{escape(a.correo)}</a>')
    entrega = (f"Puedes recoger la obra en {escape(a.ciudad)} o pedirnos un envío dentro de "
               "México; te cotizamos el envío antes de pagar." if a.ciudad else
               "Coordinamos contigo la entrega o el envío dentro de México; te cotizamos el "
               "envío antes de pagar.")
    cuerpo = (
        '<div class="texto"><h1>Cómo comprar</h1>'
        "<p>Cada obra es una pieza original y única. Por ahora no hay carrito: la compra se "
        "hace directamente con nosotros.</p><ol>"
        "<li><strong>Escríbenos</strong> desde la ficha de la obra (WhatsApp o correo). El "
        "mensaje ya lleva el nombre y la referencia de la obra.</li>"
        "<li><strong>Te confirmamos</strong> que está disponible, el precio y los detalles de "
        "la pieza.</li>"
        "<li><strong>La apartamos</strong> para ti mientras acordamos el pago.</li>"
        "<li><strong>Pago:</strong> por transferencia bancaria o como lo acordemos. Los "
        "precios están en pesos mexicanos e incluyen IVA.</li>"
        f"<li><strong>Entrega:</strong> {entrega}</li>"
        "<li><strong>Factura:</strong> si necesitas CFDI, pídelo al comprar y envíanos tus "
        "datos fiscales.</li></ol>"
        "<h2>Contacto</h2><p>" + " · ".join(contacto) + "</p>"
        "<p class=\"nota\">Solo usamos tus datos para atender tu compra. Consulta el "
        '<a href="aviso-de-privacidad.html">aviso de privacidad</a>.</p></div>')
    return pagina("Cómo comprar · Lula Macaroni", cuerpo, a, ahora, raiz="",
                  activo="comprar", ruta="como-comprar.html",
                  descripcion="Cómo comprar una obra original de Lula Macaroni en México.")


def aviso_privacidad(a: Ajustes, ahora: datetime) -> str:
    cuerpo = '<div class="texto"><h1>Aviso de privacidad</h1>' + aviso.html(a) + "</div>"
    return pagina("Aviso de privacidad · Lula Macaroni", cuerpo, a, ahora, raiz="",
                  ruta="aviso-de-privacidad.html",
                  descripcion="Aviso de privacidad integral de Lula Macaroni.")


def no_encontrada(a: Ajustes, ahora: datetime) -> str:
    cuerpo = ('<h1>Esta página no existe</h1><p class="intro">Puede que la obra ya no esté '
              'disponible. <a href="/index.html">Ver las obras disponibles</a>.</p>')
    return pagina("Página no encontrada · Lula Macaroni", cuerpo, a, ahora, raiz="/",
                  ruta="404.html")
