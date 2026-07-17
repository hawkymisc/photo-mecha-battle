"""Resolve the on-disk SQLite path for the API process.

Default: ``{PMB_DATA_DIR}/pmb.sqlite3`` (``PMB_DATA_DIR`` defaults to ``data``).
Override: ``PMB_DB_PATH`` (absolute or relative path).

Tests continue to inject ``Database(":memory:")`` via ``conftest.fresh_game_store``.
"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_db_path(*, ensure_parent: bool = False) -> Path:
    explicit = os.environ.get("PMB_DB_PATH")
    if explicit:
        path = Path(explicit)
    else:
        data_dir = Path(os.environ.get("PMB_DATA_DIR", "data"))
        path = data_dir / "pmb.sqlite3"
    if ensure_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path
