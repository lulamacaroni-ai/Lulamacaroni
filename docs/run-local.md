# Run the back office on your own Windows computer

This opens the app in your browser at `http://127.0.0.1:8770`, reading the real Shopify store and the real Google Sheet. Only your computer can open that address. Nothing in the store changes: the app only reads, except **Aprobar / Rechazar**, which records Lorena's decision in the Sheet's Aprobaciones tab.

## One-time setup

1. **Install Python 3.11 or newer.** Go to <https://www.python.org/downloads/windows/>, download the latest "Windows installer (64-bit)", run it, and on the first screen **tick "Add python.exe to PATH"** before clicking *Install Now*. (Skip this if you already have Python 3.11+.)
2. **Download the code.** Open the branch on GitHub, click the green **Code** button, then **Download ZIP**. In your Downloads folder, right-click the ZIP, choose **Extract All…**, and pick a folder such as `Documents\lulamacaroni`.
   - If you use git instead: `git clone -b <branch> https://github.com/lulamacaroni-ai/Lulamacaroni.git`
3. **First run.** In the extracted folder, double-click **`run.bat`**.
   - If Windows shows "Windows protected your PC", click **More info**, then **Run anyway** (the file came from the internet ZIP).
   - It creates a private Python environment (`.venv`), installs the app (about a minute), creates a file called **`.env`** and opens it in Notepad, then stops.
4. **Fill in `.env`.** In Notepad, find each line below and type the value after the `=` sign, with no spaces and no quotes. Copy each value from the Claude project: **Project settings → Cloud environment → gear next to "LulaMacaroni"**, where every line is `NAME=value`.

   | Line in `.env` | Where the value comes from |
   |---|---|
   | `SHOPIFY_STORE_DOMAIN` | Same name in the cloud environment (the `….myshopify.com` address) |
   | `SHOPIFY_CLIENT_ID` | Same name in the cloud environment |
   | `SHOPIFY_CLIENT_SECRET` | Same name in the cloud environment |
   | `PRODIGI_API_KEY` | Same name in the cloud environment |
   | `PRODIGI_SANDBOX_API_KEY` | Same name in the cloud environment |
   | `PRODIGI_ENV` | Change `sandbox` to `live` for real Prodigi costs |
   | `GOOGLE_SERVICE_ACCOUNT_JSON_B64` | Same name in the cloud environment. It is one very long line: copy all of it |

   Leave every other line as it is. Save (**Ctrl+S**) and close Notepad.

   `.env` holds the keys. It is ignored by git, so it never gets uploaded. Don't email it, paste it in a chat, or put it in a shared folder.

## Every time

| To do this | Double-click | What happens |
|---|---|---|
| Open the app | `run.bat` | A black window opens and your browser opens the app. Keep the black window open while you use it; close it (or press Ctrl+C) to stop |
| Refresh the data | `sync.bat` | Pulls Shopify and Prodigi into the Sheet, then prints today's summary and alerts. Same as `python -m lulamacaroni.sync` |
| Try with sample data | `run.bat demo` (from a PowerShell window in the folder) | Sample data only, clearly marked; no keys needed |
| Check the Google key | `run.bat check` (same) | Read-only check of the key, the Sheet and its tabs |

The browser address is <http://127.0.0.1:8770>. If you closed the tab, open that address again while the black window is running.

## If something goes wrong

- **"Python 3.11 or newer was not found"**: install Python (step 1) with "Add python.exe to PATH" ticked, then close and reopen the folder and try again.
- **"These are still empty in .env: …"**: the named lines have no value yet. Open `.env` with Notepad (right-click → Open with → Notepad) and fill them in.
- **"No se pudo leer el libro de datos"** in the browser: the Google key or Sheet sharing is off. Run `run.bat check`; it names the failing step.
- **Port already in use**: another copy is running. Close the other black window, or add `LULA_APP_PORT=8771` to `.env`.
