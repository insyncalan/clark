"""Sign a clark release file, offline (run by the person who owns the release key; development only).

  python3 dev/tools/sign_release.py keygen [name]              make a new key straight in your Mac Keychain; prints ONLY the public key
  python3 dev/tools/sign_release.py sign <clark-X.Y.Z-mac.zip> [name]   write clark-X.Y.Z-mac.zip.sig beside the file
  python3 dev/tools/sign_release.py public [name]              print the public key of the key already in the Keychain

The signature is Ed25519 over updates.SIGN_DOMAIN + the file's bytes, and is checked again here with the app's own verifier
before it is written. Attach the .sig to the release beside the zip. The private key is never printed. Standard library only.

Where the key lives: only in the Mac Keychain, as a generic password item (service `clark-release-signing`, account `name`,
default `release`), holding the 32-byte seed as 64 hex characters. It is never written to a file, by this tool or by anything
else it starts. `keygen` hands the seed to `security` on its standard input (`security -i`, which reads its commands there), so
the seed is never in a command line where `ps` could show it; `man security` offers only `-w` (the password as an argument) or
`-X` (hex as an argument) for a value given up front, and both would show it. `sign` and `public` read the seed back with
`security find-generic-password -w`, so macOS asks before it gives it out. Every call to `security` goes through the one function
`run_security`; the tests replace it with an in-memory fake and never reach the real Keychain.

Key loss or compromise (runbook; nothing here is automatic):
- Lost key, nobody else has it: no old copy of clark can ever be updated by a release signed with a new key, because each copy
  trusts only the public key built into it (RELEASE_PUBLIC_KEY in src/clark/updates.py).
- Compromised key (or one that may have been): treat every .sig made with it as worthless. Make a new key with `keygen` under a
  new name, put its public key in RELEASE_PUBLIC_KEY, and ship that build as a MANUAL INSTALL release, never as an update: people
  download it from the releases page and replace the clark folder by hand.
- Put the new public key's SHA-256 digest (hashlib.sha256(public key bytes).hexdigest()) in that release's notes, so anyone can
  confirm the key their copy now trusts. Say plainly in the notes that the old key is retired and why.
- From then on sign with the new key only. Delete the old Keychain item in Keychain Access. Copies that were never moved to the
  manual install keep trusting the old key and refuse the new signatures: that is the safe failure, and the notes should say so.
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(HERE), str(REPO / "src"), str(REPO / "vendor")]
import ed25519_sign  # noqa: E402
import ed25519_verify  # noqa: E402

# The domain value is imported from src/clark/updates.py on purpose, so the signer and the verifier can never drift apart.
from clark import updates  # noqa: E402

SERVICE = "clark-release-signing"
DEFAULT_NAME = "release"
SECURITY = "/usr/bin/security"
NAME_RE = re.compile(r"[A-Za-z0-9._-]{1,40}\Z")
HEX_RE = re.compile(r"[0-9a-f]{64}\Z")


class Refused(Exception):
    pass


def run_security(args, stdin=None):
    """The ONE place the Keychain tool is run: (exit code, standard output). Tests replace this; nothing else calls `security`."""
    done = subprocess.run([SECURITY] + list(args), input=stdin, capture_output=True, text=True, timeout=300)
    return done.returncode, done.stdout


def _name(name):
    if not NAME_RE.match(name or ""):
        raise Refused("the key name may use only letters, digits, dot, dash and underscore (up to 40)")
    return name


def keygen(name=DEFAULT_NAME):
    """Make a new seed and put it straight in the Keychain (never over an existing item); the public key bytes."""
    name = _name(name)
    code, _ = run_security(["find-generic-password", "-s", SERVICE, "-a", name])
    if code == 0:
        raise Refused("a key called %r is already in the Keychain; use another name, or delete that item in Keychain Access first" % name)
    seed = ed25519_sign.new_seed()
    # `security -i` reads its commands from stdin, so the seed is in a pipe and never in any argv. No -U: nothing is overwritten.
    code, _ = run_security(["-i"], stdin="add-generic-password -s %s -a %s -w %s\n" % (SERVICE, name, seed.hex()))
    if code != 0:
        raise Refused("the Keychain would not store the key (exit %d); nothing was made" % code)
    return ed25519_sign.public_key(seed)


def load_seed(name=DEFAULT_NAME):
    """The seed from the Keychain; macOS asks before it is given out."""
    code, out = run_security(["find-generic-password", "-s", SERVICE, "-a", _name(name), "-w"])
    text = out.strip()
    if code != 0 or not HEX_RE.match(text):
        raise Refused("no usable signing key called %r in the Keychain (run keygen first, or allow access when macOS asks)" % name)
    return bytes.fromhex(text)


def sign_zip(seed, zip_path):
    """Write `<zip>.sig`, after checking it verifies; the signature file's path."""
    data = Path(zip_path).read_bytes()
    sig = ed25519_sign.sign(seed, updates.SIGN_DOMAIN + data)
    if not ed25519_verify.verify(ed25519_sign.public_key(seed), updates.SIGN_DOMAIN + data, sig):
        raise Refused("the new signature did not verify; nothing was written")
    out = Path(str(zip_path) + updates.SIGNATURE_SUFFIX)
    out.write_bytes(sig)
    return out


def main(argv):
    try:
        if argv[:1] == ["keygen"] and len(argv) <= 2:
            print("public key:", keygen(*argv[1:]).hex())
            return 0
        if argv[:1] == ["public"] and len(argv) <= 2:
            print("public key:", ed25519_sign.public_key(load_seed(*argv[1:])).hex())
            return 0
        if argv[:1] == ["sign"] and 2 <= len(argv) <= 3:
            out = sign_zip(load_seed(*argv[2:]), argv[1])
            print("wrote", out)
            return 0
    except (Refused, OSError, subprocess.SubprocessError) as e:
        print("Refused:", e if isinstance(e, Refused) else getattr(e, "strerror", None) or type(e).__name__)
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
