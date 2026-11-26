"""Put products on sale in the store, only with Lorena's approval.

    python -m lulamacaroni.tienda.publicar semilla --dry-run   # what the Shopify products become
    python -m lulamacaroni.tienda.publicar semilla             # write them as drafts (borrador)
    python -m lulamacaroni.tienda.publicar solicitar           # ask Lorena to approve the catalog
    python -m lulamacaroni.tienda.publicar publicar apr-...    # after she approves: on sale

The approval covers the exact catalog (every SKU, title, price and photo) and the exact
policy texts. Any change after she approves needs a new approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime

from ..approval.gate import assert_approved, mark_executed, request_approval
from .ajustes import Ajustes
from .catalogo import CANAL, semilla
from .paginas import POLITICAS, texto_politica

TIPO = "listado"


def _ahora() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def borradores(listados: list[dict]) -> list[dict]:
    return [r for r in listados if r.get("canal") == CANAL and r.get("estado") in ("borrador", "en-aprobacion")]


def contenido(listados: list[dict], ajustes: Ajustes) -> dict:
    """What Lorena approves: each listing as buyers will see it, plus the policies' fingerprints."""
    filas = sorted(({"sku": r["sku"], "titulo": r.get("titulo_en_canal", ""), "precio": str(r.get("precio", "")),
                     "fotos": str(r.get("imagenes_producto") or r.get("imagen_url") or ""),
                     "descripcion_huella": hashlib.sha256(str(r.get("descripcion", "")).encode()).hexdigest()[:16]}
                    for r in listados), key=lambda x: x["sku"])
    politicas = {k: hashlib.sha256(texto_politica(ajustes, k).encode()).hexdigest()[:16] for k in POLITICAS}
    return {"canal": CANAL, "listados": filas, "politicas": politicas}


def solicitar(book, store, ajustes: Ajustes):
    pendientes = borradores(book.read("Listados"))
    if not pendientes:
        raise SystemExit("No hay listados en borrador para la tienda.")
    c = contenido(pendientes, ajustes)
    productos = sorted({r.get("titulo_en_canal", "") for r in pendientes})
    rec = request_approval(
        store, tipo=TIPO, linea="US-POD", creado_por="tienda",
        resumen=(f"Poner a la venta en lulamacaroni.com {len(productos)} obra(s) con "
                 f"{len(pendientes)} opción(es) de tamaño y marco, y publicar las políticas "
                 f"(envíos, devoluciones, privacidad, términos)."),
        contenido=c)
    book.upsert("Listados", [{"listado_ref": r["listado_ref"], "linea": "US-POD", "canal": CANAL,
                              "estado": "en-aprobacion", "aprobacion_id": rec.aprobacion_id}
                             for r in pendientes])
    return rec


def publicar(book, store, ajustes: Ajustes, aprobacion_id: str) -> int:
    rec = store.get(aprobacion_id)
    pendientes = [r for r in borradores(book.read("Listados")) if r.get("aprobacion_id") == aprobacion_id]
    assert_approved(rec, tipo=TIPO, contenido=contenido(pendientes, ajustes))
    skus = {r["sku"] for r in pendientes}
    book.upsert("Listados", [{"listado_ref": r["listado_ref"], "linea": "US-POD", "canal": CANAL,
                              "estado": "publicado", "ultima_sync": _ahora()} for r in pendientes])
    book.upsert("Variantes", [{"sku": v["sku"], "linea": v.get("linea") or "US-POD", "estado": "activa"}
                              for v in book.read("Variantes")
                              if v.get("sku") in skus and v.get("estado") != "descontinuada"])
    mark_executed(store, rec)
    return len(pendientes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Catálogo de la tienda propia")
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("semilla", help="crear borradores desde los productos de Shopify")
    s.add_argument("--dry-run", action="store_true")
    sub.add_parser("solicitar", help="pedir a Lorena que apruebe el catálogo")
    p = sub.add_parser("publicar", help="poner a la venta lo aprobado")
    p.add_argument("aprobacion_id")
    args = parser.parse_args(argv)

    from ..approval.store import SheetsStore, open_store
    from ..localbook import open_workbook
    from ..workbook import Workbook

    book = open_workbook()
    ajustes = Ajustes.desde_entorno()
    if args.cmd == "semilla":
        filas = semilla(book.read("Listados"), _ahora())
        existentes = {r.get("listado_ref") for r in book.read("Listados")}
        filas["Listados"] = [r for r in filas["Listados"] if r["listado_ref"] not in existentes]
        for tab, rows in filas.items():
            print(f"{tab}: {len(rows)} fila(s)")
        if args.dry_run:
            print(json.dumps(filas["Variantes"][:3], ensure_ascii=False, indent=2))
            return 0
        for tab in ("Obras", "Variantes", "Listados"):
            if filas[tab]:
                book.upsert(tab, filas[tab])
        return 0
    store = SheetsStore(book) if isinstance(book, Workbook) else open_store()
    if args.cmd == "solicitar":
        rec = solicitar(book, store, ajustes)
        print(f"Aprobación {rec.aprobacion_id} creada; Lorena la ve en Aprobar.")
        return 0
    n = publicar(book, store, ajustes, args.aprobacion_id)
    print(f"{n} opción(es) a la venta en la tienda.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
