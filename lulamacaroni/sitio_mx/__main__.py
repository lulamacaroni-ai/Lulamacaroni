"""Command line for the Mexico catalog site. See ``lulamacaroni/sitio_mx/__init__.py``."""

from __future__ import annotations

import argparse
import functools
import sys
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import config
from . import construir as c
from . import demo
from .datos import Ajustes


def _fotos_por_defecto() -> Path | None:
    v = config.get("LULA_MX_FOTOS")
    return Path(v) if v else None


def _construir(args) -> c.Resultado:
    salida = Path(args.salida) if args.salida else c.carpeta_por_defecto()
    if args.demo:
        obras, variantes = demo.filas()
        fotos = demo.fotos(Path(tempfile.mkdtemp(prefix="sitio-mx-demo-")))
        ajustes = demo.AJUSTES_DEMO
    else:
        from ..localbook import open_workbook

        book = open_workbook()
        obras, variantes = book.read("Obras"), book.read("Variantes")
        fotos = Path(args.fotos) if args.fotos else _fotos_por_defecto()
        ajustes = Ajustes.desde_entorno()
    return c.construir(obras, variantes, fotos, salida, ajustes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m lulamacaroni.sitio_mx",
                                 description="Sitio de catálogo México (fase 1)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre, ayuda in (("construir", "construye el sitio desde la hoja"),
                          ("solicitar", "construye y pide la aprobación de Lorena"),
                          ("publicar", "construye, verifica la aprobación y empaca el sitio")):
        p = sub.add_parser(nombre, help=ayuda)
        p.add_argument("--fotos", help="carpeta con una foto web por obra: <obra_id>.jpg")
        p.add_argument("--salida", help="carpeta del sitio (por defecto data/sitio-mx)")
        if nombre == "construir":
            p.add_argument("--demo", action="store_true", help="obras de ejemplo, nada real")
        else:
            p.set_defaults(demo=False)
        if nombre == "publicar":
            p.add_argument("--aprobacion", required=True, help="id de la aprobación (apr-...)")
    v = sub.add_parser("vista", help="muestra el sitio construido en 127.0.0.1")
    v.add_argument("--salida")
    v.add_argument("--puerto", type=int, default=8771)
    args = ap.parse_args(argv)

    if args.cmd == "vista":
        carpeta = Path(args.salida) if args.salida else c.carpeta_por_defecto()
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(carpeta))
        srv = ThreadingHTTPServer(("127.0.0.1", args.puerto), handler)
        print(f"Sitio en http://127.0.0.1:{args.puerto}/index.html (Ctrl+C para salir)")
        srv.serve_forever()
        return 0

    r = _construir(args)
    print(c.reporte(r))
    if args.cmd == "construir":
        return 0

    from ..approval.store import open_store

    store = open_store()
    if args.cmd == "solicitar":
        rec = c.solicitar(store, r)
        print(f"\nAprobación pedida: {rec.aprobacion_id}. Lorena la revisa en Aprobar; "
              f"después: publicar --aprobacion {rec.aprobacion_id}")
        return 0

    from ..localbook import open_workbook

    zip_path = c.publicar(store, open_workbook(), r, args.aprobacion,
                          config.REPO_ROOT / "data" / "sitio-mx-publicado")
    print(f"\nListo: {zip_path}. Súbelo al hosting (docs/setup/sitio-mx.md).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
