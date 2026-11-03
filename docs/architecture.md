# Architecture

Source documents (owned by Jon, shared at handover): the LulaMacaroni Platform Architecture and Integration Plan, the Build Plan (M1 to M18, gates G0 to G3), the Custom Build and Agent Team doc, and Lorena's central-app requirements (15 sections).

## Layers

| Layer | US prints (`US-POD`, US LLC) | Mexico originals (`MX-original`) |
|---|---|---|
| Storefront | Shopify (principal), Etsy | Spanish catalog site, browse-only; "Pregunta por esta obra" by WhatsApp or email |
| Fulfilment | Prodigi (Charlotte, NC) through its Shopify and Etsy apps | Lorena, from the studio |
| Marketing | Instagram, Pinterest, Meta Ads later; Canva, eRank, EverBee | Instagram (Spanish posts) |
| Money | Shopify and Etsy payouts to the US bank, QuickBooks Online | Phase 2 only, in the system and entity the contador chooses |
| Language | English | Mexican Spanish |

Back office, shared by both lines:

1. **Workbook** (Google Sheets, `LulaMacaroni Operaciones`) is the system of record. See [data-layer.md](data-layer.md).
2. **Connectors** are Python jobs on a schedule that read each platform into the workbook and stamp `Fuentes` with the last update.
   - Real API: Prodigi, Shopify, Etsy, Google Drive, QuickBooks.
   - Later, after app review: Meta, Pinterest.
   - Monthly CSV import: eRank, EverBee.
   - One-time manual setup: GoDaddy, Canva.
3. **Checks** run against the catalog: print resolution and proportion, the discontinued-POD guard, the sold-original guard, and order exceptions.
4. **Dashboard** is one self-contained page with today, 7 and 30 days against the prior period, margin per artwork and channel, ad spend against break-even ROAS, freshness per source, and zero vs missing vs estimated.
5. **Approval page** is where Lorena decides. See [approval-gate.md](approval-gate.md).
6. **Agents** run on Claude:
   - Asistente: daily brief, weekly summary, answers with sources.
   - Catálogo, Listados and Visual: catalog intake, listing drafts and images.
   - Contenido and Pulso: content calendar and drafts, results and recommendations.
   - Operaciones and Finanzas: order watching, monthly close.

   Each agent writes only its own tabs and names its source and period. Claude is the only assistant for now; there is no ChatGPT parity.

## Hosting

- **GitHub:** this repo, in Lorena's account.
- **Google Cloud:** the service account for the workbook and Drive, in the business account.
- **Cloudflare Pages + Access:** the public Mexico site, plus the approval page and dashboard behind a login.
- **Claude:** her account runs the agents and holds the keys as environment secrets.
- **No database for now:** Sheets is enough. Revisit if volume outgrows it or Mexico phase 2 needs one.

## Phases

| Phase | Milestones | Gate |
|---|---|---|
| 0 Foundations | M1 business and tax, M2 accounts, M3 Prodigi, M4 Shopify, M5 Etsy | G0 Nov 13, 2026: a test order on each channel reaches Prodigi once and posts to the books |
| 1 Catalog | M6 repo, M7 workbook, M8 catalog loaded, M9 checks and knowledge base | G1 Dec 4: every live listing maps to one artwork and one approved file |
| 2 Dashboard + MVP agents | M10 connectors, M11 margin and dashboard, M12 approval page and Operaciones, M13 Asistente and Finanzas | G2 Jan 22, 2027: December margin per artwork matches the books within 2% |
| 3 Content engine (+ Mexico site phase 1, Jan 25 to Mar 5) | M14 mockups, M15 Listados and Visual, M16 Contenido | G3 Mar 5 |
| 4 Growth | M17 Pulso with ads, M18 customer inbox | none |

Lorena's full requirements list goes well beyond the MVP, so its sections land phase by phase rather than all at once.
