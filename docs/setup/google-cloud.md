# Setup: Google Cloud service account and workbook (M7)

Do it signed in as the **business Google account** (`lulamacaroni@gmail.com`), not a personal one, so everything hands over with the business. Nothing from these steps goes into the repo.

Current state (2026-11-02): project, service account, key and network are done; the sheet still has to be shared with the service account, then the tabs get created.

## 1. Google Cloud project

1. Go to <https://console.cloud.google.com/> and sign in with the business account.
2. Project: **LulaMacaroni Operaciones**.
3. **APIs & Services → Library**: enable **Google Sheets API** and **Google Drive API**.

## 2. Service account and key

1. **IAM & Admin → Service Accounts → Create service account**, name `backoffice`. It needs no project roles.
2. If Google refuses to create a key ("key creation is disabled"), the organization policy `iam.disableServiceAccountKeyCreation` is on. Under **IAM & Admin → Organization policies**, open it, choose **Override parent's policy**, set it **Off** for this project only, save.
3. Open the service account, **Keys → Add key → Create new key → JSON**. A file downloads.
4. Turn the file into one line of base64. On Windows, in PowerShell:

   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\ruta\al\archivo.json")) | Set-Clipboard
   ```

   (Don't use `certutil`: it splits the text into many lines.)
5. In the Claude project: **Project settings → Cloud environment → gear next to the environment**. Add one line, all on the same line: `GOOGLE_SERVICE_ACCOUNT_JSON_B64=` followed by the paste. Save, then delete the downloaded file.
6. In the same screen, under network access, add these **Allowed domains**: `oauth2.googleapis.com`, `www.googleapis.com`, `sheets.googleapis.com`.
7. Copy the service account's email: `backoffice@<project-id>.iam.gserviceaccount.com`.

Settings reach **new** sessions only.

(On a local machine instead: keep the JSON file outside the repo and set `GOOGLE_APPLICATION_CREDENTIALS` to its path in `.env`.)

## 3. The sheet

1. In Google Drive (business account), create an empty Google Sheet named **LulaMacaroni Operaciones**.
2. Click **Share**, paste the service account email, choose **Editor**, untick **Notify people**, **Send**.

That's it. The code finds the sheet by its name among the files shared with the service account. Optionally pin it with `LULA_WORKBOOK_ID` (the long string in its URL between `/d/` and `/edit`), which is required only if two shared sheets have the same name.

## 4. Check and create the tabs

```bash
pip install -e ".[google]"
python -m lulamacaroni.google_check               # read-only: key, token, sheet, tabs
python -m lulamacaroni.setup_workbook --dry-run   # preview
python -m lulamacaroni.setup_workbook             # creates the 17 tabs with headers and dropdowns
python -m lulamacaroni.google_check               # should end with "all 17 tabs present"
```

`google_check` prints only the service account email, never the key, and says which step fails and what to do (for example, which domain to allow). `setup_workbook` never deletes a tab or a row, so it is safe to re-run when the schema changes. The empty default tab ("Hoja 1") can be deleted by hand.

## How the code uses it

- As soon as a Google key is configured, the connectors, the back office app and the approvals use the sheet. Without a key (tests, a laptop), they use local JSON files in `data/libro/`. `LULA_LIBRO=local` or `LULA_LIBRO=google` forces one. If Google is configured but fails, you get the error, never old local data that looks current.
- Writes are RAW, so a product title or a customer name is stored as text and can never run as a formula. An update writes only the cells it owns, so notes and formulas people add in other columns stay.
- The app reads all tabs in one request and keeps them for 30 seconds, well under Google's read limit. Any write is visible right away.
- Approvals live in the `Aprobaciones` tab, which becomes the audit trail.

## At handover

Lorena (or Jon with her) deletes the key and creates a new one, and the new key goes only into her Claude cloud environment. The project and the sheet already belong to the business account, so nothing else moves.
