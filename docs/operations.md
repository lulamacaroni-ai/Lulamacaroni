# Setup and operations guide (for Jon)

How the back office is wired today, how to run it, and what to hand over. Lorena's own guide is the Spanish [runbook-es.md](runbook-es.md). Step-by-step setup for each service is in [setup/](setup/). This page names variables only and never their values.

Status: 2026-11-02.

## 1. Where it runs

Everything runs in the Claude project's cloud environment **"LulaMacaroni"** (the project default). There is no local install and no server yet. A session runs the connectors and the app on demand. The app binds to `127.0.0.1:8770`, and Claude takes screenshots of it.

To run it on Jon's Windows PC: [run-local.md](run-local.md) (`run.bat`, `sync.bat`). To host it for Lorena behind a password: [hosting.md](hosting.md) (Render, `render.yaml`). The server refuses to listen beyond 127.0.0.1 unless `LULA_APP_PASSWORD` is set.

**Environment and network changes reach new sessions only.** After editing the environment, start a new thread before testing.

## 2. Environment variables

Set in Project settings → Cloud environment → gear next to "LulaMacaroni". One `KEY=value` per line. The full list with comments is in [`.env.example`](../.env.example).

Set now:

| Variable | What it is | Setup doc |
|---|---|---|
| `SHOPIFY_STORE_DOMAIN` | The `*.myshopify.com` address, not the public domain | [shopify.md](setup/shopify.md) |
| `SHOPIFY_CLIENT_ID` | Dev Dashboard app "LulaMacaroni Operaciones" | same |
| `SHOPIFY_CLIENT_SECRET` | Same app; client-credentials grant, token never stored | same |
| `PRODIGI_API_KEY` | Live key | [prodigi.md](setup/prodigi.md) |
| `PRODIGI_SANDBOX_API_KEY` | Sandbox key (separate sandbox account) | same |
| `GOOGLE_SERVICE_ACCOUNT_JSON_B64` | Base64 of the whole service-account JSON file, on one line | [google-cloud.md](setup/google-cloud.md) |

Optional, with safe defaults:

| Variable | Default | Notes |
|---|---|---|
| `PRODIGI_ENV` | `sandbox` | **Set it to `live` in the cloud environment for real Prodigi costs.** Unset means sandbox, which writes `prodigi-sandbox` in Fuentes and never falls back to the live key |
| `LULA_WORKBOOK_NAME` | `LulaMacaroni Operaciones` | The sheet is found by name among files shared with the service account |
| `LULA_WORKBOOK_ID` | empty | Pin the sheet only if two shared sheets have the same name |
| `LULA_LIBRO` | auto | `google` or `local`; auto = Google when a key is set |
| `LULA_TZ` | `America/Mexico_City` | "Hoy" and all periods use this zone |
| `SHOPIFY_API_VERSION` | `2025-10` | |
| `LULA_INVESTIGACION_CARPETA_ID` | empty | Pin the research Drive folder; otherwise it is found by the name "LulaMacaroni Investigación" |

Not set yet (sources not connected): Etsy (`ETSY_*`), QuickBooks (`QBO_*`), Meta (`META_*`, `INSTAGRAM_BUSINESS_ID`), Pinterest (`PINTEREST_ACCESS_TOKEN`), `ANTHROPIC_API_KEY` for scheduled agents, `LULA_DRIVE_FOLDER_ID`.

## 3. Allowed domains

Network access → Allowed domains on the same environment:

- `xve3fx-zk.myshopify.com` (the wildcard `*.myshopify.com` alone did not work)
- `api.prodigi.com`, `api.sandbox.prodigi.com`
- `sheets.googleapis.com`, `www.googleapis.com`, `oauth2.googleapis.com`

When Etsy, QuickBooks, Meta or Pinterest get connected, add their API hosts here too.

## 4. Google service account and the sheet

- Project **LulaMacaroni Operaciones** under the business Google account, with Sheets API and Drive API enabled.
- Service account `backoffice` (no project roles). Its JSON key is the only credential. The org policy `iam.disableServiceAccountKeyCreation` was overridden to Off for this project only so the key could be created.
- The token exchange uses PyJWT; `google-auth` is not needed.
- Sheet **LulaMacaroni Operaciones** in the business Drive, shared with the service account email as **Editor** (Notify off). The code finds it by name.
- Check without changing anything: `python -m lulamacaroni.google_check`. It prints the service-account email only and names the failing step.
- Tabs: `python -m lulamacaroni.setup_workbook --dry-run`, then without `--dry-run`. It only adds tabs, columns and dropdowns. It never deletes a tab, column or row.

**Pending your OK:** one `setup_workbook` run from PR #9's branch adds the Publicidad and Topes tabs and the new Clientes/Pedidos columns. Until it runs, the Shopify sync can't write the new columns, and Publicidad shows its numbers as missing.

## 5. Daily operations

```bash
pip install -e ".[google,dev]"
pytest                                                   # offline, no keys
python -m lulamacaroni.sync                              # THE daily command (PR #12): Shopify, then Prodigi, then today's alerts
python -m lulamacaroni.connectors.shopify --dry-run      # counts, writes nothing
python -m lulamacaroni.connectors.shopify                # Shopify alone: Listados, Pedidos, Clientes, fees, payouts
python -m lulamacaroni.connectors.prodigi --sync         # Prodigi alone: real costs into Pedidos (read-only on Prodigi)
python -m lulamacaroni.connectors.investigacion          # monthly: new eRank/EverBee CSVs from the Drive folder (PR #10)
python -m lulamacaroni.app.alertas                       # Resumen del día + alerts as text
python -m lulamacaroni.app.semanal                       # weekly summary, last full week (--actual: this week so far) (PR #14)
python -m lulamacaroni.app.server                        # the app on real data, http://127.0.0.1:8770
python -m lulamacaroni.app.server --demo                 # sample data, clearly marked
```

`sync` runs Shopify first, then Prodigi (Prodigi costs attach to Shopify orders). Each source is independent: if one fails, the others still run and the failed one is marked `error` in `Fuentes`, keeping its last good update time, so the app says the sync failed instead of showing old numbers as current. Prodigi uses `PRODIGI_ENV`, so real costs need `PRODIGI_ENV=live` in the environment. Nothing is scheduled yet; the syncs run when a session runs them.

Mexico site (PR #13): needs `LULA_MX_RESPONSABLE` and `LULA_MX_DOMICILIO` (aviso de privacidad), plus `LULA_MX_CORREO`/`LULA_MX_WHATSAPP`; not secrets, but keep the address out of the repo. Build, `solicitar` (a `listado` approval on the exact manifest), then `publicar` with that approval id. Details in [setup/sitio-mx.md](setup/sitio-mx.md).

Research (PR #10): share a Drive folder named **LulaMacaroni Investigación** with the service account as Viewer. Drive calls go through `www.googleapis.com`, which is already allowed. Lorena drops the monthly eRank/EverBee CSVs there ([setup/investigacion-es.md](setup/investigacion-es.md)).

Writes to the outside world all go through the approval gate (`assert_approved()` with the exact content, then `mark_executed()`). Today the only external write in code is `create_draft_product` in Shopify (a draft, with an approved `listado`) and a Prodigi manual order (with an approved `pedido-manual`). See [approval-gate.md](approval-gate.md).

## 6. Known issues to fix in the store before Nov 13

- 10 live products (94 variants) have no SKU and sit on the "Manual" location, so no print app receives their orders. This is the urgent alert in the app, and likely why the storefront shows Sold out.
- 7 unlisted duplicates (578 variants, `FIE-` SKUs) route to Frame It Easy. Prodigi has 0 products.
- Each live product must route to exactly one printer, never both (double print and charge).
- Test order-confirmation email deliverability.
- Which Prodigi field carries the Shopify order number is unconfirmed; the first real order settles it (`--check` prints the references).

## 7. The stacked PRs

All drafts in `lulamacaroni-ai/Lulamacaroni`, none merged yet. Through #9 each is based on the one before it, so merge in order from the bottom (#1 first). #10 to #14 all sit on #9 independently.

| PR | Branch | What |
|---|---|---|
| #1 | `claude/project-thread-9eqijk` → `main` | Foundation: schema (tabs), approval gate, Shopify and Prodigi connectors, print-file check |
| #2 | `claude/project-thread-ynjl75` → #1 | Back office app v1: Inicio, Pedidos, Catálogo, Fuentes, Aprobar |
| #3 | `claude/project-thread-d8z532` → #2 | Shopify card fees, per-order margin, "Por recibir" from payouts |
| #4 | `claude/project-thread-ys1n39` → #2 | Prodigi real costs into Pedidos |
| #5 | `claude/project-thread-cbwydj` → #2 | Google Sheets data layer (also merges #3) |
| #6 | `claude/project-thread-v57sz8` → #5 | Resumen del día and Alertas (also merges #4) |
| #7 | `claude/project-thread-yqb3bh` → #6 | Catálogo product pages and Contenido |
| #8 | `claude/project-thread-52o9j9` → #7 | Publicidad: campaigns, Topes, attribution |
| #9 | `claude/project-thread-avr357` → #8 | Clientes |
| #10 | `claude/project-thread-9e5fls` → #9 | Investigación: eRank/EverBee CSV importer from Drive, trends, competitor prices, keyword ideas |
| #11 | `claude/project-thread-95gzdm` → #9 | Runbook (ES) and this guide; docs only |
| #12 | `claude/project-thread-o6002v` → #9 | `python -m lulamacaroni.sync`: one daily sync, failed sources marked `error` |
| #13 | `claude/project-thread-eypv5y` → #9 | Mexico catalog site, phase 1: Spanish browse-only originals ([setup/sitio-mx.md](setup/sitio-mx.md)) |
| #14 | `claude/project-thread-ieltm9` → #9 | Finanzas view (gross vs net vs deposits, fees, Prodigi costs, margin before/after ads, USD and MXN apart) and the weekly summary at `/semana` (Decisiones tab) |

Later: Etsy (once the account exists), QuickBooks (business profit and cash flow in Finanzas), Cloudflare Access hosting, scheduled syncs.

## 8. Handover

See [handover.md](handover.md) for the checklist. In short: Lorena changes every password, regenerates each key (Shopify client secret, both Prodigi keys, the Google service-account key), puts the new values in her cloud environment, starts a new session, and runs `google_check`, `prodigi --check` and `shopify --dry-run`. The runbook's section 8 walks her through it in Spanish.

The repo is public. Consider making it private before real orders and customers arrive; it holds no secrets or data either way.
