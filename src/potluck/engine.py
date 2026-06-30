"""Adapter to the underlying inference engine (exo).

This is the main integration TODO. Right now `up()` is a dry-run that prints the
command it *would* launch, so the CLI is fully runnable before exo wiring exists.
Replace the body of `up()` and `topology()` to make it real (docs/ROADMAP Phase 2).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


def is_exo_installed() -> bool:
    return shutil.which("exo") is not None


@dataclass
class LaunchPlan:
    command: list[str]
    api_url: str


def plan(pool_id: str, api_port: int = 8000) -> LaunchPlan:
    """The exo invocation Potluck would run for this pool.

    exo auto-discovers peers and exposes an OpenAI-compatible API. We pass the
    pool id so Potluck-managed nodes only cluster with their own pool (wiring of
    that filter is a Phase 3 TODO).
    """
    return LaunchPlan(
        command=["exo", "--node-id", pool_id, "--chatgpt-api-port", str(api_port)],
        api_url=f"http://localhost:{api_port}/v1",
    )


def up(pool_id: str, api_port: int = 8000, dry_run: bool = True) -> LaunchPlan:
    p = plan(pool_id, api_port)
    if dry_run:
        return p
    # Phase 2: actually supervise the process, restart on crash, stream logs.
    subprocess.Popen(p.command)  # noqa: S603 — trusted local command
    return p


def topology() -> dict:
    """Live cluster view from the engine. Stub until exo wiring lands (Phase 2)."""
    return {"peers": [], "note": "engine adapter not yet wired — see docs/ROADMAP.md"}
