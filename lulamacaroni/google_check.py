"""Check the Google connection step by step, read-only.

    python -m lulamacaroni.google_check

1. The key decodes to a service account (prints only its email, which is not secret).
2. Google gives a token (oauth2.googleapis.com).
3. Drive lists the sheets shared with the service account (www.googleapis.com).
4. The workbook opens and its tabs match the schema (sheets.googleapis.com).

It never prints the key or the token, and it changes nothing.
"""

from __future__ import annotations

import sys

from . import config
from .schema import TABS
from .workbook import DEFAULT_NAME, GoogleSetupError, credentials, open_book, service_account_info

HOSTS = {
    "token": "oauth2.googleapis.com",
    "drive": "www.googleapis.com",
    "sheets": "sheets.googleapis.com",
}


def _why(exc: Exception, host: str) -> str:
    """A plain reason, without echoing response bodies (they can quote request data)."""
    import requests

    if isinstance(exc, GoogleSetupError):
        return str(exc)
    if isinstance(exc, (requests.exceptions.ProxyError, requests.exceptions.ConnectionError)):
        return f"cannot reach {host}. Add it to the cloud environment's Allowed domains."
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status == 403:
        return (f"{host} answered 403. Either the domain is blocked by the environment, or "
                "the API is not enabled in the Google Cloud project (Sheets API, Drive API).")
    if status == 404:
        return "not found. Check LULA_WORKBOOK_ID, or that the sheet is shared with the service account."
    return f"{type(exc).__name__}" + (f" (HTTP {status})" if status else "")


def run(out=print) -> int:
    # 1. key
    try:
        info = service_account_info()
        creds = credentials()
    except GoogleSetupError as exc:
        out(f"[1] key: NO. {exc}")
        return 1
    email = (info or {}).get("client_email") or getattr(creds, "service_account_email", "?")
    out(f"[1] key: ok, service account {email}")

    # 2. token
    try:
        from google.auth.transport.requests import Request

        creds.refresh(Request())
    except Exception as exc:  # noqa: BLE001 - reported, never re-raised with key material
        if type(exc).__name__ == "RefreshError":
            out("[2] token: NO. Google refused the key (deleted or rotated?). Make a new JSON "
                "key for the service account and update GOOGLE_SERVICE_ACCOUNT_JSON_B64.")
        else:
            out(f"[2] token: NO. {_why(exc, HOSTS['token'])}")
        return 1
    out("[2] token: ok")

    # 3. Drive: which sheets can it see?
    import gspread

    client = gspread.authorize(creds)
    try:
        files = client.list_spreadsheet_files()
    except Exception as exc:  # noqa: BLE001
        out(f"[3] drive: NO. {_why(exc, HOSTS['drive'])}")
        return 1
    if not files:
        out(f"[3] drive: ok, but NO sheet is shared with {email}. Open the sheet in Google "
            "Drive, click Share, paste that email, choose Editor, untick Notify, Send.")
        return 1
    out(f"[3] drive: ok, {len(files)} sheet(s) shared:")
    for f in files:
        out(f'      - "{f["name"]}"  id {f["id"]}')

    # 4. the workbook and its tabs
    try:
        book = open_book(client)
        titles = [ws.title for ws in book.worksheets()]
    except Exception as exc:  # noqa: BLE001
        out(f"[4] workbook: NO. {_why(exc, HOSTS['sheets'])}")
        return 1
    if not config.get("LULA_WORKBOOK_ID"):
        out(f'[4] workbook: ok, found by name "{config.get("LULA_WORKBOOK_NAME", DEFAULT_NAME)}" '
            f"(optional: set LULA_WORKBOOK_ID={book.id} to pin it)")
    else:
        out(f'[4] workbook: ok, "{book.title}"')
    missing = [t.nombre for t in TABS if t.nombre not in titles]
    if missing:
        out(f"    {len(missing)} of {len(TABS)} tabs missing: {', '.join(missing)}")
        out("    Create them with: python -m lulamacaroni.setup_workbook")
        return 1
    stale = []
    for t in TABS:
        header = book.worksheet(t.nombre).row_values(1)
        if header[: len(t.columnas)] != list(t.columnas):
            stale.append(t.nombre)
    if stale:
        out(f"    headers differ from the schema in: {', '.join(stale)}. "
            "Run: python -m lulamacaroni.setup_workbook")
        return 1
    out(f"    all {len(TABS)} tabs present with the right headers")
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
