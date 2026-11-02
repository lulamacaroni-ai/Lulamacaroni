# Mexico catalog site (phase 1)

A Spanish, browse-only catalog of Lorena's originals: no cart, no forms, no cookies,
no analytics. Buyers ask by WhatsApp or email from each piece's page. Prices are MXN,
IVA included. Code: `lulamacaroni/sitio_mx/`.

## What gets published

A piece shows when **all** of these hold in the "LulaMacaroni Operaciones" sheet:

| Tab | Row | Needed |
|---|---|---|
| Variantes | `linea` = MX-original, `tipo` = original | `estado` = activa; `precio_mxn_con_iva` (empty shows "Precio a consultar", never $0); `actualizado` (YYYY-MM-DD) prints "Precio actualizado el …" |
| Obras | same `obra_id` | `estado` = activa (reservada/vendida never show); `titulo_es`, `tecnica`, `anio`, `coleccion`, `ancho_cm`, `alto_cm` |

…and there is a **web photo** named after the `obra_id` (`MX-012.jpg`, `.png` or `.webp`)
in the photos folder. Photos are copied byte for byte: nothing crops, resizes or
regenerates them, and the page shows the whole photo. The build report warns when a
photo's proportions don't match the piece's measurements (possible crop) or the file is
over 4 MB. Photos never go in the repo.

## Settings (.env or the cloud environment)

| Variable | Example | Required |
|---|---|---|
| `LULA_MX_RESPONSABLE` | Lorena's legal name | yes (aviso de privacidad) |
| `LULA_MX_DOMICILIO` | address for the aviso | yes (law requires it) |
| `LULA_MX_CORREO` | info@lulamacaroni.com (default) | email or WhatsApp |
| `LULA_MX_WHATSAPP` | 521 + 10 digits | recommended |
| `LULA_MX_CIUDAD` | city for pickup/delivery | optional |
| `LULA_MX_URL` | https://mx.lulamacaroni.com (default) | optional |
| `LULA_MX_FOTOS` | folder with the web photos | or pass `--fotos` |

These are public details, not secrets, but keep the address out of the repo anyway.

## Commands

```
python -m lulamacaroni.sitio_mx construir --demo        # sample pieces, nothing real
python -m lulamacaroni.sitio_mx construir --fotos RUTA   # real build into data/sitio-mx/
python -m lulamacaroni.sitio_mx vista                    # preview http://127.0.0.1:8771
python -m lulamacaroni.sitio_mx solicitar --fotos RUTA   # asks Lorena (Aprobar screen)
python -m lulamacaroni.sitio_mx publicar --fotos RUTA --aprobacion apr-...
```

`solicitar` creates a `listado` approval for the exact manifest: every piece, its price,
the SHA-256 of its photo, the contact details and the aviso text. `publicar` rebuilds from
the sheet and refuses if anything changed since she approved; then it writes
`data/sitio-mx-publicado/sitio-mx-<fecha>.zip`, records each page in `Listados`
(`canal` sitio-mx, so the sold-original guard watches it), marks pages no longer in the
build as `retirado`, and marks the approval as used. Selling a piece = set the obra to
`vendida`, then `solicitar` + `publicar` again.

## Hosting (one-time, JIM)

Recommended: Cloudflare Pages (free, static, no server to maintain) on
`mx.lulamacaroni.com`, so the Shopify site on `lulamacaroni.com` is untouched.

1. Create a Cloudflare account with lulamacaroni@gmail.com → Workers & Pages → Create →
   Pages → **Upload assets**. Name the project `lulamacaroni-mx`.
2. Unzip the file from `publicar` and drag the folder in. Deploy.
3. In the project → Custom domains → add `mx.lulamacaroni.com`. Cloudflare shows a CNAME
   target (`lulamacaroni-mx.pages.dev`).
4. In GoDaddy (camilahaart@gmail.com) → lulamacaroni.com → DNS → Add record: type CNAME,
   name `mx`, value the target from step 3. Don't change the Shopify records.
5. Each later publish: Pages project → Create deployment → upload the new folder.

Before go-live (Jan 25, 2027): Lorena's contador or lawyer reads the aviso de privacidad
(`lulamacaroni/sitio_mx/aviso.py`); bump `FECHA_AVISO` whenever its text changes.
Inquiries are logged by hand in the `Consultas` tab (`canal` whatsapp/sitio-mx).
