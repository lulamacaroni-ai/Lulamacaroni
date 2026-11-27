"""Serve the store.

    python -m lulamacaroni.tienda.server            # http://127.0.0.1:8780, real catalog
    python -m lulamacaroni.tienda.server --demo     # sample catalog and Stripe test mode off

Hosted, the store and the back office are one service: requests for the store's hosts
(``LULA_TIENDA_HOSTS``, e.g. ``lulamacaroni.com,www.lulamacaroni.com``) are answered here,
everything else by the back office behind its password (``lulamacaroni.app.server``).

Public routes: ``/``, ``/products/<slug>``, ``/cart``, ``/checkout``, ``/thank-you``,
``/policies/<name>``, ``/sitemap.xml``, ``/robots.txt``, ``/healthz`` and Stripe's
``/stripe/webhook``. Nothing here needs a login; nothing here shows a buyer's details.
"""

from __future__ import annotations

import argparse
import logging
import re
import tempfile
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from .. import config
from . import carrito as cart
from . import correo as plantillas
from . import paginas
from .ajustes import Ajustes
from .catalogo import Catalogo
from .pedidos import registrar
from .stripe import FirmaInvalida, StripeError, parametros_checkout, verificar_webhook

log = logging.getLogger(__name__)
TEXT = "text/plain; charset=utf-8"
HTML = "text/html; charset=utf-8"
MAX_CUERPO = 1_000_000
UTM = ("utm_source", "utm_medium", "utm_campaign")
PAGADO = ("checkout.session.completed", "checkout.session.async_payment_succeeded")
CSP = ("default-src 'self'; img-src 'self' https: data:; style-src 'self' 'unsafe-inline' "
       "https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'none'; "
       "form-action 'self' https://checkout.stripe.com; frame-ancestors 'none'; base-uri 'none'")


class Limite:
    """At most ``maximo`` POSTs per minute from one address (cart and checkout)."""

    def __init__(self, maximo: int = 30, ventana: float = 60.0):
        self.maximo, self.ventana = maximo, ventana
        self._vistos: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def permite(self, ip: str, ahora: float | None = None) -> bool:
        ahora = time.monotonic() if ahora is None else ahora
        with self._lock:
            if len(self._vistos) > 10_000:
                self._vistos.clear()
            recientes = [x for x in self._vistos.get(ip, []) if ahora - x < self.ventana]
            if len(recientes) >= self.maximo:
                self._vistos[ip] = recientes
                return False
            recientes.append(ahora)
            self._vistos[ip] = recientes
            return True


class Tienda:
    """Everything a request needs; one per process, shared by every handler thread."""

    def __init__(self, book, store, ajustes: Ajustes, stripe=None, mailer=None,
                 webhook_secret: str = "", banner: str = ""):
        self.book, self.store, self.ajustes = book, store, ajustes
        self.catalogo = Catalogo(book)
        self.stripe, self.mailer = stripe, mailer
        self.webhook_secret, self.banner = webhook_secret, banner
        self.lock = threading.Lock()  # one writer at a time: order numbers and Sheet rows
        self.limite = Limite()

    @property
    def abierta(self) -> bool:
        """Checkout works only with Stripe keys and every legal setting in place."""
        return bool(self.stripe and self.webhook_secret and not self.ajustes.faltantes())


def responder(h: BaseHTTPRequestHandler, status: int, cuerpo: str | bytes, tipo: str = HTML,
              cabeceras: dict | None = None, cache: str = "no-store") -> None:
    data = cuerpo.encode("utf-8") if isinstance(cuerpo, str) else cuerpo
    h.send_response(status)
    h.send_header("Content-Type", tipo)
    h.send_header("Content-Length", str(len(data)))
    h.send_header("Cache-Control", cache)
    h.send_header("Content-Security-Policy", CSP)
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
    h.send_header("Strict-Transport-Security", "max-age=31536000")  # ignored over http
    for k, v in (cabeceras or {}).items():
        for valor in (v if isinstance(v, list) else [v]):
            h.send_header(k, valor)
    h.end_headers()
    if h.command != "HEAD":
        h.wfile.write(data)


def redirigir(h, destino: str, status: int = 303, cabeceras: dict | None = None) -> None:
    responder(h, status, "", TEXT, {"Location": destino, **(cabeceras or {})})


def _seguro(h) -> bool:
    return h.headers.get("X-Forwarded-Proto") == "https" or (
        urlparse(h.tienda.ajustes.url).scheme == "https")


def _carrito(h) -> dict[str, int]:
    return cart.decodificar(cart.leer_cookie(h.headers.get("Cookie")), h.tienda.ajustes.secreto)


def _lineas(t: Tienda, items: dict[str, int]) -> list[dict]:
    out = []
    for sku, n in items.items():
        hallado = t.catalogo.buscar_sku(sku)
        if hallado:
            out.append({"sku": sku, "producto": hallado[0], "opcion": hallado[1], "cantidad": n})
    return out


def _mismo_origen(h) -> bool:
    origen = h.headers.get("Origin") or h.headers.get("Referer")
    return bool(origen) and urlparse(origen).netloc == h.headers.get("Host")


def _largo(h) -> int:
    """Content-Length as a non-negative int; -1 when missing a number or negative."""
    try:
        largo = int(h.headers.get("Content-Length") or 0)
    except ValueError:
        return -1
    return largo if largo >= 0 else -1


def _ip(h) -> str:
    reenviada = (h.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return reenviada or h.client_address[0]


def _formulario(h) -> dict[str, str]:
    largo = min(max(_largo(h), 0), 10_000)
    return {k: v[0] for k, v in parse_qs(h.rfile.read(largo).decode("utf-8", "replace")).items()}


def _utm_cookie(params: dict, referente: str) -> str | None:
    datos = {k: params[k][:80] for k in UTM if params.get(k)}
    if referente:
        datos["referente"] = referente[:80]
    return urlencode(datos) if datos else None


def _leer_utm(h) -> dict[str, str]:
    for parte in (h.headers.get("Cookie") or "").split(";"):
        k, _, v = parte.strip().partition("=")
        if k == "lm_src":
            return {a: b[0] for a, b in parse_qs(v).items()}
    return {}


def get(h) -> None:
    t: Tienda = h.tienda
    url = urlparse(h.path)
    params = {k: v[0] for k, v in parse_qs(url.query).items()}
    ruta = url.path.rstrip("/") or "/"
    n = sum(_carrito(h).values())
    extra = {}
    src = _utm_cookie(params, _referente_externo(h))
    if src:  # first touch of this visit: remember where the buyer came from (no personal data)
        extra["Set-Cookie"] = f"lm_src={src}; Path=/; Max-Age=2592000; HttpOnly; SameSite=Lax"

    if ruta == "/healthz":
        return responder(h, 200, "ok", TEXT)
    if ruta == "/robots.txt":
        return responder(h, 200, f"User-agent: *\nAllow: /\nDisallow: /cart\nDisallow: /checkout\n"
                                 f"Sitemap: {t.ajustes.url}/sitemap.xml\n", TEXT, cache="public, max-age=3600")
    if ruta == "/sitemap.xml":
        return responder(h, 200, paginas.sitemap(t.ajustes, t.catalogo.productos()),
                         "application/xml; charset=utf-8", cache="public, max-age=3600")
    if ruta == "/":
        return responder(h, 200, paginas.inicio(t.ajustes, t.catalogo.productos(), n), cabeceras=extra)
    if ruta in ("/collections/all", "/collections", "/products", "/shop"):
        return redirigir(h, "/", 301)
    m = re.fullmatch(r"/products/([a-z0-9-]{1,120})", ruta)
    if m:
        p = t.catalogo.producto(m.group(1))
        if p is None:
            nuevo = t.catalogo.redireccion(m.group(1))
            if nuevo:
                return redirigir(h, f"/products/{nuevo}", 301)
            return responder(h, 404, paginas.no_encontrada(t.ajustes))
        try:
            foto = int(params.get("foto", "0"))
        except ValueError:
            foto = 0
        return responder(h, 200, paginas.producto(t.ajustes, p, elegido=params.get("sku", ""),
                                                   en_carrito=n, foto=foto), cabeceras=extra)
    if ruta == "/cart":
        return responder(h, 200, paginas.carrito(t.ajustes, _lineas(t, _carrito(h)), "", t.abierta))
    m = re.fullmatch(r"/policies/([a-z-]+)", ruta)
    if m and m.group(1) in paginas.POLITICAS:
        return responder(h, 200, paginas.politica(t.ajustes, m.group(1), n))
    if ruta == "/thank-you":
        numero = ""
        sid = params.get("session_id", "")
        if sid.startswith("cs_"):
            numero = next((str(r.get("numero_canal")) for r in t.book.read("Pedidos")
                           if r.get("pedido_id") == sid), "")
        vacio = cart.cookie({}, t.ajustes.secreto, _seguro(h)) if t.ajustes.secreto else None
        return responder(h, 200, paginas.gracias(t.ajustes, numero),
                         cabeceras={"Set-Cookie": vacio} if vacio else None)
    return responder(h, 404, paginas.no_encontrada(t.ajustes))


def _referente_externo(h) -> str:
    ref = urlparse(h.headers.get("Referer") or "").netloc
    return "" if not ref or ref == h.headers.get("Host") else ref


def post(h) -> None:
    t: Tienda = h.tienda
    ruta = urlparse(h.path).path
    if ruta == "/stripe/webhook":
        return webhook(h)
    if not _mismo_origen(h):
        return responder(h, 403, "Origin not allowed", TEXT)
    if not t.limite.permite(_ip(h)):
        return responder(h, 429, "Too many requests. Please wait a minute.", TEXT)
    if _largo(h) > 10_000:
        return responder(h, 413, "too large", TEXT)
    if not t.ajustes.secreto:
        return responder(h, 503, "The cart is not configured yet (LULA_TIENDA_SECRET).", TEXT)
    form = _formulario(h)
    items = _carrito(h)
    if ruta in ("/cart/add", "/cart/update"):
        sku = form.get("sku", "")
        try:
            qty = int(form.get("qty", "1"))
        except ValueError:
            qty = 1
        hallado = t.catalogo.buscar_sku(sku)
        if hallado is None:
            return redirigir(h, "/cart")
        items[sku] = (items.get(sku, 0) + qty) if ruta == "/cart/add" else qty
        items = {k: v for k, v in items.items() if v > 0}
        return redirigir(h, "/cart", cabeceras={
            "Set-Cookie": cart.cookie(items, t.ajustes.secreto, _seguro(h))})
    if ruta == "/checkout":
        lineas = _lineas(t, items)
        if not lineas or not t.abierta:
            return redirigir(h, "/cart")
        datos = [{"sku": li["sku"], "nombre": li["producto"].titulo, "detalle": li["opcion"].etiqueta,
                  "imagen": li["producto"].imagen, "precio": li["opcion"].precio,
                  "cantidad": li["cantidad"]} for li in lineas]
        meta = {"canal": "web", "carrito": ",".join(f"{li['sku']}*{li['cantidad']}" for li in lineas),
                **_leer_utm(h)}
        try:
            sesion = t.stripe.crear_checkout(parametros_checkout(
                datos, url=t.ajustes.url, envio_usd=t.ajustes.envio_usd,
                impuestos=t.ajustes.impuestos, metadata=meta))
        except StripeError:
            log.exception("checkout")
            return responder(h, 502, paginas.carrito(
                t.ajustes, lineas, "We couldn't open the secure checkout. Please try again in a minute.",
                t.abierta))
        return redirigir(h, sesion["url"])
    return responder(h, 404, "Not found", TEXT)


def webhook(h) -> None:
    t: Tienda = h.tienda
    largo = _largo(h)
    if largo < 0:
        return responder(h, 400, "bad length", TEXT)
    if largo > MAX_CUERPO:
        return responder(h, 413, "too large", TEXT)
    cuerpo = h.rfile.read(largo)
    try:
        evento = verificar_webhook(cuerpo, h.headers.get("Stripe-Signature"), t.webhook_secret)
    except (FirmaInvalida, ValueError):
        return responder(h, 400, "bad signature", TEXT)
    if evento.get("type") not in PAGADO or t.stripe is None:
        return responder(h, 200, "ignored", TEXT)
    try:
        procesar_pago(t, evento["data"]["object"]["id"])
    except Exception:
        log.exception("webhook")
        return responder(h, 500, "error", TEXT)
    return responder(h, 200, "ok", TEXT)


def procesar_pago(t: Tienda, session_id: str) -> None:
    ahora = datetime.now(UTC).replace(microsecond=0)
    sesion = t.stripe.checkout(session_id)
    if sesion.get("payment_status") != "paid":
        return
    with t.lock:  # Stripe retries and async events can arrive together
        res = registrar(sesion, t.book, t.store, t.catalogo, ahora)
        t.book.stamp_source("tienda", rows=len(res.lineas), note=f"último pedido {res.numero}")
    if not res.nuevo or not res.correo.get("para"):
        return
    if t.mailer is None or not t.mailer.activo:
        t.book.upsert("Excepciones", [{
            "excepcion_id": f"exc-{res.numero}-correo", "linea": "US-POD", "tipo": "pedido-tienda",
            "referencia": res.numero, "detalle": "confirmación no enviada: falta RESEND_API_KEY",
            "creada_en": ahora.isoformat(), "responsable": "Jon", "estado": "abierta"}])
        return
    asunto, html, texto = plantillas.confirmacion(t.ajustes, res.correo)
    try:
        t.mailer.enviar(de=t.ajustes.remitente, para=res.correo["para"], asunto=asunto, html=html,
                        texto=texto, responder_a=t.ajustes.soporte,
                        clave=f"confirmacion-{session_id}")
    except Exception:  # noqa: BLE001 - the order is recorded; a person resends the email
        log.exception("confirmation email")
        t.book.upsert("Excepciones", [{
            "excepcion_id": f"exc-{res.numero}-correo", "linea": "US-POD", "tipo": "pedido-tienda",
            "referencia": res.numero, "detalle": "confirmación no enviada: Resend falló",
            "creada_en": ahora.isoformat(), "responsable": "Jon", "estado": "abierta"}])


class Handler(BaseHTTPRequestHandler):
    tienda: Tienda = None

    def log_message(self, fmt, *args):  # no query strings (they can carry session ids)
        pass

    def do_GET(self):
        try:
            get(self)
        except Exception:
            log.exception("GET")
            responder(self, 500, "Something went wrong. Please try again in a minute.", TEXT)

    do_HEAD = do_GET

    def do_POST(self):
        try:
            post(self)
        except Exception:
            log.exception("POST")
            responder(self, 500, "Something went wrong. Please try again in a minute.", TEXT)


def tienda_desde_entorno(book, store) -> Tienda:
    """The store with whatever keys are configured; missing keys keep checkout closed."""
    from .correo import Correo
    from .stripe import StripeClient

    clave = config.get("STRIPE_SECRET_KEY")
    return Tienda(book, store, Ajustes.desde_entorno(),
                  stripe=StripeClient(clave) if clave else None, mailer=Correo.from_env(),
                  webhook_secret=config.get("STRIPE_WEBHOOK_SECRET", ""))


def iniciar_trabajador(t: Tienda, cada: float = 300):
    """Start the loop that sends approved orders to Prodigi and emails tracking."""
    from ..connectors.prodigi import ProdigiClient
    from .envios import Trabajador, ciclo

    if t.stripe is None:
        return None
    try:
        prodigi = ProdigiClient.from_env()
    except Exception:  # noqa: BLE001 - no Prodigi key yet: orders wait in the workbook
        log.warning("Prodigi key missing; approved store orders will wait")
        return None
    def una_vuelta():
        with t.lock:
            return ciclo(t.book, t.store, t.stripe, prodigi, t.mailer, t.ajustes)

    w = Trabajador(una_vuelta, cada)
    w.start()
    return w


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The store (lulamacaroni.com)")
    parser.add_argument("--port", type=int, default=int(config.get("LULA_TIENDA_PORT", "8780")))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--demo", action="store_true", help="sample catalog, checkout closed")
    args = parser.parse_args(argv)

    from ..approval.store import JsonStore, SheetsStore, open_store
    from ..localbook import LocalWorkbook, open_workbook
    from ..workbook import Workbook

    if args.demo:
        from .demo import llenar

        tmp = Path(tempfile.mkdtemp(prefix="lula-tienda-"))
        book = LocalWorkbook(tmp / "libro")
        llenar(book)
        Handler.tienda = Tienda(book, JsonStore(tmp / "aprobaciones.json"),
                                Ajustes(url=f"http://127.0.0.1:{args.port}", secreto="demo-only"))
    else:
        book = open_workbook()
        store = SheetsStore(book) if isinstance(book, Workbook) else open_store()
        Handler.tienda = tienda_desde_entorno(book, store)
        iniciar_trabajador(Handler.tienda)
    print(f"Tienda en http://127.0.0.1:{args.port}  (Ctrl+C para salir)")
    try:
        ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
