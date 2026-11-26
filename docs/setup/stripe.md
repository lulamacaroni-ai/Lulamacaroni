# Stripe: create the account and connect the store

Everything is done in Lore's business account, with **lulamacaroni@gmail.com**. Keys go only into Render (and the Claude cloud environment), never into chat, email or this repo.

## 1. Create the account (about 15 minutes, then Stripe reviews it in 1 to 3 days)

1. Open https://dashboard.stripe.com/register and sign up with lulamacaroni@gmail.com.
2. Confirm the email Stripe sends.
3. In the dashboard, click **Activate payments** (or **Complete your profile**).
4. **Business type:** Company, then **LLC**. Country: **United States**.
5. **Business details:** the LLC's legal name and EIN exactly as on the IRS letter (CP 575). Address: the LLC's US address.
6. **Industry:** Retail, then **Art, photos and prints** (or the closest option). **Website:** https://lulamacaroni.com. **Product description:** "Framed fine art prints of original paintings, made to order and shipped within the US."
7. **Representative:** Lore's details as the owner.
8. **Bank account for payouts:** the Chase business account (routing and account number).
9. **Statement descriptor:** `LULA MACARONI`.
10. Submit. Stripe emails when it's approved.

## 2. Turn on sales tax (Stripe Tax)

1. Left menu: **More** then **Tax**. Click **Get started**.
2. Origin address: the LLC's address. Default product tax code: **General - Tangible Goods**.
3. Leave **Registrations** empty for now. Stripe Tax only collects in states where the LLC is registered; the contador says when one is needed, and Stripe shows when a state's threshold is getting close.

## 3. Test keys first

1. Top right, switch **Test mode** on.
2. Left menu: **Developers** then **API keys**. Next to **Secret key** click **Reveal** and copy it (it starts with `sk_test_`).
3. Paste it in Render (step 5) as `STRIPE_SECRET_KEY`.

## 4. The webhook (how Stripe tells the store an order was paid)

1. Still in test mode: **Developers** then **Webhooks** then **Add endpoint**.
2. Endpoint URL: `https://lulamacaroni.com/stripe/webhook` (before the domain moves, use the test address Claude gives you).
3. **Select events:** `checkout.session.completed`. Click **Add endpoint**.
4. On the endpoint's page, under **Signing secret**, click **Reveal** and copy it (it starts with `whsec_`). It goes in Render as `STRIPE_WEBHOOK_SECRET`.

## 5. Put the keys in Render

1. https://dashboard.render.com, then the **lulamacaroni-backoffice** service, then **Environment**.
2. **Add Environment Variable** for each: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`. Save. Render redeploys by itself.

## 6. Going live (after the test order works)

Switch test mode off, then repeat steps 3 and 4 in live mode (the live secret key starts with `sk_live_`) and replace the two values in Render. Lore approves the first real order like any other.
