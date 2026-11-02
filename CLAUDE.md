# Working in this repo

LulaMacaroni is the back office for Lorena Vazquez's art studio. It covers two lines, `US-POD` (Shopify, Etsy and Prodigi under the US LLC) and `MX-original` (the Spanish catalog of originals), over one Google Sheets workbook. Read `README.md` and `docs/architecture.md` first.

## Hard rules

- **The repo is public.** Never commit secrets, tokens, passwords, tax IDs, customer data, order exports, art files or anyone's personal email. Settings come from `.env` through `lulamacaroni/config.py`.
- **Any action that publishes, spends, refunds, cancels or places a manual order must call `assert_approved()`** with the exact content right before acting, then `mark_executed()`. Never add a bypass flag.
- **Never crop, stretch or AI-regenerate artwork.** Checks report, and people fix.
- **Every record that touches money, a customer or a listing carries `linea`.** A schema change goes in `lulamacaroni/schema.py`; then run `python -m lulamacaroni.schema_doc`.
- Never show a missing number as zero. Use `calidad_dato` (`real`, `estimado`, `faltante`).
- Copy is in English for US buyers. The workbook, approval page, runbook and Mexico site are in Mexican Spanish.
- Tests run offline. Fake HTTP sessions, never real keys. Run `pytest` before pushing.
