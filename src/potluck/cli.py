"""The `potluck` command-line interface.

Stdlib-only so it runs with zero dependencies. Commands:

    potluck pool create <name>     create a pool, print an invite code
    potluck pool join <code>       join an existing pool
    potluck up                     bring this machine online in its pool
    potluck status                 show pool + cluster state
    potluck models                 (stub) models the pool can run
"""

from __future__ import annotations

import argparse
import sys

from . import __version__, engine, pool


def _require_pool() -> pool.Pool:
    p = pool.current()
    if p is None:
        sys.exit("This machine isn't in a pool yet. Run `potluck pool create <name>` "
                 "or `potluck pool join <code>`.")
    return p


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
    print("   Run `potluck up` to bring this machine online.")


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
    topo = engine.topology()
    peers = topo.get("peers", [])
    print(f"Peers:   {len(peers)} online")
    if topo.get("note"):
        print(f"         ({topo['note']})")


def cmd_models(args: argparse.Namespace) -> None:
    _require_pool()
    print("Listing runnable models needs the engine adapter (ROADMAP Phase 4).")
    print("It will combine online peers' RAM/VRAM and show what fits.")


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

    up = sub.add_parser("up", help="bring this machine online in its pool")
    up.add_argument("--port", type=int, default=8000)
    up.add_argument("--real", action="store_true", help="actually launch exo (default is a dry run)")
    up.set_defaults(func=cmd_up)

    status = sub.add_parser("status", help="show pool and cluster state")
    status.set_defaults(func=cmd_status)

    models = sub.add_parser("models", help="list models the pool can run")
    models.set_defaults(func=cmd_models)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
