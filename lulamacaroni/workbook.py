"""Read and upsert rows in the "LulaMacaroni Operaciones" Google Sheet.

Credentials, first one set wins:
  GOOGLE_SERVICE_ACCOUNT_JSON_B64  base64 of the key file (Claude cloud environment; one line)
  GOOGLE_SERVICE_ACCOUNT_JSON      the key file's full text
  GOOGLE_APPLICATION_CREDENTIALS   path to the key file (local machine, outside the repo)

Which sheet:
  LULA_WORKBOOK_ID    the long ID in the sheet's URL (preferred once known)
  LULA_WORKBOOK_NAME  otherwise, find the sheet shared with the service account by this
                      name (default "LulaMacaroni Operaciones")

The key and the decoded JSON are never printed or logged. Only the service account's
email (not secret) appears in messages.
"""

from __future__ import annotations

import base64
import binascii
import json
import threading
import time
from datetime import datetime, timezone

from . import config
from .schema import TABS, tab, validate_row

DEFAULT_NAME = "LulaMacaroni Operaciones"
SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)
CACHE_SECONDS = 30  # the app reads six tabs per screen; Sheets allows ~60 reads/min


class GoogleSetupError(RuntimeError):
    """A setup problem with a plain-language fix. Never contains key material."""


def _decode_b64(raw: str) -> dict:
    # Tolerate line breaks and the BEGIN/END lines that Windows certutil adds.
    body = "".join(
        line.strip() for line in raw.splitlines() if line.strip() and "-----" not in line
    )
    try:
        text = base64.b64decode(body, validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise GoogleSetupError(
            "GOOGLE_SERVICE_ACCOUNT_JSON_B64 is not valid base64. Re-copy it as one line "
            "(see docs/setup/google-cloud.md)."
        ) from None
    return _parse_key(text, "GOOGLE_SERVICE_ACCOUNT_JSON_B64")


def _parse_key(text: str, name: str) -> dict:
    try:
        info = json.loads(text)
    except ValueError:
        raise GoogleSetupError(f"{name} does not decode to JSON. Re-copy the whole key file.") from None
    missing = [k for k in ("type", "client_email", "private_key", "token_uri") if not info.get(k)]
    if not isinstance(info, dict) or info.get("type") != "service_account" or missing:
        raise GoogleSetupError(
            f"{name} is JSON but not a service account key (missing {', '.join(missing) or 'type'})."
        )
    return info


def service_account_info() -> dict | None:
    """The key as a dict, or None when only a key file path (or nothing) is configured."""
    raw = config.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64")
    if raw:
        return _decode_b64(raw)
    raw = config.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return _parse_key(raw, "GOOGLE_SERVICE_ACCOUNT_JSON")
    return None


def has_credentials() -> bool:
    return any(config.get(n) for n in (
        "GOOGLE_SERVICE_ACCOUNT_JSON_B64", "GOOGLE_SERVICE_ACCOUNT_JSON",
        "GOOGLE_APPLICATION_CREDENTIALS"))


def credentials():
    from google.oauth2 import service_account  # optional dependency: pip install .[google]

    info = service_account_info()
    if info is not None:
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    path = config.get("GOOGLE_APPLICATION_CREDENTIALS")
    if path:
        return service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
    raise GoogleSetupError(
        "No Google key configured. Set GOOGLE_SERVICE_ACCOUNT_JSON_B64 in the cloud environment."
    )


def google_client():
    import gspread

    return gspread.authorize(credentials())


def open_book(client=None):
    """Open the sheet by ``LULA_WORKBOOK_ID``, or by name among the sheets shared with us."""
    client = client or google_client()
    key = config.get("LULA_WORKBOOK_ID")
    if key:
        return client.open_by_key(key)
    name = config.get("LULA_WORKBOOK_NAME", DEFAULT_NAME)
    found = [f for f in client.list_spreadsheet_files(title=name)]
    if not found:
        raise GoogleSetupError(
            f'No sheet named "{name}" is shared with the service account. In Google Drive, '
            "open the sheet, click Share, add the service account email as Editor."
        )
    if len(found) > 1:
        ids = ", ".join(f["id"] for f in found)
        raise GoogleSetupError(
            f'{len(found)} sheets are named "{name}" ({ids}). Set LULA_WORKBOOK_ID to the right one.'
        )
    return client.open_by_key(found[0]["id"])


def col_letter(index: int) -> str:
    """0-based column index to A1 letter (0 -> A, 26 -> AA)."""
    letters = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _cell(value) -> object:
    return "" if value is None else value


class Workbook:
    """Thin layer over a gspread Spreadsheet (or a fake with the same methods in tests).

    Writes use RAW input, so text from channels (titles, names) is stored as text and
    can never run as a formula. Reads are cached for ``CACHE_SECONDS`` and fetched for
    all tabs in one request; any write clears the cache.
    """

    def __init__(self, book, cache_seconds: float = CACHE_SECONDS, clock=time.monotonic):
        self.book = book
        self.cache_seconds = cache_seconds
        self.clock = clock
        self._cache: dict[str, list[list]] = {}
        self._cached_at: float | None = None
        self._lock = threading.Lock()  # the app server answers requests in threads

    @classmethod
    def from_env(cls) -> "Workbook":
        return cls(open_book())

    # -- reading -------------------------------------------------------------

    def _refresh(self) -> None:
        titles = [ws.title for ws in self.book.worksheets()]
        wanted = [t.nombre for t in TABS if t.nombre in titles]
        values: dict[str, list[list]] = {}
        if wanted:
            resp = self.book.values_batch_get(
                [f"'{n}'" for n in wanted],
                params={"valueRenderOption": "UNFORMATTED_VALUE"},
            )
            for n, vr in zip(wanted, resp.get("valueRanges", [])):
                values[n] = vr.get("values", [])
        self._cache = values
        self._cached_at = self.clock()

    def _values(self, nombre_tab: str) -> list[list]:
        with self._lock:
            stale = self._cached_at is None or self.clock() - self._cached_at > self.cache_seconds
            if stale:
                self._refresh()
            cache = self._cache
        if nombre_tab not in cache:
            raise GoogleSetupError(
                f"The sheet has no tab {nombre_tab!r}. Run: python -m lulamacaroni.setup_workbook"
            )
        return cache[nombre_tab]

    def invalidate(self) -> None:
        self._cached_at = None

    def read(self, nombre_tab: str) -> list[dict]:
        """All rows of a tab as dicts keyed by the schema's columns (empty cells are "")."""
        t = tab(nombre_tab)
        values = self._values(nombre_tab)
        if not values:
            return []
        header = values[0]
        out = []
        for r in values[1:]:
            r = list(r) + [""] * (len(header) - len(r))
            row = {col: r[i] for i, col in enumerate(header) if col in t.columnas}
            if row.get(t.clave) not in (None, ""):
                out.append(row)
        return out

    # -- writing -------------------------------------------------------------

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
        # fresh read, never the cache; unformatted so keys and numbers come back as stored
        values = ws.get_all_values(value_render_option="UNFORMATTED_VALUE")
        header = values[0] if values else list(t.columnas)
        if list(header[: len(t.columnas)]) != list(t.columnas):
            raise ValueError(f"{nombre_tab}: header differs from schema; run setup_workbook first")
        key_idx = header.index(t.clave)
        # index into ``values``; the sheet row number is index + 1
        row_of = {str(r[key_idx]): i for i, r in enumerate(values) if i > 0 and len(r) > key_idx}

        updates, appends = [], []
        for row in rows:
            key = str(row[t.clave])
            if key in row_of:
                # only the given cells: people's notes and formulas elsewhere stay untouched
                n = row_of[key] + 1
                for col, value in row.items():
                    updates.append({"range": f"{col_letter(header.index(col))}{n}",
                                    "values": [[_cell(value)]]})
            else:
                appends.append([_cell(row.get(col, "")) for col in header])
        actualizadas = len({str(r[t.clave]) for r in rows} & set(row_of))
        try:
            if updates:
                ws.batch_update(updates, value_input_option="RAW")
            if appends:
                ws.append_rows(appends, value_input_option="RAW",
                               insert_data_option="INSERT_ROWS", table_range="A1")
        finally:
            self.invalidate()
        return {"actualizadas": actualizadas, "nuevas": len(appends)}

    def stamp_source(self, fuente: str, rows: int, estado: str = "ok", note: str = "") -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self.upsert("Fuentes", [{"fuente": fuente, "ultima_actualizacion": now, "estado": estado,
                                 "filas": rows, "nota": note}])
