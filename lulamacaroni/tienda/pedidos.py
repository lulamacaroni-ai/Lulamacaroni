"""From a paid Stripe checkout to order rows, a customer row and Lorena's approval request.

``registrar`` runs when Stripe's ``checkout.session.completed`` webhook arrives (and again if
Stripe retries it: the order is keyed by the Checkout Session id, so a retry changes nothing).

What lands in the workbook: the order lines (``Pedidos``, ``canal = web``), the buyer as
``stripe-<customer id>`` with first name + last initial, state and country (``Clientes``), and
a ``pedido-tienda`` approval whose content is exactly what Prodigi will receive except the
street address, which is replaced by its fingerprint. Email, phone and street address stay in
Stripe.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from ..approval.gate import request_approval
from .catalogo import Catalogo

CANAL = "web"
LINEA = "US-POD"
FEE_PCT, FEE_FIJO = 0.029, 0.30   # Stripe US cards; the real fee replaces it later
PRIMER_NUMERO = 1001


def envio_de(session: dict) -> dict:
    """Shipping name + address from a Checkout Session (both API shapes)."""
    info = ((session.get("collected_information") or {}).get("shipping_details")
            or session.get("shipping_details") or {})
    return {"name": info.get("name") or "", "address": dict(info.get("address") or {})}


def huella_direccion(envio: dict) -> str:
    """Fingerprint of who and where: changes if any part of the name or address changes."""
    a = envio.get("address") or {}
    partes = {k: re.sub(r"\s+", " ", str(a.get(k) or "")).strip().lower()
              for k in ("line1", "line2", "city", "state", "postal_code", "country")}
    partes["name"] = re.sub(r"\s+", " ", str(envio.get("name") or "")).strip().lower()
    return hashlib.sha256(json.dumps(partes, sort_keys=True).encode()).hexdigest()


def destinatario_prodigi(envio: dict) -> dict:
    a = envio.get("address") or {}
    direccion = {"line1": a.get("line1") or "", "postalOrZipCode": a.get("postal_code") or "",
                 "countryCode": a.get("country") or "US", "townOrCity": a.get("city") or "",
                 "stateOrCounty": a.get("state") or ""}
    if a.get("line2"):
        direccion["line2"] = a["line2"]
    return {"name": envio.get("name") or "", "address": direccion}


def nombre_corto(nombre: str) -> str:
    """'Mary Ann Smith' -> 'Mary Ann S.' (what the workbook may keep)."""
    partes = (nombre or "").split()
    if len(partes) < 2:
        return partes[0] if partes else ""
    return " ".join(partes[:-1]) + f" {partes[-1][0]}."


def _usd(centavos) -> float:
    return round((centavos or 0) / 100, 2)


def siguiente_numero(pedidos: list[dict]) -> str:
    nums = [int(m.group(1)) for r in pedidos if r.get("canal") == CANAL
            for m in [re.fullmatch(r"LM-(\d+)", str(r.get("numero_canal") or ""))] if m]
    return f"LM-{max(nums) + 1 if nums else PRIMER_NUMERO}"


@dataclass
class Resultado:
    numero: str
    nuevo: bool
    lineas: list[dict] = field(default_factory=list)
    aprobacion_id: str = ""
    problemas: list[str] = field(default_factory=list)
    correo: dict = field(default_factory=dict)   # what to email (no address in it)


def contenido_aprobacion(numero: str, session_id: str, items: list[dict], envio: dict,
                         total: float) -> dict:
    a = envio.get("address") or {}
    return {
        "pedido": numero, "canal": CANAL, "stripe_checkout": session_id,
        "shippingMethod": "Standard", "items": items,
        "destino": {"estado": a.get("state") or "", "pais": a.get("country") or ""},
        "direccion_huella": huella_direccion(envio), "cobrado_usd": round(total, 2),
    }


def registrar(session: dict, book, store, catalogo: Catalogo, ahora: datetime) -> Resultado:
    """Record a paid checkout. ``session`` is the Checkout Session read back from Stripe with
    its line items and products expanded (``StripeClient.checkout``)."""
    sid = session["id"]
    pedidos = book.read("Pedidos")
    previas = [r for r in pedidos if r.get("pedido_id") == sid]
    if previas:
        return Resultado(str(previas[0].get("numero_canal")), nuevo=False)
    if session.get("payment_status") != "paid":
        raise ValueError(f"{sid} is not paid ({session.get('payment_status')})")

    numero = siguiente_numero(pedidos)
    fecha = datetime.fromtimestamp(int(session.get("created") or ahora.timestamp()),
                                   tz=ahora.tzinfo).isoformat()
    envio = envio_de(session)
    region = (envio["address"].get("state") or "")
    pais = envio["address"].get("country") or ""
    cliente = f"stripe-{session['customer']}" if session.get("customer") else ""
    total = _usd(session.get("amount_total"))
    envio_cobrado = _usd((session.get("shipping_cost") or {}).get("amount_total")
                         or (session.get("total_details") or {}).get("amount_shipping"))
    comision = round(total * FEE_PCT + FEE_FIJO, 2)

    res = Resultado(numero, nuevo=True)
    filas, items, correo_lineas = [], [], []
    for i, li in enumerate((session.get("line_items") or {}).get("data") or []):
        prod = ((li.get("price") or {}).get("product") or {})
        sku = str((prod.get("metadata") or {}).get("sku") or "")
        cantidad = int(li.get("quantity") or 1)
        hallado = catalogo.buscar_sku(sku) if sku else None
        filas.append({
            "linea_pedido_id": f"{sid}-{i + 1}", "pedido_id": sid, "linea": LINEA, "canal": CANAL,
            "fecha": fecha, "sku": sku, "cantidad": cantidad, "moneda": "USD",
            "venta_bruta": _usd(li.get("amount_subtotal")),
            "descuento": _usd(li.get("amount_discount")),
            "impuesto_cobrado": _usd(li.get("amount_tax")),
            "envio_cobrado": envio_cobrado if i == 0 else 0.0,
            "comision_canal": comision if i == 0 else 0.0,
            "costo_pod": "", "envio_pod": "", "reembolso": 0.0, "margen_contribucion": "",
            "ruta_pod": "prodigi-api", "pod_pedido_id": "", "tracking": "", "estado": "recibido",
            "calidad_dato": "estimado", "producto": li.get("description") or prod.get("name") or "",
            "numero_canal": numero, "origen_estado": "ok" if session.get("metadata") else "pendiente",
            "origen_fuente": (session.get("metadata") or {}).get("utm_source", ""),
            "utm_fuente": (session.get("metadata") or {}).get("utm_source", ""),
            "utm_medio": (session.get("metadata") or {}).get("utm_medium", ""),
            "utm_campana": (session.get("metadata") or {}).get("utm_campaign", ""),
            "referente": (session.get("metadata") or {}).get("referente", ""),
            "cliente_id": cliente, "imagen_url": hallado[0].imagen if hallado else "",
        })
        correo_lineas.append({"nombre": prod.get("name") or sku, "detalle": prod.get("description") or "",
                              "cantidad": cantidad, "total": _usd(li.get("amount_total"))})
        if hallado is None:
            res.problemas.append(f"{sku or 'línea sin SKU'}: no está en el catálogo de la tienda")
            continue
        _, op = hallado
        if not op.pod_sku:
            res.problemas.append(f"{sku}: falta el SKU de Prodigi en Variantes")
        if not op.archivo:
            res.problemas.append(f"{sku}: falta el archivo de impresión en Variantes")
        elif not op.archivo.startswith("https://"):
            res.problemas.append(f"{sku}: el archivo de impresión debe ser un enlace https://")
        items.append({"merchantReference": sku, "sku": op.pod_sku, "copies": cantidad,
                      "sizing": "fitPrintArea",  # never crop or stretch the art
                      "attributes": {"color": op.color_pod},
                      "assets": [{"printArea": "default", "url": op.archivo}]})
    if res.problemas:
        for f in filas:
            f["estado"] = "excepcion"
    book.upsert("Pedidos", filas)
    res.lineas = filas

    if cliente:
        previos = {r.get("cliente_id"): r for r in book.read("Clientes")}
        antes = previos.get(cliente) or {}
        n = int(float(antes.get("pedidos") or 0)) + 1
        suma = round(float(antes.get("total") or 0) + total, 2)
        book.upsert("Clientes", [{
            "cliente_id": cliente, "linea": LINEA, "canal_origen": antes.get("canal_origen") or CANAL,
            "nombre": nombre_corto((session.get("customer_details") or {}).get("name") or envio["name"]),
            "pais": pais, "region": region, "pedidos": n, "total": suma, "moneda": "USD",
            "primer_pedido": antes.get("primer_pedido") or fecha, "ultimo_pedido": fecha,
            "cliente_desde": antes.get("cliente_desde") or fecha,
            "consentimiento_email": antes.get("consentimiento_email") or "desconocido",
            "ultima_sync": ahora.isoformat(),
        }])

    if res.problemas:
        book.upsert("Excepciones", [{
            "excepcion_id": f"exc-{numero}", "linea": LINEA, "tipo": "pedido-tienda",
            "referencia": numero, "detalle": "; ".join(res.problemas), "creada_en": ahora.isoformat(),
            "responsable": "Lorena", "estado": "abierta"}])
    else:
        contenido = contenido_aprobacion(numero, sid, items, envio, total)
        piezas = ", ".join(f"{li['cantidad']}× {li['nombre']} ({li['detalle']})" for li in correo_lineas)
        rec = request_approval(
            store, tipo="pedido-tienda", linea=LINEA, creado_por="tienda",
            resumen=(f"Enviar a Prodigi el pedido {numero} de la tienda: {piezas}. "
                     f"Cobrado US${total:.2f}. Destino {region or '?'}, {pais or '?'}."),
            contenido=contenido, now=ahora)
        res.aprobacion_id = rec.aprobacion_id

    detalles = session.get("customer_details") or {}
    res.correo = {
        "para": detalles.get("email") or "", "numero": numero,
        "nombre": ((detalles.get("name") or envio["name"]).split() or [""])[0],
        "lineas": correo_lineas, "subtotal": _usd(session.get("amount_subtotal")),
        "envio": envio_cobrado, "impuesto": _usd((session.get("total_details") or {}).get("amount_tax")),
        "total": total,
    }
    return res
