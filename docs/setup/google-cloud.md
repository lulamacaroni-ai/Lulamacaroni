# Setup: Google Cloud service account and workbook (M7)

About 15 minutes. Do it signed in as the **business Google account**, not a personal one, so everything hands over with the business. Nothing from these steps goes into the repo.

## 1. Google Cloud project

1. Go to <https://console.cloud.google.com/> and sign in with the business account.
2. Create a project named `lulamacaroni-ops`.
3. Open **APIs & Services → Library** and enable **Google Sheets API** and **Google Drive API**.

## 2. Service account

1. Open **IAM & Admin → Service Accounts → Create service account**.
2. Name it `lulamacaroni-bot`. Skip the optional roles; it needs none at project level.
3. Open the new account, go to **Keys → Add key → Create new key → JSON**, and download it.
4. In the Claude cloud environment (Project settings → Cloud environment), add a variable `GOOGLE_SERVICE_ACCOUNT_JSON` whose value is the **whole text** of that JSON file. Then delete the downloaded file. (On a local machine instead: keep the file outside the repo and set `GOOGLE_APPLICATION_CREDENTIALS` to its path in `.env`.)
5. Allow `*.googleapis.com` in the environment's network access.
6. Copy the service account's email address, which looks like `lulamacaroni-bot@lulamacaroni-ops.iam.gserviceaccount.com`.

## 3. Workbook and Drive folder

1. In Google Drive (business account), create a folder named `LulaMacaroni` with these subfolders: `masters`, `impresion`, `web`, `mockups`, `investigacion`.
2. In that folder, create an empty Google Sheet named **LulaMacaroni Operaciones**.
3. Share the folder with the service account email as **Editor**. The sheet inherits access from the folder.
4. Add the sheet's ID to the cloud environment as `LULA_WORKBOOK_ID`. The ID is the long string in its URL between `/d/` and `/edit`. Add the folder's ID as `LULA_DRIVE_FOLDER_ID`.

## 4. Create the tabs

```bash
pip install -e ".[google]"
python -m lulamacaroni.setup_workbook --dry-run   # preview
python -m lulamacaroni.setup_workbook             # creates 15 tabs with headers and dropdowns
```

It never deletes anything, so it is safe to re-run when the schema changes.

## At handover

Lorena (or Jon with her) deletes the key and creates a new one, and the new key goes only into her Claude cloud environment's secrets. The project and the sheet already belong to her account, so nothing else moves.
