"""Our own store on lulamacaroni.com (canal ``web``), replacing the Shopify storefront.

English pages for US buyers, Stripe Checkout for payment and sales tax, the workbook as the
catalog of record, Prodigi for printing after Lorena approves each order, and order emails
sent from the store's domain. See docs/tienda.md.

Buyers' email, phone and address stay in Stripe. The workbook keeps only Stripe ids, the
buyer's state and country, and the order lines.
"""
