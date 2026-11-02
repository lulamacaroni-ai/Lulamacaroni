"""Contribution margin per ``Pedidos`` line, with its data quality.

One rule decides every line, so Shopify, Prodigi and any later connector only fill in
their own columns and then call :func:`recalcular`:

    margen_contribucion = venta_bruta − descuento − reembolso + envio_cobrado
                          − comision_canal − costo_pod − envio_pod

Sales tax collected is left out on both sides: it is passed through to the state.
Ad spend is not per line; the Inicio screen subtracts it for the period.

``calidad_dato`` for the line:

* ``real``      every cost is known, and the print cost comes from Prodigi's own charge
                (the line has a ``pod_pedido_id``).
* ``estimado``  every cost is known, but the print cost is a quote or a price list
                (``costo_pod`` filled without a ``pod_pedido_id``). Shown with "~".
* ``faltante``  a fee or a print cost is missing. ``margen_contribucion`` stays empty:
                a missing cost is never read as zero.

``faltan(row)`` names what is missing, for the Pedidos screen.
"""

from __future__ import annotations

COSTOS = ("comision_canal", "costo_pod", "envio_pod")
NOMBRE_COSTO = {"comision_canal": "comisión del canal", "costo_pod": "coste de impresión",
                "envio_pod": "envío de la imprenta"}


def _num(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def faltan(row: dict) -> list[str]:
    """Columns this line still needs before its margin can be computed."""
    return [c for c in COSTOS if _num(row.get(c)) is None]


def calcular(row: dict) -> dict:
    """``{"margen_contribucion": ..., "calidad_dato": ...}`` for one Pedidos row."""
    if faltan(row):
        return {"margen_contribucion": "", "calidad_dato": "faltante"}
    ingreso = ((_num(row.get("venta_bruta")) or 0) - (_num(row.get("descuento")) or 0)
               - (_num(row.get("reembolso")) or 0) + (_num(row.get("envio_cobrado")) or 0))
    costos = sum(_num(row.get(c)) or 0 for c in COSTOS)
    calidad = "real" if row.get("pod_pedido_id") else "estimado"
    return {"margen_contribucion": round(ingreso - costos, 2), "calidad_dato": calidad}


def recalcular(wb) -> int:
    """Recompute every Pedidos line in the workbook; returns how many changed."""
    cambios = []
    for row in wb.read("Pedidos"):
        nuevo = calcular(row)
        if (str(row.get("margen_contribucion", "")) != str(nuevo["margen_contribucion"])
                or row.get("calidad_dato") != nuevo["calidad_dato"]):
            cambios.append({"linea_pedido_id": row["linea_pedido_id"],
                            "linea": row.get("linea") or "US-POD", **nuevo})
    if cambios:
        wb.upsert("Pedidos", cambios)
    return len(cambios)
