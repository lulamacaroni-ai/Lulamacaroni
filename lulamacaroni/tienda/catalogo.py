"""The store's catalog: what buyers can see and buy, read from the workbook.

A product is on sale only when its ``Listados`` rows have ``canal = web`` and
``estado = publicado``; publishing goes through Lorena's approval (``publicar.py``). Each
row is one buyable option (size + frame colour) whose ``sku`` joins ``Variantes`` for the
Prodigi SKU and the print file.

Prices always come from here, never from the buyer's browser.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field

CANAL = "web"
TIPO = "Framed print"
PROVEEDOR = "prodigi"
CACHE_SEGUNDOS = 300
REINTENTO_SEGUNDOS = 60  # after a failed Sheet read
log = logging.getLogger(__name__)


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def norm_tamano(texto: str) -> str:
    """``16×12``, ``16 x 12`` or ``16X12"`` -> ``16x12`` (width x height, as listed)."""
    t = texto.replace("×", "x").replace("X", "x").replace('"', "").replace(" ", "")
    if not re.fullmatch(r"\d+(\.\d+)?x\d+(\.\d+)?", t):
        raise ValueError(f"size not understood: {texto!r}")
    return t


def prodigi_box(tamano: str) -> str:
    """Prodigi box-frame SKU for a size: short side first (``16x12`` -> ``GLOBAL-BOX-12X16``)."""
    a, b = sorted(float(x) for x in norm_tamano(tamano).split("x"))
    fmt = lambda v: f"{v:g}"
    return f"GLOBAL-BOX-{fmt(a)}X{fmt(b)}"


def _precio(valor) -> float | None:
    try:
        v = float(str(valor).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _area(tamano: str) -> float:
    try:
        a, b = (float(x) for x in norm_tamano(tamano).split("x"))
    except ValueError:
        return 0.0
    return a * b


@dataclass
class Opcion:
    sku: str
    tamano: str          # "16x12", width x height in inches
    marco: str           # frame colour as shown to buyers ("Black")
    precio: float
    pod_sku: str
    color_pod: str       # Prodigi's attribute value ("black")
    archivo: str         # print file URL (Variantes.archivo_impresion); "" = missing

    @property
    def etiqueta(self) -> str:
        return f'{self.tamano.replace("x", " × ")} in · {self.marco} frame'

    @property
    def lista_para_imprimir(self) -> bool:
        return bool(self.pod_sku and self.archivo)


@dataclass
class Producto:
    slug: str
    titulo: str
    descripcion: str
    imagenes: list[str]
    tipo: str
    opciones: list[Opcion] = field(default_factory=list)

    @property
    def desde(self) -> float:
        return min(o.precio for o in self.opciones)

    @property
    def imagen(self) -> str:
        return self.imagenes[0] if self.imagenes else ""

    def opcion(self, sku: str) -> Opcion | None:
        return next((o for o in self.opciones if o.sku == sku), None)


def construir(listados: list[dict], variantes: list[dict]) -> list[Producto]:
    """Products on sale, in the workbook's order. Pure function over rows."""
    maestro = {str(v.get("sku")): v for v in variantes if v.get("sku")}
    productos: dict[str, Producto] = {}
    for r in listados:
        if r.get("canal") != CANAL or r.get("estado") != "publicado":
            continue
        sku = str(r.get("sku") or "")
        precio = _precio(r.get("precio"))
        v = maestro.get(sku)
        if not sku or precio is None or v is None or v.get("estado") == "descontinuada":
            continue
        clave = str(r.get("id_producto_canal") or slug(r.get("titulo_en_canal") or sku))
        p = productos.get(clave)
        if p is None:
            imagenes = [u for u in str(r.get("imagenes_producto") or "").split() if u]
            if not imagenes and r.get("imagen_url"):
                imagenes = [str(r["imagen_url"])]
            p = productos[clave] = Producto(
                slug=clave, titulo=str(r.get("titulo_en_canal") or clave),
                descripcion=str(r.get("descripcion") or ""), imagenes=imagenes,
                tipo=str(r.get("tipo_producto") or TIPO))
        marco = str(v.get("marco") or "").strip()
        p.opciones.append(Opcion(
            sku=sku, tamano=str(v.get("tamano") or ""), marco=marco.capitalize(), precio=precio,
            pod_sku=str(v.get("pod_sku") or ""), color_pod=marco.lower(),
            archivo=str(v.get("archivo_impresion") or "")))
    for p in productos.values():
        p.opciones.sort(key=lambda o: (_area(o.tamano), o.marco))
    return [p for p in productos.values() if p.opciones]


class Catalogo:
    """Cached view of the catalog; reloads from the workbook every few minutes."""

    def __init__(self, book, ttl: float = CACHE_SEGUNDOS, clock=time.monotonic):
        self.book, self.ttl, self.clock = book, ttl, clock
        self._productos: list[Producto] = []
        self._cuando = None
        self._lock = threading.Lock()

    def productos(self) -> list[Producto]:
        with self._lock:
            if self._cuando is None or self.clock() - self._cuando > self.ttl:
                try:
                    self._productos = construir(self.book.read("Listados"),
                                                self.book.read("Variantes"))
                    self._cuando = self.clock()
                except Exception:  # noqa: BLE001 - Sheet outage: keep the last good catalog
                    if self._cuando is None:
                        raise
                    log.warning("catalog reload failed; serving the last good copy")
                    self._cuando = self.clock() - self.ttl + REINTENTO_SEGUNDOS
            return self._productos

    def refrescar(self) -> None:
        with self._lock:
            self._cuando = None

    def producto(self, clave: str) -> Producto | None:
        return next((p for p in self.productos() if p.slug == clave), None)

    def buscar_sku(self, sku: str) -> tuple[Producto, Opcion] | None:
        for p in self.productos():
            o = p.opcion(sku)
            if o:
                return p, o
        return None

    def redireccion(self, handle: str) -> str | None:
        """An old Shopify address (``a-borrowed-constellation-2``) -> our slug, if one fits."""
        base = re.sub(r"-\d+$", "", handle)
        return base if base != handle and self.producto(base) else None


# --- seed from the Shopify sync ---------------------------------------------------------------

def _iniciales(titulo: str) -> str:
    return "".join(w[0] for w in re.findall(r"[A-Za-z0-9]+", titulo)).upper()


def semilla(listados_shopify: list[dict], ahora: str) -> dict[str, list[dict]]:
    """Draft Obras, Variantes and Listados (``canal web``) from the live Shopify products.

    Uses only Shopify's published products (the Prodigi box frames, "Title / 8x8 / Black").
    Everything comes out as ``borrador``: nothing is on sale until Lorena approves the
    catalog. Print files and costs stay empty: Lorena supplies the files; the costs come
    from a Prodigi quote.
    """
    obras: dict[str, dict] = {}
    variantes: dict[str, dict] = {}
    listados: list[dict] = []
    codigos: dict[str, str] = {}
    for r in listados_shopify:
        if r.get("canal") != "shopify" or r.get("estado") != "publicado":
            continue
        partes = [x.strip() for x in str(r.get("titulo_en_canal") or "").split(" / ")]
        if len(partes) < 3:
            continue
        titulo, tamano, marco = partes[0], norm_tamano(partes[1]), partes[2]
        obra_id = slug(titulo)
        codigo = _iniciales(titulo)
        if codigos.setdefault(codigo, obra_id) != obra_id:
            codigo = obra_id.upper()
        sku = f"LM-{codigo}-{tamano.upper()}-{marco.upper()[:2]}"
        obras.setdefault(obra_id, {
            "obra_id": obra_id, "titulo": titulo, "estado": "borrador",
            "notas": "Creada desde la tienda Shopify; revisar título en español y medidas.",
        })
        variantes[sku] = {
            "sku": sku, "obra_id": obra_id, "linea": "US-POD", "tipo": "enmarcado",
            "tamano": tamano, "papel": "EMA 200gsm", "marco": f"box {marco.lower()}",
            "pod_proveedor": PROVEEDOR, "pod_sku": prodigi_box(tamano),
            "archivo_impresion": "", "costo_usd": "", "precio_usd": r.get("precio", ""),
            "estado": "borrador", "actualizado": ahora,
        }
        # the buyer-facing colour is the last word ("Black"); the Prodigi value is "black"
        variantes[sku]["marco"] = marco.lower()
        listados.append({
            "listado_ref": f"web-{sku}", "sku": sku, "linea": "US-POD", "canal": CANAL,
            "id_en_canal": sku, "titulo_en_canal": titulo, "url": f"/products/{obra_id}",
            "precio": r.get("precio", ""), "inventario": "", "estado": "borrador",
            "aprobacion_id": "", "ultima_sync": ahora, "id_producto_canal": obra_id,
            "ruta_pod": "prodigi-api", "imagen_url": r.get("imagen_url", ""),
            "descripcion": r.get("descripcion", ""), "etiquetas": r.get("etiquetas", ""),
            "tipo_producto": TIPO, "imagenes_producto": r.get("imagenes_producto", ""),
        })
    return {"Obras": list(obras.values()), "Variantes": list(variantes.values()),
            "Listados": listados}
