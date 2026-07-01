"""Measure real tokens/sec and feed it back into the planner.

The planner's default speeds come from a memory-bandwidth heuristic. `bench` closes
the loop: run a real prompt against the OpenAI-compatible endpoint, measure tok/s,
and back out the *effective* bandwidth for the machine that served it — then store
that as an override so future `potluck plan` estimates match reality.

Pure functions (tok/s, calibration math) are separated from the HTTP call so they're
testable without a live server.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass

from . import models


def tokens_per_sec(completion_tokens: int, seconds: float) -> float:
    return completion_tokens / seconds if seconds > 0 else 0.0


def effective_bandwidth_gbps(model: models.Model, quant: str, measured_tps: float) -> float:
    """Invert the decode model: tok/s = bandwidth / active_gb  ⇒  bandwidth = active_gb * tok/s.

    For a *single-machine* (route) benchmark this yields that machine's effective
    memory bandwidth, which is exactly the knob the planner uses.
    """
    return models.active_gb(model, quant) * measured_tps


@dataclass
class BenchResult:
    model: str
    completion_tokens: int
    seconds: float
    tokens_per_sec: float
    effective_bandwidth_gbps: float | None = None


def run_bench(api_url: str, model_id: str, model: models.Model, quant: str,
              prompt: str = "Write a short paragraph about the ocean.",
              max_tokens: int = 128, timeout: float = 300.0) -> BenchResult:
    """Hit <api_url>/chat/completions once and time the generation."""
    url = api_url.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": False,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        payload = json.loads(resp.read())
    elapsed = time.perf_counter() - start

    usage = payload.get("usage", {})
    completion = usage.get("completion_tokens")
    if completion is None:  # fall back to rough word count if server omits usage
        text = payload["choices"][0]["message"]["content"]
        completion = max(1, round(len(text.split()) * 1.3))

    tps = tokens_per_sec(completion, elapsed)
    return BenchResult(
        model=model.name, completion_tokens=completion, seconds=elapsed,
        tokens_per_sec=tps, effective_bandwidth_gbps=effective_bandwidth_gbps(model, quant, tps),
    )
