"""Where approval records live.

``JsonStore`` keeps them in a local, git-ignored JSON file until the workbook is live.
A ``SheetsStore`` with the same four methods (add, get, update, all) will write to the
``Aprobaciones`` tab; the gate and the page don't care which one they get.
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


def open_store() -> JsonStore:
    path = config.get("LULA_APPROVALS_PATH", "data/aprobaciones.json")
    p = Path(path)
    if not p.is_absolute():
        p = config.REPO_ROOT / p
    return JsonStore(p)
