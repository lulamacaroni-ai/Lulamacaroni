"""Mexico catalog site, phase 1: a Spanish, browse-only catalog of Lorena's originals.

No checkout and no forms: a buyer writes by WhatsApp or email to ask for a piece.
Prices are in MXN with IVA included. The site is plain static files built from the
workbook (``Obras`` + ``Variantes`` with ``linea`` MX-original), so the public host
never holds a key or touches the Sheet.

    python -m lulamacaroni.sitio_mx construir --imagenes RUTA   # build into data/sitio-mx/
    python -m lulamacaroni.sitio_mx vista                       # preview on 127.0.0.1:8771
    python -m lulamacaroni.sitio_mx solicitar                   # ask Lorena to approve it
    python -m lulamacaroni.sitio_mx publicar --aprobacion ID    # approved build -> zip

See docs/setup/sitio-mx.md.
"""
