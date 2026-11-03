from lulamacaroni.schema import LINEAS, TABS, tab, validate_row

MONEY_AND_CUSTOMER_TABS = ["Variantes", "Listados", "Pedidos", "Pagos", "Gastos", "Clientes",
                           "Contenido", "Campanas", "Consultas", "Aprobaciones", "Excepciones"]


def test_every_money_listing_or_customer_tab_is_tagged_by_line():
    for name in MONEY_AND_CUSTOMER_TABS:
        t = tab(name)
        assert t.lleva_linea, name
        assert "linea" in t.validaciones, name


def test_lines_are_the_two_businesses():
    assert LINEAS == ("US-POD", "MX-original")
    assert "compartido" in tab("Gastos").validaciones["linea"]
    assert "compartido" not in tab("Pedidos").validaciones["linea"]


def test_tab_names_unique():
    names = [t.nombre for t in TABS]
    assert len(names) == len(set(names))


def test_validate_row_requires_line_and_key():
    problems = validate_row("Pedidos", {"pedido_id": "1"})
    assert any("linea_pedido_id" in p for p in problems)
    assert any("linea" in p for p in problems)


def test_validate_row_rejects_bad_dropdown_and_unknown_column():
    problems = validate_row("Variantes", {"sku": "A-1", "linea": "US", "color_raro": "x"})
    assert any("linea='US'" in p for p in problems)
    assert any("color_raro" in p for p in problems)


def test_validate_row_accepts_good_row():
    row = {"sku": "LM-001-12x16", "obra_id": "LM-001", "linea": "US-POD", "tipo": "impresion",
           "estado": "activa"}
    assert validate_row("Variantes", row) == []


def test_metric_tabs_distinguish_zero_from_missing():
    for name in ["Pedidos", "Contenido", "Campanas"]:
        assert tab(name).validaciones["calidad_dato"] == ("real", "estimado", "faltante")


def test_data_layer_doc_is_in_sync():
    from lulamacaroni.schema_doc import DOC_PATH, render

    assert DOC_PATH.read_text(encoding="utf-8") == render(), (
        "docs/data-layer.md is stale: run python -m lulamacaroni.schema_doc"
    )
