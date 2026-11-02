"""Read and upsert rows in the "LulaMacaroni Operaciones" workbook.

Credentials, in order:
  GOOGLE_SERVICE_ACCOUNT_JSON     the key file's full text (cloud environment secret)
  GOOGLE_APPLICATION_CREDENTIALS  path to the key file (local machine)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import config
from .schema import tab, validate_row


def google_client():
    import gspread  # optional dependency: pip install .[google]

    raw = config.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return gspread.service_account_from_dict(json.loads(raw))
    return gspread.service_account(filename=config.require("GOOGLE_APPLICATION_CREDENTIALS"))


def _cell(value) -> object:
    return "" if value is None else value


class Workbook:
    """Thin layer over a gspread Spreadsheet (or a fake with the same methods in tests)."""

    def __init__(self, book):
        self.book = book

    @classmethod
    def from_env(cls) -> "Workbook":
        return cls(google_client().open_by_key(config.require("LULA_WORKBOOK_ID")))

    def read(self, nombre_tab: str) -> list[dict]:
        """All rows of a tab as dicts keyed by the schema's columns (empty cells are "")."""
        t = tab(nombre_tab)
        values = self.book.worksheet(nombre_tab).get_all_values()
        if not values:
            return []
        header = values[0]
        out = []
        for r in values[1:]:
            r = list(r) + [""] * (len(header) - len(r))
            row = {col: r[i] for i, col in enumerate(header) if col in t.columnas}
            if row.get(t.clave):
                out.append(row)
        return out

    def upsert(self, nombre_tab: str, rows: list[dict]) -> dict[str, int]:
        """Insert new rows and update existing ones by the tab's key column.

        Only the columns present in ``rows`` are written, so columns that people or
        other syncs fill (costs, notes) are left alone on update. Invalid rows are
        refused before anything is written.
        """
        t = tab(nombre_tab)
        problems = {r.get(t.clave, "?"): validate_row(nombre_tab, r) for r in rows}
        problems = {k: v for k, v in problems.items() if v}
        if problems:
            raise ValueError(f"{nombre_tab}: invalid rows {problems}")

        rows = list({str(r[t.clave]): r for r in rows}.values())  # same key twice: last wins
        ws = self.book.worksheet(nombre_tab)
        values = ws.get_all_values()
        header = values[0] if values else list(t.columnas)
        if list(header[: len(t.columnas)]) != list(t.columnas):
            raise ValueError(f"{nombre_tab}: header differs from schema; run setup_workbook first")
        key_idx = header.index(t.clave)
        # index into ``values``; the sheet row number is index + 1
        row_of = {r[key_idx]: i for i, r in enumerate(values) if i > 0 and len(r) > key_idx}

        updates, appends = [], []
        for row in rows:
            key = str(row[t.clave])
            if key in row_of:
                existing = values[row_of[key]] + [""] * (len(header) - len(values[row_of[key]]))
                merged = [
                    _cell(row[col]) if col in row else existing[i]
                    for i, col in enumerate(header)
                ]
                updates.append({"range": f"A{row_of[key] + 1}", "values": [merged]})
            else:
                appends.append([_cell(row.get(col, "")) for col in header])
        if updates:
            ws.batch_update(updates, value_input_option="USER_ENTERED")
        if appends:
            ws.append_rows(appends, value_input_option="USER_ENTERED")
        return {"actualizadas": len(updates), "nuevas": len(appends)}

    def stamp_source(self, fuente: str, rows: int, estado: str = "ok", note: str = "") -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self.upsert("Fuentes", [{"fuente": fuente, "ultima_actualizacion": now, "estado": estado,
                                 "filas": rows, "nota": note}])
