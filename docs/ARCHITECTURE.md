# Architecture

Potluck is a **thin coordination + UX layer** over a distributed-inference engine
(default: [exo](https://github.com/exo-explore/exo)). It deliberately owns as little
of the hard path as possible.

## The one constraint that shapes everything: bandwidth

Splitting a model across machines saves **memory**, not **speed**. Each forward pass
ships activations between devices, so throughput is gated by the network link, not
the GPUs.

Rough, real-world numbers (from public benchmarks):

| Link between nodes | Experience |
|--------------------|------------|
| Thunderbolt 5 + RDMA (M4 Pro/Max) | Excellent — adding nodes adds speed |
| 10GbE / Thunderbolt bridge        | Good for large models |
| 2.5GbE                            | Usable for batch, marginal for chat |
| 1GbE / Wi-Fi                      | Poor for interactive use |
| Open internet                     | Unusable for splitting one request |

**Consequence:** Potluck pools are LAN-first or low-latency-mesh-first (Tailscale /
Thunderbolt). We do **not** try to split a single request across the public internet.
"Rent your idle Mac to strangers" would require that, which is why Potluck is not a
public marketplace.

## Components

```
┌────────────────────────── one machine ──────────────────────────┐
│                                                                  │
│  potluck CLI ──► pool config (~/.potluck/pool.json)              │
│      │              • pool id, name, invite code, shared key     │
│      │              • known peers                                │
│      │                                                           │
│      ├──► transport: LAN discovery  OR  Tailscale mesh           │
│      │                                                           │
│      └──► supervises:  exo node  ──►  OpenAI-compatible API      │
│                          (Metal / CUDA backend, auto-parallel)   │
└──────────────────────────────────────────────────────────────────┘
```

- **CLI (`src/potluck/cli.py`)** — user entry point: `pool create/join`, `up`,
  `status`, `models`.
- **Pool (`src/potluck/pool.py`)** — the part Potluck *owns*: group identity, invite
  codes, the shared key that gates who can join, and the peer list. This is the
  genuine gap above exo today.
- **Config (`src/potluck/config.py`)** — local state under `~/.potluck/`.
- **Engine adapter** — launches/monitors exo and reads its topology. Currently
  stubbed; this is the main integration TODO (see ROADMAP).

## Trust model

Pools are **closed groups of mutually trusting people**. Membership is gated by a
shared secret (the invite code derives a pool key). This is appropriate because:

1. Prompts and activations flow between members' machines.
2. Members run model weights and inference code from each other's coordination.

We explicitly do **not** sandbox against malicious pool members in v1 — the social
contract ("these are my friends/my own machines") is the security boundary, same as
a home NAS or a shared Plex server. A future "untrusted batch" mode (non-sensitive
jobs only, signed runtimes) could relax this; it is out of scope for the MVP.

## Why exo as the engine

- Automatic device discovery + topology-aware auto-parallel (the hard scheduling).
- Apple Silicon via MLX + MLX-distributed; tensor parallelism across nodes.
- OpenAI-compatible API, so every existing app/tool just works.
- Active, popular, day-0 RDMA-over-Thunderbolt support.

The engine is pluggable in principle (llama.cpp RPC / GPUStack could be alternative
backends), but v1 targets exo only to stay focused.

### How Potluck maps onto the *real* exo CLI

Verified against exo `main` (2026). exo is a master/worker cluster you launch with
`uv run exo` (or the `exo` console script); you do **not** pass it a model or topology.
Potluck's `engine.py` builds this real invocation:

| Potluck concept | Real exo flag | Notes |
|---|---|---|
| Pool identity | `--namespace potluck-<pool_id>` | Nodes with different namespaces never connect — this *is* pool isolation, enforced by exo. |
| API / dashboard port | `--api-port 52415` | exo's real default (not 8000). |
| CPU/weak node in a split | `--no-worker` | Coordinator-only: contributes networking, runs no inference. Ideal for a CPU-only laptop. |
| Off-LAN trusted peers | `--bootstrap-peers <multiaddr,...>` | libp2p dial addresses. |
| Which model to run | *(none — chosen per API request)* | exo has no launch-time model flag; you request the model against `/v1/chat/completions`. |

**Route vs split is realized by which nodes run a worker in the pool's namespace**, not
by a flag: route = one worker (others offline or `--no-worker`); split = a worker on
each chosen machine.

**Install reality:** exo is *not* `pip install exo`. It needs Python **3.13** (exact),
`uv`, `node` (to build its dashboard), Rust (nightly), `macmon`, and Xcode's Metal
toolchain, then a clone + dashboard build. `scripts/setup.sh` installs the Potluck CLI
reliably and then checks/report which exo prerequisites are missing.

## Data & privacy

- No prompt logging by default.
- Coordination metadata (who's online, topology) stays within the pool.
- Potluck has no central server. The "first" machine that creates a pool is just the
  bootstrap peer; there is no cloud dependency.
