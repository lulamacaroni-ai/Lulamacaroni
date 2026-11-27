# Resend: order emails from orders@lulamacaroni.com

Resend sends the two order emails (confirmation and "your print shipped"). The free plan covers 3,000 emails a month.

1. Open https://resend.com/signup and sign up with lulamacaroni@gmail.com.
2. Left menu: **Domains**, then **Add Domain**. Type `lulamacaroni.com`, region **US East**. Click **Add**.
3. Resend shows three or four DNS records (TXT and MX for a `send` subdomain, and a TXT for `resend._domainkey`). Leave that page open.
4. In another tab, open GoDaddy (camilahaart@gmail.com), then **My Products**, then **lulamacaroni.com**, then **DNS**.
5. For each record Resend shows, click **Add New Record**, pick the same **Type**, and copy the **Name** and **Value** exactly. These are new records on a `send` subdomain: they don't touch the MX records of info@lulamacaroni.com, so the inbox keeps working.
6. Back in Resend, click **Verify DNS Records**. It can take up to an hour.
7. Left menu: **API Keys**, then **Create API Key**, name `tienda`, permission **Sending access**, domain `lulamacaroni.com`. Copy the key (it starts with `re_`).
8. In Render, under the service's **Environment**, add `RESEND_API_KEY` with that value.
