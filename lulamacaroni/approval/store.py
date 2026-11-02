"""Where approval records live.

``SheetsStore`` keeps them in the ``Aprobaciones`` tab of the workbook (Google Sheet, or
its local stand-in). ``JsonStore`` keeps them in a local, git-ignored JSON file when no
workbook is configured. Both have the same four methods (add, get, update, all); the
gate and the page don't care which one they get.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .. import config
from .gate import Approval


class JsonStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, rows: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)  # atomic: a crash never leaves half a file

    def all(self) -> list[Approval]:
        return [Approval.from_row(r) for r in self._load()]

    def get(self, aprobacion_id: str) -> Approval:
        for record in self.all():
            if record.aprobacion_id == aprobacion_id:
                return record
        raise KeyError(aprobacion_id)

    def add(self, record: Approval) -> None:
        rows = self._load()
        if any(r["aprobacion_id"] == record.aprobacion_id for r in rows):
            raise ValueError(f"duplicate {record.aprobacion_id}")
        rows.append(record.to_row())
        self._save(rows)

    def update(self, record: Approval) -> None:
        rows = self._load()
        for i, r in enumerate(rows):
            if r["aprobacion_id"] == record.aprobacion_id:
                rows[i] = record.to_row()
                self._save(rows)
                return
        raise KeyError(record.aprobacion_id)


class SheetsStore:
    """Approvals in the ``Aprobaciones`` tab. Every value is stored as text, so the
    fingerprint and the JSON detail come back exactly as written."""

    TAB = "Aprobaciones"

    def __init__(self, book):
        self.book = book

    def all(self) -> list[Approval]:
        return [Approval.from_row(r) for r in self.book.read(self.TAB)]

    def get(self, aprobacion_id: str) -> Approval:
        for record in self.all():
            if record.aprobacion_id == aprobacion_id:
                return record
        raise KeyError(aprobacion_id)

    def add(self, record: Approval) -> None:
        if any(r.aprobacion_id == record.aprobacion_id for r in self.all()):
            raise ValueError(f"duplicate {record.aprobacion_id}")
        self.book.upsert(self.TAB, [record.to_row()])

    def update(self, record: Approval) -> None:
        self.get(record.aprobacion_id)  # KeyError if it was never requested
        self.book.upsert(self.TAB, [record.to_row()])


def open_store():
    """The ``Aprobaciones`` tab when the Google Sheet is in use, otherwise the JSON file."""
    from ..localbook import backend

    if backend() == "google":
        from ..workbook import Workbook

        return SheetsStore(Workbook.from_env())
    path = config.get("LULA_APPROVALS_PATH", "data/aprobaciones.json")
    p = Path(path)
    if not p.is_absolute():
        p = config.REPO_ROOT / p
    return JsonStore(p)
