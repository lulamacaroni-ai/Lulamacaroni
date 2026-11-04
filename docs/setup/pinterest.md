# Pinterest: connect the account (read-only)

The back office **reads** Lorena's business Pinterest account (`@lulamacaroni`, login `info@lulamacaroni.com`): her boards, her pins, the account's daily impressions, saves and clicks, each pin's numbers for the last 30 days, and ad spend if the account ever gets a Pinterest ad account. It never creates, edits or deletes anything on Pinterest. It stores nothing about other people (no comments, followers or audiences).

What shows up where:

| Screen | What |
|---|---|
| Contenido → Pinterest | Impressions, saves, link clicks and pin clicks for the last 30 days of data; the most seen pins with the Shopify product each one links to; the boards |
| Anuncios, Inicio, Finanzas | Pinterest ad spend, only if an ad account exists. Without one it stays "fuente no conectada", never $0 |
| Fuentes | `Pinterest` and `Pinterest Ads`, the last sync, and when the permission expires |
| Alertas | A warning 7 days before the permission expires |

## Settings (names only)

| Variable | Where | What |
|---|---|---|
| `PINTEREST_ACCESS_TOKEN` | Claude cloud environment "LulaMacaroni" (and `.env` if you run `sync.bat`) | The permission made below |
| `PINTEREST_TOKEN_VENCE` | Same place | Its expiry date, copied together with it |

**Render does not need them.** The hosted app only reads the Sheet; the sync runs in a Claude session (or `sync.bat`).

Under **Network access → Allowed domains** of the same environment, add `api.pinterest.com`. Environment changes reach new sessions only.

Never paste the token or the app secret in chat, docs, email or git.

## 1. Create the developer app (once)

1. In the browser where you're signed in to Lorena's Pinterest, open <https://developers.pinterest.com/apps/>.
2. If it asks you to accept the developer terms, accept them.
3. Click **Connect app** (or *Create app*).
4. Fill in:
   - **App name:** `LulaMacaroni Oficina`
   - **Company name:** `LulaMacaroni`
   - **Website URL:** `https://lulamacaroni.com`
   - **Privacy policy URL:** `https://lulamacaroni.com/policies/privacy-policy`
   - **Description / purpose:** `Read-only reporting of our own boards, pins and analytics for our internal back office. No posting.`
   - If it asks what the app is for, pick the analytics/reporting option and say it's for your own account.
5. Submit. The app card shows **Trial access pending** until Pinterest approves it. That usually takes from minutes to a day or two; you get an email at `info@lulamacaroni.com`.
6. When the card says **Trial access**, open the app and keep the page open. In step 2 you copy two values straight from it:
   - **App ID** (a number)
   - **App secret key** (click *Show*)
7. On the same page find **Redirect URIs**, add exactly `http://localhost:8085/` and click **Save** (or *Add*).

### Trial vs Standard access

Trial access is enough for this: it reads your own account, boards, pins and analytics. Its limits are about 1,000 API calls a day per app (the daily sync uses roughly 110) and that pins *created* through the API stay private, which doesn't matter because we don't create pins. **Standard access** (the *Upgrade* button on the app card; Pinterest asks for a demo video and reviews it by hand) is only needed later if the back office should publish pins or if Pinterest ads reading turns out to need it.

## 2. Make the permission (about 2 minutes; again about once a month)

On your Windows PC:

1. Press the **Windows** key, type `PowerShell`, and open **Windows PowerShell**.
2. Copy the whole block below, right-click inside the PowerShell window to paste it, and press **Enter**. It needs no edits.

```powershell
& {
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  $appId = (Read-Host "Pinterest App ID").Trim()
  $sec = Read-Host "Pinterest App secret key (it won't show while you paste)" -AsSecureString
  $secret = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)).Trim()
  $redirect = "http://localhost:8085/"
  $scopes = "user_accounts:read,boards:read,pins:read,ads:read"
  $url = "https://www.pinterest.com/oauth/?client_id=$appId&redirect_uri=$([uri]::EscapeDataString($redirect))&response_type=code&scope=$scopes&state=lula"
  Start-Process $url
  Write-Host ""
  Write-Host "In the browser: click 'Give access'. The next page says the site can't be reached. That's expected."
  $back = Read-Host "Click the browser's address bar, press Ctrl+A then Ctrl+C, come back here, right-click to paste, press Enter"
  if ($back -notmatch "[?&]code=([^&]+)") { Write-Host "No code in that address. Run the block again." -ForegroundColor Red; return }
  $basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$($appId):$secret"))
  try {
    $r = Invoke-RestMethod -Method Post -Uri "https://api.pinterest.com/v5/oauth/token" -Headers @{ Authorization = "Basic $basic" } -ContentType "application/x-www-form-urlencoded" -Body @{ grant_type = "authorization_code"; code = $Matches[1]; redirect_uri = $redirect }
  } catch { Write-Host "Pinterest refused: $($_.Exception.Message). Run the block again." -ForegroundColor Red; return }
  $vence = (Get-Date).AddSeconds([int]$r.expires_in - 86400).ToString("yyyy-MM-dd")
  "PINTEREST_ACCESS_TOKEN=$($r.access_token)`r`nPINTEREST_TOKEN_VENCE=$vence" | Set-Clipboard
  Write-Host ""
  Write-Host "Done. Two lines are on your clipboard. The permission expires $vence." -ForegroundColor Green
  Write-Host "Permissions granted: $($r.scope)"
}
```

3. It asks for the **App ID**: copy it from the Pinterest app page, right-click in PowerShell to paste, **Enter**.
4. It asks for the **App secret key**: copy it the same way, right-click to paste (nothing shows, that's normal), **Enter**.
5. A browser tab opens on Pinterest asking to give *LulaMacaroni Oficina* access. Check it's the `@lulamacaroni` account and click **Give access** (or *Allow*).
6. The tab then says *This site can't be reached* with `localhost` in the address. That's expected. Click the address bar, **Ctrl+A**, **Ctrl+C**, go back to PowerShell, right-click, **Enter**.
7. PowerShell says **Done** in green and the expiry date. Two lines are now on your clipboard. Don't paste them anywhere except the next step.

## 3. Put it in the cloud environment

1. Open the Claude project → **Project settings** → **Cloud environment** → the gear next to **LulaMacaroni**.
2. Click at the end of the environment variables box, press **Enter** for a new line, and **Ctrl+V**. Two new lines appear: `PINTEREST_ACCESS_TOKEN=…` and `PINTEREST_TOKEN_VENCE=…`. (When you renew, replace the two old lines instead of adding new ones.)
3. Under **Allowed domains**, add `api.pinterest.com` (first time only).
4. **Save**. Then start a new thread and ask Claude to "sync Pinterest". It runs `python -m lulamacaroni.connectors.pinterest --check` first (prints only the account name and counts), then the sync.

From then on the daily `python -m lulamacaroni.sync` includes Pinterest automatically.

## Renewing

Pinterest permissions made this way last about 30 days. Pinterest's renewal tokens change on every use and the sync can't save a new secret into the environment by itself, so it doesn't renew on its own. A week before the date, Alertas says **"Pinterest: el permiso vence en N día(s)"**. Repeat steps 2 and 3 (same app, same block). If it expires anyway, nothing breaks: Pinterest numbers show as out of date (`atrasada`), never as zero, until the new one is in.

## Commands

```bash
python -m lulamacaroni.connectors.pinterest --check     # account name, counts, expiry; writes nothing
python -m lulamacaroni.connectors.pinterest --dry-run   # what the sync would write; writes nothing
python -m lulamacaroni.connectors.pinterest             # sync into the Sheet
```

The Sheet needs three new tabs first (`Tableros`, `Pines`, `PinterestDiario`): `python -m lulamacaroni.setup_workbook --dry-run`, then without `--dry-run`. It only adds tabs, headers and dropdowns.
