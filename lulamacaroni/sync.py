"""Run every connected sync in one go, then print today's alerts.

    python -m lulamacaroni.sync            # Shopify (orders, listings, payouts, customers), then Prodigi
                                           # costs, then Pinterest (when PINTEREST_ACCESS_TOKEN is set)

This is the one command a daily routine runs. Each source is independent: if one fails,
the others still run, and the failed one is marked ``error`` in the Fuentes tab so the app
raises "la última sincronización falló" instead of quietly showing old numbers as current.
The error note keeps only the error type, never the message (it can echo a response body).
The last good update time is kept, so the app never shows failed data as fresh.

Reads Shopify, Prodigi and Pinterest only; writes only the workbook. Etsy and QuickBooks have no
account yet and stay "fuente no conectada".
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Callable

from . import config


def _shopify() -> None:
    from .connectors import shopify

    shopify.main([])


def _prodigi() -> None:
    from .connectors import prodigi

    prodigi.main(["--sync"])


def _pinterest() -> None:
    from .connectors import pinterest

    pinterest.main([])


def _prodigi_fuente() -> str:
    # same key the connector stamps: a sandbox run must never look like live data
    return "prodigi" if config.get("PRODIGI_ENV", "sandbox") == "live" else "prodigi-sandbox"


STEPS: list[tuple[str, Callable[[], str], Callable[[], None]]] = [
    ("Shopify", lambda: "shopify", _shopify),
    ("Prodigi", _prodigi_fuente, _prodigi),
]


def pasos() -> list:
    """The steps to run. Pinterest joins only once its token is set: a source that was never
    connected stays "sin conectar", not "error"."""
    out = list(STEPS)
    if config.get("PINTEREST_ACCESS_TOKEN"):
        out.append(("Pinterest", lambda: "pinterest", _pinterest))
    return out


def mark_error(wb, fuente: str, exc: BaseException) -> None:
    """Mark ``fuente`` as failed, keeping its last good update time (or none)."""
    previo = next((r for r in wb.read("Fuentes") if r.get("fuente") == fuente), {})
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    wb.upsert("Fuentes", [{
        "fuente": fuente,
        "ultima_actualizacion": previo.get("ultima_actualizacion", ""),
        "estado": "error",
        "filas": previo.get("filas", ""),
        "nota": f"falló el {ahora} ({type(exc).__name__}); los números pueden estar incompletos",
    }])


def run(wb=None, steps=None, out=sys.stdout) -> int:
    """Run each step; return how many failed."""
    from .localbook import open_workbook

    wb = wb if wb is not None else open_workbook()
    fallas = 0
    for nombre, fuente, step in steps if steps is not None else pasos():
        print(f"== {nombre}", file=out, flush=True)
        try:
            step()
        except Exception as exc:  # noqa: BLE001 - one source failing must not stop the rest
            fallas += 1
            print(f"{nombre}: falló ({type(exc).__name__})", file=out)
            try:
                mark_error(wb, fuente(), exc)
            except Exception as exc2:  # noqa: BLE001
                print(f"{nombre}: tampoco se pudo marcar el error ({type(exc2).__name__})",
                      file=out)
    return fallas


def main(argv: list[str] | None = None) -> int:
    fallas = run()
    from .app import alertas

    alertas.main()
    return 1 if fallas else 0


if __name__ == "__main__":
    raise SystemExit(main())
