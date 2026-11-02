"""Sample rows for ``--demo`` and the tests. Invented titles and amounts, no real data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def demo_rows(now: datetime | None = None) -> dict[str, list[dict]]:
    now = now or datetime.now(timezone.utc)
    titles = ["Sample Garden", "Sample Harbor", "Sample Owl"]
    listados = []
    for pi, title in enumerate(titles, start=1):
        for vi, size in enumerate(("8x10", "12x16", "18x24"), start=1):
            listados.append({
                "listado_ref": f"shopify-{pi}{vi}", "sku": f"DEMO-{pi}-{size}" if pi != 3 else "",
                "linea": "US-POD", "canal": "shopify", "id_en_canal": f"{pi}{vi}",
                "titulo_en_canal": f"{title} / {size}", "url": "", "precio": 60 + 20 * vi,
                "inventario": "", "estado": "publicado" if pi != 2 else "pausado",
                "ultima_sync": _iso(now), "id_producto_canal": str(pi),
                "ruta_pod": ("prodigi-app", "frame-it-easy-app", "manual")[pi - 1],
            })
    pedidos = []
    plan = [  # (days ago, product, size idx, price, state, route, refund)
        (0.2, 0, 2, 100.0, "recibido", "prodigi-app", 0),
        (1.5, 1, 1, 80.0, "en-produccion", "prodigi-app", 0),
        (3, 2, 3, 120.0, "recibido", "manual", 0),
        (5, 0, 1, 80.0, "enviado", "prodigi-app", 0),
        (9, 0, 2, 100.0, "entregado", "prodigi-app", 0),
        (12, 1, 2, 100.0, "reembolsado", "prodigi-app", 100.0),
    ]
    for n, (days, pi, vi, price, estado, ruta, refund) in enumerate(plan, start=1001):
        pedidos.append({
            "linea_pedido_id": f"shopify-{n}-1", "pedido_id": f"shopify-{n}", "linea": "US-POD",
            "canal": "shopify", "fecha": _iso(now - timedelta(days=days)),
            "sku": listados[pi * 3 + vi - 1]["sku"], "cantidad": 1, "moneda": "USD",
            "venta_bruta": price, "descuento": 0, "impuesto_cobrado": 0, "envio_cobrado": 0,
            "reembolso": refund, "ruta_pod": ruta, "estado": estado,             "producto": f"{titles[pi]} - {('8x10', '12x16', '18x24')[vi - 1]}",
            "tracking": "DEMO123" if estado in ("enviado", "entregado") else "",
            "numero_canal": f"#{n}",
            # Shopify Payments fee (2.9% + 30¢); Prodigi charge once Prodigi has billed it
            "comision_canal": round(price * 0.029 + 0.30, 2),
            **({"pod_pedido_id": f"ord_demo{n}", "costo_pod": 28.0 + 6 * vi, "envio_pod": 7.5}
               if ruta == "prodigi-app" and estado != "recibido" else {}),
        })
    fuentes = [{"fuente": "shopify", "ultima_actualizacion": _iso(now - timedelta(minutes=12)),
                "estado": "ok", "filas": len(listados) + len(pedidos), "nota": ""},
               {"fuente": "shopify-pagos", "ultima_actualizacion": _iso(now - timedelta(minutes=12)),
                "estado": "ok", "filas": 2, "nota": ""}]
    pagos = [
        {"pago_id": "shopify-payout-1", "linea": "US-POD", "canal": "shopify",
         "fecha": _iso(now - timedelta(days=8)), "moneda": "USD", "monto_depositado": 94.81,
         "comisiones": 5.19, "retenciones": 0, "reembolsos": 0, "conciliado": "no",
         "estado": "pagado"},
        {"pago_id": "shopify-payout-2", "linea": "US-POD", "canal": "shopify",
         "fecha": _iso(now + timedelta(days=1)), "moneda": "USD", "monto_depositado": 77.38,
         "comisiones": 2.62, "retenciones": 0, "reembolsos": 0, "conciliado": "no",
         "estado": "en-transito"},
    ]
    return {"Listados": listados, "Pedidos": pedidos, "Fuentes": fuentes, "Pagos": pagos}


def fill_demo(book, now: datetime | None = None) -> None:
    from ..margen import recalcular

    for tab_name, rows in demo_rows(now).items():
        book.upsert(tab_name, rows)
    recalcular(book)
