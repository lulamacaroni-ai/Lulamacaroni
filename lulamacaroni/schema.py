"""Data layer schema for the "LulaMacaroni Operaciones" Google Sheets workbook.

The workbook is the system of record: Lorena can read and fix every row herself.
Tab and column names are in Spanish because she is the one who opens them.

Two lines of business share one back office. Every record that carries money,
a customer or a listing is tagged with ``linea`` so the US LLC's numbers never
mix with the Mexico originals:

* ``US-POD``       prints sold on Shopify and Etsy, printed and shipped by Prodigi (US LLC)
* ``MX-original``  original pieces shown to local buyers on the Spanish catalog site

Only ``Gastos`` (expenses) may also use ``compartido`` for costs that serve both
lines (for example the Claude subscription); the contador decides how to split them.

Number rule from Lorena's requirements: every metric row says whether the value is
real, estimated or missing (``calidad_dato``), so a missing number is never shown as zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- Controlled vocabularies (become dropdowns in the sheet) -------------------

LINEAS = ("US-POD", "MX-original")
LINEAS_GASTOS = LINEAS + ("compartido",)

ESTADOS_PAGO = ("programado", "en-transito", "pagado", "fallido", "cancelado")

CANALES = ("shopify", "etsy", "sitio-mx", "whatsapp", "instagram", "pinterest", "otro")

TIPOS_VARIANTE = ("original", "impresion", "enmarcado", "descargable")

ESTADOS_OBRA = ("borrador", "activa", "reservada", "vendida", "archivada")
ESTADOS_VARIANTE = ("borrador", "activa", "descontinuada")
ESTADOS_LISTADO = ("borrador", "en-aprobacion", "publicado", "pausado", "retirado")
ESTADOS_PEDIDO = (
    "recibido", "enviado-a-pod", "en-produccion", "enviado", "entregado",
    "cancelado", "reembolsado", "excepcion",
)
ESTADOS_CONTENIDO = ("idea", "borrador", "aprobado", "programado", "publicado", "fallido")
PLATAFORMAS_CONTENIDO = ("instagram", "pinterest", "otro")
FORMATOS_CONTENIDO = ("post", "carrusel", "reel", "story", "pin", "video-pin", "otro")
# What needs Lorena's approval before it happens (from her list: publish, spend, refund)
TIPOS_APROBACION = (
    "listado",            # publish or change a listing on Shopify, Etsy or the Mexico site
    "contenido",          # post, reel, story or pin
    "anuncio",            # new ad or creative
    "presupuesto",        # any ad budget change
    "reembolso",          # refund
    "cancelacion",        # cancel an order
    "pedido-manual",      # manual POD order or reprint
    "respuesta-cliente",  # customer reply outside approved templates
    "precio",             # price change
)
ESTADOS_APROBACION = ("pendiente", "aprobado", "rechazado", "expirado", "cancelado")
ESTADOS_EXCEPCION = ("abierta", "en-curso", "resuelta")

# Who fulfils an order line. Orders the Prodigi (or Frame It Easy) app already routes
# must never also be sent through the Prodigi API, or the print is made twice.
RUTAS_POD = ("prodigi-app", "frame-it-easy-app", "prodigi-api", "manual", "desconocida")
# A listing can also sit at two print locations at once ("varias"): double-print risk.
RUTAS_LISTADO = RUTAS_POD + ("varias",)

CALIDAD_DATO = ("real", "estimado", "faltante")

ORIENTACIONES = ("vertical", "horizontal", "cuadrada")


@dataclass(frozen=True)
class Tab:
    """One sheet tab: its name, what one row represents, and its columns.

    ``validaciones`` maps a column name to the allowed values (a dropdown).
    ``clave`` is the column that must be unique within the tab.
    """

    nombre: str
    fila: str
    columnas: tuple[str, ...]
    clave: str
    validaciones: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.clave not in self.columnas:
            raise ValueError(f"{self.nombre}: key column {self.clave!r} not in columns")
        for col in self.validaciones:
            if col not in self.columnas:
                raise ValueError(f"{self.nombre}: validation on unknown column {col!r}")
        if len(set(self.columnas)) != len(self.columnas):
            raise ValueError(f"{self.nombre}: duplicate column names")

    @property
    def lleva_linea(self) -> bool:
        return "linea" in self.columnas


TABS: tuple[Tab, ...] = (
    Tab(
        nombre="Obras",
        fila="Una obra de arte (shared by both lines; the line lives on each variant)",
        clave="obra_id",
        columnas=(
            "obra_id", "titulo", "titulo_es", "anio", "tecnica", "coleccion", "tema",
            "colores", "ancho_cm", "alto_cm", "orientacion", "proporcion",
            "estado", "archivo_master", "version_aprobada", "notas",
        ),
        validaciones={"estado": ESTADOS_OBRA, "orientacion": ORIENTACIONES},
    ),
    Tab(
        nombre="Variantes",
        fila="Un producto vendible (SKU)",
        clave="sku",
        columnas=(
            "sku", "obra_id", "linea", "tipo", "tamano", "papel", "marco",
            "pod_proveedor", "pod_sku", "archivo_impresion", "costo_usd", "precio_usd",
            "precio_mxn_con_iva", "estado", "actualizado",
            # pixel size of archivo_impresion ("7200x9600") for the print-file check;
            # costo_usd = print + Prodigi shipping to the US, from a quote (an estimate)
            "archivo_px",
        ),
        validaciones={"linea": LINEAS, "tipo": TIPOS_VARIANTE, "estado": ESTADOS_VARIANTE},
    ),
    Tab(
        nombre="Listados",
        fila="Un SKU publicado en un canal",
        clave="listado_ref",
        columnas=(
            "listado_ref", "sku", "linea", "canal", "id_en_canal", "titulo_en_canal", "url",
            "precio", "inventario", "estado", "aprobacion_id", "ultima_sync",
            "id_producto_canal", "ruta_pod",
        ),
        validaciones={"linea": LINEAS, "canal": CANALES, "estado": ESTADOS_LISTADO,
                      "ruta_pod": RUTAS_LISTADO},
    ),
    Tab(
        nombre="Pedidos",
        fila="Una línea de pedido",
        clave="linea_pedido_id",
        columnas=(
            "linea_pedido_id", "pedido_id", "linea", "canal", "fecha", "sku", "cantidad",
            "moneda", "venta_bruta", "descuento", "impuesto_cobrado", "envio_cobrado",
            "comision_canal", "costo_pod", "envio_pod", "reembolso", "margen_contribucion",
            "ruta_pod", "pod_pedido_id", "tracking", "estado", "calidad_dato",
            "producto", "numero_canal",
        ),
        validaciones={
            "linea": LINEAS, "canal": CANALES, "estado": ESTADOS_PEDIDO, "ruta_pod": RUTAS_POD,
            "calidad_dato": CALIDAD_DATO,
        },
    ),
    Tab(
        nombre="Pagos",
        fila="Un depósito o payout recibido (kept apart from the gross sale)",
        clave="pago_id",
        columnas=(
            "pago_id", "linea", "canal", "fecha", "moneda", "monto_depositado",
            "comisiones", "retenciones", "reembolsos", "pedidos_incluidos",
            "conciliado", "nota", "estado",
        ),
        validaciones={"linea": LINEAS, "canal": CANALES, "conciliado": ("si", "no"),
                      "estado": ESTADOS_PAGO},
    ),
    Tab(
        nombre="Gastos",
        fila="Un gasto",
        clave="gasto_id",
        columnas=(
            "gasto_id", "linea", "fecha", "proveedor", "concepto", "categoria", "moneda",
            "monto", "impuesto", "comprobante", "criterio_reparto", "nota",
        ),
        validaciones={"linea": LINEAS_GASTOS},
    ),
    Tab(
        nombre="Clientes",
        fila="Un cliente o contacto (only what the channel shares and consent allows)",
        clave="cliente_id",
        columnas=(
            "cliente_id", "linea", "canal_origen", "nombre", "pais", "consentimiento_email",
            "primer_pedido", "pedidos", "nota",
        ),
        validaciones={
            "linea": LINEAS, "canal_origen": CANALES,
            "consentimiento_email": ("si", "no", "desconocido"),
        },
    ),
    Tab(
        nombre="Contenido",
        fila="Una publicación, reel, story o pin",
        clave="contenido_id",
        columnas=(
            "contenido_id", "linea", "obra_id", "plataforma", "formato", "idioma", "estado",
            "aprobacion_id", "programado_para", "url", "resultado", "calidad_dato",
            # what gets approved: the exact text and the approved image file (never edited)
            "titulo", "texto", "archivo",
        ),
        validaciones={
            "linea": LINEAS, "estado": ESTADOS_CONTENIDO, "idioma": ("en", "es"),
            "plataforma": PLATAFORMAS_CONTENIDO, "formato": FORMATOS_CONTENIDO,
            "calidad_dato": CALIDAD_DATO,
        },
    ),
    Tab(
        nombre="Campanas",
        fila="Un anuncio o conjunto de anuncios, por día",
        clave="campana_dia_id",
        columnas=(
            "campana_dia_id", "linea", "plataforma", "campana_id", "anuncio_id", "obra_id",
            "destino", "fecha", "gasto", "impresiones", "clics", "compras_atribuidas",
            "valor_atribuido", "calidad_dato",
        ),
        validaciones={"linea": LINEAS, "calidad_dato": CALIDAD_DATO},
    ),
    Tab(
        nombre="Consultas",
        fila="Un mensaje o interesado (Mexico site inquiries land here)",
        clave="consulta_id",
        columnas=(
            "consulta_id", "linea", "canal", "fecha", "tipo", "obra_id", "resumen",
            "estado", "responsable",
        ),
        validaciones={
            "linea": LINEAS, "canal": CANALES,
            "tipo": ("producto", "tamano", "compra", "envio", "pedido", "dano", "devolucion",
                     "colaboracion", "spam", "otro"),
            "estado": ("nueva", "en-curso", "respondida", "cerrada"),
        },
    ),
    Tab(
        nombre="Aprobaciones",
        fila="Una solicitud de aprobación y la decisión de Lorena",
        clave="aprobacion_id",
        columnas=(
            "aprobacion_id", "tipo", "linea", "resumen", "detalle", "huella", "monto_usd",
            "creado_por", "creado_en", "expira_en", "estado", "decidido_por",
            "decidido_en", "nota_decision", "ejecutado_en",
        ),
        validaciones={"tipo": TIPOS_APROBACION, "linea": LINEAS, "estado": ESTADOS_APROBACION},
    ),
    Tab(
        nombre="Excepciones",
        fila="Un problema que necesita a una persona",
        clave="excepcion_id",
        columnas=(
            "excepcion_id", "linea", "tipo", "referencia", "detalle", "creada_en",
            "responsable", "plazo", "estado", "resuelta_en",
        ),
        validaciones={"linea": LINEAS, "estado": ESTADOS_EXCEPCION},
    ),
    Tab(
        nombre="Decisiones",
        fila="Una decisión o prueba",
        clave="decision_id",
        columnas=("decision_id", "fecha", "decision", "razon", "responsable", "resultado"),
    ),
    Tab(
        nombre="Conocimiento",
        fila="Una regla o dato aprobado (voz, paleta, políticas, FAQ)",
        clave="conocimiento_id",
        columnas=("conocimiento_id", "tema", "idioma", "texto", "aprobado_en", "vigente"),
        validaciones={
            "tema": ("voz", "paleta", "producto", "politica", "faq", "rubrica"),
            "idioma": ("en", "es"), "vigente": ("si", "no"),
        },
    ),
    Tab(
        nombre="Fuentes",
        fila="Una fuente de datos y su última actualización",
        clave="fuente",
        columnas=("fuente", "ultima_actualizacion", "estado", "filas", "nota"),
        validaciones={"estado": ("ok", "atrasada", "error", "sin-conectar")},
    ),
)

TABS_BY_NAME: dict[str, Tab] = {t.nombre: t for t in TABS}


def tab(nombre: str) -> Tab:
    try:
        return TABS_BY_NAME[nombre]
    except KeyError:
        raise KeyError(f"Unknown tab {nombre!r}; known: {', '.join(TABS_BY_NAME)}") from None


def validate_row(nombre_tab: str, row: dict[str, object]) -> list[str]:
    """Return a list of problems with ``row`` for ``nombre_tab`` (empty list = valid).

    Checks unknown columns, a missing key, the ``linea`` tag and dropdown values.
    Empty cells are allowed except for the key and ``linea``.
    """
    t = tab(nombre_tab)
    problems: list[str] = []
    for col in row:
        if col not in t.columnas:
            problems.append(f"columna desconocida: {col}")
    if not row.get(t.clave):
        problems.append(f"falta la clave {t.clave}")
    if t.lleva_linea and not row.get("linea"):
        problems.append("falta linea (US-POD o MX-original)")
    for col, allowed in t.validaciones.items():
        value = row.get(col)
        if value not in (None, "") and value not in allowed:
            problems.append(f"{col}={value!r} no es válido; opciones: {', '.join(allowed)}")
    return problems
