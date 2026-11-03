"""Aviso de privacidad integral for the Mexico catalog site.

Written for what the site actually does in phase 1: it has no forms, no cookies, no
analytics and no third-party scripts. Personal data only arrives when someone writes by
WhatsApp or email to ask about or buy a piece, and when a sale needs delivery or a CFDI.

It follows the elements the Ley Federal de Protección de Datos Personales en Posesión de
los Particulares (DOF 20-03-2025) asks of an aviso integral: who is responsible and where,
what data, primary and secondary purposes, how to refuse the secondary ones, transfers,
ARCO rights, revoking consent, limiting use, and how changes are announced.
Lorena's contador or lawyer should read it once before the site goes live.
"""

from __future__ import annotations

from html import escape

from .datos import Ajustes

FECHA_AVISO = "2 de noviembre de 2026"   # change it whenever the text changes


def secciones(a: Ajustes) -> list[tuple[str, str]]:
    """(heading, HTML body) pairs. Values from the settings are escaped."""
    resp = escape(a.responsable or "[falta el nombre del responsable]")
    dom = escape(a.domicilio or "[falta el domicilio]")
    correo = escape(a.correo)
    canales = f"el correo <a href=\"mailto:{correo}\">{correo}</a>"
    if a.whatsapp:
        canales += f" o por WhatsApp al +{escape(a.whatsapp)}"
    return [
        ("Quién es responsable de tus datos",
         f"<p>{resp}, artista que vende su obra original bajo el nombre Lula Macaroni, con "
         f"domicilio en {dom}, es responsable del tratamiento de tus datos personales. "
         f"Para cualquier tema de privacidad escríbenos a {canales}.</p>"),
        ("Qué datos usamos",
         "<p>Este sitio no tiene formularios, no usa cookies, ni herramientas de "
         "analítica o publicidad. Solo recibimos datos cuando tú nos escribes:</p><ul>"
         "<li>Al pedir información: tu nombre, tu número de WhatsApp o tu correo, y lo que "
         "nos cuentes en tu mensaje.</li>"
         "<li>Si compras una obra: dirección y datos de quien recibe la entrega.</li>"
         "<li>Si pides factura (CFDI): nombre o razón social, RFC, régimen fiscal, código "
         "postal fiscal y uso del CFDI.</li></ul>"
         "<p>No pedimos datos personales sensibles. Los pagos se hacen por transferencia "
         "o en persona; no guardamos datos de tarjetas.</p>"
         "<p>El servicio que aloja este sitio puede registrar datos técnicos de cada visita "
         "(dirección IP, navegador, fecha y hora) por seguridad. No los usamos para "
         "identificarte.</p>"),
        ("Para qué los usamos",
         "<p><strong>Finalidades necesarias</strong> para atenderte y venderte una obra:</p>"
         "<ul><li>Responder tus preguntas sobre obras, precios y disponibilidad.</li>"
         "<li>Apartar y vender la obra, coordinar el pago y la entrega o recolección.</li>"
         "<li>Emitir la factura (CFDI) si la pides, y cumplir obligaciones fiscales y "
         "legales.</li><li>Atender aclaraciones sobre tu compra.</li></ul>"
         "<p><strong>Finalidad adicional</strong>, que no es necesaria para la compra: "
         "avisarte de obras nuevas, exposiciones o ventas especiales. Solo lo haremos si "
         "nos dices que sí.</p>"),
        ("Cómo negarte a la finalidad adicional",
         f"<p>Puedes decirnos en cualquier momento que no quieres recibir esos avisos, "
         f"escribiendo a {canales}. Negarte no afecta tu compra ni tu atención.</p>"),
        ("Con quién compartimos tus datos",
         "<p>No vendemos ni rentamos tus datos. Solo los compartimos, sin necesitar tu "
         "consentimiento porque así lo permite la ley, con:</p><ul>"
         "<li>El Servicio de Administración Tributaria (SAT), mediante el proveedor "
         "autorizado de certificación, cuando emitimos una factura.</li>"
         "<li>Autoridades que lo requieran conforme a la ley.</li>"
         "<li>La paquetería o persona que entregue tu obra, solo con los datos de "
         "entrega.</li></ul>"
         "<p>Si en el futuro necesitáramos compartirlos con alguien más, te pediremos "
         "tu consentimiento antes.</p>"),
        ("Tus derechos ARCO",
         f"<p>Tienes derecho a conocer qué datos tenemos y cómo los usamos (Acceso), a "
         f"corregirlos (Rectificación), a pedir que los eliminemos (Cancelación) y a oponerte "
         f"a un uso específico (Oposición). Escríbenos a {canales} con:</p><ul>"
         "<li>Tu nombre y un medio para responderte.</li>"
         "<li>Una identificación oficial (o la de tu representante y el documento que lo "
         "acredite).</li>"
         "<li>Qué datos y qué derecho quieres ejercer, y cualquier dato que nos ayude a "
         "encontrarlos.</li></ul>"
         "<p>Te responderemos en un máximo de 20 días hábiles y, si procede, lo haremos "
         "efectivo dentro de los 15 días hábiles siguientes. Si no estás de acuerdo con la "
         "respuesta, puedes acudir a la autoridad de protección de datos (actualmente la "
         "Secretaría Anticorrupción y Buen Gobierno).</p>"),
        ("Cómo retirar tu consentimiento o limitar el uso",
         f"<p>Puedes retirar tu consentimiento o pedirnos que dejemos de usar tus datos para "
         f"una finalidad escribiendo a {canales}, con los mismos datos que para los derechos "
         "ARCO. Algunos datos debemos conservarlos el tiempo que exige la ley fiscal. "
         "También puedes inscribirte en el Registro Público para Evitar Publicidad de la "
         "Profeco.</p>"),
        ("Cambios a este aviso",
         "<p>Si cambia este aviso, publicaremos la versión nueva en esta misma página con "
         "su fecha de actualización.</p>"),
    ]


def html(a: Ajustes) -> str:
    partes = [f"<h2>{escape(t)}</h2>{cuerpo}" for t, cuerpo in secciones(a)]
    return (f"<p class=\"fecha\">Última actualización: {FECHA_AVISO}</p>" + "".join(partes))
