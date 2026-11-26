# Our own store (canal `web`)

The store on lulamacaroni.com replaces the Shopify storefront. It lives in `lulamacaroni/tienda/` and runs in the same Render service as the back office:

| Host | Who | What answers |
|---|---|---|
| `lulamacaroni.com`, `www.lulamacaroni.com` (`LULA_TIENDA_HOSTS`) | Buyers, no login | The store, in English |
| `admin.lulamacaroni.com`, the `onrender.com` address, `127.0.0.1` | Lore and Jon, password | The back office, now the store's admin (new **Tienda web** screen) |

## How an order flows

1. The buyer picks a size and frame and adds it to the cart. The cart is a signed cookie that holds SKUs and quantities only.
2. **Check out securely** creates a Stripe Checkout Session with prices taken from the workbook (never from the browser), US-only shipping, and Stripe Tax. The buyer pays on Stripe's page; card data never reaches us.
3. Stripe calls `POST /stripe/webhook` (`checkout.session.completed`). The signature is checked, then the session is read back from Stripe and recorded:
   - `Pedidos`: one row per line, `canal = web`, number `LM-1001` onwards, `calidad_dato = estimado` until the real Stripe fee and Prodigi cost arrive.
   - `Clientes`: `stripe-<customer id>`, first name + last initial, state, country. **Email, phone and street address stay in Stripe.**
   - `Aprobaciones`: a `pedido-tienda` request with exactly what Prodigi will receive, except the street address, which is stored as a SHA-256 fingerprint.
   - The buyer gets the confirmation email (Resend, from `orders@lulamacaroni.com`).
   - If a SKU has no print file or Prodigi SKU, the order becomes an `Excepciones` row instead, and no approval is created.
4. Lore approves in **Aprobar**. Every few minutes the service sends approved orders to Prodigi: it reads the address from Stripe, checks it against the approved fingerprint, sends the order with the approval id as Prodigi's `idempotencyKey`, and marks the approval used. A changed address means no print and a new exception.
5. When Prodigi reports tracking, the buyer gets the shipped email and `Pedidos` moves to `enviado`.

Prints always use `sizing: fitPrintArea`: Prodigi never crops or stretches the file. The print file must already have the right proportion (the resolution check reports it).

## Later: automatic approval of routine orders

For now Lore taps every order (JIM, 2026-11-26). The plan for automating it is still an approval: Lore approves one standing rule, for example "send to Prodigi any order whose items all have a checked print file, whose total is under US$300, and whose address matches Stripe", with an expiry date. An order that fits the rule is sent and recorded against it, and anything outside the rule still waits for her tap. There is no bypass flag; switching the rule off is one tap in Aprobar.

## Putting products on sale

```bash
python -m lulamacaroni.tienda.publicar semilla --dry-run   # Shopify's 10 live products -> 94 draft options
python -m lulamacaroni.tienda.publicar semilla             # write them to Obras, Variantes, Listados (borrador)
python -m lulamacaroni.tienda.publicar solicitar           # one approval for the whole catalog + policies
python -m lulamacaroni.tienda.publicar publicar apr-...    # after Lore approves: on sale
```

The approval covers every SKU, title, price, photo link and description fingerprint, plus the four policy texts. Any later change needs a new approval.

Prodigi SKUs come from the size (`16x12` becomes `GLOBAL-BOX-12X16`, frame colour `black` or `white`). `Variantes.archivo_impresion` must hold the full-size print file's URL before that option can be printed.

## Photos

Phase 1 uses the product photo links copied from Shopify. They stop working when Shopify closes, so before the switch the photos move to a Drive folder and the links in `Listados` are updated. Photos are shown whole (`object-fit: contain`).

## Settings

| Setting | What |
|---|---|
| `STRIPE_SECRET_KEY` | `sk_test_...` while testing, `sk_live_...` at launch |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` from the webhook endpoint in Stripe |
| `RESEND_API_KEY` | order emails |
| `LULA_TIENDA_HOSTS` | `lulamacaroni.com,www.lulamacaroni.com` |
| `LULA_TIENDA_URL` | `https://lulamacaroni.com` |
| `LULA_TIENDA_SECRET` | any long random text; signs the cart (Render can generate it) |
| `LULA_US_RAZON_SOCIAL`, `LULA_US_DOMICILIO`, `LULA_US_ESTADO` | the LLC's legal name, address and state, shown in the policies |
| `LULA_TIENDA_ENVIO_USD` | flat shipping per order; `0` (default) = free shipping |
| `LULA_TIENDA_IMPUESTOS` | `no` turns Stripe Tax off (default on) |

Checkout stays closed (the cart says "Checkout opens soon") until Stripe's two keys, the legal settings and the cart secret are all set. The **Tienda web** screen lists what's missing.

## Run it locally

```bash
python -m lulamacaroni.tienda.server --demo   # sample catalog with placeholder images, http://127.0.0.1:8780
python -m lulamacaroni.tienda.envios          # one pass: approved orders to Prodigi, tracking emails
```

## Refunds

`StripeClient.reembolsar` refunds only with an approved `reembolso` record for the exact content. Phase 1 has no refund button yet: Lore refunds from the Stripe dashboard, or Claude prepares the approval.

## Later phases

Chat (Crisp) and the CRM in Clientes; analytics, Merchant Center feed, Pinterest and Meta tags, and email campaigns for buyers who opt in. See the plan doc.
