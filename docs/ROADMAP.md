# Roadmap

Ordered so each step produces something you can actually run. Items marked **stub**
are scaffolded in code but not yet wired to exo.

## Phase 0 — Prove the core works (no Potluck code needed)
- [ ] Install exo on 2+ of your machines.
- [ ] Cluster them, run a model that doesn't fit on one machine.
- [ ] Write down every painful step. **This is the real spec for Potluck.**

## Phase 1 — Pool identity (the part Potluck owns) ✅ scaffolded
- [x] `potluck pool create <name>` → generate pool id + invite code + shared key.
- [x] `potluck pool join <code>` → store pool membership locally.
- [x] Local config under `~/.potluck/`.
- [ ] Derive a real shared key from the invite code (currently a placeholder).

## Phase 1.5 — The planner (let people decide) ✅ scaffolded
The product philosophy: **Potluck doesn't choose route-vs-split for you — it shows
the trade-offs and you pick.**
- [x] Device registry: `device detect` (auto), `device add` (peers), `device ls`.
- [x] Model sizing (dense + MoE) and quant footprints.
- [x] `potluck plan <model>` ranks every route/split strategy with fit + est. tok/s.
- [ ] Calibrate the speed model against real runs (replace heuristic bandwidths).
- [ ] Pull live device specs from online peers instead of manual registration.

## Phase 2 — Engine adapter  **stub → real**
- [x] Honor the chosen strategy: `potluck up --mode route|split --devices a,b`.
- [x] `potluck up --real` launches exo (dry run by default so you can vet the command).
- [x] `potluck status` / dashboard probe the endpoint for reachability.
- [ ] Verify/lock exo flags against a pinned exo version (they drift between releases).
- [ ] Real process supervision: restart-on-crash, log streaming.
- [ ] Per-peer topology detail (needs a stable exo topology API).

## Phase 1.6 — Calibration ✅
- [x] `potluck bench` measures real tok/s against the live endpoint.
- [x] `--calibrate <device>` writes measured bandwidth back so `plan` matches reality.

## Phase 5 — Dashboard ✅ (v1)
- [x] `potluck dashboard` — local web page: machines, memory, engine status, live plan.
- [ ] Auto-refresh + show current running model and measured throughput.

## Phase 3 — Discovery / transport
- [ ] LAN auto-discovery of pool peers.
- [ ] Optional Tailscale integration for off-LAN trusted pools.
- [ ] Gate discovery by the pool's shared key.

## Phase 4 — "What can I run?"
- [ ] `potluck models` — given combined RAM/VRAM of online peers, list models that
      fit and a rough tokens/sec estimate based on the slowest link.

## Phase 5 — Dashboard
- [ ] Minimal local web UI: online peers, combined memory, current model, throughput.

## Later / maybe
- [ ] Untrusted "batch only" mode for non-sensitive jobs.
- [ ] Alternative engine backends (llama.cpp RPC, GPUStack).
- [ ] Optional metering if a pool ever wants to settle costs internally.

## Explicit non-goals (for now)
- Public GPU marketplace / paying strangers.
- Splitting a single request across the open internet.
- Reimplementing exo's scheduler.
