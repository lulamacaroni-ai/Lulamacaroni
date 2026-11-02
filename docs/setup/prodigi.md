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

## Next slice: costs and margin

1. **Read Prodigi orders and match them to `Pedidos`.** Use `merchantReference` or the sales-channel id that Prodigi's Shopify app stores. Fill in `pod_pedido_id`, `costo_pod`, `envio_pod` and tracking. The first live `--check` confirms which field carries the Shopify order.
2. **Read Shopify Payments fees** (balance transactions) into `comision_canal`. Read payouts into `Pagos`. This also fills "Por recibir".
3. **Compute `margen_contribucion` per line** once every cost is known. Mark the line `calidad_dato = real`. Until then, use `estimado` (from a Prodigi quote) or `faltante`. A missing cost is never treated as zero.
4. **Inicio and Pedidos** then show margin per order, artwork and channel, with real against estimated cost.
