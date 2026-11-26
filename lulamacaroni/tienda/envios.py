"""After Lorena's tap: send approved store orders to Prodigi, then email tracking when they ship.

Runs every few minutes inside the store service (``Trabajador``) and on demand with
``python -m lulamacaroni.tienda.envios``. Each step is safe to repeat:

* an approval is used once (``mark_executed``), and Prodigi gets the approval id as its
  ``idempotencyKey``, so a crash between the two can't print twice;
* the shipped email goes out only while ``Pedidos.tracking`` is empty, and Resend gets an
  idempotency key, so a retry doesn't send it twice.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

from ..approval.gate import NotApproved, mark_executed
from . import correo as plantillas
from .ajustes import Ajustes
from .pedidos import CANAL, destinatario_prodigi, envio_de, huella_direccion

log = logging.getLogger(__name__)
EN_IMPRENTA = ("enviado-a-pod", "en-produccion")


def _ahora() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _excepcion(book, ref: str, detalle: str, ahora: datetime) -> None:
    book.upsert("Excepciones", [{
        "excepcion_id": f"exc-{ref}", "linea": "US-POD", "tipo": "pedido-tienda",
        "referencia": ref, "detalle": detalle, "creada_en": ahora.isoformat(),
        "responsable": "Lorena", "estado": "abierta"}])


def enviar_aprobados(book, store, stripe, prodigi, ahora: datetime | None = None) -> list[str]:
    """Send every approved, unused ``pedido-tienda``. Returns the order numbers sent."""
    ahora = ahora or _ahora()
    enviados = []
    for rec in store.all():
        if rec.tipo != "pedido-tienda" or rec.estado != "aprobado" or rec.ejecutado_en:
            continue
        c = rec.contenido
        envio = envio_de(stripe.checkout(c["stripe_checkout"]))
        try:
            orden = prodigi.create_store_order(c, destinatario_prodigi(envio),
                                               huella_direccion(envio), approval=rec)
        except NotApproved as exc:
            _excepcion(book, c["pedido"], str(exc), ahora)
            continue
        mark_executed(store, rec, now=ahora)
        lineas = [r for r in book.read("Pedidos") if r.get("pedido_id") == c["stripe_checkout"]]
        book.upsert("Pedidos", [{"linea_pedido_id": r["linea_pedido_id"], "linea": "US-POD",
                                 "estado": "enviado-a-pod", "pod_pedido_id": orden.get("id", "")}
                                for r in lineas])
        enviados.append(c["pedido"])
    return enviados


def _rastreo(orden: dict) -> tuple[str, str, str] | None:
    for s in orden.get("shipments") or []:
        t = s.get("tracking") or {}
        if t.get("number"):
            return str(t["number"]), str(t.get("url") or ""), str((s.get("carrier") or {}).get("name") or "")
    return None


def avisar_enviados(book, stripe, prodigi, mailer, ajustes: Ajustes,
                    ahora: datetime | None = None) -> list[str]:
    """Email tracking for store orders Prodigi has shipped. Returns the order numbers."""
    ahora = ahora or _ahora()
    por_pedido: dict[str, list[dict]] = {}
    for r in book.read("Pedidos"):
        if (r.get("canal") == CANAL and r.get("estado") in EN_IMPRENTA and r.get("pod_pedido_id")
                and not r.get("tracking")):
            por_pedido.setdefault(r["pedido_id"], []).append(r)
    avisados = []
    for sid, lineas in por_pedido.items():
        rastreo = _rastreo(prodigi.get_order(lineas[0]["pod_pedido_id"]))
        if rastreo is None:
            continue
        numero_rastreo, url, transportista = rastreo
        nota = ""
        if mailer.activo:
            detalles = (stripe.checkout(sid).get("customer_details") or {})
            if detalles.get("email"):
                asunto, html, texto = plantillas.enviado(
                    ajustes, lineas[0]["numero_canal"], ((detalles.get("name") or "").split() or [""])[0],
                    numero_rastreo, url, transportista)
                mailer.enviar(de=ajustes.remitente, para=detalles["email"], asunto=asunto, html=html,
                              texto=texto, responder_a=ajustes.soporte, clave=f"enviado-{sid}")
        else:
            nota = "correo de envío no mandado: falta RESEND_API_KEY"
            _excepcion(book, f"{lineas[0]['numero_canal']}-correo", nota, ahora)
        book.upsert("Pedidos", [{"linea_pedido_id": r["linea_pedido_id"], "linea": "US-POD",
                                 "estado": "enviado", "tracking": numero_rastreo} for r in lineas])
        avisados.append(lineas[0]["numero_canal"])
    return avisados


def ciclo(book, store, stripe, prodigi, mailer, ajustes: Ajustes) -> dict:
    enviados = enviar_aprobados(book, store, stripe, prodigi)
    avisados = avisar_enviados(book, stripe, prodigi, mailer, ajustes)
    book.stamp_source("tienda", rows=len(enviados) + len(avisados),
                      note=f"{len(enviados)} a Prodigi, {len(avisados)} con guía")
    return {"enviados": enviados, "avisados": avisados}


class Trabajador(threading.Thread):
    """Background loop in the store service: one ``ciclo`` every ``cada`` seconds."""

    def __init__(self, hacer, cada: float = 300):
        super().__init__(daemon=True, name="tienda-envios")
        self.hacer, self.cada, self.alto = hacer, cada, threading.Event()

    def run(self) -> None:
        while not self.alto.wait(self.cada):
            try:
                self.hacer()
            except Exception:
                log.exception("ciclo de envíos falló")


def main(argv: list[str] | None = None) -> int:
    from ..approval.store import SheetsStore, open_store
    from ..connectors.prodigi import ProdigiClient
    from ..localbook import open_workbook
    from ..workbook import Workbook
    from .correo import Correo
    from .stripe import StripeClient

    book = open_workbook()
    store = SheetsStore(book) if isinstance(book, Workbook) else open_store()
    r = ciclo(book, store, StripeClient.from_env(), ProdigiClient.from_env(), Correo.from_env(),
              Ajustes.desde_entorno())
    print(f"Enviados a Prodigi: {', '.join(r['enviados']) or 'ninguno'}")
    print(f"Avisos de envío: {', '.join(r['avisados']) or 'ninguno'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
