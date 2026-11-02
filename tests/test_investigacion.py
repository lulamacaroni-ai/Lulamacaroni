from datetime import date, datetime, timezone

import pytest

from lulamacaroni.app import investigacion as inv
from lulamacaroni.app.alertas import resumen_dia
from lulamacaroni.app.demo import fill_demo
from lulamacaroni.app.screens import Datos, render
from lulamacaroni.approval import JsonStore
from lulamacaroni.connectors import investigacion as ci
from lulamacaroni.localbook import LocalWorkbook
from lulamacaroni.schema import validate_row

NOW = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)

ERANK = (b"Keyword,Avg. Searches,Avg. Clicks,Avg. CTR,Etsy Competition,Google Searches\n"
         b'boho wall art,"1,200",400,33%,"21,000",90\n'
         b"framed botanical print,< 20,5,20%,800,10\n"
         b",50,1,1%,10,1\n")
EVERBEE = ("Product Name,Shop Name,Price,Mo. Sales,Mo. Revenue,Reviews,Favorites\n"
           "Boho Art Print,Shop A,$18.00,40,$720,210,900\n"
           "Framed Flower Art,Shop B,$95.00,4,$380,12,80\n"
           "Instant Download Printable,Shop C,$4.99,150,$748,1200,3000\n").encode()


@pytest.fixture
def book(tmp_path):
    return LocalWorkbook(tmp_path / "libro")


# --- parsing ----------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,val", [("1,234", 1234), ("$12.50", 12.5), ("33%", 33),
                                     ("1.2k", 1200), ("< 20", None), ("N/A", None),
                                     ("12,5", 12.5), ("", None), ("Low", None)])
def test_numero(raw, val):
    assert ci.numero(raw) == val


@pytest.mark.parametrize("texto,cat", [("boho wall art", "print"),
                                       ("instant download printable", "descargable"),
                                       ("framed botanical print", "enmarcado"),
                                       ("throw pillow cover", "cojin"),
                                       ("peel and stick wallpaper", "wallpaper"),
                                       ("party decorations", "otro")])
def test_categoria(texto, cat):
    assert ci.categoria(texto) == cat


def test_fecha_en_nombre():
    assert ci.fecha_en_nombre("erank-2026-10-15.csv") == date(2026, 10, 15)
    assert ci.fecha_en_nombre("everbee_20261101.csv") == date(2026, 11, 1)
    assert ci.fecha_en_nombre("erank 2026-09.csv") == date(2026, 9, 1)
    assert ci.fecha_en_nombre("export.csv") is None


def test_erank_keywords_are_read_and_unknown_columns_listed():
    lec = ci.leer("erank-keywords.csv", ERANK)
    assert (lec.fuente, lec.tipo, lec.omitidas) == ("erank", "keyword", 1)
    assert lec.ignoradas == ["Google Searches"]
    boho, framed = lec.filas
    assert (boho["busquedas"], boho["competencia"], boho["categoria"]) == (1200, 21000, "print")
    assert framed["busquedas"] == ""        # "< 20" is not a number we can use
    assert framed["categoria"] == "enmarcado"


def test_source_detected_from_headers_and_currency_from_price():
    lec = ci.leer("export-noviembre.csv", EVERBEE)
    assert (lec.fuente, lec.tipo) == ("everbee", "producto")
    assert [f["moneda"] for f in lec.filas] == ["USD"] * 3
    assert lec.filas[0]["ventas_mes"] == 40 and lec.filas[0]["precio"] == 18


def test_unknown_source_and_no_useful_columns_are_refused():
    assert "erank" in ci.leer("datos.csv", b"Keyword,Searches\nx,1\n").error
    assert "No encontré" in ci.leer("erank.csv", b"Foo,Bar\n1,2\n").error
    assert "vacío" in ci.leer("erank.csv", b"").error


def test_semicolon_and_windows_encoding():
    raw = "Palabra clave;Búsquedas;Competencia\ncojín floral;1.200;300\n".encode("cp1252")
    lec = ci.leer("erank.csv", raw)
    assert lec.tipo == "keyword" and lec.filas[0]["keyword"] == "cojín floral"
    assert lec.filas[0]["competencia"] == 300


# --- import into the workbook -----------------------------------------------------------------

def test_import_writes_rows_import_log_and_source(book):
    r = ci.importar(book, "erank-keywords-2026-10-30.csv", ERANK, now=NOW)
    assert r["estado"] == "parcial" and r["filas"] == 2 and r["fecha_export"] == "2026-10-30"
    assert r["fecha_export_origen"] == "nombre-archivo"
    rows = book.read("Investigacion")
    assert len(rows) == 2 and all(validate_row("Investigacion", x) == [] for x in rows)
    assert {x["fecha_export"] for x in rows} == {"2026-10-30"}
    (imp,) = book.read("Importaciones")
    assert "Avg. Searches→busquedas" in imp["columnas_usadas"]
    (fuente,) = [f for f in book.read("Fuentes") if f["fuente"] == "erank"]
    assert fuente["estado"] == "ok" and fuente["filas"] == 2


def test_same_file_twice_changes_nothing(book):
    ci.importar(book, "erank-2026-10-30.csv", ERANK, now=NOW)
    again = ci.importar(book, "erank-copia.csv", ERANK, now=NOW)
    assert again["repetido"] and len(book.read("Investigacion")) == 2
    assert len(book.read("Importaciones")) == 1


def test_refused_file_is_logged_but_writes_no_rows(book):
    r = ci.importar(book, "datos.csv", b"Foo\n1\n", now=NOW)
    assert r["estado"] == "error" and r["nota"]
    assert book.read("Investigacion") == [] and book.read("Fuentes") == []
    assert book.read("Importaciones")[0]["estado"] == "error"


def test_dry_run_writes_nothing(book):
    ci.importar(book, "erank-2026-10-30.csv", ERANK, now=NOW, escribir=False)
    assert book.read("Investigacion") == [] and book.read("Importaciones") == []


def test_export_date_falls_back_to_file_date_then_import_day(book):
    f = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    assert ci.importar(book, "erank.csv", ERANK, fecha_archivo=f, now=NOW)["fecha_export"] \
        == "2026-10-03"
    r = ci.importar(book, "everbee.csv", EVERBEE, now=NOW)
    assert (r["fecha_export"], r["fecha_export_origen"]) == ("2026-11-02", "dia-importacion")


# --- Drive ------------------------------------------------------------------------------------

class FakeResp:
    def __init__(self, data=None, content=b""):
        self._data, self.content = data, content

    def json(self):
        return self._data


class FakeDrive:
    def __init__(self, files):
        self.files, self.calls = files, []

    def request(self, method, url, params=None):
        self.calls.append((url, params))
        if url == ci.DRIVE and "folder" in params["q"]:
            return FakeResp({"files": [{"id": "F1", "name": ci.CARPETA_NOMBRE}]})
        if url == ci.DRIVE:
            assert "'F1' in parents" in params["q"]
            return FakeResp({"files": self.files})
        if url.endswith("/export"):
            return FakeResp(content=EVERBEE)
        return FakeResp(content=ERANK)


def test_drive_folder_imports_csv_and_sheets_and_refuses_excel(book):
    drive = FakeDrive([
        {"id": "a", "name": "erank-2026-10-30.csv", "mimeType": "text/csv"},
        {"id": "b", "name": "everbee productos", "mimeType": ci.SHEET_MIME,
         "modifiedTime": "2026-10-31T10:00:00Z"},
        {"id": "c", "name": "erank.xlsx", "mimeType": ci.XLSX_MIMES[0]},
    ])
    res = ci.importar_drive(book, drive, NOW)
    assert [r["estado"] for r in res] == ["parcial", "ok", "error"]
    assert "CSV" in res[2]["nota"]
    assert res[1]["fecha_export"] == "2026-10-31" and res[1]["archivo_id"] == "b"
    assert len(book.read("Investigacion")) == 5


def test_drive_needs_the_google_key(book):
    from lulamacaroni.workbook import GoogleSetupError

    with pytest.raises(GoogleSetupError):
        ci.drive_http(book)


# --- the view ---------------------------------------------------------------------------------

def test_trend_rules():
    d = [date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)]
    assert inv.tendencia(list(zip(d, (1, 2, 3))))[0] == "sube"
    assert inv.tendencia(list(zip(d, (3, 2, 1))))[0] == "baja"
    assert inv.tendencia(list(zip(d, (10, 10, 30))))[0] == "pico"
    assert inv.tendencia(list(zip(d, (10, 12, 11))))[0] == "estable"
    assert inv.tendencia(list(zip(d[:1], (5,))))[0] == "sin-historial"
    # two exports in the same month count once
    assert inv.tendencia([(date(2026, 10, 1), 1), (date(2026, 10, 20), 9)])[0] == "sin-historial"


def test_empty_view_shows_dashes_not_zeros(tmp_path):
    d = Datos(LocalWorkbook(tmp_path / "vacio"), JsonStore(tmp_path / "a.json"), NOW)
    datos = inv.resumen(d.investigacion, d.fuentes, NOW)
    assert all(x.calidad == "faltante" for x in datos)
    html = render("/investigacion", {}, d)
    assert "Aún no hay exports importados" in html and "cero real" not in html


def test_view_without_the_new_tabs(tmp_path):
    from lulamacaroni.workbook import GoogleSetupError

    class OldSheet(LocalWorkbook):
        def read(self, nombre):
            if nombre in ("Investigacion", "Importaciones", "Keywords"):
                raise GoogleSetupError(nombre)
            return super().read(nombre)

    d = Datos(OldSheet(tmp_path), JsonStore(tmp_path / "a.json"), NOW)
    assert d.investigacion.faltan_tabs == ["Investigacion", "Importaciones", "Keywords"]
    assert "setup_workbook" in render("/investigacion", {}, d)


@pytest.fixture
def demo(tmp_path):
    b = LocalWorkbook(tmp_path / "libro")
    fill_demo(b, NOW)
    return Datos(b, JsonStore(tmp_path / "a.json"), NOW)


def test_demo_keywords_trends_prices_and_suggestions(demo):
    i = demo.investigacion
    by = {k.texto: k for k in i.keywords}
    assert by["garden wall art"].tendencia == "sube"
    assert by["framed boat print"].tendencia == "baja"
    assert by["harbor painting"].tendencia == "pico"
    assert all(k.busquedas.calidad == "estimado" for k in i.keywords)
    assert "erank-keywords-ejemplo-2026-11-01.csv" in by["garden wall art"].busquedas.fuente
    # opportunities never include a falling keyword
    assert "framed boat print" not in [k.texto for k in i.oportunidades]
    pr = {p.categoria: p for p in i.precios}
    assert (pr["print"].minimo.valor, pr["print"].maximo.valor) == (18, 24.5)
    assert pr["print"].minimo.calidad == "real" and pr["print"].ventas.calidad == "estimado"
    harbor = next(s for s in i.sugerencias if s.obra_id == "DEMO-002")
    assert harbor.ideas[0][0].texto == "harbor painting"
    garden = next(s for s in i.sugerencias if s.obra_id == "DEMO-001")
    assert garden.lista and "garden wall art" not in [k.texto for k, _ in garden.ideas]


def test_demo_screen_and_alerts(demo):
    html = render("/investigacion", {}, demo)
    for txt in ("Keywords y tendencias", "Precios de la competencia", "garden wall art",
                "no garantiza ventas", "¿De dónde sale?"):
        assert txt in html
    tabla = render("/investigacion", {"c": "cojin"}, demo).split(
        "Keywords y tendencias")[1].split("Oportunidades para revisar")[0]
    assert "pink flower pillow" in tabla and "boat" not in tabla
    titulos = [a.titulo for a in resumen_dia(demo).alertas]
    assert any("suben 3 meses seguidos" in t for t in titulos)


def test_stale_export_alert(book):
    ci.importar(book, "erank-2026-08-01.csv", ERANK, now=NOW)
    i = inv.investigacion(book.read("Investigacion"), book.read("Importaciones"), [], [])
    assert inv.avisos(i, NOW)[0][0] == "atencion"
    d = inv.resumen(i, {}, NOW)[0]
    assert "toca exportar" in d.nota and d.calidad == "real"


def test_text_from_files_is_escaped(book, tmp_path):
    ci.importar(book, "erank-2026-10-30.csv",
                b"Keyword,Searches,Competition\n<script>x</script> print,500,10\n", now=NOW)
    d = Datos(book, JsonStore(tmp_path / "a.json"), NOW)
    assert "<script>x" not in render("/investigacion", {}, d)
