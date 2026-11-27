"""Sample catalog for ``--demo`` and tests: clearly fake, no real art, nothing from the Sheet.

Images are plain SVG placeholders (data: URLs), so the demo never shows or copies Lorena's art.
"""

from __future__ import annotations

from base64 import b64encode

from .catalogo import semilla

PIEZAS = (
    ("Sample Print One", (("8x8", "79.00"), ("12x12", "99.00"), ("20x20", "129.00"))),
    ("Sample Print Two", (("16x12", "119.00"), ("24x18", "129.00"))),
)


def placeholder(texto: str, w: int = 800, h: int = 800) -> str:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
           f'<rect width="{w}" height="{h}" fill="#e3d9c8"/><text x="50%" y="50%" font-family="sans-serif" '
           f'font-size="36" fill="#6f655e" text-anchor="middle">{texto}</text></svg>')
    return "data:image/svg+xml;base64," + b64encode(svg.encode()).decode()


def filas_shopify() -> list[dict]:
    """Rows shaped like the Shopify sync's published Listados."""
    out = []
    for titulo, tamanos in PIEZAS:
        foto = placeholder(titulo)
        for tam, precio in tamanos:
            for color in ("Black", "White"):
                out.append({"canal": "shopify", "estado": "publicado",
                            "titulo_en_canal": f"{titulo} / {tam} / {color}", "precio": precio,
                            "imagen_url": foto, "imagenes_producto": foto,
                            "descripcion": "A sample description. Nothing here is real."})
    return out


def llenar(book, publicado: bool = True, con_archivos: bool = True) -> dict[str, list[dict]]:
    filas = semilla(filas_shopify(), "2026-11-26T00:00:00+00:00")
    for v in filas["Variantes"]:
        v["estado"] = "activa"
        if con_archivos:
            v["archivo_impresion"] = f"https://example.com/print-files/{v['sku']}.tif"
    if publicado:
        for li in filas["Listados"]:
            li["estado"] = "publicado"
    for tab, rows in filas.items():
        book.upsert(tab, rows)
    return filas
