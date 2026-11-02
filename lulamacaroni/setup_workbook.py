"""Create or update the tabs, headers and dropdowns of the "LulaMacaroni Operaciones" workbook.

Usage:
    python -m lulamacaroni.setup_workbook --dry-run     # show what would change, no Google access
    python -m lulamacaroni.setup_workbook               # apply (needs LULA_WORKBOOK_ID and the service account)

It only adds missing tabs and writes header rows and validations. It never deletes
a tab or a data row, so it is safe to re-run after the schema grows.
"""

from __future__ import annotations

import argparse
import sys

from . import config
from .schema import TABS, Tab

HEADER_ROWS = 1
VALIDATION_ROWS = 5000  # rows below the header that get dropdowns


def _col_letter(index: int) -> str:
    """0-based column index to A1 letter (0 -> A, 26 -> AA)."""
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def header_range(t: Tab) -> str:
    return f"'{t.nombre}'!A1:{_col_letter(len(t.columnas) - 1)}1"


def validation_requests(t: Tab, sheet_id: int) -> list[dict]:
    """Sheets API batchUpdate requests that add a dropdown to each validated column."""
    requests = []
    for col, allowed in t.validaciones.items():
        idx = t.columnas.index(col)
        requests.append({
            "setDataValidation": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": HEADER_ROWS,
                    "endRowIndex": HEADER_ROWS + VALIDATION_ROWS,
                    "startColumnIndex": idx,
                    "endColumnIndex": idx + 1,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": v} for v in allowed],
                    },
                    "strict": True,
                    "showCustomUi": True,
                },
            }
        })
    return requests


def plan(existing_tabs: set[str]) -> list[str]:
    lines = []
    for t in TABS:
        action = "update headers" if t.nombre in existing_tabs else "create tab"
        lines.append(
            f"{action:15} {t.nombre:13} {len(t.columnas):2} columns, "
            f"{len(t.validaciones)} dropdowns{', linea tagged' if t.lleva_linea else ''}"
        )
    return lines


def apply() -> None:
    import gspread  # optional dependency: pip install .[google]

    workbook_id = config.require("LULA_WORKBOOK_ID")
    creds_path = config.require("GOOGLE_APPLICATION_CREDENTIALS")
    gc = gspread.service_account(filename=creds_path)
    book = gc.open_by_key(workbook_id)
    existing = {ws.title: ws for ws in book.worksheets()}

    for line in plan(set(existing)):
        print(line)

    requests: list[dict] = []
    for t in TABS:
        ws = existing.get(t.nombre)
        if ws is None:
            ws = book.add_worksheet(title=t.nombre, rows=HEADER_ROWS + VALIDATION_ROWS,
                                    cols=len(t.columnas))
        elif ws.col_count < len(t.columnas):
            ws.add_cols(len(t.columnas) - ws.col_count)
        ws.update(range_name=header_range(t).split("!", 1)[1], values=[list(t.columnas)])
        ws.freeze(rows=HEADER_ROWS)
        requests.extend(validation_requests(t, ws.id))

    if requests:
        book.batch_update({"requests": requests})
    print(f"Done: {len(TABS)} tabs ready.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the plan only")
    args = parser.parse_args(argv)
    if args.dry_run:
        for line in plan(set()):
            print(line)
        return 0
    apply()
    return 0


if __name__ == "__main__":
    sys.exit(main())
