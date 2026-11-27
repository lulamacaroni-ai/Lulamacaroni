"""Tienda: the admin for our own store on lulamacaroni.com (canal ``web``).

What Lorena and Jon need to run it: whether checkout can open (keys and legal settings), the
web orders by step (waiting for her approval, at Prodigi, shipped, with a problem), and the
store's catalog by state. Read-only: approving an order or the catalog happens in Aprobar,
and putting products on sale is ``python -m lulamacaroni.tienda.publicar``.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from .. import config
from ..tienda.ajustes import Ajustes
from ..tienda.catalogo import construir

PASOS = (
    ("recibido", "Esperan tu aprobación", "Pagados. Apruébalos en Aprobar y se mandan a Prodigi."),
    ("excepcion", "Con un problema", "Falta el archivo de impresión o el SKU de Prodigi: revisar."),
    ("enviado-a-pod", "En Prodigi", "Aprobados y enviados a imprimir."),
    ("en-produccion", "En producción", "Prodigi los está haciendo."),
    ("enviado", "Enviados", "Con guía; el cliente recibió el correo de envío."),
)


@dataclass
class Requisito:
    nombre: str
    listo: bool
    como: str


def requisitos(ajustes: Ajustes | None = None) -> list[Requisito]:
    """What checkout needs before it opens, read from the settings (never their values)."""
    a = ajustes or Ajustes.desde_entorno()
    clave = config.get("STRIPE_SECRET_KEY") or ""
    return [
        Requisito("Cuenta de Stripe (clave secreta)", bool(clave),
                  "STRIPE_SECRET_KEY en Render" + (" · modo de prueba" if clave.startswith("sk_test_") else "")),
        Requisito("Aviso de pagos de Stripe (webhook)", bool(config.get("STRIPE_WEBHOOK_SECRET")),
                  "STRIPE_WEBHOOK_SECRET en Render"),
        Requisito("Correos de pedido (Resend)", bool(config.get("RESEND_API_KEY")),
                  "RESEND_API_KEY en Render y el dominio verificado en GoDaddy"),
        Requisito("Prodigi en modo real", config.get("PRODIGI_ENV") == "live" and bool(config.get("PRODIGI_API_KEY")),
                  "PRODIGI_ENV=live y PRODIGI_API_KEY"),
        Requisito("Nombre legal de la LLC", bool(a.razon_social), "LULA_US_RAZON_SOCIAL (sale en políticas)"),
        Requisito("Domicilio de la LLC", bool(a.domicilio), "LULA_US_DOMICILIO (sale en políticas)"),
        Requisito("Estado donde se constituyó", bool(a.estado_constitucion), "LULA_US_ESTADO"),
        Requisito("Firma del carrito", bool(a.secreto), "LULA_TIENDA_SECRET (Render la genera)"),
        Requisito("Dominio de la tienda", bool(config.get("LULA_TIENDA_HOSTS")),
                  "LULA_TIENDA_HOSTS=lulamacaroni.com,www.lulamacaroni.com"),
    ]


def render(d, banner: str = "", ajustes: Ajustes | None = None) -> str:
    from .views import page, usd

    reqs = requisitos(ajustes)
    faltan = [r for r in reqs if not r.listo]
    filas_req = "".join(
        f"<tr><td>{escape(r.nombre)}</td><td><span class='badge {'ok' if r.listo else 'amber'}'>"
        f"{'listo' if r.listo else 'falta'}</span></td><td class='meta'>{escape(r.como)}</td></tr>"
        for r in reqs)
    estado = ("<span class='badge ok'>El cobro está abierto</span>" if not faltan else
              f"<span class='badge amber'>El cobro está cerrado: faltan {len(faltan)}</span>")

    web = [r for r in d.pedidos_rows if r.get("canal") == "web"]
    por_pedido: dict[str, list[dict]] = {}
    for r in web:
        por_pedido.setdefault(str(r.get("pedido_id")), []).append(r)
    bloques = []
    for clave, titulo, ayuda in PASOS:
        pedidos = [ls for ls in por_pedido.values() if ls[0].get("estado") == clave]
        if not pedidos:
            continue
        items = "".join(
            f"<tr><td><strong>{escape(str(ls[0].get('numero_canal')))}</strong></td>"
            f"<td>{escape(str(ls[0].get('fecha'))[:10])}</td>"
            f"<td>{escape(', '.join(str(r.get('producto')) for r in ls))}</td>"
            f"<td>{usd(sum(float(r.get('venta_bruta') or 0) for r in ls))}</td>"
            f"<td>{escape(str(ls[0].get('tracking') or '—'))}</td></tr>" for ls in pedidos)
        bloques.append(f"<h2>{escape(titulo)} ({len(pedidos)})</h2><p class='meta'>{escape(ayuda)}</p>"
                       "<div class='tablebox'><table><thead><tr><th>Pedido</th><th>Fecha</th>"
                       f"<th>Obras</th><th>Venta</th><th>Guía</th></tr></thead><tbody>{items}</tbody></table></div>")
    pendientes = sum(1 for a in d.approvals if a.tipo == "pedido-tienda" and a.estado == "pendiente")
    pedidos_html = "".join(bloques) or "<p class='meta'>Todavía no hay pedidos de la tienda propia.</p>"
    if pendientes:
        pedidos_html = (f"<p><a class='badge amber' href='/aprobar'>{pendientes} pedido(s) por aprobar"
                        "</a></p>") + pedidos_html

    listados = [r for r in d.listados if r.get("canal") == "web"]
    cuenta = {e: sum(1 for r in listados if r.get("estado") == e)
              for e in ("publicado", "en-aprobacion", "borrador", "pausado", "retirado")}
    en_venta = construir(d.listados, d.variantes)
    sin_archivo = sum(1 for p in en_venta for o in p.opciones if not o.archivo)
    filas_prod = "".join(
        f"<tr><td>{escape(p.titulo)}</td><td>{len(p.opciones)}</td><td>desde {usd(p.desde)}</td>"
        f"<td>{sum(1 for o in p.opciones if not o.archivo) or '—'}</td></tr>" for p in en_venta)
    catalogo = (
        f"<p>En venta: <strong>{cuenta['publicado']}</strong> opción(es) · por aprobar: "
        f"{cuenta['en-aprobacion']} · borrador: {cuenta['borrador']} · pausadas: {cuenta['pausado']}</p>"
        + (f"<p class='meta'>{sin_archivo} opción(es) en venta sin archivo de impresión: si alguien las "
           "compra, el pedido queda con un problema hasta que subas el archivo.</p>" if sin_archivo else "")
        + ("<div class='tablebox'><table><thead><tr><th>Obra</th><th>Opciones</th><th>Precio</th>"
           f"<th>Sin archivo</th></tr></thead><tbody>{filas_prod}</tbody></table></div>" if filas_prod else
           "<p class='meta'>Nada en venta todavía. Los productos de Shopify se pasan como borrador con "
           "<code>python -m lulamacaroni.tienda.publicar semilla</code> y salen a la venta cuando apruebas.</p>"))

    body = (
        "<h1>Tienda propia</h1><p class='sub'>lulamacaroni.com: el catálogo, los pedidos y lo que "
        f"falta para abrir el cobro.</p><p>{estado}</p>"
        f"<h2>Pedidos de la tienda</h2>{pedidos_html}"
        f"<h2>Catálogo en la tienda</h2>{catalogo}"
        "<h2>Para abrir el cobro</h2><div class='tablebox'><table><thead><tr><th>Qué</th><th>Estado</th>"
        f"<th>Dónde</th></tr></thead><tbody>{filas_req}</tbody></table></div>"
        "<p class='legend'>Fuente: libro de datos (Pedidos, Listados y Variantes con canal web) y los "
        "ajustes del servidor. Los datos del comprador (correo, dirección) viven en Stripe, no aquí.</p>")
    return page("Tienda", "/tienda", body, banner)
