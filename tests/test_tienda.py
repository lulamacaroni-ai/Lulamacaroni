"""The own store (canal web): catalog, cart, Stripe checkout, orders, approval, Prodigi, emails.

Everything offline: fake Stripe/Prodigi/Resend sessions and a loopback server.
"""

import http.client
import json
import threading
from datetime import UTC, datetime
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

import pytest

from lulamacaroni.approval import JsonStore, NotApproved, decide
from lulamacaroni.connectors.prodigi import ProdigiClient
from lulamacaroni.localbook import LocalWorkbook
from lulamacaroni.tienda import carrito, envios, pedidos, publicar
from lulamacaroni.tienda import server as srv
from lulamacaroni.tienda.ajustes import Ajustes
from lulamacaroni.tienda.catalogo import (
    Catalogo,
    construir,
    norm_tamano,
    prodigi_box,
    semilla,
)
from lulamacaroni.tienda.correo import Correo
from lulamacaroni.tienda.demo import filas_shopify, llenar
from lulamacaroni.tienda.stripe import (
    FirmaInvalida,
    StripeClient,
    aplanar,
    firmar,
    parametros_checkout,
    verificar_webhook,
)

NOW = datetime(2026, 11, 26, 18, 0, tzinfo=UTC)
AJ = Ajustes(url="https://lulamacaroni.com", razon_social="Sample LLC", domicilio="1 Sample St",
             estado_constitucion="Wyoming", secreto="s3cret")
ADDRESS = {"line1": "1 Main St", "line2": "", "city": "Austin", "state": "TX",
           "postal_code": "78701", "country": "US"}


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self._body, self.reason, self.text = status, body, "x", json.dumps(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        return self.responses.pop(0)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)


@pytest.fixture
def book(tmp_path):
    b = LocalWorkbook(tmp_path / "libro")
    llenar(b)
    return b


@pytest.fixture
def store(tmp_path):
    return JsonStore(tmp_path / "aprobaciones.json")


def session_pagada(sku="LM-SPO-8X8-BL", qty=1, sid="cs_test_1", name="Mary Ann Smith", address=None):
    unit = 7900
    return {
        "id": sid, "payment_status": "paid", "created": int(NOW.timestamp()), "customer": "cus_1",
        "amount_subtotal": unit * qty, "amount_total": unit * qty + 650,
        "total_details": {"amount_tax": 650, "amount_shipping": 0},
        "shipping_cost": {"amount_total": 0},
        "customer_details": {"email": "buyer@example.com", "name": name},
        "collected_information": {"shipping_details": {"name": name, "address": address or ADDRESS}},
        "metadata": {"canal": "web", "utm_source": "pinterest"},
        "line_items": {"data": [{
            "quantity": qty, "amount_subtotal": unit * qty, "amount_discount": 0, "amount_tax": 650,
            "amount_total": unit * qty + 650, "description": "Sample Print One",
            "price": {"product": {"name": "Sample Print One", "description": "8 × 8 in · Black frame",
                                  "metadata": {"sku": sku}}}}]},
    }


class FakeStripe:
    def __init__(self, sesiones=None):
        self.sesiones = dict(sesiones or {})
        self.creadas = []

    def crear_checkout(self, params, idempotency_key=None):
        self.creadas.append(params)
        return {"id": "cs_test_new", "url": "https://checkout.stripe.com/c/pay/cs_test_new"}

    def checkout(self, sid):
        return self.sesiones[sid]


class FakeMailer:
    activo = True

    def __init__(self):
        self.enviados = []

    def enviar(self, **kw):
        self.enviados.append(kw)
        return "em_1"


# --- catalog ----------------------------------------------------------------------------------

def test_sizes_and_prodigi_skus():
    assert norm_tamano("16×12") == "16x12" and norm_tamano('8 X 8"') == "8x8"
    assert prodigi_box("16x12") == "GLOBAL-BOX-12X16" and prodigi_box("8x8") == "GLOBAL-BOX-8X8"
    with pytest.raises(ValueError):
        norm_tamano("large")


def test_seed_makes_drafts_from_shopify_products():
    filas = semilla(filas_shopify(), "2026-11-26")
    assert {r["estado"] for r in filas["Listados"]} == {"borrador"}
    assert {r["canal"] for r in filas["Listados"]} == {"web"}
    v = next(v for v in filas["Variantes"] if v["sku"] == "LM-SPT-16X12-WH")
    assert v["pod_sku"] == "GLOBAL-BOX-12X16" and v["marco"] == "white" and v["linea"] == "US-POD"
    assert v["archivo_impresion"] == ""  # Lore supplies the print file; nothing is invented
    assert len(filas["Obras"]) == 2


def test_only_published_web_listings_are_for_sale(book):
    productos = construir(book.read("Listados"), book.read("Variantes"))
    assert [p.slug for p in productos] == ["sample-print-one", "sample-print-two"]
    p = productos[0]
    assert p.desde == 79.0 and [o.tamano for o in p.opciones][:2] == ["8x8", "8x8"]
    assert p.opciones[0].etiqueta == "8 × 8 in · Black frame"
    borradores = [dict(r, estado="borrador") for r in book.read("Listados")]
    assert construir(borradores, book.read("Variantes")) == []


def test_old_shopify_addresses_redirect(book):
    c = Catalogo(book)
    assert c.redireccion("sample-print-one-2") == "sample-print-one"
    assert c.redireccion("nothing-here-2") is None


# --- cart -------------------------------------------------------------------------------------

def test_cart_cookie_is_signed():
    valor = carrito.codificar({"LM-A": 2}, "k")
    assert carrito.decodificar(valor, "k") == {"LM-A": 2}
    assert carrito.decodificar(valor, "other") == {}
    datos, firma = valor.rsplit(".", 1)
    assert carrito.decodificar(datos[:-2] + "xx." + firma, "k") == {}
    assert carrito.decodificar(carrito.codificar({"LM-A": 99}, "k"), "k") == {"LM-A": 10}


# --- Stripe -----------------------------------------------------------------------------------

def test_form_encoding():
    assert aplanar({"a": {"b": [1, True]}, "c": None}) == [("a[b][0]", "1"), ("a[b][1]", "true")]


def test_checkout_parameters_use_catalog_prices_and_us_shipping():
    p = parametros_checkout([{"sku": "LM-A", "nombre": "A", "detalle": "8 × 8", "imagen": "https://x/y.jpg",
                              "precio": 79.0, "cantidad": 2}], url=AJ.url, envio_usd=0,
                            impuestos=True, metadata={"canal": "web", "vacio": ""})
    item = p["line_items"][0]
    assert item["price_data"]["unit_amount"] == 7900 and item["quantity"] == 2
    assert item["price_data"]["product_data"]["metadata"] == {"sku": "LM-A"}
    assert p["shipping_address_collection"]["allowed_countries"] == ["US"]
    assert p["automatic_tax"] == {"enabled": True}
    assert p["shipping_options"][0]["shipping_rate_data"]["display_name"] == "Free shipping"
    assert p["success_url"] == "https://lulamacaroni.com/thank-you?session_id={CHECKOUT_SESSION_ID}"
    assert p["metadata"] == {"canal": "web"}


def test_stripe_client_sends_bearer_and_form():
    s = FakeSession(FakeResponse(200, {"id": "cs_1", "url": "https://checkout.stripe.com/x"}))
    c = StripeClient("sk_test_abc", session=s)
    assert c.crear_checkout({"mode": "payment"}, idempotency_key="k1")["id"] == "cs_1"
    method, url, kw = s.calls[0]
    assert url.endswith("/checkout/sessions") and kw["headers"]["Authorization"] == "Bearer sk_test_abc"
    assert kw["headers"]["Idempotency-Key"] == "k1" and kw["data"] == [("mode", "payment")]
    assert c.modo == "test" and "sk_test_abc" not in repr(c)


def test_webhook_signature():
    cuerpo = b'{"type":"checkout.session.completed"}'
    cab = firmar(cuerpo, "whsec_x", t=1000)
    assert verificar_webhook(cuerpo, cab, "whsec_x", ahora=1010)["type"] == "checkout.session.completed"
    for cuerpo2, secreto, ahora in ((cuerpo + b" ", "whsec_x", 1010), (cuerpo, "whsec_y", 1010),
                                    (cuerpo, "whsec_x", 2000)):
        with pytest.raises(FirmaInvalida):
            verificar_webhook(cuerpo2, cab, secreto, ahora=ahora)


def test_refund_needs_approval(store):
    from lulamacaroni.approval import request_approval

    c = StripeClient("sk_test_abc", session=FakeSession(FakeResponse(200, {"id": "re_1"})))
    contenido = {"payment_intent": "pi_1", "pedido": "LM-1001", "motivo": "llegó dañado"}
    with pytest.raises(NotApproved):
        c.reembolsar(contenido, approval=None)
    rec = request_approval(store, tipo="reembolso", linea="US-POD", resumen="r", contenido=contenido,
                           creado_por="t")
    decide(store, rec.aprobacion_id, aprobar=True, decidido_por="Lorena")
    assert c.reembolsar(contenido, approval=store.get(rec.aprobacion_id))["id"] == "re_1"


# --- order -> workbook -> approval -> Prodigi -> emails ---------------------------------------

def test_paid_checkout_becomes_order_customer_and_approval(book, store):
    res = pedidos.registrar(session_pagada(qty=2), book, store, Catalogo(book), NOW)
    assert res.nuevo and res.numero == "LM-1001" and not res.problemas
    fila = book.read("Pedidos")[0]
    assert fila["canal"] == "web" and fila["linea"] == "US-POD" and fila["estado"] == "recibido"
    assert fila["venta_bruta"] == 158.0 and fila["impuesto_cobrado"] == 6.5
    assert fila["calidad_dato"] == "estimado" and fila["utm_fuente"] == "pinterest"
    cli = book.read("Clientes")[0]
    assert cli["cliente_id"] == "stripe-cus_1" and cli["nombre"] == "Mary Ann S." and cli["region"] == "TX"
    texto = json.dumps(book.read("Pedidos") + book.read("Clientes") + [a.to_row() for a in store.all()])
    for privado in ("buyer@example.com", "1 Main St", "78701", "Smith"):
        assert privado not in texto  # buyer details stay in Stripe
    rec = store.get(res.aprobacion_id)
    item = rec.contenido["items"][0]
    assert rec.tipo == "pedido-tienda" and rec.estado == "pendiente"
    assert item["sku"] == "GLOBAL-BOX-8X8" and item["copies"] == 2 and item["sizing"] == "fitPrintArea"
    assert item["attributes"] == {"color": "black"}
    # Stripe retries the webhook: nothing doubles
    again = pedidos.registrar(session_pagada(qty=2), book, store, Catalogo(book), NOW)
    assert not again.nuevo and len(book.read("Pedidos")) == 1 and len(store.all()) == 1


def test_order_without_print_file_is_an_exception(tmp_path, store):
    b = LocalWorkbook(tmp_path / "otro")
    llenar(b, con_archivos=False)
    res = pedidos.registrar(session_pagada(), b, store, Catalogo(b), NOW)
    assert res.problemas and not res.aprobacion_id and store.all() == []
    assert b.read("Pedidos")[0]["estado"] == "excepcion"
    assert "archivo de impresión" in b.read("Excepciones")[0]["detalle"]


def _prodigi(*responses):
    return ProdigiClient(api_key="k", env="sandbox", session=FakeSession(*responses))


def test_approved_order_goes_to_prodigi_once(book, store):
    sesion = session_pagada()
    res = pedidos.registrar(sesion, book, store, Catalogo(book), NOW)
    stripe = FakeStripe({"cs_test_1": sesion})
    prodigi = _prodigi(FakeResponse(200, {"order": {"id": "ord_9"}}))
    assert envios.enviar_aprobados(book, store, stripe, prodigi, NOW) == []  # not approved yet
    decide(store, res.aprobacion_id, aprobar=True, decidido_por="Lorena")
    assert envios.enviar_aprobados(book, store, stripe, prodigi, NOW) == ["LM-1001"]
    body = prodigi.session.calls[0][2]["json"]
    assert body["merchantReference"] == "LM-1001" and body["idempotencyKey"] == res.aprobacion_id
    assert body["recipient"]["address"]["postalOrZipCode"] == "78701"
    fila = book.read("Pedidos")[0]
    assert fila["estado"] == "enviado-a-pod" and fila["pod_pedido_id"] == "ord_9"
    assert envios.enviar_aprobados(book, store, stripe, prodigi, NOW) == []  # used once


def test_changed_address_after_approval_is_not_sent(book, store):
    res = pedidos.registrar(session_pagada(), book, store, Catalogo(book), NOW)
    decide(store, res.aprobacion_id, aprobar=True, decidido_por="Lorena")
    otra = session_pagada(address=dict(ADDRESS, line1="9 Other Rd"))
    prodigi = _prodigi()
    assert envios.enviar_aprobados(book, store, FakeStripe({"cs_test_1": otra}), prodigi, NOW) == []
    assert prodigi.session.calls == [] and "dirección" in book.read("Excepciones")[0]["detalle"]


def test_shipped_order_emails_tracking_once(book, store):
    sesion = session_pagada()
    res = pedidos.registrar(sesion, book, store, Catalogo(book), NOW)
    decide(store, res.aprobacion_id, aprobar=True, decidido_por="Lorena")
    stripe = FakeStripe({"cs_test_1": sesion})
    envios.enviar_aprobados(book, store, stripe, _prodigi(FakeResponse(200, {"order": {"id": "ord_9"}})), NOW)
    enviada = {"order": {"id": "ord_9", "shipments": [
        {"carrier": {"name": "UPS"}, "tracking": {"number": "1Z999", "url": "https://ups.example/1Z999"}}]}}
    mailer = FakeMailer()
    prodigi = _prodigi(FakeResponse(200, enviada))
    assert envios.avisar_enviados(book, stripe, prodigi, mailer, AJ, NOW) == ["LM-1001"]
    assert mailer.enviados[0]["para"] == "buyer@example.com" and "1Z999" in mailer.enviados[0]["texto"]
    assert book.read("Pedidos")[0]["tracking"] == "1Z999"
    assert envios.avisar_enviados(book, stripe, prodigi, mailer, AJ, NOW) == []


def test_resend_client():
    s = FakeSession(FakeResponse(200, {"id": "em_1"}))
    c = Correo("re_key", session=s)
    assert c.enviar(de="a@b.c", para="d@e.f", asunto="s", html="<p>h</p>", texto="h",
                    responder_a="info@x", clave="k") == "em_1"
    assert s.calls[0][2]["headers"]["Authorization"] == "Bearer re_key"
    assert not Correo("").activo and "re_key" not in repr(c)


# --- publishing needs Lorena's approval --------------------------------------------------------

def test_catalog_goes_on_sale_only_after_approval(tmp_path, store):
    b = LocalWorkbook(tmp_path / "pub")
    llenar(b, publicado=False)
    assert construir(b.read("Listados"), b.read("Variantes")) == []
    rec = publicar.solicitar(b, store, AJ)
    with pytest.raises(NotApproved):
        publicar.publicar(b, store, AJ, rec.aprobacion_id)
    decide(store, rec.aprobacion_id, aprobar=True, decidido_por="Lorena")
    assert publicar.publicar(b, store, AJ, rec.aprobacion_id) == 10
    assert len(construir(b.read("Listados"), b.read("Variantes"))) == 2


def test_price_change_after_approval_needs_a_new_one(tmp_path, store):
    b = LocalWorkbook(tmp_path / "pub2")
    llenar(b, publicado=False)
    rec = publicar.solicitar(b, store, AJ)
    decide(store, rec.aprobacion_id, aprobar=True, decidido_por="Lorena")
    r = b.read("Listados")[0]
    b.upsert("Listados", [{"listado_ref": r["listado_ref"], "linea": "US-POD", "canal": "web", "precio": "1.00"}])
    with pytest.raises(NotApproved):
        publicar.publicar(b, store, AJ, rec.aprobacion_id)


# --- the web server ---------------------------------------------------------------------------

@pytest.fixture
def servidor(book, store):
    stripe = FakeStripe({"cs_test_1": session_pagada()})
    mailer = FakeMailer()
    tienda = srv.Tienda(book, store, AJ, stripe=stripe, mailer=mailer, webhook_secret="whsec_t")

    class H(srv.Handler):
        pass

    H.tienda = tienda
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd.server_address[1], tienda
    httpd.shutdown()


def _pedir(puerto, metodo, ruta, cuerpo=b"", cabeceras=None):
    con = http.client.HTTPConnection("127.0.0.1", puerto, timeout=5)
    con.request(metodo, ruta, body=cuerpo, headers=cabeceras or {})
    r = con.getresponse()
    return r.status, dict(r.getheaders()), r.read().decode()


def test_pages_render(servidor):
    puerto, _ = servidor
    status, _, html = _pedir(puerto, "GET", "/")
    assert status == 200 and "Sample Print One" in html and "From $79" in html
    status, cab, html = _pedir(puerto, "GET", "/products/sample-print-one")
    assert status == 200 and "application/ld+json" in html and "Add to cart" in html
    assert "object-fit:contain" in html and "script-src 'none'" in cab["Content-Security-Policy"]
    status, cab, _ = _pedir(puerto, "GET", "/products/sample-print-one-2")
    assert status == 301 and cab["Location"] == "/products/sample-print-one"
    status, _, html = _pedir(puerto, "GET", "/policies/privacy")
    assert status == 200 and "Sample LLC" in html and "Prodigi" in html and "Printful" not in html
    assert _pedir(puerto, "GET", "/sitemap.xml")[2].count("<loc>") == 7
    assert _pedir(puerto, "GET", "/nope")[0] == 404


def test_cart_and_checkout_use_server_prices(servidor):
    puerto, tienda = servidor
    origen = {"Origin": f"http://127.0.0.1:{puerto}", "Host": f"127.0.0.1:{puerto}",
              "Content-Type": "application/x-www-form-urlencoded"}
    assert _pedir(puerto, "POST", "/cart/add", b"sku=LM-SPO-8X8-BL&qty=2")[0] == 403  # no origin
    status, cab, _ = _pedir(puerto, "POST", "/cart/add", urlencode({"sku": "LM-SPO-8X8-BL", "qty": 2,
                                                                    "price": "0.01"}).encode(), origen)
    assert status == 303 and "lm_cart=" in cab["Set-Cookie"]
    cookie = cab["Set-Cookie"].split(";")[0]
    status, _, html = _pedir(puerto, "GET", "/cart", cabeceras={"Cookie": cookie})
    assert "Subtotal $158" in html and "Check out securely" in html
    status, cab, _ = _pedir(puerto, "POST", "/checkout", b"", {**origen, "Cookie": cookie})
    assert status == 303 and cab["Location"].startswith("https://checkout.stripe.com/")
    item = tienda.stripe.creadas[0]["line_items"][0]
    assert item["price_data"]["unit_amount"] == 7900 and item["quantity"] == 2


def test_checkout_stays_closed_without_legal_settings(book, store):
    t = srv.Tienda(book, store, Ajustes(secreto="x"), stripe=FakeStripe(), webhook_secret="w")
    assert not t.abierta


def test_webhook_records_order_and_sends_confirmation(servidor):
    puerto, tienda = servidor
    cuerpo = json.dumps({"type": "checkout.session.completed",
                         "data": {"object": {"id": "cs_test_1"}}}).encode()
    assert _pedir(puerto, "POST", "/stripe/webhook", cuerpo, {"Stripe-Signature": "t=1,v1=bad"})[0] == 400
    status, _, _ = _pedir(puerto, "POST", "/stripe/webhook", cuerpo,
                          {"Stripe-Signature": firmar(cuerpo, "whsec_t")})
    assert status == 200
    assert tienda.book.read("Pedidos")[0]["numero_canal"] == "LM-1001"
    assert tienda.mailer.enviados[0]["para"] == "buyer@example.com"
    _pedir(puerto, "POST", "/stripe/webhook", cuerpo, {"Stripe-Signature": firmar(cuerpo, "whsec_t")})
    assert len(tienda.mailer.enviados) == 1  # a retry doesn't email twice
    status, _, html = _pedir(puerto, "GET", "/thank-you?session_id=cs_test_1")
    assert "LM-1001" in html


def test_back_office_routes_store_hosts(book, store, monkeypatch):
    from lulamacaroni.app import server as app_server

    class H(app_server.Handler):
        pass

    H.book, H.store, H.password = book, store, "pw"
    H.tienda = srv.Tienda(book, store, AJ)
    H.tienda_hosts = {"shop.test"}
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        puerto = httpd.server_address[1]
        status, _, html = _pedir(puerto, "GET", "/", cabeceras={"Host": "shop.test"})
        assert status == 200 and "Sample Print One" in html  # public, no password
        assert _pedir(puerto, "GET", "/", cabeceras={"Host": "admin.test"})[0] == 401
    finally:
        httpd.shutdown()


def test_admin_screen(book, store):
    from lulamacaroni.app.screens import Datos, render

    pedidos.registrar(session_pagada(), book, store, Catalogo(book), NOW)
    html = render("/tienda", {}, Datos(book, store, NOW))
    assert "Tienda propia" in html and "LM-1001" in html and "Esperan tu aprobación" in html
    assert "1 pedido(s) por aprobar" in html and "buyer@example.com" not in html
