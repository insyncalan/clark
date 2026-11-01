"""Ed25519 signing (RFC 8032, section 5.1.6) for release signing. Development only: the app never signs anything.

This module lives in dev/tools on purpose and must never be importable from src/clark (a test checks that nothing in src/
or vendor/ names it). It borrows the curve arithmetic from the verify-only library in vendor/ed25519_verify.
Pure Python, standard library only. Not constant time: use it offline, on your own machine, for a release.
"""
import hashlib
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2] / "vendor"))
import ed25519_verify as ev  # noqa: E402

SEED_BYTES = 32


def _expand(seed):
    if not isinstance(seed, (bytes, bytearray)) or len(seed) != SEED_BYTES:
        raise ValueError("a private seed is exactly 32 bytes")
    h = hashlib.sha512(bytes(seed)).digest()
    a = bytearray(h[:32])
    a[0] &= 248
    a[31] &= 127
    a[31] |= 64
    return int.from_bytes(a, "little"), h[32:]


def public_key(seed):
    """The 32-byte public key for a 32-byte private seed."""
    a, _ = _expand(seed)
    return ev.encode(ev.mul(a, ev.BASE))


def sign(seed, message):
    """The 64-byte signature of `message` under `seed`."""
    a, prefix = _expand(seed)
    key = ev.encode(ev.mul(a, ev.BASE))
    r = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % ev.L
    r_bytes = ev.encode(ev.mul(r, ev.BASE))
    k = ev.challenge(r_bytes, key, message)
    s = (r + k * a) % ev.L
    return r_bytes + s.to_bytes(32, "little")


def new_seed():
    return os.urandom(SEED_BYTES)
