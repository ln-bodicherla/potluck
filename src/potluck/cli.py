"""The `potluck` command-line interface.

Stdlib-only so it runs with zero dependencies. Commands:

    potluck pool create <name>      create a pool, print an invite code
    potluck pool join <code>        join an existing pool

    potluck device detect           add THIS machine (auto-detected)
    potluck device add <name> ...   register a peer machine's specs
    potluck device ls               list the pool's machines
    potluck device rm <name>        remove a machine

    potluck plan <model>            rank route/split strategies with fit + speed
    potluck up                      bring this machine online in its pool
    potluck status                  show pool + cluster state
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict

from . import __version__, config, engine, models, planner, pool
from .devices import Device, detect_local


# ---- device registry helpers ------------------------------------------------

def _load_devices() -> list[Device]:
    return [Device(**d) for d in config.load_devices()]


def _save_devices(devs: list[Device]) -> None:
    config.save_devices([asdict(d) for d in devs])


def _upsert_device(dev: Device) -> None:
    devs = [d for d in _load_devices() if d.name != dev.name]
    devs.append(dev)
    _save_devices(devs)


# ---- pool -------------------------------------------------------------------

def cmd_pool_create(args: argparse.Namespace) -> None:
    p = pool.Pool.create(args.name)
    pool.persist(p)
    print(f"🍲 Created pool '{p.name}'  (id {p.pool_id})\n")
    print(f"   Invite code:  {p.code}\n")
    print("   Share that code with the people/machines you want in the pool.")
    print("   On each of them, run:  potluck pool join " + p.code)


def cmd_pool_join(args: argparse.Namespace) -> None:
    try:
        p = pool.Pool.join(args.code, name=args.name or "")
    except ValueError as e:
        sys.exit(str(e))
    pool.persist(p)
    print(f"🍲 Joined pool {p.pool_id} with code {p.code}.")
    print("   Run `potluck device detect` then `potluck up`.")


# ---- devices ----------------------------------------------------------------

def cmd_device_detect(args: argparse.Namespace) -> None:
    dev = detect_local(name=args.name or "")
    _upsert_device(dev)
    print(f"Registered this machine: {dev.label()}")
    if dev.backend == "cpu":
        print("   (no GPU detected — this machine will be the slow link in any split)")


def cmd_device_add(args: argparse.Namespace) -> None:
    if args.backend not in ("metal", "cuda", "cpu"):
        sys.exit("backend must be one of: metal, cuda, cpu")
    dev = Device(name=args.name, ram_gb=args.ram, backend=args.backend,
                 bandwidth_gbps=args.bandwidth, notes="manually added")
    _upsert_device(dev)
    print(f"Registered peer: {dev.label()}  (usable ≈ {dev.usable_gb():.1f} GB)")


def cmd_device_ls(args: argparse.Namespace) -> None:
    devs = _load_devices()
    if not devs:
        print("No machines registered. Add this one with `potluck device detect`,")
        print("and peers with e.g. `potluck device add mac16 --ram 16 --backend metal`.")
        return
    total = sum(d.usable_gb() for d in devs)
    print(f"{'NAME':<14}{'RAM':>6}{'BACKEND':>9}{'USABLE':>9}")
    for d in devs:
        print(f"{d.name:<14}{d.ram_gb:>5.0f}G{d.backend:>9}{d.usable_gb():>7.1f}G")
    print(f"{'—'*38}\n{'pool total usable':<29}{total:>7.1f}G")


def cmd_device_rm(args: argparse.Namespace) -> None:
    devs = [d for d in _load_devices() if d.name != args.name]
    _save_devices(devs)
    print(f"Removed {args.name}.")


# ---- plan -------------------------------------------------------------------

def cmd_plan(args: argparse.Namespace) -> None:
    devs = _load_devices()
    if not devs:
        sys.exit("No machines registered yet. Run `potluck device detect` and add peers first.")
    try:
        model = models.resolve(args.model, params=args.params)
    except ValueError as e:
        sys.exit(str(e))

    need = models.footprint_gb(model, args.quant, args.ctx)
    strategies = planner.plan(devs, model, quant=args.quant, link=args.link, ctx_tokens=args.ctx)

    print(f"Model:  {model.name}  @ {args.quant}   (~{need:.1f} GB needed, ctx {args.ctx})")
    print(f"Link:   {args.link}   |   pool: {' + '.join(d.label() for d in devs)}\n")
    print(f"{'#':>2}  {'STRATEGY':<9}{'MACHINES':<26}{'FITS':>5}{'~TOK/S':>9}  NOTE")
    for i, s in enumerate(strategies, 1):
        fits = "yes" if s.fits else "NO"
        tps = f"{s.tokens_per_sec:.1f}" if s.fits else "—"
        print(f"{i:>2}  {s.kind:<9}{s.device_label()[:24]:<26}{fits:>5}{tps:>9}  {s.note}")
    print("\nSpeeds are rough estimates (memory-bandwidth model) to compare options — not benchmarks.")
    print("You decide: route = fastest if it fits one machine; split = bigger models, slower.")


# ---- up / status ------------------------------------------------------------

def _require_pool() -> pool.Pool:
    p = pool.current()
    if p is None:
        sys.exit("This machine isn't in a pool yet. Run `potluck pool create <name>` "
                 "or `potluck pool join <code>`.")
    return p


def cmd_up(args: argparse.Namespace) -> None:
    p = _require_pool()
    if not engine.is_exo_installed():
        print("⚠️  exo isn't installed. Run ./scripts/setup.sh first.\n")
    plan = engine.up(p.pool_id, api_port=args.port, dry_run=not args.real)
    mode = "LAUNCHING" if args.real else "DRY RUN (pass --real to actually start)"
    print(f"[{mode}] pool '{p.name}' ({p.pool_id})")
    print("   command:  " + " ".join(plan.command))
    print("   API:      " + plan.api_url + "  (OpenAI-compatible)")


def cmd_status(args: argparse.Namespace) -> None:
    p = pool.current()
    if p is None:
        print("Not in a pool. Run `potluck pool create <name>` or `pool join <code>`.")
        return
    print(f"Pool:    {p.name or '(unnamed)'}  ({p.pool_id})")
    print(f"Role:    {p.role}")
    print(f"exo:     {'installed' if engine.is_exo_installed() else 'NOT installed'}")
    devs = _load_devices()
    print(f"Devices: {len(devs)} registered ({sum(d.usable_gb() for d in devs):.0f}G usable)")
    topo = engine.topology()
    print(f"Peers:   {len(topo.get('peers', []))} online")
    if topo.get("note"):
        print(f"         ({topo['note']})")


# ---- parser -----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="potluck", description="Pool machines, run big models together.")
    parser.add_argument("--version", action="version", version=f"potluck {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    pool_p = sub.add_parser("pool", help="manage pool membership")
    pool_sub = pool_p.add_subparsers(dest="pool_command", required=True)
    create = pool_sub.add_parser("create", help="create a new pool")
    create.add_argument("name")
    create.set_defaults(func=cmd_pool_create)
    join = pool_sub.add_parser("join", help="join an existing pool by invite code")
    join.add_argument("code")
    join.add_argument("--name", default="", help="local label for the pool")
    join.set_defaults(func=cmd_pool_join)

    dev_p = sub.add_parser("device", help="manage the pool's machines")
    dev_sub = dev_p.add_subparsers(dest="device_command", required=True)
    detect = dev_sub.add_parser("detect", help="auto-detect and register this machine")
    detect.add_argument("--name", default="", help="override the machine's name")
    detect.set_defaults(func=cmd_device_detect)
    add = dev_sub.add_parser("add", help="register a peer machine's specs")
    add.add_argument("name")
    add.add_argument("--ram", type=float, required=True, help="RAM in GB")
    add.add_argument("--backend", default="metal", help="metal | cuda | cpu")
    add.add_argument("--bandwidth", type=float, default=None, help="override mem bandwidth GB/s")
    add.set_defaults(func=cmd_device_add)
    ls = dev_sub.add_parser("ls", help="list registered machines")
    ls.set_defaults(func=cmd_device_ls)
    rm = dev_sub.add_parser("rm", help="remove a machine")
    rm.add_argument("name")
    rm.set_defaults(func=cmd_device_rm)

    plan_p = sub.add_parser("plan", help="rank route/split strategies for a model")
    plan_p.add_argument("model", help="catalog name (e.g. llama-3.3-70b) or any label with --params")
    plan_p.add_argument("--params", type=float, default=None, help="model size in B params for custom models")
    plan_p.add_argument("--quant", default="q4", help="q2 q3 q4 q5 q6 q8 fp16")
    plan_p.add_argument("--link", default="wifi", help="wifi | ethernet | thunderbolt")
    plan_p.add_argument("--ctx", type=int, default=4096, help="context tokens")
    plan_p.set_defaults(func=cmd_plan)

    up = sub.add_parser("up", help="bring this machine online in its pool")
    up.add_argument("--port", type=int, default=8000)
    up.add_argument("--real", action="store_true", help="actually launch exo (default is a dry run)")
    up.set_defaults(func=cmd_up)

    status = sub.add_parser("status", help="show pool and cluster state")
    status.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
