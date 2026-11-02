from lulamacaroni.schema import tab
from lulamacaroni.setup_workbook import _col_letter, header_range, plan, validation_requests


def test_col_letter():
    assert [_col_letter(i) for i in (0, 25, 26, 27, 51, 52)] == ["A", "Z", "AA", "AB", "AZ", "BA"]


def test_header_range_covers_all_columns():
    t = tab("Pedidos")
    assert header_range(t) == f"'Pedidos'!A1:{_col_letter(len(t.columnas) - 1)}1"


def test_validation_requests_point_at_right_column():
    t = tab("Variantes")
    reqs = validation_requests(t, sheet_id=42)
    linea = next(r for r in reqs if r["setDataValidation"]["rule"]["condition"]["values"][0]
                 ["userEnteredValue"] == "US-POD")
    rng = linea["setDataValidation"]["range"]
    assert rng["sheetId"] == 42
    assert rng["startColumnIndex"] == t.columnas.index("linea")
    assert rng["startRowIndex"] == 1  # header stays free


def test_plan_marks_existing_tabs_as_updates():
    lines = plan({"Obras"})
    assert lines[0].startswith("update headers")
    assert lines[1].startswith("create tab")


class _WS:
    def __init__(self, title, values=()):
        self.title, self._values = title, [list(r) for r in values]


def test_only_an_empty_starter_tab_is_removed():
    from lulamacaroni.setup_workbook import removable_starter_tabs

    tabs = [_WS("Obras", [["obra_id"]]), _WS("Sheet1"), _WS("Hoja 1", [["", " "]]),
            _WS("Notas"), _WS("Sheet2")]
    out = removable_starter_tabs(tabs, lambda w: w._values)
    assert [w.title for w in out] == ["Sheet1", "Hoja 1"]
    assert removable_starter_tabs([_WS("Sheet1", [["hola"]])], lambda w: w._values) == []
    # never removes the only tab
    assert removable_starter_tabs([_WS("Sheet1")], lambda w: w._values) == []
