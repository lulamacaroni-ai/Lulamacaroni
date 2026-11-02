"""Catálogo: every product and variant with who prints it, its cost, margin and print file.

Lorena's requirements, section 2 (catálogo maestro) and 9 (POD): each SKU tied to its
artwork, price, cost, printer and print file, with US and Mexico kept apart. Sources:

* ``Listados``   what the channels have (Shopify today): status, variants, SKU, price and
                 the printer each variant routes to (from its stock locations).
* ``Variantes``  the master row per SKU, filled by hand or by a later sync: artwork,
                 size, print file and its pixel size, cost quote, Mexico price.
* ``Obras``      the artwork itself; Mexico originals live only here and in Variantes.
* ``Pedidos``    real margin per SKU once it has sold.

Nothing here edits a file: the print-file check only reports (never crop, stretch or
regenerate). Pure functions over rows, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..checks.resolution import Result, check, parse_size
from . import metrics as m

# Shopify Payments on the Basic plan (US cards). Only for the estimate before a sale;
# a real sale uses the fee Shopify actually charged (Pedidos.comision_canal).
FEE_PCT, FEE_FIJO = 0.029, 0.30

SIN_IMPRENTA = {"manual", "desconocida"}
FUENTE_LISTADOS = "Shopify (productos, variantes y ubicaciones)"
FUENTE_HOJA = "Libro de datos (pestañas Variantes y Obras)"


@dataclass
class Archivo:
    estado: str      # ideal | aceptable | baja-resolucion | no-apto | sin-revisar
    motivo: str

    @property
    def ok(self) -> bool:
        return self.estado in ("ideal", "aceptable")


def revisar_archivo(variante: dict | None) -> Archivo:
    """Print-file check for one SKU from its Variantes row. Reports only."""
    if not variante:
        return Archivo("sin-revisar", "SKU sin fila en Variantes")
    if not variante.get("archivo_impresion"):
        return Archivo("sin-revisar", "falta el archivo de impresión en Variantes")
    px, tam = (variante.get("archivo_px") or "").strip(), (variante.get("tamano") or "").strip()
    if not px or not tam:
        return Archivo("sin-revisar", "faltan " + " y ".join(
            n for n, v in (("los píxeles del archivo", px), ("el tamaño", tam)) if not v))
    try:
        w, h = (int(float(x)) for x in px.lower().replace("×", "x").split("x"))
        r: Result = check(w, h, *parse_size(tam))
    except ValueError:
        return Archivo("sin-revisar", f"no se entiende archivo_px={px!r} o tamano={tam!r}")
    return Archivo(r.estado, r.motivo)


@dataclass
class Variante:
    listado: dict
    etiqueta: str
    sku: str
    precio: float | None
    ruta: str
    maestro: dict | None        # Variantes row, if any
    costo: m.Dato
    margen: m.Dato
    archivo: Archivo
    margen_real: float | None = None
    ventas: int = 0


@dataclass
class Ficha:
    """One product on a channel with its variants and, if linked, its artwork."""
    producto: m.Producto
    variantes: list[Variante]
    obras: list[dict] = field(default_factory=list)

    @property
    def con_costo(self) -> int:
        return sum(1 for v in self.variantes if v.costo.calidad != "faltante")

    @property
    def archivos_mal(self) -> int:
        return sum(1 for v in self.variantes if v.archivo.estado in ("no-apto", "baja-resolucion"))

    @property
    def archivos_sin(self) -> int:
        return sum(1 for v in self.variantes if v.archivo.estado == "sin-revisar")


def _etiqueta(listado: dict) -> str:
    t = listado.get("titulo_en_canal") or ""
    return t.split(" / ", 1)[1] if " / " in t else "única"


def costo_dato(maestro: dict | None, actualizado: datetime) -> m.Dato:
    definicion = ("Coste de impresión más envío de la imprenta a EUA para una pieza, según "
                  "cotización guardada en Variantes.costo_usd. El coste real llega con cada "
                  "pedido de Prodigi.")
    valor = m.num((maestro or {}).get("costo_usd"))
    if valor is None:
        nota = "SKU sin fila en Variantes" if not maestro else "falta costo_usd en Variantes"
        return m.faltante("Coste", FUENTE_HOJA, "cotización vigente", definicion, nota)
    return m.Dato("Coste", valor, "estimado", FUENTE_HOJA, "cotización vigente", definicion,
                  actualizado, "usd", nota="cotización, no cargo real")


def margen_dato(precio: float | None, costo: m.Dato, actualizado: datetime) -> m.Dato:
    definicion = ("Precio − comisión de Shopify Payments estimada (2.9% + 30¢) − coste de "
                  "Variantes. Sin descuentos, impuestos, envío cobrado ni anuncios.")
    if precio is None or costo.calidad == "faltante":
        nota = "falta el precio" if precio is None else "falta el coste"
        return m.faltante("Margen estimado", "Listados + Variantes", "por pieza", definicion, nota)
    fee = round(precio * FEE_PCT + FEE_FIJO, 2)
    return m.Dato("Margen estimado", round(precio - fee - costo.valor, 2), "estimado",
                  "Listados + Variantes", "por pieza", definicion, actualizado, "usd",
                  nota=f"comisión estimada {fee:.2f}")


def fichas(productos: list[m.Producto], listados: list[dict], variantes: list[dict],
           obras: list[dict], pedidos_rows: list[dict], now: datetime) -> list[Ficha]:
    by_sku = {v.get("sku"): v for v in variantes if v.get("sku")}
    obra_by_id = {o.get("obra_id"): o for o in obras if o.get("obra_id")}
    ventas: dict[str, list[float]] = {}
    for r in pedidos_rows:
        if r.get("sku") and r.get("calidad_dato") == "real" and r.get("estado") in m.VIVOS:
            ventas.setdefault(r["sku"], []).append(m.num(r.get("margen_contribucion")) or 0)
    grupos: dict[tuple[str, str], list[dict]] = {}
    for r in listados:
        pid = str(r.get("id_producto_canal") or r.get("url") or
                  (r.get("titulo_en_canal") or "").split(" / ")[0])
        grupos.setdefault((r.get("canal", ""), pid), []).append(r)
    out = []
    for p in productos:
        vs = []
        for r in grupos.get((p.canal, p.id_producto), []):
            sku = r.get("sku") or ""
            maestro = by_sku.get(sku) if sku else None
            precio = m.num(r.get("precio"))
            costo = costo_dato(maestro, now)
            reales = ventas.get(sku, [])
            vs.append(Variante(r, _etiqueta(r), sku, precio, r.get("ruta_pod") or "",
                               maestro, costo, margen_dato(precio, costo, now),
                               revisar_archivo(maestro),
                               round(sum(reales) / len(reales), 2) if reales else None,
                               len(reales)))
        ids = dict.fromkeys(v.maestro.get("obra_id") for v in vs if v.maestro and
                            v.maestro.get("obra_id"))
        out.append(Ficha(p, vs, [obra_by_id[i] for i in ids if i in obra_by_id]))
    return out


@dataclass
class Original:
    """A Mexico original: an artwork row plus its MX-original variant (if any)."""
    obra: dict
    variante: dict | None

    @property
    def precio_mxn(self) -> float | None:
        return m.num((self.variante or {}).get("precio_mxn_con_iva"))


def originales(obras: list[dict], variantes: list[dict]) -> list[Original]:
    mx = {}
    for v in variantes:
        if v.get("linea") == "MX-original" and v.get("tipo") == "original":
            mx.setdefault(v.get("obra_id"), v)
    obra_by_id = {o.get("obra_id"): o for o in obras}
    out = [Original(obra_by_id.get(oid) or {"obra_id": oid}, v) for oid, v in mx.items()]
    out.sort(key=lambda o: (o.obra.get("titulo_es") or o.obra.get("titulo") or "").lower())
    return out


def resumen(fs: list[Ficha], origs: list[Original], obras: list[dict],
            fuentes: dict[str, m.EstadoFuente], now: datetime) -> list[m.Dato]:
    """The counts on top of the Catálogo screen, each with its source."""
    shop = fuentes["shopify"]
    act = shop.actualizado
    per = "a la fecha (última sincronización)"
    if not shop.conectada:
        nota = "Shopify no está conectado."
        datos = [m.faltante(e, FUENTE_LISTADOS, per, d, nota, "n") for e, d in (
            ("Productos en venta", "Productos activos en la tienda."),
            ("Variantes en venta", "Variantes de los productos activos."),
            ("Sin imprenta", "Variantes en venta que no llegan a ninguna imprenta."),
            ("Con coste", "Variantes en venta con coste conocido."))]
    else:
        venta = [f for f in fs if f.producto.estado == "publicado"]
        vv = [v for f in venta for v in f.variantes]
        datos = [
            m.Dato("Productos en venta", len(venta), "real", FUENTE_LISTADOS, per,
                   "Productos con estado activo en Shopify (visibles en la tienda).", act, "n",
                   nota=f"{len(fs)} en total", enlace="/catalogo?f=venta"),
            m.Dato("Variantes en venta", len(vv), "real", FUENTE_LISTADOS, per,
                   "Variantes (tamaño, marco…) de los productos activos.", act, "n",
                   nota=f"{sum(1 for v in vv if not v.sku)} sin SKU"),
            m.Dato("Sin imprenta", sum(1 for v in vv if v.ruta in SIN_IMPRENTA), "real",
                   FUENTE_LISTADOS, per,
                   "Variantes en venta cuya ubicación de inventario es “Manual” o no está "
                   "clara: un pedido no le llega a Prodigi ni a Frame It Easy.", act, "n",
                   enlace="/catalogo?f=avisos"),
            m.Dato("Con coste", sum(1 for v in vv if v.costo.calidad != "faltante"), "real",
                   FUENTE_HOJA, "cotización vigente",
                   "Variantes en venta con coste cotizado en Variantes.costo_usd. Sin coste no "
                   "hay margen estimado.", now, "n", nota=f"de {len(vv)}"),
        ]
    if not obras:
        datos.append(m.faltante(
            "Originales MX", FUENTE_HOJA, "a la fecha",
            "Obras originales a la venta en México (Variantes con línea MX-original).",
            "Aún no se cargan obras en la hoja.", "n", "/catalogo?f=mx"))
    else:
        disp = sum(1 for o in origs if o.obra.get("estado") == "activa")
        datos.append(m.Dato(
            "Originales MX", len(origs), "real", FUENTE_HOJA, "a la fecha",
            "Obras originales con variante MX-original en la hoja, de cualquier estado.", now,
            "n", nota=f"{disp} disponible(s)", enlace="/catalogo?f=mx"))
    return datos


def avisos_archivo(fs: list[Ficha]) -> list[tuple[str, int]]:
    """(product title, variants whose print file is not printable) for live products."""
    return [(f.producto.titulo, f.archivos_mal) for f in fs
            if f.producto.estado == "publicado" and f.archivos_mal]
