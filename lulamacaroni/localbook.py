"""A local stand-in for the workbook: one JSON file per tab, same rules as the sheet.

When no Google key is configured (tests, a laptop without the key, ``LULA_LIBRO=local``),
the connectors and the app read and write here (``LULA_LOCAL_DATA``, default
``data/libro``, git-ignored). Same validation, same upsert-by-key, same ``Fuentes``
stamp, so switching to the sheet later is a setting, not a rewrite.

Files here hold business data (orders, listings). They live only in the machine or
cloud environment that ran the sync, never in git.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .schema import tab, validate_row


class LocalWorkbook:
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)

    def _path(self, nombre_tab: str) -> Path:
        tab(nombre_tab)  # unknown tab -> clear error
        return self.folder / f"{nombre_tab}.json"

    def read(self, nombre_tab: str) -> list[dict]:
        path = self._path(nombre_tab)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, nombre_tab: str, rows: list[dict]) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.folder, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self._path(nombre_tab))

    def upsert(self, nombre_tab: str, rows: list[dict]) -> dict[str, int]:
        """Same contract as :meth:`Workbook.upsert`: only given columns change on update."""
        t = tab(nombre_tab)
        problems = {r.get(t.clave, "?"): validate_row(nombre_tab, r) for r in rows}
        problems = {k: v for k, v in problems.items() if v}
        if problems:
            raise ValueError(f"{nombre_tab}: invalid rows {problems}")
        existing = {str(r[t.clave]): r for r in self.read(nombre_tab)}
        nuevas = actualizadas = 0
        for row in {str(r[t.clave]): r for r in rows}.values():
            key = str(row[t.clave])
            if key in existing:
                existing[key] = {**existing[key], **row}
                actualizadas += 1
            else:
                existing[key] = {col: row.get(col, "") for col in t.columnas}
                nuevas += 1
        self._write(nombre_tab, [{col: r.get(col, "") for col in t.columnas}
                                 for r in existing.values()])
        return {"actualizadas": actualizadas, "nuevas": nuevas}

    def stamp_source(self, fuente: str, rows: int, estado: str = "ok", note: str = "") -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self.upsert("Fuentes", [{"fuente": fuente, "ultima_actualizacion": now, "estado": estado,
                                 "filas": rows, "nota": note}])


def local_folder() -> Path:
    p = Path(config.get("LULA_LOCAL_DATA", "data/libro"))
    return p if p.is_absolute() else config.REPO_ROOT / p


def backend() -> str:
    """``google`` or ``local``.

    ``LULA_LIBRO`` forces one (``google`` / ``local``). Otherwise Google is used as soon
    as a service account key or ``LULA_WORKBOOK_ID`` is configured. There is no silent
    fallback: if Google is configured but unreachable, the caller gets the error instead
    of old local data that looks current.
    """
    forced = (config.get("LULA_LIBRO") or "").strip().lower()
    if forced in ("google", "local"):
        return forced
    from .workbook import has_credentials

    return "google" if (has_credentials() or config.get("LULA_WORKBOOK_ID")) else "local"


def open_workbook():
    """The Google Sheet when configured (see :func:`backend`), otherwise the local JSON files."""
    if backend() == "google":
        from .workbook import Workbook

        return Workbook.from_env()
    return LocalWorkbook(local_folder())
