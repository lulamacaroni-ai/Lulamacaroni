"""Details of Lore's artwork used to decorate the back office screens.

Each screen shows one detail of a different painting next to its title, and every page ends
with a small row of round "stamps", one per painting. The files in static/arte/ are plain
rectangular crops of the Shopify product images, scaled down proportionally: nothing is
stretched, repainted or regenerated, and each detail names the painting it comes from.

How they were made (to redo or add one): take the product's main image from the store
(…/cdn/shop/files/NAME?width=1600), cut a 4:5 window around the detail (stamps: a square),
and save it at 320×400 (stamps 120×120) as JPEG quality 78.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

CARPETA = Path(__file__).parent / "static" / "arte"

# Paintings in the US store: handle -> title as it appears in Shopify.
OBRAS = {
    "the-tender-art-of-vanishing-2": "The Tender Art of Vanishing",
    "where-light-ripens-1": "Where Light Ripens",
    "the-shape-of-a-secret-1": "The Shape of a Secret",
    "the-geometry-of-forever-1": "The Geometry of Forever",
    "the-weight-of-a-distant-star-2": "The Weight of a Distant Star",
    "the-lightness-of-becoming": "The Lightness of Becoming",
    "the-borrowed-face-2": "The Borrowed Face",
    "a-borrowed-constellation-2": "A Borrowed Constellation",
    "the-sea-has-no-mirrors": "The Sea Has No Mirrors",
    "the-gravity-of-a-wish-2": "The Gravity of a Wish",
}

# Screen -> (detail file, painting it comes from).
PANTALLAS = {
    "/inicio": ("inicio", "the-tender-art-of-vanishing-2"),
    "/alertas": ("alertas", "where-light-ripens-1"),
    "/aprobar": ("aprobar", "the-shape-of-a-secret-1"),
    "/catalogo": ("catalogo", "the-geometry-of-forever-1"),
    "/pedidos": ("pedidos", "the-weight-of-a-distant-star-2"),
    "/clientes": ("clientes", "the-lightness-of-becoming"),
    "/contenido": ("contenido", "the-borrowed-face-2"),
    "/publicidad": ("publicidad", "a-borrowed-constellation-2"),
    "/investigacion": ("investigacion", "the-sea-has-no-mirrors"),
    "/finanzas": ("finanzas", "the-gravity-of-a-wish-2"),
    "/semana": ("semana", "where-light-ripens-1"),
    "/fuentes": ("fuentes", "the-sea-has-no-mirrors"),
}

# Every file the server may hand out, by URL path. Nothing outside this list is served.
ARCHIVOS = {f"/arte/{nombre}.jpg": CARPETA / f"{nombre}.jpg"
            for nombre in [d for d, _ in PANTALLAS.values()] + [f"sello-{h}" for h in OBRAS]}


def detalle(activo: str) -> str:
    """The framed detail shown beside a screen's title ('' when the screen has none)."""
    if activo not in PANTALLAS:
        return ""
    nombre, obra = PANTALLAS[activo]
    titulo = OBRAS[obra]
    return (f'<figure class="obra" aria-hidden="true"><img src="/arte/{nombre}.jpg" alt="" '
            f'width="160" height="200" decoding="async"><figcaption>Detalle de '
            f"<i>{escape(titulo)}</i></figcaption></figure>")


def motivo(activo: str) -> str:
    """URL of the round stamp used in this screen's empty states."""
    obra = PANTALLAS.get(activo, ("", "the-geometry-of-forever-1"))[1]
    return f"/arte/sello-{obra}.jpg"


def sellos() -> str:
    """A quiet row of round stamps at the foot of every page, one per painting."""
    items = "".join(f'<img src="/arte/sello-{h}.jpg" alt="" title="{escape(t)}" width="44" '
                    'height="44" decoding="async">' for h, t in OBRAS.items())
    return f'<div class="sellos" aria-hidden="true">{items}</div>'
