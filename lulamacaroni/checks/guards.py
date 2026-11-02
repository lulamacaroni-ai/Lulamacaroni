"""Catalog guards.

* Discontinued POD product (US line): a live listing whose Prodigi SKU is no longer
  offered, or whose variant is marked ``descontinuada``. Target: caught within 15 minutes.
* Sold original (Mexico line): an original marked ``vendida`` or ``reservada`` that
  still shows on the Mexico catalog site.

Both return findings for the ``Excepciones`` tab; neither unpublishes anything by itself.
Taking a listing down goes through the approval gate like any other change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class Finding:
    linea: str
    tipo: str
    referencia: str
    detalle: str


def discontinued_pod(variantes: Iterable[dict], listados: Iterable[dict],
                     pod_available: Callable[[str], bool]) -> list[Finding]:
    by_sku = {v["sku"]: v for v in variantes if v.get("linea") == "US-POD"}
    findings = []
    for l in listados:
        if l.get("linea") != "US-POD" or l.get("estado") != "publicado":
            continue
        v = by_sku.get(l["sku"])
        if v is None:
            findings.append(Finding("US-POD", "sku-sin-variante", l["listado_ref"],
                                    f"{l['sku']} publicado en {l['canal']} sin variante en el catálogo"))
        elif v.get("estado") == "descontinuada":
            findings.append(Finding("US-POD", "pod-descontinuado", l["listado_ref"],
                                    f"{l['sku']} está descontinuada pero sigue en {l['canal']}"))
        elif v.get("pod_sku") and not pod_available(v["pod_sku"]):
            findings.append(Finding("US-POD", "pod-descontinuado", l["listado_ref"],
                                    f"Prodigi ya no ofrece {v['pod_sku']} ({l['sku']} en {l['canal']})"))
    return findings


def sold_original(obras: Iterable[dict], variantes: Iterable[dict],
                  listados: Iterable[dict]) -> list[Finding]:
    unavailable = {o["obra_id"] for o in obras if o.get("estado") in ("vendida", "reservada")}
    obra_by_sku = {v["sku"]: v["obra_id"] for v in variantes if v.get("tipo") == "original"}
    findings = []
    for l in listados:
        if l.get("linea") != "MX-original" or l.get("estado") != "publicado":
            continue
        obra = obra_by_sku.get(l["sku"])
        if obra in unavailable:
            findings.append(Finding("MX-original", "original-vendido", l["listado_ref"],
                                    f"La obra {obra} ya no está disponible y sigue en {l['canal']}"))
    return findings
