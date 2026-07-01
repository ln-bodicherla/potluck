"""Adapter to the underlying inference engine (exo).

Turns a chosen strategy (route vs split, which machines, which model) into an exo
invocation, and can actually launch/probe it.

IMPORTANT: exo's CLI flags evolve between versions, and exo auto-splits across
whatever peers it discovers. So the route/split distinction is realized by *which
machines you bring online*, not a single magic flag:
  - route  → run exo on ONE machine; don't bring peers up for this model.
  - split  → run exo on each listed machine; exo auto-parallelises across them.
The flags below are the common shape; verify them against your installed exo with
`exo --help`. `up(..., dry_run=True)` (the default) prints the command without
running it precisely so you can eyeball this.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

DEFAULT_API_PORT = 8000  # exo's own default is 52415; we keep it configurable


def is_exo_installed() -> bool:
    return shutil.which("exo") is not None


@dataclass
class LaunchPlan:
    command: list[str]
    api_url: str
    mode: str
    devices: list[str]
    model: str | None
    guidance: list[str] = field(default_factory=list)


def build_command(pool_id: str, port: int, model: str | None = None,
                  extra: list[str] | None = None) -> list[str]:
    cmd = ["exo", "--node-id", pool_id, "--chatgpt-api-port", str(port)]
    if model:
        # NOTE: verify the run-model flag for your exo version (`exo run <model>` also exists).
        cmd += ["--run-model", model]
    if extra:
        cmd += extra
    return cmd


def plan(pool_id: str, mode: str = "split", devices: list[str] | None = None,
         model: str | None = None, port: int = DEFAULT_API_PORT) -> LaunchPlan:
    devices = devices or []
    cmd = build_command(pool_id, port, model)
    guidance: list[str] = []
    if mode == "route":
        target = devices[0] if devices else "this machine"
        guidance += [
            f"Route mode: run this ONLY on '{target}'.",
            "Do not bring peers online for this model, or exo will split it.",
        ]
    else:  # split
        guidance += [
            "Split mode: run `potluck up` on EACH of these machines:",
            "   " + (", ".join(devices) if devices else "(all pool machines)"),
            "exo auto-parallelises across whoever is online — slowest node sets the pace.",
        ]
    return LaunchPlan(
        command=cmd, api_url=f"http://localhost:{port}/v1",
        mode=mode, devices=devices, model=model, guidance=guidance,
    )


def up(pool_id: str, mode: str = "split", devices: list[str] | None = None,
       model: str | None = None, port: int = DEFAULT_API_PORT,
       dry_run: bool = True) -> LaunchPlan:
    p = plan(pool_id, mode=mode, devices=devices, model=model, port=port)
    if not dry_run:
        # Fire-and-forget; a real supervisor (restart-on-crash, log streaming) is a TODO.
        subprocess.Popen(p.command)  # noqa: S603 — trusted local command
    return p


def probe_api(api_url: str, timeout: float = 1.5) -> bool:
    """Best-effort check that an OpenAI-compatible endpoint is up."""
    import urllib.error
    import urllib.request

    base = api_url.rstrip("/")
    for path in ("/models", "/../"):  # /v1/models, then root
        try:
            with urllib.request.urlopen(base + path, timeout=timeout) as r:  # noqa: S310
                if r.status < 500:
                    return True
        except (urllib.error.URLError, OSError, ValueError):
            continue
    return False


def topology(api_url: str | None = None) -> dict:
    """Live cluster view. exo doesn't expose a stable topology API across versions,
    so for now we just report whether the endpoint is reachable."""
    if api_url and probe_api(api_url):
        return {"peers": ["(endpoint reachable — per-peer detail TBD)"], "reachable": True}
    return {"peers": [], "reachable": False,
            "note": "engine not reachable — start it with `potluck up --real`"}
