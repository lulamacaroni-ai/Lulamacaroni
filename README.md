# LulaMacaroni

Back office for **Lula Macaroni**, the art studio of Lorena Vazquez. One platform covers two lines of business:

| Line | Tag | What it is |
|---|---|---|
| US prints | `US-POD` | Prints sold on Shopify (principal store) and Etsy, printed and shipped inside the US by Prodigi, under the US LLC |
| Mexico originals | `MX-original` | Original pieces shown to local buyers on a Spanish catalog site. Phase 1 is browse-only, and buyers ask by WhatsApp or email. Phase 2 adds checkout and CFDI once the contador decides the fiscal setup |

Both lines share one workbook, one dashboard, one set of agents and one approval page. Every record is tagged by line, so the money never mixes.

The goal is for Lorena to spend her time making art. The system drafts, checks and reports, and **she approves anything that publishes, spends, refunds or cancels.**

## What's here

```
lulamacaroni/
  schema.py            Workbook tabs, columns, dropdowns, linea tags (system of record)
  setup_workbook.py    Creates/updates the tabs in the Google Sheet (safe to re-run)
  schema_doc.py        Regenerates docs/data-layer.md from the schema
  config.py            Reads settings from .env (never from code)
  approval/            Approval gate, store, and the Spanish approval page
  workbook.py          Read and upsert rows in the workbook by key; stamps Fuentes
  workbook.py          The Google Sheet: key, find the sheet, cached reads, RAW upserts
  google_check.py      Read-only check of key, token, sheet and tabs
  localbook.py         Same thing in local JSON files (data/libro/) when no Google key is set
  app/                 The back office app: Inicio, Alertas, Aprobar, Catálogo, Contenido, Publicidad, Pedidos, Clientes, Fuentes (Spanish)
  connectors/shopify.py  Shopify Admin GraphQL (client-credentials app): listings, orders, POD routing
  connectors/prodigi.py  Prodigi Print API v4 (orders, tracking, quotes, products)
  checks/resolution.py   Print-file resolution/proportion check, never crops or stretches
  checks/guards.py       Discontinued-POD and sold-original guards
docs/
  architecture.md      How the pieces fit, phases and gates
  data-layer.md        Every tab and column (generated)
  approval-gate.md     The approval rules and how hosting works
  setup/google-cloud.md  Step by step: service account + workbook
  setup/shopify.md     Where the Shopify app's credentials go
  runbook-es.md        Lorena's runbook in Spanish (stub, grows with the build)
  handover.md          What Lorena receives and what she rotates
tests/                 pytest suite (no network, no secrets)
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[google,dev]"
cp .env.example .env          # local only; in the Claude cloud environment use its environment variables
pytest                        # everything runs offline

python -m lulamacaroni.setup_workbook --dry-run         # what the workbook will look like
python -m lulamacaroni.approval.server --demo           # approval page with sample requests
python -m lulamacaroni.app.server --demo                # back office app with sample data
python -m lulamacaroni.connectors.shopify               # live read-only sync (to the sheet, or data/libro/ without a key)
python -m lulamacaroni.app.server                       # back office app on that data, http://127.0.0.1:8770
python -m lulamacaroni.app.alertas                      # today's summary + alerts as plain text (read-only)
python -m lulamacaroni.checks.resolution obra.jpg 8x10 12x16 18x24
```

## Rules for this repo

1. **This repo is public, so it never holds secrets or business data.** API keys and tokens go only in the git-ignored `.env`, and at handover they move to Lorena's Claude cloud environment as secrets. No passwords, EINs, RFCs, customer data, order exports or art files. Art lives in Google Drive, and records live in the workbook.
2. **Everything is created in Lorena's accounts, never Jon's.** That covers the Google Cloud project, the Etsy, Pinterest and Meta developer apps, and the Prodigi keys. Nothing depends on a personal account of whoever built it.
3. **Nothing publishes, spends, refunds or cancels without an approval record** whose fingerprint matches the exact content (see `docs/approval-gate.md`).
4. **Never stretch, crop or AI-regenerate the art.** If a size doesn't fit, the check says so and Lorena supplies a file.
5. **Every number says where it came from**: source, period, last update, and whether it is real, estimated or missing.
6. Language: customer-facing text for US buyers is in English. Anything Lorena reads (workbook, approval page, runbook) and the Mexico site are in Mexican Spanish.

## Status

| Milestone | State |
|---|---|
| M6 Repo foundation | This PR |
| M7 Workbook | Service account, key and data layer ready; share the sheet with the service account, then run `setup_workbook` ([setup](docs/setup/google-cloud.md)) |
| M9 Resolution check | Ready; DPI thresholds to confirm with Prodigi samples |
| M10 Connectors | Shopify ready (needs the app credentials in the cloud environment); Prodigi ready (needs sandbox key); Etsy, QuickBooks next |
| M11 Dashboard | First read-only slice: Inicio (daily summary: qué pasó, qué requiere atención, 3 actions; Shopify / Etsy / accounting slots; today, 7, 30 days vs prior period), Alertas, Pedidos, Catálogo (per-variant printer, cost, estimated margin, print-file check, Mexico originals), Contenido (calendar and queue per platform, approval status per piece), Publicidad (planned campaigns in the Publicidad tab, spend limits in Topes, approval per campaign and budget change, Shopify order attribution from UTM/referrer; platform results "—" until an ad API is connected; nothing is ever sent to a platform), Clientes (Shopify customers synced with minimal data: short name, country/state, Shopify's order count and total, email consent; Mexico buyers typed in the Clientes tab; how each buyer first arrived from Shopify's customer journey; notes with who/when and follow-ups, overdue ones feed the daily summary; Etsy slot "fuente no conectada"), Fuentes. Every number carries source, period, definition, last update and real / missing / estimated |
| M12 Approval gate | Gate, store and page ready, also inside the app as Aprobar; hosting behind Cloudflare Access next |
