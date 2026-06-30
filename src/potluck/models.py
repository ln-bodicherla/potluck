"""Model sizing — turn a model + quantization into a memory & compute footprint.

We separate two param counts so MoE models are handled honestly:
  - memory_params_b: total weights (drives whether it FITS)
  - compute_params_b: params active per token (drives SPEED; == total for dense models)
"""

from __future__ import annotations

from dataclasses import dataclass

# Approx GB of weights per billion params, by quantization.
QUANT_GB_PER_B = {
    "q2": 0.34,
    "q3": 0.43,
    "q4": 0.56,  # q4_k_m, the common default
    "q5": 0.70,
    "q6": 0.82,
    "q8": 1.06,
    "fp16": 2.0,
}


@dataclass
class Model:
    name: str
    memory_params_b: float
    compute_params_b: float | None = None  # None → dense (== memory)

    def active_params_b(self) -> float:
        return self.compute_params_b or self.memory_params_b


# Small starter catalog spanning the scenarios that matter for a home pool.
CATALOG: dict[str, Model] = {
    "llama-3.1-8b": Model("Llama-3.1-8B", 8),
    "qwen2.5-14b": Model("Qwen2.5-14B", 14),
    "qwen2.5-32b": Model("Qwen2.5-32B", 32),
    "qwen3-32b": Model("Qwen3-32B", 32),
    "mixtral-8x7b": Model("Mixtral-8x7B", 46.7, compute_params_b=12.9),  # MoE
    "llama-3.3-70b": Model("Llama-3.3-70B", 70),
    "qwen2.5-72b": Model("Qwen2.5-72B", 72),
}


def quant_bytes_per_b(quant: str) -> float:
    q = quant.lower()
    if q not in QUANT_GB_PER_B:
        raise ValueError(f"Unknown quant {quant!r}. Try one of: {', '.join(QUANT_GB_PER_B)}")
    return QUANT_GB_PER_B[q]


def weight_gb(model: Model, quant: str) -> float:
    return model.memory_params_b * quant_bytes_per_b(quant)


def active_gb(model: Model, quant: str) -> float:
    """Bytes actually read per token — what decode speed is bound by."""
    return model.active_params_b() * quant_bytes_per_b(quant)


def kv_overhead_gb(model: Model, ctx_tokens: int = 4096) -> float:
    """Rough KV-cache + runtime overhead. Scales with model size and context."""
    return 0.5 + (model.memory_params_b / 70.0) * (ctx_tokens / 4096) * 2.0


def footprint_gb(model: Model, quant: str, ctx_tokens: int = 4096) -> float:
    return weight_gb(model, quant) + kv_overhead_gb(model, ctx_tokens)


def resolve(name: str, params: float | None = None) -> Model:
    """Look up a catalog model, or synthesize one from a raw param count."""
    if params is not None:
        return Model(name=f"custom-{params:g}b", memory_params_b=params)
    key = name.lower()
    if key in CATALOG:
        return CATALOG[key]
    raise ValueError(
        f"Unknown model {name!r}. Known: {', '.join(CATALOG)}. "
        "Or pass --params N to size an arbitrary model."
    )
