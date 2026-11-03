# Setup: Shopify connector

The store has a Dev Dashboard app named **LulaMacaroni Operaciones**. Its scopes are read/write products and inventory, read orders, customers, reports and locations, plus read merchant-managed and third-party fulfillment orders (added 2026-11-02). It uses the client-credentials grant: the connector trades the Client ID and secret for a short-lived Admin API token each run, and never stores the token.

## Where the credentials go

They go in the **Claude cloud environment**, never in chat, docs or this repo:

1. Open Project settings → Cloud environment, and edit the LulaMacaroni environment (or add it).
2. Add these environment variables:
   - `SHOPIFY_STORE_DOMAIN`: the `*.myshopify.com` address (Shopify admin → Settings → Domains), not the public domain
   - `SHOPIFY_CLIENT_ID`
   - `SHOPIFY_CLIENT_SECRET`
3. Under network access, allow `*.myshopify.com`.

On a local machine, the same names go in `.env` instead.

## Run

```bash
python -m lulamacaroni.connectors.shopify --dry-run          # counts + 3 sample rows, writes nothing
python -m lulamacaroni.connectors.shopify --to-json exports/  # files (git-ignored), before the workbook exists
python -m lulamacaroni.connectors.shopify                    # upsert Listados + Pedidos, stamp Fuentes
```

## Prodigi and Frame It Easy are already on the store

Both apps receive Shopify orders on their own and print them. The connector records who fulfils each order line in `Pedidos.ruta_pod` (`prodigi-app`, `frame-it-easy-app`, `manual`, `desconocida`). It reads this from the fulfilment location Shopify assigned.

- A line routed to an app is **never** sent through the Prodigi API as well; that would print and charge twice. The Prodigi API is only for approved reprints and manual orders.
- A line marked `manual` or `desconocida` means no app picked it up. The dry run counts these lines, and Operaciones raises them as exceptions.
- Decide which app prints which products, so one product isn't mapped in both apps.

## Limits

- Without the `read_all_orders` scope, Shopify returns only the last 60 days of orders. That's fine for the daily sync. Older history needs that scope or a one-time CSV export.
- Channel fees and Prodigi costs are not in the order. Those columns stay empty, with `calidad_dato = faltante`, until the payouts and Prodigi syncs fill them.
- The only write is `create_draft_product`. It creates a **draft** and needs an approved `listado` record. Publishing is a separate approved step.
