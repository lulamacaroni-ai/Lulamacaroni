"""Sample pieces for previewing the site. Not real art: flat colour panels marked EJEMPLO."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .datos import Ajustes

# (obra_id, título, técnica, año, colección, ancho_cm, alto_cm, precio, colores)
PIEZAS = (
    ("EJ-01", "Jardín de ejemplo", "acrílico sobre tela", 2025, "Jardines", 60, 80, 14500,
     ("#d98c5f", "#7a9e7e")),
    ("EJ-02", "Patio al mediodía (ejemplo)", "óleo sobre tela", 2024, "Jardines", 50, 50, 9800,
     ("#e8c468", "#c0603f")),
    ("EJ-03", "Bugambilias (ejemplo)", "acrílico sobre papel", 2025, "Jardines", 40, 30, 6200,
     ("#b84a7a", "#f2d4c2")),
    ("EJ-04", "Puerto de ejemplo", "óleo sobre tela", 2023, "Mar", 100, 70, 23000,
     ("#3f6e8c", "#e9d8b4")),
    ("EJ-05", "Marea baja (ejemplo)", "técnica mixta", 2024, "Mar", 30, 40, None,
     ("#5b8fa8", "#2b3f4f")),
    ("EJ-06", "Barcas (ejemplo)", "acuarela", 2025, "Mar", 45, 60, 7400,
     ("#9fb7c4", "#d26d4b")),
)

AJUSTES_DEMO = Ajustes(
    responsable="[Nombre del responsable — ejemplo]",
    domicilio="[Domicilio — ejemplo]",
    correo="info@lulamacaroni.com",
    whatsapp="5200000000000",
    url="https://mx.lulamacaroni.com",
    ciudad="[ciudad — ejemplo]",
)


def filas(actualizado: str = "2026-11-02") -> tuple[list[dict], list[dict]]:
    obras, variantes = [], []
    for oid, titulo, tecnica, anio, col, an, al, precio, _ in PIEZAS:
        obras.append({"obra_id": oid, "titulo_es": titulo, "tecnica": tecnica, "anio": anio,
                      "coleccion": col, "ancho_cm": an, "alto_cm": al, "estado": "activa"})
        variantes.append({"sku": f"{oid}-ORIG", "obra_id": oid, "linea": "MX-original",
                          "tipo": "original", "precio_mxn_con_iva": precio or "",
                          "estado": "activa", "actualizado": actualizado})
    # one sold piece and one print variant: neither may appear on the site
    obras.append({"obra_id": "EJ-07", "titulo_es": "Vendida (ejemplo)", "estado": "vendida"})
    variantes.append({"sku": "EJ-07-ORIG", "obra_id": "EJ-07", "linea": "MX-original",
                      "tipo": "original", "precio_mxn_con_iva": 5000, "estado": "activa"})
    variantes.append({"sku": "EJ-01-8x10", "obra_id": "EJ-01", "linea": "US-POD",
                      "tipo": "impresion", "estado": "activa"})
    return obras, variantes


def fotos(carpeta: Path) -> Path:
    """Write one sample panel per piece, in the piece's own proportions."""
    carpeta.mkdir(parents=True, exist_ok=True)
    for oid, _, _, _, _, an, al, _, (c1, c2) in PIEZAS:
        w, h = an * 12, al * 12
        im = Image.new("RGB", (w, h), c1)
        d = ImageDraw.Draw(im)
        d.ellipse((w * 0.18, h * 0.22, w * 0.82, h * 0.78), fill=c2)
        d.rectangle((0, h * 0.86, w, h), fill=c2)
        d.text((w * 0.05, h * 0.04), f"EJEMPLO {oid}", fill="#ffffff")
        im.save(carpeta / f"{oid}.jpg", quality=88)
    return carpeta
