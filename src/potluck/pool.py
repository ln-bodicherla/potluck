"""Pool identity & membership — the part Potluck genuinely owns above exo.

A "pool" is a closed group of mutually trusting machines (your devices, your
friends, your team). Membership is gated by a shared secret encoded in a friendly
invite code, e.g.  POT-7F3A-9K2Q.

NOTE: the cryptographic gating here is intentionally minimal for the scaffold — the
invite code currently *is* the shared secret. Phase 1 (see docs/ROADMAP.md) replaces
this with a proper key derivation so discovery can be authenticated.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import asdict, dataclass

from . import config

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTUVWXYZ"  # Crockford-ish: no I/L/O to avoid confusion


def _chunk() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(4))


def new_invite_code() -> str:
    """A human-shareable code like POT-7F3A-9K2Q."""
    return f"POT-{_chunk()}-{_chunk()}"


def pool_id_from_code(code: str) -> str:
    """Deterministic pool id derived from the invite code."""
    return hashlib.sha256(code.encode()).hexdigest()[:12]


@dataclass
class Pool:
    name: str
    code: str
    pool_id: str
    role: str  # "creator" | "member"

    @classmethod
    def create(cls, name: str) -> "Pool":
        code = new_invite_code()
        return cls(name=name, code=code, pool_id=pool_id_from_code(code), role="creator")

    @classmethod
    def join(cls, code: str, name: str = "") -> "Pool":
        code = code.strip().upper()
        if not code.startswith("POT-"):
            raise ValueError(f"That doesn't look like a Potluck invite code: {code!r}")
        return cls(name=name, code=code, pool_id=pool_id_from_code(code), role="member")


def current() -> Pool | None:
    data = config.load_pool()
    if not data:
        return None
    return Pool(**data)


def persist(pool: Pool) -> None:
    config.save_pool(asdict(pool))
