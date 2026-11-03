"""Sample rows for ``--demo`` and the tests. Invented titles and amounts, no real data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def demo_rows(now: datetime | None = None) -> dict[str, list[dict]]:
    now = now or datetime.now(timezone.utc)
    titles = ["Sample Garden", "Sample Harbor", "Sample Owl"]
    listados = []
    for pi, title in enumerate(titles, start=1):
        for vi, size in enumerate(("8x10", "12x16", "18x24"), start=1):
            listados.append({
                "listado_ref": f"shopify-{pi}{vi}", "sku": f"DEMO-{pi}-{size}" if pi != 3 else "",
                "linea": "US-POD", "canal": "shopify", "id_en_canal": f"{pi}{vi}",
                "titulo_en_canal": f"{title} / {size}", "url": "", "precio": 60 + 20 * vi,
                "inventario": "", "estado": "publicado" if pi != 2 else "pausado",
                "ultima_sync": _iso(now), "id_producto_canal": str(pi),
                "ruta_pod": ("prodigi-app", "frame-it-easy-app", "manual")[pi - 1],
            })
    origenes = [  # last visit per Shopify's customer journey (invented)
        {"origen_estado": "ok", "origen_fuente": "instagram", "origen_tipo": "ad",
         "utm_fuente": "instagram", "utm_medio": "paid_social", "utm_campana": "garden-otono",
         "referente": "l.instagram.com"},
        {"origen_estado": "ok", "origen_fuente": "pinterest", "origen_tipo": "",
         "utm_fuente": "", "utm_medio": "", "utm_campana": "", "referente": "pinterest.com"},
        {"origen_estado": "ok", "origen_fuente": "direct", "origen_tipo": "", "utm_fuente": "",
         "utm_medio": "", "utm_campana": "", "referente": ""},
        {"origen_estado": "ok", "origen_fuente": "instagram", "origen_tipo": "ad",
         "utm_fuente": "instagram", "utm_medio": "paid_social", "utm_campana": "garden-otono",
         "referente": "l.instagram.com"},
        {"origen_estado": "sin-recorrido"},
        {},
    ]
    pedidos = []
    plan = [  # (days ago, product, size idx, price, state, route, refund)
        (0.2, 0, 2, 100.0, "recibido", "prodigi-app", 0),
        (1.5, 1, 1, 80.0, "en-produccion", "prodigi-app", 0),
        (3, 2, 3, 120.0, "recibido", "manual", 0),
        (5, 0, 1, 80.0, "enviado", "prodigi-app", 0),
        (9, 0, 2, 100.0, "entregado", "prodigi-app", 0),
        (12, 1, 2, 100.0, "reembolsado", "prodigi-app", 100.0),
    ]
    for n, (days, pi, vi, price, estado, ruta, refund) in enumerate(plan, start=1001):
        pedidos.append({
            "linea_pedido_id": f"shopify-{n}-1", "pedido_id": f"shopify-{n}", "linea": "US-POD",
            "canal": "shopify", "fecha": _iso(now - timedelta(days=days)),
            "sku": listados[pi * 3 + vi - 1]["sku"], "cantidad": 1, "moneda": "USD",
            "venta_bruta": price, "descuento": 0, "impuesto_cobrado": 0, "envio_cobrado": 0,
            "reembolso": refund, "ruta_pod": ruta, "estado": estado,             "producto": f"{titles[pi]} - {('8x10', '12x16', '18x24')[vi - 1]}",
            "tracking": "DEMO123" if estado in ("enviado", "entregado") else "",
            "numero_canal": f"#{n}",
            # Shopify Payments fee (2.9% + 30¢); Prodigi charge once Prodigi has billed it
            "comision_canal": round(price * 0.029 + 0.30, 2),
            **origenes[n - 1001],
            "cliente_id": ("shopify-cliente-901", "shopify-cliente-902", "",
                           "shopify-cliente-901", "shopify-cliente-903",
                           "shopify-cliente-902")[n - 1001],
            **({"pod_pedido_id": f"ord_demo{n}", "costo_pod": 28.0 + 6 * vi, "envio_pod": 7.5}
               if ruta == "prodigi-app" and estado != "recibido" else {}),
        })
    fuentes = [{"fuente": "shopify", "ultima_actualizacion": _iso(now - timedelta(minutes=12)),
                "estado": "ok", "filas": len(listados) + len(pedidos), "nota": ""},
               {"fuente": "shopify-clientes",
                "ultima_actualizacion": _iso(now - timedelta(minutes=12)), "estado": "ok",
                "filas": 3, "nota": ""},
               {"fuente": "shopify-pagos", "ultima_actualizacion": _iso(now - timedelta(minutes=12)),
                "estado": "ok", "filas": 2, "nota": ""}]
    pagos = [
        {"pago_id": "shopify-payout-1", "linea": "US-POD", "canal": "shopify",
         "fecha": _iso(now - timedelta(days=8)), "moneda": "USD", "monto_depositado": 94.81,
         "comisiones": 5.19, "retenciones": 0, "reembolsos": 0, "conciliado": "no",
         "estado": "pagado"},
        {"pago_id": "shopify-payout-2", "linea": "US-POD", "canal": "shopify",
         "fecha": _iso(now + timedelta(days=1)), "moneda": "USD", "monto_depositado": 77.38,
         "comisiones": 2.62, "retenciones": 0, "reembolsos": 0, "conciliado": "no",
         "estado": "en-transito"},
    ]
    obras = [
        {"obra_id": "DEMO-001", "titulo": "Sample Garden", "titulo_es": "Jardín de ejemplo",
         "coleccion": "Ejemplo", "orientacion": "vertical", "estado": "activa",
         "version_aprobada": "v1"},
        {"obra_id": "DEMO-002", "titulo": "Sample Harbor", "titulo_es": "Puerto de ejemplo",
         "tecnica": "acrílico sobre tela", "ancho_cm": 60, "alto_cm": 80,
         "orientacion": "vertical", "estado": "activa"},
    ]
    variantes = [  # Sample Garden: 3:4 file, so 8x10 (4:5) can't print without a new file
        {"sku": f"DEMO-1-{size}", "obra_id": "DEMO-001", "linea": "US-POD", "tipo": "impresion",
         "tamano": size, "pod_proveedor": "prodigi", "archivo_impresion": "demo-garden-v1.tif",
         "archivo_px": "5400x7200", "costo_usd": cost, "estado": "activa"}
        for size, cost in (("8x10", 24.0), ("12x16", 31.0), ("18x24", 44.0))
    ] + [
        {"sku": "DEMO-2-ORIG", "obra_id": "DEMO-002", "linea": "MX-original", "tipo": "original",
         "precio_mxn_con_iva": 14500, "estado": "activa"},
    ]
    contenido = [
        {"contenido_id": "c-1", "linea": "US-POD", "obra_id": "DEMO-001",
         "plataforma": "instagram", "formato": "reel", "idioma": "en", "estado": "programado",
         "programado_para": _iso(now + timedelta(days=1)), "titulo": "Garden reveal reel",
         "texto": "Sample caption for a slow pan over the original. Link in bio.",
         "archivo": "demo-garden-v1.tif"},
        {"contenido_id": "c-2", "linea": "US-POD", "obra_id": "DEMO-001",
         "plataforma": "pinterest", "formato": "pin", "idioma": "en", "estado": "borrador",
         "programado_para": _iso(now + timedelta(days=4)), "titulo": "Garden print pin",
         "texto": "Sample pin description.", "archivo": "demo-garden-v1.tif"},
        {"contenido_id": "c-3", "linea": "MX-original", "obra_id": "DEMO-002",
         "plataforma": "instagram", "formato": "carrusel", "idioma": "es", "estado": "idea",
         "titulo": "Proceso de la obra (idea)"},
    ]
    hoy = now.date()
    publicidad = [
        {"campana_id": "pub-1", "linea": "US-POD", "plataforma": "meta",
         "nombre": "Garden otoño (ejemplo)", "obra_id": "DEMO-001", "objetivo": "ventas",
         "audiencia": "EUA, decoración botánica", "destino": "shopify",
         "url_destino": "https://example.com/products/sample-garden",
         "utm_campana": "garden-otono", "texto": "Sample ad copy for the garden print.",
         "archivo": "demo-garden-v1.tif", "presupuesto_diario_usd": 8,
         "presupuesto_total_usd": 200, "inicio": str(hoy - timedelta(days=10)),
         "fin": str(hoy + timedelta(days=15)), "estado": "activa"},
        {"campana_id": "pub-2", "linea": "US-POD", "plataforma": "pinterest",
         "nombre": "Harbor pins (ejemplo)", "obra_id": "DEMO-002", "objetivo": "tráfico",
         "destino": "shopify", "utm_campana": "harbor-pins", "texto": "Sample pin ad copy.",
         "archivo": "demo-harbor-v1.tif", "presupuesto_diario_usd": 5,
         "presupuesto_total_usd": 70, "inicio": str(hoy + timedelta(days=2)),
         "fin": str(hoy + timedelta(days=16)), "estado": "borrador"},
        {"campana_id": "pub-3", "linea": "US-POD", "plataforma": "meta",
         "nombre": "Owl prueba (ejemplo)", "destino": "shopify", "texto": "Sample test ad.",
         "presupuesto_diario_usd": 25, "inicio": str(hoy + timedelta(days=5)),
         "estado": "por-aprobar"},
    ]
    topes_rows = [
        {"plataforma": "meta", "linea": "US-POD", "tope_diario_usd": 15, "tope_mensual_usd": 300,
         "cambio_max_pct": 20, "definido_por": "Lore (ejemplo)", "actualizado": _iso(now)},
        {"plataforma": "pinterest", "linea": "US-POD", "tope_diario_usd": 10,
         "tope_mensual_usd": 150, "cambio_max_pct": 20, "definido_por": "Lore (ejemplo)",
         "actualizado": _iso(now)},
    ]
    hace = lambda d: _iso(now - timedelta(days=d))  # noqa: E731
    clientes_rows = [  # invented people
        {"cliente_id": "shopify-cliente-901", "linea": "US-POD", "canal_origen": "shopify",
         "nombre": "Ana E.", "pais": "US", "region": "CA", "consentimiento_email": "si",
         "pedidos": 3, "total": 260.0, "moneda": "USD", "ultimo_pedido": hace(0.2),
         "cliente_desde": hace(40), "ultima_sync": hace(0),
         "nota": "Pidió el 18x24 enmarcado para regalo (ejemplo).", "nota_por": "Lore",
         "nota_fecha": hace(3)},
        {"cliente_id": "shopify-cliente-902", "linea": "US-POD", "canal_origen": "shopify",
         "nombre": "Ben J.", "pais": "US", "region": "TX", "consentimiento_email": "no",
         "pedidos": 2, "total": 80.0, "moneda": "USD", "ultimo_pedido": hace(1.5),
         "cliente_desde": hace(12), "ultima_sync": hace(0),
         "nota_shopify": "Prefers no gift receipt (example).",
         "seguimiento": "Confirmar que llegó el reemplazo (ejemplo)",
         "seguimiento_para": str((now - timedelta(days=2)).date()),
         "seguimiento_estado": "pendiente"},
        {"cliente_id": "shopify-cliente-903", "linea": "US-POD", "canal_origen": "shopify",
         "nombre": "Cleo K.", "pais": "US", "region": "NY", "consentimiento_email": "desconocido",
         "pedidos": 1, "total": 100.0, "moneda": "USD", "ultimo_pedido": hace(9),
         "cliente_desde": hace(9), "ultima_sync": hace(0)},
        {"cliente_id": "mx-001", "linea": "MX-original", "canal_origen": "whatsapp",
         "nombre": "Daniela R.", "pais": "MX", "region": "CDMX", "pedidos": 1,
         "total": 14500, "moneda": "MXN", "ultimo_pedido": str((now - timedelta(days=20)).date()),
         "nota": "Compró el original del puerto; le interesa la serie nueva (ejemplo).",
         "nota_por": "Lore", "nota_fecha": hace(20),
         "seguimiento": "Avisarle cuando esté la serie nueva (ejemplo)",
         "seguimiento_para": str((now + timedelta(days=10)).date()),
         "seguimiento_estado": "pendiente"},
    ]
    return {"Clientes": clientes_rows, "Listados": listados, "Pedidos": pedidos, "Fuentes": fuentes, "Pagos": pagos,
            "Obras": obras, "Variantes": variantes, "Contenido": contenido,
            "Publicidad": publicidad, "Topes": topes_rows}


def seed_publicidad(book, store, now: datetime | None = None) -> None:
    """Demo approvals: pub-1 approved (it is running), pub-2 waiting for Lore."""
    from ..approval.gate import decide
    from .publicidad import solicitar

    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    # pub-1 shows as running, so it was approved before it started
    book.upsert("Publicidad", [{"campana_id": "pub-1", "linea": "US-POD", "estado": "borrador"}])
    rec = solicitar(book, store, "pub-1", creado_por="Ejemplo", now=now - timedelta(days=11))
    decide(store, rec.aprobacion_id, aprobar=True, decidido_por="Lore (ejemplo)",
           now=now - timedelta(days=11))
    book.upsert("Publicidad", [{"campana_id": "pub-1", "linea": "US-POD", "estado": "activa"}])
    solicitar(book, store, "pub-2", creado_por="Ejemplo", now=now)


def seed_investigacion(book, now: datetime | None = None) -> None:
    """Demo research: three monthly eRank keyword exports and one EverBee product export,
    run through the real importer. Sample words only; never written to the live sheet."""
    from ..connectors.investigacion import importar

    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    book.upsert("Obras", [
        {"obra_id": "DEMO-001", "tema": "garden flowers", "colores": "green, pink"},
        {"obra_id": "DEMO-002", "tema": "harbor boats", "colores": "blue"}])
    mes = now.date().replace(day=1)
    previo = (mes - timedelta(days=1)).replace(day=1)
    fechas = [(previo - timedelta(days=1)).replace(day=1), previo, mes]
    # keyword, searches over three months, competition
    kws = (("garden wall art", (900, 1100, 1400), 21000),
           ("botanical print", (2400, 2300, 2500), 98000),
           ("harbor painting", (300, 280, 900), 6400),
           ("framed boat print", (500, 450, 400), 12000),
           ("garden printable", (1500, 1600, 1550), 54000),
           ("pink flower pillow", (200, 210, 230), 3100))
    for i, f in enumerate(fechas):
        lines = ["Keyword,Avg. Searches,Avg. Clicks,Avg. CTR,Etsy Competition,Google Searches"]
        lines += [f'{k},"{v[i]:,}",{v[i] // 3},{33 + i}%,"{c:,}",120' for k, v, c in kws]
        importar(book, f"erank-keywords-ejemplo-{f.isoformat()}.csv",
                 ("\n".join(lines)).encode(), now=now - timedelta(days=(2 - i) * 30))
    prods = ["Product Name,Shop Name,Price,Mo. Sales,Mo. Revenue,Reviews,Favorites",
             "Sample Garden Art Print 8x10,Tienda Ejemplo A,$18.00,40,$720,210,900",
             "Sample Botanical Poster,Tienda Ejemplo B,$24.50,22,$539,95,400",
             "Sample Framed Harbor Print,Tienda Ejemplo C,$68.00,9,$612,30,150",
             "Sample Framed Flower Art,Tienda Ejemplo D,$95.00,4,$380,12,80",
             "Sample Garden Printable Download,Tienda Ejemplo E,$4.99,150,$748,1200,3000"]
    importar(book, f"everbee-productos-ejemplo-{mes.isoformat()}.csv",
             ("\n".join(prods)).encode(), now=now)
    book.upsert("Keywords", [
        {"keyword_id": "kw-demo-1", "obra_id": "DEMO-001", "linea": "US-POD",
         "canal": "shopify", "keyword": "garden wall art", "categoria": "print",
         "estado": "probando", "desde": fechas[1].isoformat(), "nota": "ejemplo"}])


def fill_demo(book, now: datetime | None = None) -> None:
    from ..margen import recalcular

    for tab_name, rows in demo_rows(now).items():
        book.upsert(tab_name, rows)
    recalcular(book)
    seed_investigacion(book, now)
