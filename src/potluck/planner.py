"""The decision engine.

Given the pool's devices, a model, and the network link, enumerate the realistic
strategies and estimate fit + tokens/sec for each — so a human can choose, rather
than the tool choosing for them.

Two families of strategy:
  - ROUTE: one device runs the whole model. No per-token network cost. Fastest when
    the model fits on a single machine.
  - SPLIT: the model is pipeline-split across a subset of devices. Unlocks models too
    big for any one machine, but devices run one-at-a-time per token, so the slowest
    device (and, a little, the network) sets the pace.

All speeds are rough estimates from a memory-bandwidth model, clearly labelled as
such in the UI. They're meant to be *comparable*, not exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from . import models
from .devices import Device
from .models import Model

# Per-hop network latency (ms) added per token, by link type.
LINK_LATENCY_MS = {"wifi": 4.0, "ethernet": 0.5, "thunderbolt": 0.05}


@dataclass
class Strategy:
    kind: str  # "route" | "split"
    devices: list[Device]
    fits: bool
    tokens_per_sec: float
    headroom_gb: float  # spare usable memory (negative = doesn't fit)
    note: str

    def device_label(self) -> str:
        return " + ".join(d.name for d in self.devices)


def _route_speed(model: Model, quant: str, dev: Device) -> float:
    seconds_per_token = models.active_gb(model, quant) / dev.bandwidth()
    return 1.0 / seconds_per_token if seconds_per_token > 0 else 0.0


def _split_speed(model: Model, quant: str, devs: list[Device], link: str) -> float:
    """Pipeline decode: each device reads its share of weights once per token, in
    sequence; add a network hop between consecutive devices."""
    total_usable = sum(d.usable_gb() for d in devs)
    weight = models.weight_gb(model, quant)
    active_frac = models.active_gb(model, quant) / max(models.weight_gb(model, quant), 1e-9)
    compute_s = 0.0
    for d in devs:
        share = weight * (d.usable_gb() / total_usable)  # memory allocated here
        compute_s += (share * active_frac) / d.bandwidth()  # active bytes read per token
    hops = len(devs) - 1
    network_s = hops * LINK_LATENCY_MS.get(link, 4.0) / 1000.0
    total = compute_s + network_s
    return 1.0 / total if total > 0 else 0.0


def plan(
    devices: list[Device],
    model: Model,
    quant: str = "q4",
    link: str = "wifi",
    ctx_tokens: int = 4096,
) -> list[Strategy]:
    need = models.footprint_gb(model, quant, ctx_tokens)
    strategies: list[Strategy] = []

    # ROUTE: every single device that could host the whole model.
    for d in devices:
        head = d.usable_gb() - need
        if head >= 0:
            strategies.append(Strategy(
                kind="route", devices=[d], fits=True,
                tokens_per_sec=_route_speed(model, quant, d),
                headroom_gb=head,
                note="whole model on one machine — no network cost",
            ))

    # SPLIT: every subset of 2+ devices whose combined memory holds the model.
    for r in range(2, len(devices) + 1):
        for combo in combinations(devices, r):
            combo = list(combo)
            usable = sum(d.usable_gb() for d in combo)
            head = usable - need
            if head < 0:
                continue
            has_cpu = any(d.backend == "cpu" for d in combo)
            note = "splits to fit a bigger model"
            if has_cpu:
                note += "; includes a CPU node (slowest link)"
            strategies.append(Strategy(
                kind="split", devices=combo, fits=True,
                tokens_per_sec=_split_speed(model, quant, combo, link),
                headroom_gb=head, note=note,
            ))

    if not strategies:
        # Nothing fits — report the best-effort full split so the user sees how short.
        usable = sum(d.usable_gb() for d in devices)
        strategies.append(Strategy(
            kind="split", devices=list(devices), fits=False,
            tokens_per_sec=0.0, headroom_gb=usable - need,
            note=f"does NOT fit — short by {need - usable:.1f} GB even using everything",
        ))

    # Best experience first: fits, then fastest.
    strategies.sort(key=lambda s: (not s.fits, -s.tokens_per_sec))
    return strategies
