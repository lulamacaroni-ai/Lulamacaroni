# Approval gate

Lorena's rule is that nothing publishes, spends, refunds or cancels without her approval. At first she approves every new ad and every budget change. Later, limited rules can run without asking, but only ones she agrees to explicitly.

## What needs approval

| `tipo` | Examples |
|---|---|
| `listado` | New or changed listing on Shopify, Etsy or the Mexico site; taking a listing down |
| `contenido` | Instagram post, reel, story; Pinterest pin |
| `anuncio` | New ad or creative |
| `presupuesto` | Any ad budget change (needs `monto_usd`) |
| `reembolso` | Refund |
| `cancelacion` | Order cancellation |
| `pedido-manual` | Manual Prodigi order or reprint |
| `respuesta-cliente` | Customer reply outside the approved templates |
| `precio` | Price change |

Read-only work never needs approval. That covers syncing orders, computing margin, drafting text and running checks.

## How a request becomes an action

```
agent drafts content ──► request_approval()  ──► Aprobaciones row, estado = pendiente
                                                   │
                         Lorena, approval page ◄───┘  Aprobar / Rechazar (+ nota)
                                                   │
publisher, right before acting ──► assert_approved(record, tipo, exact content)
                                                   │ passes only if:
                                                   │  • estado = aprobado
                                                   │  • same tipo
                                                   │  • not expired (7 days by default)
                                                   │  • not already executed
                                                   │  • SHA-256 fingerprint of the content still matches
                                                   ▼
                                     act, then mark_executed()  (one approval = one action)
```

The fingerprint is the core safeguard. Lorena sees the exact content under "Ver exactamente qué se publica", and if anything changes after she approves (price, title, budget), the fingerprint no longer matches and the action is refused until she approves the new version.

## Where records live

- **Without a Google key** (tests, a laptop): a local JSON file (`LULA_APPROVALS_PATH`, git-ignored).
- **With the Google key configured:** the `Aprobaciones` tab, through `SheetsStore` with the same methods (`add`, `get`, `update`, `all`). The workbook then becomes the audit trail. Every published item has an approval record, which is one of the Build Plan's success measures.

## Hosting so she can approve from her phone

The local server binds to `127.0.0.1` and checks that form posts come from the same origin. To use it from her phone, it gets hosted behind **Cloudflare Access** (a login in front of the page) under the business Google account, as the Architecture plan recommends. It must never be exposed without that login. The notification that something is waiting starts as an email or a plain link. WhatsApp Business is optional and comes later (M18).

## Not built yet

- ~~`SheetsStore`~~ done (`lulamacaroni/approval/store.py`)
- Notifications (daily digest of pending approvals)
- Spending caps per platform and per day (her requirement 4). The `presupuesto` type already requires an amount, so caps can be enforced at request time.
- Agreed auto-rules (later, only with her explicit OK)
