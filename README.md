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
                      │  OpenAI-compatible API (:8000)
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
./scripts/setup.sh          # installs exo + the potluck CLI

# On the first machine — create a pool:
potluck pool create my-house
#   → prints an invite code, e.g.  POT-7F3A-9K2Q

# On every other machine — join it:
potluck pool join POT-7F3A-9K2Q

# On any machine — bring it online and see the combined cluster:
potluck up
potluck status
```

## Project layout

| Path | What |
|------|------|
| `src/potluck/` | The Potluck CLI + pool/group logic (the part we own) |
| `scripts/setup.sh` | Installs exo and the `potluck` command |
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
