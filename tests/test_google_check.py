import gspread

from lulamacaroni import google_check
from lulamacaroni.schema import TABS


class FakeCreds:
    service_account_email = "bot@proyecto.iam.gserviceaccount.com"

    def refresh(self, request):
        pass


class FakeWs:
    def __init__(self, t):
        self.title, self.t = t.nombre, t

    def row_values(self, n):
        return list(self.t.columnas)


class FakeBook:
    id, title = "abc", "LulaMacaroni Operaciones"

    def __init__(self, tabs):
        self.ws = [FakeWs(t) for t in tabs]

    def worksheets(self):
        return self.ws

    def worksheet(self, name):
        return next(w for w in self.ws if w.title == name)


class FakeClient:
    def __init__(self, files, book):
        self.files, self.book = files, book

    def list_spreadsheet_files(self, title=None):
        return [f for f in self.files if title is None or f["name"] == title]

    def open_by_key(self, key):
        return self.book


def _run(monkeypatch, files, tabs):
    monkeypatch.delenv("LULA_WORKBOOK_ID", raising=False)
    monkeypatch.setattr(google_check, "service_account_info", lambda: None)
    monkeypatch.setattr(google_check, "credentials", lambda: FakeCreds())
    monkeypatch.setattr(gspread, "authorize", lambda c: FakeClient(files, FakeBook(tabs)))
    lines = []
    return google_check.run(lines.append), "\n".join(lines)


SHEET = [{"id": "abc", "name": "LulaMacaroni Operaciones"}]


def test_all_good(monkeypatch):
    code, text = _run(monkeypatch, SHEET, TABS)
    assert code == 0 and "all 17 tabs" in text and "bot@proyecto" in text


def test_nothing_shared(monkeypatch):
    code, text = _run(monkeypatch, [], TABS)
    assert code == 1 and "Share" in text


def test_tabs_missing(monkeypatch):
    code, text = _run(monkeypatch, SHEET, TABS[:3])
    assert code == 1 and "14 of 17 tabs missing" in text and "setup_workbook" in text


def test_no_key(monkeypatch):
    for n in ("GOOGLE_SERVICE_ACCOUNT_JSON_B64", "GOOGLE_SERVICE_ACCOUNT_JSON",
              "GOOGLE_APPLICATION_CREDENTIALS"):
        monkeypatch.delenv(n, raising=False)
    lines = []
    assert google_check.run(lines.append) == 1 and "[1] key: NO" in lines[0]
