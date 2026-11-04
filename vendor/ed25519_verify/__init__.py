"""Ed25519 signature verification (RFC 8032, section 5.1.7), verify only. Standard library only.

Written for clark from the RFC and placed in the public domain (CC0). It checks strictly, as a signed update needs:
- a signature is exactly 64 bytes and a public key exactly 32;
- S must be below the group order L (no second signature for the same message), so an S + L copy is refused;
- the encodings of R and of the public key must be canonical: y below p, and no "negative zero" x;
- R and the public key must not be points of small order (which would let a signature pass for many keys or messages);
- an all-zero signature is refused.
The check is the cofactorless one, [S]B == R + [k]A. It is slow (pure Python, a few milliseconds) and not constant time,
which does not matter: it handles only public data. There is no signing here (see dev/tools/ed25519_sign.py).
"""
import hashlib

__all__ = ["verify", "SIGNATURE_BYTES", "KEY_BYTES"]

SIGNATURE_BYTES = 64
KEY_BYTES = 32

P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
D = -121665 * pow(121666, P - 2, P) % P
SQRT_M1 = pow(2, (P - 1) // 4, P)

# Points are (X, Y, Z, T) in extended coordinates, x = X/Z, y = Y/Z, T = XY/Z.
IDENTITY = (0, 1, 1, 0)


def _add_ed(a, b):
    """Unified addition on the twisted Edwards curve (a = -1), extended coordinates."""
    x1, y1, z1, t1 = a
    x2, y2, z2, t2 = b
    A = (y1 - x1) * (y2 - x2) % P
    B = (y1 + x1) * (y2 + x2) % P
    C = t1 * 2 * D * t2 % P
    E = z1 * 2 * z2 % P
    F, G, H, I = B - A, E - C, E + C, B + A
    return (F * G % P, H * I % P, G * H % P, F * I % P)


def mul(s, point):
    """s * point by double-and-add."""
    q = IDENTITY
    while s > 0:
        if s & 1:
            q = _add_ed(q, point)
        point = _add_ed(point, point)
        s >>= 1
    return q


def equal(a, b):
    """True when two points are the same point."""
    return (a[0] * b[2] - b[0] * a[2]) % P == 0 and (a[1] * b[2] - b[1] * a[2]) % P == 0


def small_order(point):
    """True for a point of order 1, 2, 4 or 8 (eight times it is the identity)."""
    return equal(mul(8, point), IDENTITY)


def _recover_x(y, sign):
    if y >= P:
        return None
    x2 = (y * y - 1) * pow(D * y * y + 1, P - 2, P) % P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P != 0:
        x = x * SQRT_M1 % P
    if (x * x - x2) % P != 0:
        return None
    if (x & 1) != sign:
        x = P - x
    return x


def decode(s):
    """The point a 32-byte encoding names, or None when the encoding is wrong or not canonical."""
    if not isinstance(s, (bytes, bytearray)) or len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % P)


def encode(point):
    zinv = pow(point[2], P - 2, P)
    x, y = point[0] * zinv % P, point[1] * zinv % P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


_GY = 4 * pow(5, P - 2, P) % P
_GX = _recover_x(_GY, 0)
BASE = (_GX, _GY, 1, _GX * _GY % P)


def challenge(r_bytes, key, message):
    return int.from_bytes(hashlib.sha512(r_bytes + key + message).digest(), "little") % L


def verify(public_key, message, signature):
    """True only for a valid, strictly checked signature. Anything wrong, of any kind, is False; it never raises for bad input."""
    try:
        if not isinstance(public_key, (bytes, bytearray)) or not isinstance(signature, (bytes, bytearray)):
            return False
        public_key, signature, message = bytes(public_key), bytes(signature), bytes(message)
        if len(public_key) != KEY_BYTES or len(signature) != SIGNATURE_BYTES or signature == bytes(SIGNATURE_BYTES):
            return False
        a_point = decode(public_key)
        r_bytes = signature[:32]
        r_point = decode(r_bytes)
        s = int.from_bytes(signature[32:], "little")
        if a_point is None or r_point is None or s >= L:
            return False
        if small_order(a_point) or small_order(r_point):
            return False
        k = challenge(r_bytes, public_key, message)
        return equal(mul(s, BASE), _add_ed(r_point, mul(k, a_point)))
    except Exception:
        return False
