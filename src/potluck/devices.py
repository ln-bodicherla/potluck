"""Describe the machines in a pool.

A Device is what the planner reasons over. We auto-detect the local machine and let
users register their peers' specs so the planner can compare strategies for the
whole pool — without every machine needing to be online yet.

Memory/bandwidth numbers are deliberately rough heuristics (clearly the defaults are
overridable). The goal is to put *comparable* estimates in front of a human, not to
be a benchmark.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass, field

# Nominal memory bandwidth (GB/s) by compute backend. Decode speed is bandwidth-bound,
# so this drives the tok/s estimate. Apple Silicon varies a lot by tier (M-base ~100,
# Pro ~200, Max ~400, Ultra ~800); we use a conservative default you can override.
_DEFAULT_BANDWIDTH = {"metal": 150.0, "cuda": 400.0, "cpu": 50.0}

# Fraction of total RAM realistically usable for model weights + KV cache.
_USABLE_FRACTION = {"metal": 0.72, "cuda": 0.85, "cpu": 0.60}


@dataclass
class Device:
    name: str
    ram_gb: float
    backend: str  # "metal" | "cuda" | "cpu"
    bandwidth_gbps: float | None = None  # override; else backend default
    notes: str = ""

    def usable_gb(self) -> float:
        return self.ram_gb * _USABLE_FRACTION.get(self.backend, 0.6)

    def bandwidth(self) -> float:
        return self.bandwidth_gbps or _DEFAULT_BANDWIDTH.get(self.backend, 50.0)

    def label(self) -> str:
        return f"{self.name} ({self.ram_gb:.0f}GB/{self.backend})"


def _detect_ram_gb() -> float:
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            return int(out.strip()) / (1024**3)
        if system == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) / (1024**2)  # kB → GB
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return 16.0  # safe fallback


def _detect_backend() -> str:
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "metal"
    if shutil.which("nvidia-smi"):
        return "cuda"
    return "cpu"


def detect_local(name: str = "") -> Device:
    backend = _detect_backend()
    return Device(
        name=name or platform.node() or "this-machine",
        ram_gb=round(_detect_ram_gb()),
        backend=backend,
        notes="auto-detected",
    )
