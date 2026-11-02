"""Settings read from the environment (.env locally, cloud secrets at handover).

Nothing here has a default secret. A missing value raises a clear error naming
the variable, so a run never silently falls back to someone else's account.
"""

from __future__ import annotations

import os
from pathlib import Path

try:  # python-dotenv is optional at import time so tests run without it
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

REPO_ROOT = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    load_dotenv(REPO_ROOT / ".env", override=False)


class MissingSetting(RuntimeError):
    pass


def get(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def require(name: str) -> str:
    value = get(name)
    if value is None:
        raise MissingSetting(
            f"{name} is not set. Add it to .env (see .env.example); never commit it."
        )
    return value
