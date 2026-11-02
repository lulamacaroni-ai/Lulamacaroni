"""Render the approval page Lorena uses from her phone (Spanish, one screen)."""

from __future__ import annotations

from html import escape

from .gate import Approval

TIPO_LABEL = {
    "listado": "Listado",
    "contenido": "Publicación",
    "anuncio": "Anuncio",
    "presupuesto": "Presupuesto",
    "reembolso": "Reembolso",
    "cancelacion": "Cancelación",
    "pedido-manual": "Pedido manual",
    "respuesta-cliente": "Respuesta a cliente",
    "precio": "Cambio de precio",
}
LINEA_LABEL = {"US-POD": "EUA · impresiones", "MX-original": "México · originales"}
ESTADO_LABEL = {
    "pendiente": "Pendiente", "aprobado": "Aprobado", "rechazado": "Rechazado",
    "expirado": "Expirado", "cancelado": "Cancelado",
}

CSS = """
:root{--bg:#faf8f5;--card:#fff;--ink:#1d1b19;--muted:#6b645c;--line:#e6e0d8;
--ok:#2f6b3a;--no:#9b2c2c;--accent:#b4532a}
@media (prefers-color-scheme:dark){:root{--bg:#171513;--card:#211e1b;--ink:#f1ece6;
--muted:#a89f95;--line:#38322c;--ok:#7cc48a;--no:#e58b8b;--accent:#e08a5f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:640px;margin:0 auto;padding:16px}
h1{font-size:1.4rem;margin:8px 0 4px}h2{font-size:1rem;margin:24px 0 8px;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:10px 0}
.meta{color:var(--muted);font-size:.85rem}.tag{display:inline-block;border:1px solid var(--line);
border-radius:999px;padding:1px 8px;margin-right:6px;font-size:.8rem}
details pre{white-space:pre-wrap;word-break:break-word;font-size:.8rem;background:var(--bg);
padding:8px;border-radius:8px}
form{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
input[type=text]{flex:1 1 100%;padding:10px;border:1px solid var(--line);border-radius:8px;
background:var(--bg);color:var(--ink)}
button{flex:1;padding:12px;border:0;border-radius:8px;font-weight:600;color:#fff;cursor:pointer}
.ok{background:var(--ok)}.no{background:var(--no)}
.empty{color:var(--muted);text-align:center;padding:24px}
"""


def _card(a: Approval, actionable: bool) -> str:
    monto = f'<span class="tag">US${escape(a.monto_usd)}</span>' if a.monto_usd else ""
    estado = ESTADO_LABEL.get(a.estado, a.estado)
    parts = [
        '<article class="card">',
        f'<span class="tag">{escape(TIPO_LABEL.get(a.tipo, a.tipo))}</span>'
        f'<span class="tag">{escape(LINEA_LABEL.get(a.linea, a.linea))}</span>{monto}',
        f"<p><strong>{escape(a.resumen)}</strong></p>",
        f'<p class="meta">Preparado por {escape(a.creado_por)} · {escape(a.creado_en[:16])}'
        f" · vence {escape(a.expira_en[:10])}"
        + ("" if actionable else f" · {escape(estado)}") + "</p>",
        f"<details><summary>Ver exactamente qué se publica</summary>"
        f"<pre>{escape(a.detalle)}</pre></details>",
    ]
    if actionable:
        parts.append(
            '<form method="post" action="/decidir">'
            f'<input type="hidden" name="aprobacion_id" value="{escape(a.aprobacion_id)}">'
            '<input type="text" name="nota" placeholder="Nota (opcional)">'
            '<button class="ok" name="decision" value="aprobar">Aprobar</button>'
            '<button class="no" name="decision" value="rechazar">Rechazar</button>'
            "</form>"
        )
    parts.append("</article>")
    return "".join(parts)


def render_cards(approvals: list[Approval], recent: int = 10) -> str:
    """The page body (heading, pending cards, recent decisions), reused by the back office app."""
    pending = sorted((a for a in approvals if a.estado == "pendiente"), key=lambda a: a.creado_en)
    decided = sorted((a for a in approvals if a.estado != "pendiente"),
                     key=lambda a: a.decidido_en or a.creado_en, reverse=True)[:recent]
    body = [f"<h1>Aprobaciones</h1><p class='meta'>{len(pending)} pendiente(s)</p>"]
    body.append("".join(_card(a, True) for a in pending)
                or '<p class="empty">Nada por aprobar. 🎨</p>')
    if decided:
        body.append("<h2>Decididas recientemente</h2>")
        body.append("".join(_card(a, False) for a in decided))
    return "".join(body)


def render(approvals: list[Approval], recent: int = 10) -> str:
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Aprobaciones</title><style>{CSS}</style></head>"
        f"<body><main>{render_cards(approvals, recent)}</main></body></html>"
    )
