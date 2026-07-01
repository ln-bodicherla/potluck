# Potluck 🍲

**Pool your Macs, PCs, and GPUs with people you trust — and run AI models none of your machines could run alone.**

Everyone brings a machine to the table; you share the compute feast. Potluck is a
dead-simple, friendly layer on top of the [exo](https://github.com/exo-explore/exo)
distributed-inference engine. exo does the hard part (splitting a model across
devices); Potluck makes it trivial to **form a group, join a shared pool, and see
what you can now run** — the parts that are still rough today.

> ⚠️ **Status: early scaffold.** This repo is a starting point, not a finished
> product. The distributed-inference core is delegated to exo. Potluck adds
> onboarding, grouping, and a dashboard. See [docs/ROADMAP.md](docs/ROADMAP.md).

---

## Why this exists

You have a couple of Macs (and maybe a gaming PC). Individually, none can hold a
large model in memory. Together, they can — if you can get them to cooperate.

The engine for that exists ([exo](https://github.com/exo-explore/exo),
[llama.cpp RPC](https://github.com/ggml-org/llama.cpp)). What's missing is the
*social* and *UX* layer:

- One-click install on each machine
- "Create a pool, invite your friends with a code" — like a multiplayer lobby
- A dashboard showing combined VRAM/RAM, who's online, and **which models you can run now**
- Sensible defaults so non-experts get a working cluster

That's Potluck.

## What it is NOT (yet)

- ❌ A paid GPU marketplace. Renting idle Macs to strangers is a *trust + payments*
  problem, not an inference problem — and splitting one request across the public
  internet is too slow to be viable (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).
  Pools are for people who trust each other (home, friends, family, a team).
- ❌ A reimplementation of exo. We wrap it.

## How it works (high level)

```
                 your laptop                 friend's Mac Studio
            ┌─────────────────────┐      ┌─────────────────────┐
            │   potlauck agent    │◄────►│    potluck agent    │
            │   └─ exo node       │ LAN/ │    └─ exo node      │
            │      (Metal)        │ TS   │       (Metal)       │
            └─────────┬───────────┘      └─────────────────────┘
                      │  OpenAI-compatible API (:52415)
                      ▼
            your apps / chat UI / scripts
```

Pool members run the Potluck agent. It starts an exo node, discovers other members
of the same pool, and exposes a single OpenAI-compatible endpoint. The model is
auto-split across whoever is online.

> **Networking reality:** model-splitting is bandwidth-bound. It's great on the same
> LAN (especially Thunderbolt / 10GbE) and over a low-latency mesh VPN like Tailscale.
> It is *not* good over the open internet for interactive chat. Potluck is built
> around that constraint, not against it.

## Quickstart

```bash
# On each machine you want in the pool:
git clone https://github.com/<you>/potluck
cd potluck
./scripts/setup.sh          # installs the potluck CLI + checks exo prerequisites

# On the first machine — create a pool:
potluck pool create my-house
#   → prints an invite code, e.g.  POT-7F3A-9K2Q

# On every other machine — join it:
potluck pool join POT-7F3A-9K2Q

# Describe your machines (auto-detect this one, add the others):
potluck device detect
potluck device add mac16  --ram 16 --backend metal
potluck device add lenovo --ram 16 --backend cpu

# Bring a machine online:
potluck up
potluck status
```

## Decide your strategy — `potluck plan`

Potluck doesn't pick *route vs split* for you. It shows you the trade-offs and
**you decide**. Ask it about any model and it ranks every option with fit + an
estimated tokens/sec:

```text
$ potluck plan llama-3.3-70b --quant q4 --link wifi

 #  STRATEGY MACHINES                FITS   ~TOK/S  NOTE
 1  split    mac32 + mac16 + lenovo   yes      2.6  splits to fit a bigger model; includes a CPU node

$ potluck plan qwen2.5-32b --quant q4

 #  STRATEGY MACHINES                FITS   ~TOK/S  NOTE
 1  route    mac32                    yes      8.4  whole model on one machine — no network cost
 2  split    mac32 + mac16            yes      8.1  splits to fit a bigger model
```

- **route** = one machine runs the whole model. Fastest, when it fits.
- **split** = pool memory to run a model too big for any one machine — slower, since
  machines take turns per token and the slowest node sets the pace.

Speeds are rough memory-bandwidth estimates meant to *compare* options, not to be
benchmarks. Try `--link ethernet` / `--link thunderbolt` to see how wiring changes it,
or `--params 120 --quant q3` to size a model that isn't in the catalog.

## Run a chosen strategy

```bash
# Route a model to one machine (fastest when it fits):
potluck up --mode route  --devices mac32 --model qwen2.5-32b --real

# Split a big model across machines (run on EACH listed machine):
potluck up --mode split --devices mac32,mac16 --model llama-3.3-70b --real
```

Without `--real` it's a dry run that just prints the exact `exo` command and what to
run where. (exo's flags vary by version — the dry run lets you eyeball them.)

## Make the estimates real — `potluck bench`

The planner ships with heuristic speeds. Measure your actual hardware and feed it back:

```bash
potluck bench qwen2.5-32b --url http://localhost:52415/v1 --calibrate mac32
#   → 8.4 tok/s → effective bandwidth ≈ 150 GB/s
#   ✓ calibrated 'mac32' — future `potluck plan` uses your real numbers
```

## Web dashboard

```bash
potluck dashboard          # → http://127.0.0.1:8777/
```

A single local page: your machines, combined memory, whether the engine is up, and
the route/split plan for any model — with dropdowns to change model/quant/link.

## Project layout

| Path | What |
|------|------|
| `src/potluck/` | The Potluck CLI + pool/group logic (the part we own) |
| `scripts/setup.sh` | Installs the `potluck` command; checks exo's prerequisites |
| `docs/ARCHITECTURE.md` | Design, the networking constraint, trust model |
| `docs/ROADMAP.md` | What's a stub vs. real, ordered build plan |

## Contributing

This is at the "scaffold" stage — the most useful contribution right now is wiring
the stubs in `src/potluck/pool.py` to the real exo runtime. See the roadmap.

## License

Apache-2.0. See [LICENSE](LICENSE).

## Credits

Stands entirely on the shoulders of [exo](https://github.com/exo-explore/exo) and
[llama.cpp](https://github.com/ggml-org/llama.cpp). Go star them.
