# Prodigi: keys and the first read-only run

Prodigi is the print-on-demand provider for the US line. Its Shopify and Etsy apps receive orders by themselves, so the back office only **reads** from Prodigi: order status, tracking and real costs. It writes only a manual order or reprint, and only with an approved `pedido-manual` record.

## Where the keys go

They go in the Claude cloud environment "LulaMacaroni" as environment variables. Never put them in chat, docs or git.

| Variable | Value |
|---|---|
| `PRODIGI_SANDBOX_API_KEY` | The sandbox key (Prodigi sandbox dashboard → Settings → Integrations → API) |
| `PRODIGI_API_KEY` | The live key (live dashboard → same place) |
| `PRODIGI_ENV` | Optional. `sandbox` (the default) or `live` |

Under network access, allow `api.sandbox.prodigi.com` and `api.prodigi.com`. Environment changes take effect only in a new session.

A sandbox run never falls back to the live key. If `PRODIGI_SANDBOX_API_KEY` is missing, the run stops with an error naming it.

## First run (changes nothing)

```bash
python -m lulamacaroni.connectors.prodigi --check                    # sandbox
PRODIGI_ENV=live python -m lulamacaroni.connectors.prodigi --check   # live, read-only
```

It prints whether the key works, how many orders there are by stage, and the references of the first three. It prints no recipient data.

## Status (2026-11-02)

Both keys work: sandbox and live each answered "key OK, 0 orders". The network block is gone.

## Costs into Pedidos

```bash
PRODIGI_ENV=live python -m lulamacaroni.connectors.prodigi --sync
```

Reads Prodigi only. Run it after the Shopify sync. For each Prodigi order it finds the Shopify order and writes **only** `pod_pedido_id`, `costo_pod` and `envio_pod` on that order's Pedidos lines, then calls `margen.recalcular(wb)` for margin and `calidad_dato`. It stamps `Fuentes` as `prodigi` (live) or `prodigi-sandbox`, so a sandbox run never looks like live data.

- **Matching.** Which Prodigi field carries the Shopify order is not confirmed yet, because there were no orders. The sync tries `merchantReference`, `idempotencyKey` and every `metadata` value, against the Shopify order name in `numero_canal` ("#1005") and the Shopify id in `pedido_id`. A Prodigi order that matches nothing is counted in the `Fuentes` note and listed by `--sync` (Prodigi id and references only), never guessed. After the first real order, run `--check`: it prints the reference and metadata keys, which settles the field.
- **Real costs only.** Costs come from the order's Prodigi `charges`. Charge lines with an item id are print cost; lines without one are shipping. An order Prodigi has not charged yet gets only `pod_pedido_id`, and its cost stays empty (missing, never zero).
- **Placing cost on lines.** Item cost goes to the Shopify line whose SKU matches the Prodigi item's `merchantReference` or SKU. If any item can't be placed, the whole item cost goes on the first Prodigi line and 0 on the others, so the order's margin is right. Shipping always goes on the first Prodigi line. Frame It Easy lines are never touched.
- Cancelled Prodigi orders are skipped.

## Still to do

- Confirm the matching field on the first real order.
- Shopify Payments fees into `comision_canal` and payouts into `Pagos` (other slice; payouts need `read_shopify_payments_payouts` and `read_shopify_payments_accounts`).
- Tracking stays from Shopify fulfillments, which the Prodigi app fills.
