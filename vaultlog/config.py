"""Locate the default vault file."""

from __future__ import annotations

import os
from pathlib import Path


def default_vault_path() -> Path:
    env = os.environ.get("VAULTLOG_PATH")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".vaultlog" / "journal.vault"
