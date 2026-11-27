from datetime import datetime, timedelta, timezone

import pytest

from lulamacaroni.app import catalogo as cat
from lulamacaroni.app import contenido as cont
from lulamacaroni.app import metrics as m
from lulamacaroni.app.alertas import resumen_dia
from lulamacaroni.app.demo import fill_demo
from lulamacaroni.app.screens import Datos, render
from lulamacaroni.approval import JsonStore, request_approval
from lulamacaroni.approval.gate import decide
from lulamacaroni.localbook import LocalWorkbook

NOW = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)


@pytest.fixture
def book(tmp_path):
    b = LocalWorkbook(tmp_path / "libro")
    fill_demo(b, NOW)
    return b


@pytest.fixture
def store(tmp_path):
    return JsonStore(tmp_path / "aprobaciones.json")


# --- print-file check ---------------------------------------------------------------------

def test_print_file_check_reports_and_never_guesses():
    assert cat.revisar_archivo(None).estado == "sin-revisar"
    assert cat.revisar_archivo({"sku": "A"}).motivo == "falta el archivo de impresión en Variantes"
    base = {"archivo_impresion": "a.tif", "archivo_px": "5400x7200"}
    assert cat.revisar_archivo({**base, "tamano": "18x24"}).estado == "ideal"
    wrong = cat.revisar_archivo({**base, "tamano": "8x10"})
    assert wrong.estado == "no-apto" and "no se recorta" in wrong.motivo
    assert cat.revisar_archivo({**base, "archivo_px": "", "tamano": "8x10"}).estado == "sin-revisar"
    assert cat.revisar_archivo({**base, "archivo_px": "raro", "tamano": "8x10"}).estado == "sin-revisar"


# --- cost and margin -----------------------------------------------------------------------

def test_cost_is_an_estimate_and_missing_cost_means_no_margin():
    c = cat.costo_dato({"costo_usd": "31"}, NOW)
    assert c.calidad == "estimado" and c.valor == 31
    mg = cat.margen_dato(100.0, c, NOW)
    assert mg.calidad == "estimado" and mg.valor == round(100 - (2.9 + 0.30) - 31, 2)
    falta = cat.costo_dato(None, NOW)
    assert falta.calidad == "faltante" and falta.valor is None
    assert cat.margen_dato(100.0, falta, NOW).calidad == "faltante"


def test_fichas_join_shopify_variants_with_the_sheet(book, store):
    d = Datos(book, store, NOW)
    garden = next(f for f in d.fichas if f.producto.titulo == "Sample Garden")
    assert [o["obra_id"] for o in garden.obras] == ["DEMO-001"]
    assert garden.con_costo == 3 and garden.archivos_mal == 1
    owl = next(f for f in d.fichas if f.producto.titulo == "Sample Owl")
    assert owl.con_costo == 0 and not owl.obras
    assert all(v.margen.calidad == "faltante" for v in owl.variantes)


def test_originals_come_only_from_the_sheet():
    assert cat.originales([], []) == []
    origs = cat.originales([{"obra_id": "X", "titulo_es": "Uno", "estado": "activa"}],
                           [{"sku": "X-O", "obra_id": "X", "linea": "MX-original",
                             "tipo": "original", "precio_mxn_con_iva": "9000"}])
    assert len(origs) == 1 and origs[0].precio_mxn == 9000


def test_catalog_counts_missing_when_nothing_is_loaded(tmp_path, store):
    d = Datos(LocalWorkbook(tmp_path), store, NOW)
    datos = cat.resumen(d.fichas, [], [], d.fuentes, NOW)
    assert all(x.calidad == "faltante" for x in datos)
    html = render("/catalogo", {}, d)
    assert "Aún no hay originales en la hoja" in html and "falta el dato" in html


def test_catalog_screens_render(book, store):
    d = Datos(book, store, NOW)
    html = render("/catalogo", {}, d)
    assert "Originales México" in html and "Puerto de ejemplo" in html and "MX$14,500" in html
    assert "¿De dónde sale?" in html and "dos imprentas" not in html
    assert "Imprime: Prodigi" in html
    garden = next(f for f in d.fichas if f.producto.titulo == "Sample Garden")
    det = render("/catalogo/producto", {"c": "shopify", "id": garden.producto.id_producto}, d)
    assert "no sirve" in det and "DEMO-1-12x16" in det and "estimado" in det
    assert render("/catalogo/producto", {"c": "shopify", "id": "nope"}, d) is None
    assert "Sample Garden" in render("/catalogo", {"f": "avisos"}, d)
    mx = render("/catalogo", {"f": "mx"}, d)
    assert "Puerto de ejemplo" in mx and "Sample Owl" not in mx


def test_bad_print_file_on_a_live_product_is_an_alert(book, store):
    alertas = resumen_dia(Datos(book, store, NOW)).alertas
    assert any("archivo que no sirve" in a.titulo for a in alertas)


# --- content and its approval ---------------------------------------------------------------

def _pieza(**kw):
    return {"contenido_id": "c-9", "linea": "US-POD", "plataforma": "instagram",
            "formato": "post", "idioma": "en", "estado": "borrador",
            "programado_para": (NOW + timedelta(days=1)).isoformat(),
            "texto": "Hello", "archivo": "a.tif", **kw}


def test_content_gate_states(tmp_path, store):
    row = _pieza()
    assert cont.gate(row, {}, NOW).estado == "no-hace-falta"
    assert cont.gate({**row, "estado": "programado"}, {}, NOW).estado == "sin-aprobacion"
    a = request_approval(store, tipo="contenido", linea="US-POD", resumen="post",
                         contenido=cont.contenido_aprobable(row), creado_por="test", now=NOW)
    row["aprobacion_id"] = a.aprobacion_id
    assert cont.gate(row, {a.aprobacion_id: a}, NOW).estado == "pendiente"
    a = decide(store, a.aprobacion_id, aprobar=True, decidido_por="Lorena", now=NOW)
    assert cont.gate(row, {a.aprobacion_id: a}, NOW).estado == "ok"
    changed = {**row, "estado": "programado", "texto": "Hello!"}
    g = cont.gate(changed, {a.aprobacion_id: a}, NOW)
    assert g.estado == "cambio" and g.alerta
    assert cont.gate({**row, "aprobacion_id": "apr-x"}, {}, NOW).estado == "perdida"


def test_unapproved_scheduled_content_is_urgent(book, store):
    alertas = resumen_dia(Datos(book, store, NOW)).alertas
    a = next(a for a in alertas if a.area == "contenido")
    assert a.nivel == "urgente" and "sin aprobación" in a.detalle


def test_content_screen(book, store, tmp_path):
    d = Datos(book, store, NOW)
    html = render("/contenido", {}, d)
    assert "Próximos 14 días" in html and "Garden reveal reel" in html
    assert "Ideas (1)" in html and "Instagram aún no está conectado" in html
    assert "Pinterest: resultados" in html and "Pines más vistos (3)" in html
    pin = render("/contenido", {"pl": "pinterest"}, d)
    assert "Garden print pin" in pin and "Garden reveal reel" not in pin
    empty = render("/contenido", {}, Datos(LocalWorkbook(tmp_path / "vacio"), store, NOW))
    assert "Aún no hay piezas" in empty


def test_content_screen_escapes_text(tmp_path, store):
    b = LocalWorkbook(tmp_path)
    b.upsert("Contenido", [_pieza(titulo="<b>x</b>", texto="<script>y</script>")])
    html = render("/contenido", {}, Datos(b, store, NOW))
    assert "<script>y" not in html and "&lt;b&gt;x" in html


def test_resultados_missing_until_platforms_connect():
    datos = cont.resumen([], m.estado_fuentes([], NOW), NOW)
    assert next(x for x in datos if x.etiqueta == "Resultados de Instagram").calidad == "faltante"
