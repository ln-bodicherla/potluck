"""Local Potluck state, stored under ~/.potluck/.

No cloud, no central server — everything a machine needs to know about its pool
lives here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def config_dir() -> Path:
    """Directory holding this machine's Potluck state. Override with $POTLUCK_HOME."""
    root = os.environ.get("POTLUCK_HOME")
    path = Path(root) if root else Path.home() / ".potluck"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pool_file() -> Path:
    return config_dir() / "pool.json"


def devices_file() -> Path:
    return config_dir() / "devices.json"


def load_devices() -> list[dict[str, Any]]:
    """The pool's known machines (this one + registered peers)."""
    path = devices_file()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def save_devices(items: list[dict[str, Any]]) -> None:
    devices_file().write_text(json.dumps(items, indent=2) + "\n")


def load_pool() -> dict[str, Any] | None:
    """Return this machine's pool membership, or None if it hasn't joined one."""
    path = pool_file()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_pool(data: dict[str, Any]) -> None:
    pool_file().write_text(json.dumps(data, indent=2) + "\n")
