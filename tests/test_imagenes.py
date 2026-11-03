"""Real product content from Shopify: images (links to its CDN, shown whole), text, tags."""

from datetime import datetime, timezone

from lulamacaroni.app import views
from lulamacaroni.app.screens import Datos, render
from lulamacaroni.approval import JsonStore
from lulamacaroni.connectors.shopify import (
    MAX_DESCRIPCION, order_to_rows, product_content, product_images, product_to_listing_rows,
)
from lulamacaroni.localbook import LocalWorkbook
from lulamacaroni.schema import validate_row

from test_shopify import PRODUCT, _order

NOW = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)
CDN = "https://cdn.shopify.com/s/files/1/0001/files/"


def _img(name, alt=""):
    return {"url": f"{CDN}{name}?v=1", "altText": alt}


RICH = {
    **PRODUCT,
    "description": "A hand holds a spark.\nSecond paragraph.",
    "tags": ["floral", "gift"],
    "productType": "Art print",
    "featuredMedia": {"preview": {"image": _img("cover.jpg")}},
    "media": {"nodes": [{"image": _img("cover.jpg")}, {"image": _img("room.jpg")}, {}]},
    "variants": {"nodes": [
        {**PRODUCT["variants"]["nodes"][0], "image": _img("framed-12x16.jpg")},
        {**PRODUCT["variants"]["nodes"][1], "image": None},
    ]},
}


def test_listing_rows_carry_images_and_content():
    rows = product_to_listing_rows(RICH, "2026-11-02T19:00:00+00:00")
    assert rows[0]["imagen_url"] == f"{CDN}framed-12x16.jpg?v=1"   # the variant's own mockup
    assert rows[1]["imagen_url"] == f"{CDN}cover.jpg?v=1"          # else the product cover
    assert rows[0]["imagenes_producto"].splitlines() == [f"{CDN}cover.jpg?v=1",
                                                         f"{CDN}room.jpg?v=1"]
    assert rows[0]["descripcion"].startswith("A hand holds") and rows[0]["etiquetas"] == "floral, gift"
    assert rows[1]["tipo_producto"] == "Art print"
    for r in rows:
        assert validate_row("Listados", r) == []


def test_product_without_media_or_text_leaves_cells_empty():
    rows = product_to_listing_rows(PRODUCT, "2026-11-02T19:00:00+00:00")
    assert all(r["imagen_url"] == "" and r["imagenes_producto"] == "" and r["descripcion"] == ""
               for r in rows)


def test_gallery_is_capped_and_long_text_says_it_was_cut():
    many = {**RICH, "media": {"nodes": [{"image": _img(f"{i}.jpg")} for i in range(20)]}}
    assert len(product_images(many)) == 6
    long = product_content({**RICH, "description": "x" * (MAX_DESCRIPCION + 10)})
    assert len(long["descripcion"]) < 50_000 and "recortada" in long["descripcion"]


def test_order_lines_carry_their_image():
    order = _order()
    order["lineItems"]["nodes"][0]["image"] = _img("line.jpg")
    rows = order_to_rows(order)
    assert rows[0]["imagen_url"] == f"{CDN}line.jpg?v=1" and rows[1]["imagen_url"] == ""


def test_image_is_shown_whole_and_only_from_https():
    html = views.imagen(f"{CDN}a.jpg?v=1", 'Say "hi"')
    assert f'src="{CDN}a.jpg?v=1&amp;width=240"' in html and "&quot;hi&quot;" in html
    assert 'loading="lazy"' in html
    assert "object-fit:contain" in views.CSS and "object-fit:cover" not in views.CSS
    assert "sin imagen" in views.imagen("javascript:alert(1)", "x")
    assert "sin imagen" in views.imagen("", "x")
    # other hosts are linked as they are, never rewritten
    assert 'src="https://example.com/a.jpg"' in views.imagen("https://example.com/a.jpg", "x")


def _book(tmp_path):
    b = LocalWorkbook(tmp_path / "libro")
    b.upsert("Listados", product_to_listing_rows(RICH, "2026-11-02T19:00:00+00:00"))
    b.stamp_source("shopify", rows=2)
    return b


def test_catalog_and_product_page_show_real_content(tmp_path):
    d = Datos(_book(tmp_path), JsonStore(tmp_path / "a.json"), NOW)
    cat = render("/catalogo", {}, d)
    assert f"{CDN}cover.jpg?v=1&amp;width=800" in cat and 'class="ph xl"' in cat  # large card
    det = render("/catalogo/producto", {"c": "shopify", "id": "1"}, d)
    assert "En la tienda" in det and "<p>Second paragraph.</p>" in det
    assert "floral, gift" in det and "Art print" in det and "Fuente: Shopify" in det
    assert f"{CDN}cover.jpg?v=1&amp;width=1600" in det and 'class="ph cover"' in det  # big cover
    assert det.index('class="ph cover"') < det.index("En la tienda")  # the art comes first
    assert f"{CDN}room.jpg?v=1&amp;width=320" in det          # gallery
    assert f"{CDN}framed-12x16.jpg?v=1&amp;width=160" in det  # variant mockup


def test_product_page_before_the_first_content_sync(tmp_path):
    b = LocalWorkbook(tmp_path / "libro")
    b.upsert("Listados", [{"listado_ref": "shopify-11", "linea": "US-POD", "canal": "shopify",
                           "titulo_en_canal": "Old row", "estado": "publicado",
                           "id_producto_canal": "1"}])
    d = Datos(b, JsonStore(tmp_path / "a.json"), NOW)
    assert "sin imagen" in render("/catalogo", {}, d)
    assert "próxima sincronización" in render("/catalogo/producto", {"c": "shopify", "id": "1"}, d)


def test_pedidos_show_the_line_image(tmp_path):
    b = _book(tmp_path)
    order = _order()
    order["lineItems"]["nodes"][0]["image"] = _img("line.jpg")
    b.upsert("Pedidos", order_to_rows(order))
    html = render("/pedidos", {}, Datos(b, JsonStore(tmp_path / "a.json"), NOW))
    assert f"{CDN}line.jpg?v=1&amp;width=160" in html
