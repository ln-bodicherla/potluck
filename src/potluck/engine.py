"""Adapter to the underlying inference engine (exo).

Verified against exo `main` (2026): a master/worker cluster you run with `uv run exo`
(or the `exo` console script). exo auto-discovers peers and auto-parallelises; you do
NOT tell it a model or a topology on the command line.

Real facts this adapter maps to (from exo's own argparse):
  - API + dashboard default port is **52415** (`--api-port`).
  - **`--namespace`** isolates a cluster: nodes with different namespaces never
    connect. This is exactly Potluck's "pool" — we set `--namespace potluck-<pool_id>`.
  - **`--no-worker`** makes a node coordinator-only (networking, no inference) — the
    right setting for a weak/CPU node so it doesn't drag a split.
  - The model is chosen per-request via the OpenAI-compatible API, not at launch.

So route vs split is realized by *which nodes run a worker in the pool's namespace*:
  - route → run one worker; keep others offline or `--no-worker`.
  - split → run a worker on each chosen machine (same namespace); exo splits across them.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

DEFAULT_API_PORT = 52415  # exo's real default


def is_exo_installed() -> bool:
    return shutil.which("exo") is not None


def namespace_for(pool_id: str) -> str:
    return f"potluck-{pool_id}"


@dataclass
class LaunchPlan:
    command: list[str]
    api_url: str
    mode: str
    devices: list[str]
    model: str | None
    guidance: list[str] = field(default_factory=list)


def build_command(pool_id: str, port: int = DEFAULT_API_PORT, no_worker: bool = False,
                  bootstrap_peers: list[str] | None = None,
                  use_uv: bool = False) -> list[str]:
    cmd = ["uv", "run", "exo"] if use_uv else ["exo"]
    cmd += ["--namespace", namespace_for(pool_id), "--api-port", str(port)]
    if no_worker:
        cmd.append("--no-worker")  # coordinator-only: no local inference
    if bootstrap_peers:
        cmd += ["--bootstrap-peers", ",".join(bootstrap_peers)]
    return cmd


def plan(pool_id: str, mode: str = "split", devices: list[str] | None = None,
         model: str | None = None, port: int = DEFAULT_API_PORT,
         no_worker: bool = False, bootstrap_peers: list[str] | None = None,
         use_uv: bool = False) -> LaunchPlan:
    devices = devices or []
    cmd = build_command(pool_id, port, no_worker=no_worker,
                        bootstrap_peers=bootstrap_peers, use_uv=use_uv)
    guidance: list[str] = []
    if mode == "route":
        target = devices[0] if devices else "this machine"
        guidance += [
            f"Route mode: run a worker ONLY on '{target}'.",
            "Keep other pool machines offline (or start them with --no-worker),",
            "otherwise exo will auto-split the model across them.",
        ]
    else:  # split
        guidance += [
            "Split mode: run `potluck up` on EACH of these machines (same namespace):",
            "   " + (", ".join(devices) if devices else "(all pool machines)"),
            "exo auto-parallelises across all workers — the slowest sets the pace.",
            "Tip: start a CPU-only machine with `--no-worker` so it helps with",
            "networking without dragging inference.",
        ]
    if model:
        guidance.append(f"Pick the model ('{model}') at request time via the API — exo "
                        "has no launch-time model flag.")
    return LaunchPlan(
        command=cmd, api_url=f"http://localhost:{port}/v1",
        mode=mode, devices=devices, model=model, guidance=guidance,
    )


def up(pool_id: str, mode: str = "split", devices: list[str] | None = None,
       model: str | None = None, port: int = DEFAULT_API_PORT,
       no_worker: bool = False, dry_run: bool = True) -> LaunchPlan:
    p = plan(pool_id, mode=mode, devices=devices, model=model, port=port, no_worker=no_worker)
    if not dry_run:
        # Fire-and-forget; real supervision (restart-on-crash, log streaming) is a TODO.
        subprocess.Popen(p.command)  # noqa: S603 — trusted local command
    return p


def probe_api(api_url: str, timeout: float = 1.5) -> bool:
    """Best-effort check that exo's OpenAI-compatible endpoint is up."""
    import urllib.error
    import urllib.request

    base = api_url.rstrip("/")
    for path in ("/models", "/../"):  # /v1/models, then root/dashboard
        try:
            with urllib.request.urlopen(base + path, timeout=timeout) as r:  # noqa: S310
                if r.status < 500:
                    return True
        except (urllib.error.URLError, OSError, ValueError):
            continue
    return False


def topology(api_url: str | None = None) -> dict:
    """Live cluster view. exo's per-peer topology API isn't stable across versions, so
    for now we just report whether the endpoint is reachable."""
    if api_url and probe_api(api_url):
        return {"peers": ["(endpoint reachable — per-peer detail TBD)"], "reachable": True}
    return {"peers": [], "reachable": False,
            "note": "engine not reachable — start it with `potluck up --real`"}
