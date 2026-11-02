# Handover to Lorena

Jon builds everything, and then Lorena runs it from her own Claude account. These rules keep that handover clean from day one:

- **Built in her accounts.** The Google Cloud project, the developer apps (Etsy, Pinterest, Meta), the Prodigi keys, the Shopify custom app and this GitHub repo all live under Lorena's or the business's accounts.
- **Secrets only in `.env` during the build**, which git ignores. Variable names are listed in `.env.example` with empty values.
- **Nothing goes live without her approval** during the build, either. Drafts are fine; publishing, spending and real orders go through the approval page.

## What she receives

1. A Claude project with Spanish instructions, the plan docs, and the agents and skills from this repo.
2. This repo, already in her GitHub account (`lulamacaroni-ai`).
3. A Claude cloud environment holding the API keys as secrets. They are entered once and never put in the repo or chat.
4. Her own Google Drive and Gmail connectors on the business account.
5. The Spanish runbook ([runbook-es.md](runbook-es.md)).

## Handover checklist

- [ ] Change every password used during the build (password manager).
- [ ] Regenerate the keys:
  - [ ] Prodigi API keys
  - [ ] Shopify custom app token
  - [ ] Etsy app secret and refresh token
  - [ ] Google service-account key
  - [ ] QuickBooks app secret
  - [ ] Meta and Pinterest tokens
- [ ] Put the new keys in her Claude cloud environment's secrets.
- [ ] Downgrade Jon to a collaborator seat where the service allows one (Google, Pinterest, GoDaddy delegate, Shopify staff), or remove him.
- [ ] Confirm two-factor sign-in on every account goes to her phone.
- [ ] Run `pytest` and one sandbox approval end to end from her account.
