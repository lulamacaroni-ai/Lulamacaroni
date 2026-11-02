import pytest

from lulamacaroni.schema import tab
from lulamacaroni.workbook import Workbook


class FakeSheet:
    def __init__(self, values):
        self.values = values

    def get_all_values(self):
        return [list(r) for r in self.values]

    def batch_update(self, updates, value_input_option=None):
        for u in updates:
            row = int(u["range"][1:]) - 1
            self.values[row] = list(u["values"][0])

    def append_rows(self, rows, value_input_option=None):
        self.values.extend(list(r) for r in rows)


class FakeBook:
    def __init__(self):
        self.sheets = {t: FakeSheet([list(tab(t).columnas)]) for t in ("Listados", "Fuentes")}

    def worksheet(self, name):
        return self.sheets[name]


def _row(ref, precio):
    return {"listado_ref": ref, "sku": "LM-1", "linea": "US-POD", "canal": "shopify", "precio": precio}


def test_upsert_inserts_then_updates_and_keeps_other_columns():
    book = FakeBook()
    wb = Workbook(book)
    assert wb.upsert("Listados", [_row("shopify-1", 95)]) == {"actualizadas": 0, "nuevas": 1}
    sheet = book.sheets["Listados"]
    cols = tab("Listados").columnas
    sheet.values[1][cols.index("aprobacion_id")] = "apr-x"  # filled by someone else
    assert wb.upsert("Listados", [_row("shopify-1", 80)]) == {"actualizadas": 1, "nuevas": 0}
    assert len(sheet.values) == 2
    assert sheet.values[1][cols.index("precio")] == 80
    assert sheet.values[1][cols.index("aprobacion_id")] == "apr-x"


def test_upsert_refuses_invalid_rows():
    wb = Workbook(FakeBook())
    with pytest.raises(ValueError):
        wb.upsert("Listados", [{"listado_ref": "x", "linea": "US"}])


def test_upsert_refuses_stale_header():
    book = FakeBook()
    book.sheets["Listados"].values[0] = ["otra", "cosa"]
    with pytest.raises(ValueError, match="setup_workbook"):
        Workbook(book).upsert("Listados", [_row("shopify-1", 1)])


def test_stamp_source():
    book = FakeBook()
    Workbook(book).stamp_source("shopify", rows=12)
    assert book.sheets["Fuentes"].values[1][0] == "shopify"
