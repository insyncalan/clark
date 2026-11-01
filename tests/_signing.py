"""A throw-away signing key for the update tests, and a way to sign a fake download as a release would be.

The key is fixed and public (the RFC 8032 section 7.1 test key), so it protects nothing: it only lets tests stand in for the
offline release key. `trust_test_key(case)` makes the app trust it for that one test and puts the shipped constant back
afterwards (nothing is trusted at import, so no test can pass because another test left a key behind); a test of the
placeholder or of another key patches `updates.RELEASE_PUBLIC_KEY` itself with `mock.patch.object`.
"""
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401  (puts vendor/ and dev/tools/ on the path)
import ed25519_sign
from clark import updates

TEST_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
TEST_PUBLIC = ed25519_sign.public_key(TEST_SEED)
OTHER_SEED = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
OTHER_PUBLIC = ed25519_sign.public_key(OTHER_SEED)


def signature_for(data, seed=TEST_SEED):
    return ed25519_sign.sign(seed, updates.SIGN_DOMAIN + data)


def sign_file(path, seed=TEST_SEED):
    """Write `<path>.sig` over the file's present bytes."""
    path = Path(path)
    sig = Path(str(path) + updates.SIGNATURE_SUFFIX)
    sig.write_bytes(signature_for(path.read_bytes(), seed))
    return sig


def trust_test_key(case):
    """Trust the test key for this one test; the shipped constant is put back when the test ends."""
    patcher = mock.patch.object(updates, "RELEASE_PUBLIC_KEY", TEST_PUBLIC)
    patcher.start()
    case.addCleanup(patcher.stop)
