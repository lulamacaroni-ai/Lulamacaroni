import base64
import json
import re

import pytest

from lulamacaroni import workbook as wbmod
from lulamacaroni.approval.gate import assert_approved, decide, request_approval
from lulamacaroni.approval.store import SheetsStore
from lulamacaroni.schema import TABS, tab
from lulamacaroni.workbook import GoogleSetupError, Workbook, col_letter

# A fake key: right shape, not a real key.
FAKE_KEY = {
    "type": "service_account",
    "client_email": "bot@proyecto.iam.gserviceaccount.com",
    "private_key": "-----BEGIN PRIVATE KEY-----\nnot-a-key\n-----END PRIVATE KEY-----\n",
    "token_uri": "https://oauth2.googleapis.com/token",
}


def _cell_index(a1):
    m = re.fullmatch(r"([A-Z]+)(\d+)", a1)
    col = 0
    for ch in m.group(1):
        col = col * 26 + ord(ch) - 64
    return int(m.group(2)) - 1, col - 1


class FakeSheet:
    def __init__(self, title, values):
        self.title = title
        self.values = values
        self.input_options = []

    def get_all_values(self, **kw):
        return [list(r) for r in self.values]

    def batch_update(self, updates, value_input_option=None):
        self.input_options.append(value_input_option)
        for u in updates:
            r, c = _cell_index(u["range"])
            while len(self.values) <= r:
                self.values.append([])
            row = self.values[r]
            row += [""] * (c + 1 - len(row))
            row[c] = u["values"][0][0]

    def append_rows(self, rows, value_input_option=None, **kw):
        self.input_options.append(value_input_option)
        self.values.extend(list(r) for r in rows)


class FakeBook:
    def __init__(self, tabs=("Listados", "Fuentes", "Aprobaciones")):
        self.sheets = {t: FakeSheet(t, [list(tab(t).columnas)]) for t in tabs}
        self.batch_gets = 0

    def worksheet(self, name):
        return self.sheets[name]

    def worksheets(self):
        return list(self.sheets.values())

    def values_batch_get(self, ranges, params=None):
        self.batch_gets += 1
        return {"valueRanges": [{"range": r, "values": self.sheets[r.strip("'")].get_all_values()}
                                for r in ranges]}


def _row(ref, precio):
    return {"listado_ref": ref, "sku": "LM-1", "linea": "US-POD", "canal": "shopify", "precio": precio}


def test_col_letter():
    assert [col_letter(i) for i in (0, 25, 26, 27, 51, 52)] == ["A", "Z", "AA", "AB", "AZ", "BA"]


def test_upsert_inserts_then_updates_only_given_cells():
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


def test_writes_are_raw_so_text_never_becomes_a_formula():
    book = FakeBook()
    wb = Workbook(book)
    wb.upsert("Listados", [{**_row("shopify-1", 1), "titulo_en_canal": "=IMPORTXML(1)"}])
    wb.upsert("Listados", [_row("shopify-1", 2)])
    assert set(book.sheets["Listados"].input_options) == {"RAW"}


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


def test_read_returns_dicts_by_schema_column_and_skips_blank_rows():
    book = FakeBook()
    cols = list(tab("Listados").columnas)
    book.sheets["Listados"].values += [["shopify-1", "LM-1"], [""] * len(cols)]
    rows = Workbook(book).read("Listados")
    assert len(rows) == 1
    assert rows[0]["listado_ref"] == "shopify-1" and rows[0]["sku"] == "LM-1"
    assert rows[0]["precio"] == "" and set(rows[0]) == set(cols)


def test_reads_are_batched_cached_and_cleared_by_writes():
    book = FakeBook()
    now = [0.0]
    wb = Workbook(book, cache_seconds=30, clock=lambda: now[0])
    wb.read("Listados"), wb.read("Fuentes"), wb.read("Aprobaciones")
    assert book.batch_gets == 1
    now[0] = 10
    wb.read("Listados")
    assert book.batch_gets == 1
    wb.upsert("Listados", [_row("shopify-1", 5)])
    assert wb.read("Listados")[0]["precio"] == 5  # a write is visible right away
    assert book.batch_gets == 2
    now[0] = 100
    wb.read("Listados")
    assert book.batch_gets == 3


def test_missing_tab_says_run_setup():
    with pytest.raises(GoogleSetupError, match="setup_workbook"):
        Workbook(FakeBook()).read("Pedidos")


# --- credentials -----------------------------------------------------------

def _env(monkeypatch, **values):
    for name in ("GOOGLE_SERVICE_ACCOUNT_JSON_B64", "GOOGLE_SERVICE_ACCOUNT_JSON",
                 "GOOGLE_APPLICATION_CREDENTIALS", "LULA_WORKBOOK_ID", "LULA_WORKBOOK_NAME",
                 "LULA_LIBRO"):
        monkeypatch.delenv(name, raising=False)
    for k, v in values.items():
        monkeypatch.setenv(k, v)


def test_b64_key_decodes(monkeypatch):
    _env(monkeypatch, GOOGLE_SERVICE_ACCOUNT_JSON_B64=base64.b64encode(
        json.dumps(FAKE_KEY).encode()).decode())
    assert wbmod.service_account_info()["client_email"] == FAKE_KEY["client_email"]


def test_b64_key_with_line_breaks_and_certutil_header(monkeypatch):
    b64 = base64.b64encode(json.dumps(FAKE_KEY).encode()).decode()
    wrapped = "\n".join(b64[i:i + 64] for i in range(0, len(b64), 64))
    _env(monkeypatch, GOOGLE_SERVICE_ACCOUNT_JSON_B64=
         f"-----BEGIN CERTIFICATE-----\n{wrapped}\n-----END CERTIFICATE-----")
    assert wbmod.service_account_info()["client_email"] == FAKE_KEY["client_email"]


@pytest.mark.parametrize("value", ["no es base64!", base64.b64encode(b"{}").decode(),
                                   base64.b64encode(b"not json").decode()])
def test_bad_key_errors_never_echo_the_value(monkeypatch, value):
    _env(monkeypatch, GOOGLE_SERVICE_ACCOUNT_JSON_B64=value)
    with pytest.raises(GoogleSetupError) as exc:
        wbmod.service_account_info()
    assert value not in str(exc.value)


def test_backend_choice(monkeypatch):
    from lulamacaroni.localbook import backend

    _env(monkeypatch)
    assert backend() == "local"
    _env(monkeypatch, GOOGLE_SERVICE_ACCOUNT_JSON_B64="x")
    assert backend() == "google"
    _env(monkeypatch, GOOGLE_SERVICE_ACCOUNT_JSON_B64="x", LULA_LIBRO="local")
    assert backend() == "local"


class FakeClient:
    def __init__(self, files):
        self.files = files
        self.opened = None

    def list_spreadsheet_files(self, title=None):
        return [f for f in self.files if title is None or f["name"] == title]

    def open_by_key(self, key):
        self.opened = key
        return key


def test_open_book_by_name_or_id(monkeypatch):
    _env(monkeypatch)
    client = FakeClient([{"id": "abc", "name": "LulaMacaroni Operaciones"},
                         {"id": "zzz", "name": "Otra"}])
    assert wbmod.open_book(client) == "abc"
    _env(monkeypatch, LULA_WORKBOOK_ID="pinned")
    assert wbmod.open_book(client) == "pinned"


def test_open_book_explains_missing_or_duplicate(monkeypatch):
    _env(monkeypatch)
    with pytest.raises(GoogleSetupError, match="Share"):
        wbmod.open_book(FakeClient([]))
    two = [{"id": "a", "name": "LulaMacaroni Operaciones"},
           {"id": "b", "name": "LulaMacaroni Operaciones"}]
    with pytest.raises(GoogleSetupError, match="LULA_WORKBOOK_ID"):
        wbmod.open_book(FakeClient(two))


# --- approvals in the sheet ------------------------------------------------

def test_sheets_store_round_trip_keeps_the_gate_intact():
    book = FakeBook()
    store = SheetsStore(Workbook(book, cache_seconds=0))
    contenido = {"titulo": "Print 8x10", "precio": 45}
    rec = request_approval(store, tipo="listado", linea="US-POD", resumen="Nuevo listado",
                           contenido=contenido, creado_por="agente")
    assert store.get(rec.aprobacion_id).estado == "pendiente"
    with pytest.raises(ValueError):
        store.add(rec)
    decide(store, rec.aprobacion_id, aprobar=True, decidido_por="Lorena")
    again = store.get(rec.aprobacion_id)
    assert_approved(again, tipo="listado", contenido=contenido)
    assert len(book.sheets["Aprobaciones"].values) == 2  # updated in place, not appended
    with pytest.raises(KeyError):
        store.update(type(rec)(**{**rec.to_row(), "aprobacion_id": "apr-no-existe"}))


def test_every_schema_tab_is_known():
    assert len(TABS) == 20
