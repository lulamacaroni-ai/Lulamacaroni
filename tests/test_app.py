from datetime import datetime, timedelta, timezone

import pytest

from lulamacaroni.app import metrics as m
from lulamacaroni.app.demo import demo_rows, fill_demo
from lulamacaroni.app.screens import Datos, render
from lulamacaroni.approval import JsonStore, request_approval
from lulamacaroni.localbook import LocalWorkbook

NOW = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)


@pytest.fixture
def book(tmp_path):
    b = LocalWorkbook(tmp_path / "libro")
    fill_demo(b, NOW)
    return b


@pytest.fixture
def store(tmp_path):
    return JsonStore(tmp_path / "aprobaciones.json")


def _dato(res, label):
    return next(d for d in res.datos if d.etiqueta == label)


# --- local workbook ----------------------------------------------------------------

def test_local_workbook_upsert_keeps_other_columns(tmp_path):
    b = LocalWorkbook(tmp_path)
    row = {"listado_ref": "shopify-1", "sku": "A", "linea": "US-POD", "canal": "shopify",
           "precio": 95}
    assert b.upsert("Listados", [row]) == {"actualizadas": 0, "nuevas": 1}
    assert b.upsert("Listados", [{"listado_ref": "shopify-1", "linea": "US-POD",
                                  "precio": 99}]) == {"actualizadas": 1, "nuevas": 0}
    [saved] = b.read("Listados")
    assert saved["sku"] == "A" and saved["precio"] == 99


def test_local_workbook_refuses_invalid_rows(tmp_path):
    with pytest.raises(ValueError):
        LocalWorkbook(tmp_path).upsert("Pedidos", [{"linea_pedido_id": "x", "estado": "raro",
                                                    "linea": "US-POD"}])
    assert LocalWorkbook(tmp_path).read("Pedidos") == []


# --- sources -----------------------------------------------------------------------

def test_sources_not_stamped_are_unconnected_and_old_ones_late():
    rows = [{"fuente": "shopify", "ultima_actualizacion": (NOW - timedelta(hours=30)).isoformat(),
             "estado": "ok"}]
    f = m.estado_fuentes(rows, NOW)
    assert f["shopify"].estado == "atrasada" and f["shopify"].conectada
    assert f["etsy"].estado == "sin-conectar" and not f["etsy"].conectada


# --- metrics: zero vs missing ---------------------------------------------------------

def test_nothing_connected_means_missing_never_zero():
    res = m.resumen([], [], m.estado_fuentes([], NOW), m.periodo("7", NOW))
    for d in res.datos:
        assert d.calidad == "faltante" and d.valor is None


def test_connected_with_no_orders_is_a_real_zero():
    f = m.estado_fuentes([{"fuente": "shopify", "ultima_actualizacion": NOW.isoformat(),
                           "estado": "ok"}], NOW)
    res = m.resumen([], [], f, m.periodo("hoy", NOW))
    pedidos = _dato(res, "Pedidos")
    assert pedidos.valor == 0 and pedidos.es_cero
    assert "Etsy" in pedidos.nota  # partial: says which channel is missing
    assert _dato(res, "Margen de contribución").calidad == "faltante"
    assert _dato(res, "Gasto publicitario").calidad == "faltante"


def test_net_sales_period_and_comparison():
    rows = demo_rows(NOW)
    f = m.estado_fuentes(rows["Fuentes"], NOW)
    res = m.resumen(rows["Pedidos"], [], f, m.periodo("7", NOW))
    ventas = _dato(res, "Ventas netas")
    # last 7 days: 100 + 80 + 120 + 80; previous 7: 100 (delivered) + (100 − 100 refunded)
    assert ventas.valor == 380.0 and ventas.previo == 100.0
    assert round(ventas.cambio_pct) == 280
    assert _dato(res, "Pedidos").valor == 4
    assert ventas.fuente == "Shopify" and ventas.periodo.endswith("hora de CDMX")


def test_cancelled_orders_are_not_sales():
    rows = [{"pedido_id": "shopify-1", "fecha": NOW.isoformat(), "venta_bruta": "50",
             "estado": "cancelado", "linea": "US-POD"}]
    f = m.estado_fuentes([{"fuente": "shopify", "ultima_actualizacion": NOW.isoformat()}], NOW)
    res = m.resumen(rows, [], f, m.periodo("hoy", NOW + timedelta(minutes=1)))
    assert _dato(res, "Pedidos").valor == 0


def test_today_uses_mexico_city_midnight():
    # 05:30 UTC on Nov 2 is still Nov 1 in CDMX (UTC−6)
    per = m.periodo("hoy", datetime(2026, 11, 2, 5, 30, tzinfo=timezone.utc))
    assert per.inicio.astimezone(timezone.utc) == datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc)


# --- orders and catalog ------------------------------------------------------------------

def test_orders_without_a_printer_need_attention():
    pedidos = m.agrupar_pedidos(demo_rows(NOW)["Pedidos"])
    atencion = [p for p in pedidos if p.grupo == "atencion"]
    assert [p.numero for p in atencion] == ["1003"]
    assert {p.numero for p in pedidos if p.grupo == "cerrado"} == {"1005", "1006"}


def test_catalog_groups_variants_and_flags_missing_skus():
    productos = m.agrupar_catalogo(demo_rows(NOW)["Listados"])
    assert len(productos) == 3
    owl = next(p for p in productos if p.titulo == "Sample Owl")
    assert owl.variantes == 3 and owl.sin_sku == 3 and owl.avisos
    assert owl.precio_min == 80 and owl.precio_max == 120


# --- screens -----------------------------------------------------------------------------

@pytest.mark.parametrize("path,needle", [
    ("/inicio", "Hola, Lore"), ("/pedidos", "Necesitan atención"), ("/catalogo", "Catálogo"),
    ("/fuentes", "sin conectar"), ("/aprobar", "Aprobaciones"), ("/alertas", "Urgente"),
])
def test_every_screen_renders(book, store, path, needle):
    html = render(path, {}, Datos(book, store, NOW), banner="Datos de ejemplo")
    assert needle in html and "Datos de ejemplo" in html


def test_missing_numbers_show_a_dash_not_zero(book, store):
    html = render("/inicio", {"p": "30"}, Datos(book, store, NOW))
    assert "falta el dato" in html and "¿De dónde sale?" in html
    assert render("/nope", {}, Datos(book, store, NOW)) is None


def test_screens_escape_store_text(tmp_path, store):
    b = LocalWorkbook(tmp_path)
    b.upsert("Listados", [{"listado_ref": "shopify-1", "linea": "US-POD", "canal": "shopify",
                           "titulo_en_canal": "<script>x</script>", "estado": "publicado"}])
    html = render("/catalogo", {}, Datos(b, store, NOW))
    assert "<script>x" not in html and "&lt;script&gt;" in html


def test_prodigi_source_reads_the_key_like_the_connector(monkeypatch):
    from lulamacaroni.app.metrics import estado_fuentes

    now = datetime.now(timezone.utc)
    monkeypatch.delenv("PRODIGI_ENV", raising=False)
    monkeypatch.setenv("PRODIGI_SANDBOX_API_KEY", "x")
    assert "lista" in estado_fuentes([], now)["prodigi"].nota
    monkeypatch.delenv("PRODIGI_SANDBOX_API_KEY")
    assert estado_fuentes([], now)["prodigi"].nota == "falta la llave de sandbox"
    monkeypatch.setenv("PRODIGI_ENV", "live")
    monkeypatch.setenv("PRODIGI_API_KEY", "y")
    assert estado_fuentes([], now)["prodigi"].nota == "llave de live lista; aún sin sincronizar costos"


def test_root_is_inicio_with_the_welcome_art_over_it(book, store):
    from lulamacaroni.app import views

    html = render("/", {}, Datos(book, store, NOW), banner="Datos de ejemplo")
    # Inicio is already underneath, so nothing has to load when the art fades away
    assert "Hola, Lore" in html and "id='portada'" in html and "Datos de ejemplo" in html
    assert html.index("id='portada'") < html.index("Hola, Lore")
    assert "href='/inicio'" in html and "Entrar" in html  # works without JavaScript too
    # /inicio and old /?p= links open plain Inicio
    assert "id='portada'" not in render("/inicio", {}, Datos(book, store, NOW))
    assert "id='portada'" not in render("/", {"p": "30"}, Datos(book, store, NOW))
    # the logo in the menu goes back to the front door
    assert 'class="brand" href="/"' in html
    # the art is never cropped or stretched, and the page still works without it
    assert "object-fit:contain" in views.PORTADA_CSS and "width:auto;height:auto" in views.PORTADA_CSS
    assert "<img" in views.portada(True) and "<img" not in views.portada(False)


def test_welcome_art_fades_away_every_time(book, store):
    from lulamacaroni.app import views

    html = render("/", {}, Datos(book, store, NOW))
    assert "classList.add('fuera')" in html and f"setTimeout(quita,{views.PORTADA_ESPERA_MS})" in html
    assert "sessionStorage" not in html  # no once-per-visit memory that could hide it
    # reduce motion keeps the plain fade and only drops the zoom
    assert "@media (prefers-reduced-motion:reduce){.portada img{animation:none}}" in views.PORTADA_CSS


def test_puppy_plays_on_inicio_but_not_on_the_welcome_page(book, store):
    from lulamacaroni.app import views

    d = Datos(book, store)
    inicio = render("/inicio", {}, d)
    # the script address carries a hash of the file, so browsers never run a stale copy
    assert f"/perrito.js?v={views.PERRITO_VERSION}" in inicio and len(views.PERRITO_VERSION) == 10
    assert "getElementById('portada')" in inicio  # waits for the welcome art to fade first
    assert "prefers-reduced-motion" in inicio  # no motion for people who turn it off
    assert "perrito" not in views.portada(True)  # never on the welcome page
    assert "pointer-events:none" in views.CSS  # it never blocks a click


def test_puppy_art_is_cut_out_but_never_stretched():
    from PIL import Image

    from lulamacaroni.app import views
    from lulamacaroni.app.screens import PERRITO

    im = Image.open(PERRITO)
    assert im.mode == "RGBA"  # background removed
    # same proportions as the trimmed artwork (1246×1136): resized evenly, never stretched
    assert abs(im.width / im.height - 1246 / 1136) < 0.01
    from lulamacaroni.app.screens import PERRITO_JS

    js = PERRITO_JS.read_text(encoding="utf-8")
    assert "1136 / 1246" in js and 'preserveAspectRatio: "xMidYMid meet"' in js  # never stretched
    assert "/perrito.js" in views.PERRITO_JS  # the animation loads only when it plays
    # the dog walks to a pillow by the greeting, turns round twice and lies down facing forward
    for clave in ("main h1", "PASO", "VUELTAS", "echarse", "iterations: Infinity",
                  "DEL = {", "TRAS = {",  # three-bone legs: wrist and hock, not just a knee
                  "pf-sombra", "pf-vol", "lejos",  # depth: ground shadow, shading, far legs set back
                  "ANG_DEL", "ANG_TRAS", "olfatea", "suspiro",  # gait curves, sniff, sit-then-lie, sigh
                  "asoma", "overflow:hidden"):  # peeks in from the right edge without side-scrolling
        assert clave in js
    assert "inicio)?$" in views.PERRITO_JS  # only on Inicio, next to "Hola, Lore"


def test_every_screen_has_its_own_painting_detail(book, store):
    from lulamacaroni.app import arte
    from lulamacaroni.app.views import NAV

    d = Datos(book, store, NOW)
    vistos = set()
    for path, _ in NAV:
        html = render(path, {}, d)
        nombre = arte.PANTALLAS[path][0]
        assert 'class="cab"' in html and f"/arte/{nombre}.jpg" in html, path
        assert "Detalle de <i>" in html and 'class="sellos"' in html, path
        assert html.index('class="cab"') < html.index("<h1>")  # beside the title, above the data
        vistos.add(nombre)
    assert len(vistos) == len(NAV)  # a different detail on each screen


def test_painting_details_are_small_and_never_stretched():
    from PIL import Image

    from lulamacaroni.app import arte

    total = 0
    for ruta, archivo in arte.ARCHIVOS.items():
        assert archivo.is_file(), ruta
        total += archivo.stat().st_size
        w, h = Image.open(archivo).size
        sello = archivo.name.startswith("sello-")
        assert (w, h) == ((120, 120) if sello else (320, 400)), ruta
    assert total < 400_000  # the whole set stays light
    # every stamp is a painting in the store, and every detail names its painting
    assert len([r for r in arte.ARCHIVOS if "/sello-" in r]) == len(arte.OBRAS) == 10


def test_product_page_keeps_the_cover_as_the_only_art(book, store):
    d = Datos(book, store, NOW)
    cat = render("/catalogo", {}, d)
    assert 'class="galeria"' in cat and 'class="ph xl"' in cat
    link = cat.split('class="t"><a href="', 1)[1].split('"', 1)[0].replace("&amp;", "&")
    params = dict(kv.split("=") for kv in link.split("?", 1)[1].split("&"))
    det = render("/catalogo/producto", params, d)
    assert 'class="obra"' not in det and 'class="sellos"' in det
