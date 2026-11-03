# Hosting the back office for Lorena (Render)

The app runs as one web service on [Render](https://render.com) under Lorena's accounts, at an address like `https://lulamacaroni-backoffice.onrender.com`. Every page asks for a password first. The service will not start without one.

## What the hosted app does and doesn't do

- It **reads the Google Sheet** and shows the same 12 screens as the local app. Aprobar / Rechazar records Lorena's decision in the Aprobaciones tab.
- It **does not pull from Shopify or Prodigi**. The data is as fresh as the last `python -m lulamacaroni.sync` (`sync.bat` on Jon's PC, or a Claude cloud session). So the host only needs the Google key and the password, not the Shopify or Prodigi secrets.
- **Free plan:** the service sleeps after about 15 minutes with no visits, so the first page after a pause takes about a minute to load. The paid Starter plan stays awake.

## Settings (names only)

| Variable | Value | Where it's set |
|---|---|---|
| `LULA_APP_PASSWORD` | A long password Lorena chooses (12+ characters) | Asked for when the Blueprint is created |
| `GOOGLE_SERVICE_ACCOUNT_JSON_B64` | Same as in the Claude cloud environment (one long line) | Same |
| `PRODIGI_ENV`, `LULA_TZ`, `PYTHON_VERSION` | Already in `render.yaml` | Nothing to do |

The browser login asks for a user name and a password. The user name can be anything (for example `lore`); only the password is checked.

## Steps

0. **`render.yaml` must be on the `mvp` branch.** Merge draft PR #16 into `mvp` first (GitHub → PR #16 → *Ready for review* → *Merge*). This merges into `mvp`, not `main`.
1. Go to <https://dashboard.render.com/register> and click **GitHub**. Sign in as Lorena's GitHub account (`lulamacaroni-ai`). Use `lulamacaroni@gmail.com` if Render asks for an email.
2. In the Render dashboard, click **New +** (top right), then **Blueprint**.
3. Under *Connect a repository*, click **Configure account** (or *Connect GitHub*). On GitHub's page choose **Only select repositories**, pick **Lulamacaroni**, and click **Install** (or *Save*). Back in Render, click **Connect** next to `lulamacaroni-ai/Lulamacaroni`.
4. On the Blueprint page:
   - **Blueprint Name**: `LulaMacaroni`
   - **Branch**: `mvp`
   - Render reads `render.yaml` and lists one service, `lulamacaroni-backoffice`.
   - It shows two empty boxes: type the password into `LULA_APP_PASSWORD`, and paste the long value from the Claude cloud environment into `GOOGLE_SERVICE_ACCOUNT_JSON_B64`.
5. Click **Deploy Blueprint** (or *Apply*). The first build takes a few minutes. When the service shows **Live**, click it and open the `….onrender.com` address at the top.
6. The browser asks for a user name and password. Type `lore` and the password. You should see **Inicio**.
7. Send Lorena the address. Tell her the password by phone or in person, not by email or chat.

## Changing things later

- **New code**: every push to `mvp` redeploys automatically.
- **Change the password**: Render → the service → **Environment** → edit `LULA_APP_PASSWORD` → **Save, rebuild, and deploy**.
- **Rotate the Google key at handover**: same screen, replace `GOOGLE_SERVICE_ACCOUNT_JSON_B64`.
- **Stop it**: Render → the service → **Settings** → **Suspend Web Service**.

## Not yet

- A scheduled daily sync on the host (Render Cron Job, paid). Until then, run `sync.bat` or ask Claude to sync.
- A custom address like `app.lulamacaroni.com` (Render → Settings → Custom Domains, plus a CNAME at GoDaddy).
