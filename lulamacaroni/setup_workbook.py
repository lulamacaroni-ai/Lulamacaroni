"""Create or update the tabs, headers and dropdowns of the "LulaMacaroni Operaciones" workbook.

Usage:
    python -m lulamacaroni.setup_workbook --dry-run     # show what would change, no Google access
    python -m lulamacaroni.setup_workbook               # apply (needs the service account key)

It only adds missing tabs and writes header rows and validations. It never deletes a
data row, and the only tab it ever removes is Google's empty starter tab ("Sheet1" /
"Hoja 1"), and only when it holds no value at all and the workbook's own tabs exist. So
it is safe to re-run after the schema grows.
"""

from __future__ import annotations

import argparse
import sys

from .schema import TABS, Tab
from .workbook import col_letter as _col_letter

HEADER_ROWS = 1
# Google's starter tab in English and Spanish accounts. Removed only while completely empty.
STARTER_TABS = ("Sheet1", "Hoja 1", "Hoja1")
VALIDATION_ROWS = 5000  # rows below the header that get dropdowns


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


def removable_starter_tabs(worksheets, values_of) -> list:
    """Starter tabs that are safe to delete: a starter name, not a workbook tab, no values.

    ``values_of(ws)`` returns the tab's cell values (``ws.get_all_values``). Never returns
    every tab, so the workbook always keeps at least one.
    """
    ours = {t.nombre for t in TABS}
    out = []
    for ws in worksheets:
        if ws.title in STARTER_TABS and ws.title not in ours:
            if not any(str(c).strip() for row in values_of(ws) for c in row):
                out.append(ws)
    return out if len(out) < len(list(worksheets)) else []


def apply() -> None:
    from .workbook import open_book

    book = open_book()
    print(f'Sheet: "{book.title}"')
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
    for ws in removable_starter_tabs(book.worksheets(), lambda w: w.get_all_values()):
        book.del_worksheet(ws)
        print(f'removed empty starter tab "{ws.title}"')
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
