"""Approval gate: nothing publishes, spends, refunds or cancels without Lorena's approval.

How it works
------------
1. An agent that wants to act calls :func:`request_approval` with the exact content it
   will publish or send (listing text, post, budget, refund...). The record stores a
   fingerprint (SHA-256) of that content and starts as ``pendiente``.
2. Lorena approves or rejects it on the approval page.
3. Right before acting, the code that publishes calls :func:`assert_approved` with the
   content it is about to send. It passes only if the record is ``aprobado``, of the
   right type, not expired, not already executed, and the fingerprint still matches.
   Any edit after approval changes the fingerprint and needs a new approval.
4. After acting, :func:`mark_executed` stamps the record so it can never be used twice.

Records live in the ``Aprobaciones`` tab of the Google Sheet when a Google key is
configured; otherwise a local JSON file (``LULA_APPROVALS_PATH``) holds them through the
same store interface.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta, timezone
from typing import Any

from ..schema import LINEAS, TIPOS_APROBACION

DEFAULT_TTL = timedelta(days=7)


class NotApproved(PermissionError):
    """Raised when an action is attempted without a valid approval."""


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime | None) -> str:
    return dt.isoformat() if dt else ""


def _parse(value: str) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def fingerprint(contenido: Any) -> str:
    """Stable SHA-256 of the content (key order and whitespace don't matter)."""
    canonical = json.dumps(contenido, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class Approval:
    aprobacion_id: str
    tipo: str
    linea: str
    resumen: str
    detalle: str          # JSON of the content, so Lorena sees exactly what she approves
    huella: str           # fingerprint of that content
    creado_por: str
    creado_en: str
    expira_en: str
    monto_usd: str = ""
    estado: str = "pendiente"
    decidido_por: str = ""
    decidido_en: str = ""
    nota_decision: str = ""
    ejecutado_en: str = ""

    @property
    def contenido(self) -> Any:
        return json.loads(self.detalle)

    def to_row(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Approval":
        names = {f.name for f in fields(cls)}
        return cls(**{k: ("" if v is None else str(v)) for k, v in row.items() if k in names})


def request_approval(store, *, tipo: str, linea: str, resumen: str, contenido: Any,
                     creado_por: str, monto_usd: float | None = None,
                     ttl: timedelta = DEFAULT_TTL, now: datetime | None = None) -> Approval:
    if tipo not in TIPOS_APROBACION:
        raise ValueError(f"tipo {tipo!r} not in {TIPOS_APROBACION}")
    if linea not in LINEAS:
        raise ValueError(f"linea {linea!r} not in {LINEAS}")
    if tipo == "presupuesto" and monto_usd is None:
        raise ValueError("a budget approval needs monto_usd")
    now = now or now_utc()
    record = Approval(
        aprobacion_id=f"apr-{now:%Y%m%d}-{uuid.uuid4().hex[:6]}",
        tipo=tipo,
        linea=linea,
        resumen=resumen,
        detalle=json.dumps(contenido, ensure_ascii=False, sort_keys=True, indent=2),
        huella=fingerprint(contenido),
        creado_por=creado_por,
        creado_en=_iso(now),
        expira_en=_iso(now + ttl),
        monto_usd="" if monto_usd is None else f"{monto_usd:.2f}",
    )
    store.add(record)
    return record


def decide(store, aprobacion_id: str, *, aprobar: bool, decidido_por: str,
           nota: str = "", now: datetime | None = None) -> Approval:
    record = store.get(aprobacion_id)
    if record.estado != "pendiente":
        raise ValueError(f"{aprobacion_id} is already {record.estado}")
    now = now or now_utc()
    if _parse(record.expira_en) and now > _parse(record.expira_en):
        record.estado = "expirado"
    else:
        record.estado = "aprobado" if aprobar else "rechazado"
        record.decidido_por = decidido_por
        record.decidido_en = _iso(now)
        record.nota_decision = nota
    store.update(record)
    return record


def assert_approved(record: Approval | None, *, tipo: str, contenido: Any,
                    now: datetime | None = None) -> None:
    """Raise :class:`NotApproved` unless ``record`` authorises exactly this action."""
    if record is None:
        raise NotApproved("Sin aprobación: no approval record was given.")
    if record.estado != "aprobado":
        raise NotApproved(f"{record.aprobacion_id} está {record.estado}, no aprobado.")
    if record.tipo != tipo:
        raise NotApproved(f"{record.aprobacion_id} aprueba '{record.tipo}', no '{tipo}'.")
    if record.ejecutado_en:
        raise NotApproved(f"{record.aprobacion_id} ya se usó el {record.ejecutado_en}.")
    now = now or now_utc()
    expira = _parse(record.expira_en)
    if expira and now > expira:
        raise NotApproved(f"{record.aprobacion_id} expiró el {record.expira_en}.")
    if record.huella != fingerprint(contenido):
        raise NotApproved(
            f"{record.aprobacion_id}: el contenido cambió después de aprobarse; "
            "hace falta una nueva aprobación."
        )


def mark_executed(store, record: Approval, now: datetime | None = None) -> Approval:
    record.ejecutado_en = _iso(now or now_utc())
    store.update(record)
    return record
