# Data layer: LulaMacaroni Operaciones workbook

_Generated from `lulamacaroni/schema.py` by `python -m lulamacaroni.schema_doc`. Edit the schema, not this file._

The Google Sheets workbook is the system of record. Lorena owns it in the business Google account, and the repo's service account reads and writes it. Tab and column names are in Spanish because she reads them.

## Two lines, one back office

Every record that carries money, a customer or a listing has a `linea` column: `US-POD`, `MX-original`. `Gastos` also allows `compartido` for costs that serve both lines; the contador decides the split. The dashboard reports each line separately and together, and the US LLC's numbers never mix with the Mexico originals.

Metric tabs carry `calidad_dato` (`real`, `estimado`, `faltante`) so a missing number is never shown as zero. `Pedidos` (gross sale) and `Pagos` (deposit received) are separate tabs so a sale is never counted twice as income.

## Tabs

### Obras

One row per: Una obra de arte (shared by both lines; the line lives on each variant). Key: `obra_id`.

| Column | Allowed values |
|---|---|
| `obra_id` |  |
| `titulo` |  |
| `titulo_es` |  |
| `anio` |  |
| `tecnica` |  |
| `coleccion` |  |
| `tema` |  |
| `colores` |  |
| `ancho_cm` |  |
| `alto_cm` |  |
| `orientacion` | vertical, horizontal, cuadrada |
| `proporcion` |  |
| `estado` | borrador, activa, reservada, vendida, archivada |
| `archivo_master` |  |
| `version_aprobada` |  |
| `notas` |  |

### Variantes

One row per: Un producto vendible (SKU). Key: `sku`.

| Column | Allowed values |
|---|---|
| `sku` |  |
| `obra_id` |  |
| `linea` | US-POD, MX-original |
| `tipo` | original, impresion, enmarcado, descargable |
| `tamano` |  |
| `papel` |  |
| `marco` |  |
| `pod_proveedor` |  |
| `pod_sku` |  |
| `archivo_impresion` |  |
| `costo_usd` |  |
| `precio_usd` |  |
| `precio_mxn_con_iva` |  |
| `estado` | borrador, activa, descontinuada |
| `actualizado` |  |
| `archivo_px` |  |

### Listados

One row per: Un SKU publicado en un canal. Key: `listado_ref`.

| Column | Allowed values |
|---|---|
| `listado_ref` |  |
| `sku` |  |
| `linea` | US-POD, MX-original |
| `canal` | shopify, etsy, sitio-mx, whatsapp, instagram, pinterest, otro |
| `id_en_canal` |  |
| `titulo_en_canal` |  |
| `url` |  |
| `precio` |  |
| `inventario` |  |
| `estado` | borrador, en-aprobacion, publicado, pausado, retirado |
| `aprobacion_id` |  |
| `ultima_sync` |  |
| `id_producto_canal` |  |
| `ruta_pod` | prodigi-app, frame-it-easy-app, prodigi-api, manual, desconocida, varias |
| `imagen_url` |  |
| `descripcion` |  |
| `etiquetas` |  |
| `tipo_producto` |  |
| `imagenes_producto` |  |

### Pedidos

One row per: Una línea de pedido. Key: `linea_pedido_id`.

| Column | Allowed values |
|---|---|
| `linea_pedido_id` |  |
| `pedido_id` |  |
| `linea` | US-POD, MX-original |
| `canal` | shopify, etsy, sitio-mx, whatsapp, instagram, pinterest, otro |
| `fecha` |  |
| `sku` |  |
| `cantidad` |  |
| `moneda` |  |
| `venta_bruta` |  |
| `descuento` |  |
| `impuesto_cobrado` |  |
| `envio_cobrado` |  |
| `comision_canal` |  |
| `costo_pod` |  |
| `envio_pod` |  |
| `reembolso` |  |
| `margen_contribucion` |  |
| `ruta_pod` | prodigi-app, frame-it-easy-app, prodigi-api, manual, desconocida |
| `pod_pedido_id` |  |
| `tracking` |  |
| `estado` | recibido, enviado-a-pod, en-produccion, enviado, entregado, cancelado, reembolsado, excepcion |
| `calidad_dato` | real, estimado, faltante |
| `producto` |  |
| `numero_canal` |  |
| `origen_estado` | ok, sin-recorrido, pendiente, sin-permiso |
| `origen_fuente` |  |
| `origen_tipo` |  |
| `utm_fuente` |  |
| `utm_medio` |  |
| `utm_campana` |  |
| `referente` |  |
| `cliente_id` |  |
| `imagen_url` |  |

### Pagos

One row per: Un depósito o payout recibido (kept apart from the gross sale). Key: `pago_id`.

| Column | Allowed values |
|---|---|
| `pago_id` |  |
| `linea` | US-POD, MX-original |
| `canal` | shopify, etsy, sitio-mx, whatsapp, instagram, pinterest, otro |
| `fecha` |  |
| `moneda` |  |
| `monto_depositado` |  |
| `comisiones` |  |
| `retenciones` |  |
| `reembolsos` |  |
| `pedidos_incluidos` |  |
| `conciliado` | si, no |
| `nota` |  |
| `estado` | programado, en-transito, pagado, fallido, cancelado |

### Gastos

One row per: Un gasto. Key: `gasto_id`.

| Column | Allowed values |
|---|---|
| `gasto_id` |  |
| `linea` | US-POD, MX-original, compartido |
| `fecha` |  |
| `proveedor` |  |
| `concepto` |  |
| `categoria` |  |
| `moneda` |  |
| `monto` |  |
| `impuesto` |  |
| `comprobante` |  |
| `criterio_reparto` |  |
| `nota` |  |

### Clientes

One row per: Un cliente o contacto (only what the channel shares and consent allows). Key: `cliente_id`.

| Column | Allowed values |
|---|---|
| `cliente_id` |  |
| `linea` | US-POD, MX-original |
| `canal_origen` | shopify, etsy, sitio-mx, whatsapp, instagram, pinterest, otro |
| `nombre` |  |
| `pais` |  |
| `consentimiento_email` | si, no, desconocido |
| `primer_pedido` |  |
| `pedidos` |  |
| `nota` |  |
| `region` |  |
| `total` |  |
| `moneda` |  |
| `ultimo_pedido` |  |
| `cliente_desde` |  |
| `nota_shopify` |  |
| `nota_por` |  |
| `nota_fecha` |  |
| `seguimiento` |  |
| `seguimiento_para` |  |
| `seguimiento_estado` | pendiente, hecho, cancelado |
| `ultima_sync` |  |

### Contenido

One row per: Una publicación, reel, story o pin. Key: `contenido_id`.

| Column | Allowed values |
|---|---|
| `contenido_id` |  |
| `linea` | US-POD, MX-original |
| `obra_id` |  |
| `plataforma` | instagram, pinterest, otro |
| `formato` | post, carrusel, reel, story, pin, video-pin, otro |
| `idioma` | en, es |
| `estado` | idea, borrador, aprobado, programado, publicado, fallido |
| `aprobacion_id` |  |
| `programado_para` |  |
| `url` |  |
| `resultado` |  |
| `calidad_dato` | real, estimado, faltante |
| `titulo` |  |
| `texto` |  |
| `archivo` |  |

### Campanas

One row per: Un anuncio o conjunto de anuncios, por día. Key: `campana_dia_id`.

| Column | Allowed values |
|---|---|
| `campana_dia_id` |  |
| `linea` | US-POD, MX-original |
| `plataforma` |  |
| `campana_id` |  |
| `anuncio_id` |  |
| `obra_id` |  |
| `destino` |  |
| `fecha` |  |
| `gasto` |  |
| `impresiones` |  |
| `clics` |  |
| `compras_atribuidas` |  |
| `valor_atribuido` |  |
| `calidad_dato` | real, estimado, faltante |

### Publicidad

One row per: Una campaña planeada: creativo, destino, presupuesto y su aprobación. Key: `campana_id`.

| Column | Allowed values |
|---|---|
| `campana_id` |  |
| `linea` | US-POD, MX-original |
| `plataforma` | meta, pinterest, google, etsy-ads, otro |
| `nombre` |  |
| `obra_id` |  |
| `objetivo` |  |
| `audiencia` |  |
| `destino` | shopify, etsy, sitio-mx, instagram, otro |
| `url_destino` |  |
| `utm_campana` |  |
| `texto` |  |
| `archivo` |  |
| `presupuesto_diario_usd` |  |
| `presupuesto_total_usd` |  |
| `inicio` |  |
| `fin` |  |
| `estado` | idea, borrador, por-aprobar, aprobada, activa, pausada, terminada, rechazada |
| `aprobacion_id` |  |
| `nota` |  |

### Topes

One row per: El límite de gasto que Lorena fija por plataforma de anuncios. Key: `plataforma`.

| Column | Allowed values |
|---|---|
| `plataforma` | meta, pinterest, google, etsy-ads, otro |
| `linea` | US-POD, MX-original |
| `tope_diario_usd` |  |
| `tope_mensual_usd` |  |
| `cambio_max_pct` |  |
| `definido_por` |  |
| `actualizado` |  |
| `nota` |  |

### Consultas

One row per: Un mensaje o interesado (Mexico site inquiries land here). Key: `consulta_id`.

| Column | Allowed values |
|---|---|
| `consulta_id` |  |
| `linea` | US-POD, MX-original |
| `canal` | shopify, etsy, sitio-mx, whatsapp, instagram, pinterest, otro |
| `fecha` |  |
| `tipo` | producto, tamano, compra, envio, pedido, dano, devolucion, colaboracion, spam, otro |
| `obra_id` |  |
| `resumen` |  |
| `estado` | nueva, en-curso, respondida, cerrada |
| `responsable` |  |

### Aprobaciones

One row per: Una solicitud de aprobación y la decisión de Lorena. Key: `aprobacion_id`.

| Column | Allowed values |
|---|---|
| `aprobacion_id` |  |
| `tipo` | listado, contenido, anuncio, presupuesto, reembolso, cancelacion, pedido-manual, respuesta-cliente, precio |
| `linea` | US-POD, MX-original |
| `resumen` |  |
| `detalle` |  |
| `huella` |  |
| `monto_usd` |  |
| `creado_por` |  |
| `creado_en` |  |
| `expira_en` |  |
| `estado` | pendiente, aprobado, rechazado, expirado, cancelado |
| `decidido_por` |  |
| `decidido_en` |  |
| `nota_decision` |  |
| `ejecutado_en` |  |

### Excepciones

One row per: Un problema que necesita a una persona. Key: `excepcion_id`.

| Column | Allowed values |
|---|---|
| `excepcion_id` |  |
| `linea` | US-POD, MX-original |
| `tipo` |  |
| `referencia` |  |
| `detalle` |  |
| `creada_en` |  |
| `responsable` |  |
| `plazo` |  |
| `estado` | abierta, en-curso, resuelta |
| `resuelta_en` |  |

### Decisiones

One row per: Una decisión o prueba. Key: `decision_id`.

| Column | Allowed values |
|---|---|
| `decision_id` |  |
| `fecha` |  |
| `decision` |  |
| `razon` |  |
| `responsable` |  |
| `resultado` |  |

### Conocimiento

One row per: Una regla o dato aprobado (voz, paleta, políticas, FAQ). Key: `conocimiento_id`.

| Column | Allowed values |
|---|---|
| `conocimiento_id` |  |
| `tema` | voz, paleta, producto, politica, faq, rubrica |
| `idioma` | en, es |
| `texto` |  |
| `aprobado_en` |  |
| `vigente` | si, no |

### Investigacion

One row per: Una fila de un export de eRank o EverBee: una keyword o un producto de la competencia. Key: `investigacion_id`.

| Column | Allowed values |
|---|---|
| `investigacion_id` |  |
| `importacion_id` |  |
| `linea` | US-POD, MX-original |
| `fuente` | erank, everbee |
| `tipo` | keyword, producto |
| `fecha_export` |  |
| `mercado` |  |
| `categoria` | print, enmarcado, descargable, cojin, wallpaper, otro |
| `keyword` |  |
| `busquedas` |  |
| `clics` |  |
| `ctr` |  |
| `competencia` |  |
| `tendencia` |  |
| `titulo` |  |
| `tienda` |  |
| `precio` |  |
| `moneda` |  |
| `ventas_mes` |  |
| `ingresos_mes` |  |
| `resenas` |  |
| `favoritos` |  |
| `etiquetas` |  |

### Importaciones

One row per: Un archivo CSV de eRank o EverBee importado (o que no se pudo importar). Key: `importacion_id`.

| Column | Allowed values |
|---|---|
| `importacion_id` |  |
| `fuente` | erank, everbee |
| `tipo` | keyword, producto |
| `archivo` |  |
| `archivo_id` |  |
| `fecha_export` |  |
| `fecha_export_origen` | nombre-archivo, archivo, dia-importacion |
| `importado_en` |  |
| `filas` |  |
| `filas_omitidas` |  |
| `columnas_usadas` |  |
| `columnas_ignoradas` |  |
| `estado` | ok, parcial, error |
| `nota` |  |

### Keywords

One row per: Una keyword que Lorena quiere probar en una obra, y cómo le fue. Key: `keyword_id`.

| Column | Allowed values |
|---|---|
| `keyword_id` |  |
| `obra_id` |  |
| `linea` | US-POD, MX-original |
| `canal` | shopify, etsy, sitio-mx, whatsapp, instagram, pinterest, otro |
| `keyword` |  |
| `categoria` | print, enmarcado, descargable, cojin, wallpaper, otro |
| `estado` | a-probar, probando, en-uso, descartada |
| `desde` |  |
| `hasta` |  |
| `resultado` |  |
| `nota` |  |
| `actualizado` |  |

### Tableros

One row per: Un tablero de Pinterest de la cuenta del negocio. Key: `tablero_id`.

| Column | Allowed values |
|---|---|
| `tablero_id` |  |
| `nombre` |  |
| `descripcion` |  |
| `privacidad` | publico, protegido, secreto |
| `pines` |  |
| `seguidores` |  |
| `creado` |  |
| `ultima_sync` |  |

### Pines

One row per: Un pin de la cuenta, con sus números de los últimos 30 días según Pinterest. Key: `pin_id`.

| Column | Allowed values |
|---|---|
| `pin_id` |  |
| `linea` | US-POD, MX-original |
| `tablero_id` |  |
| `tablero` |  |
| `titulo` |  |
| `descripcion` |  |
| `enlace` |  |
| `id_producto_canal` |  |
| `producto` |  |
| `imagen_url` |  |
| `tipo_medio` |  |
| `creado` |  |
| `periodo` |  |
| `impresiones` |  |
| `guardados` |  |
| `clics_pin` |  |
| `clics_enlace` |  |
| `calidad_dato` | real, estimado, faltante |
| `ultima_sync` |  |

### PinterestDiario

One row per: Un día de la cuenta de Pinterest: impresiones, guardados y clics de todos los pines. Key: `fecha`.

| Column | Allowed values |
|---|---|
| `fecha` |  |
| `linea` | US-POD, MX-original |
| `impresiones` |  |
| `guardados` |  |
| `clics_pin` |  |
| `clics_enlace` |  |
| `interacciones` |  |
| `estado_pinterest` |  |
| `calidad_dato` | real, estimado, faltante |
| `ultima_sync` |  |

### Fuentes

One row per: Una fuente de datos y su última actualización. Key: `fuente`.

| Column | Allowed values |
|---|---|
| `fuente` |  |
| `ultima_actualizacion` |  |
| `estado` | ok, atrasada, error, sin-conectar |
| `filas` |  |
| `nota` |  |
