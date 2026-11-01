"""Sign a clark release file, offline (run by the person who owns the release key; development only).

  python3 dev/tools/sign_release.py keygen <key file> [--passphrase]   make a new private key file; prints ONLY the public key
  python3 dev/tools/sign_release.py sign <key file> <clark-X.Y.Z-mac.zip>   write clark-X.Y.Z-mac.zip.sig beside the file
  python3 dev/tools/sign_release.py public <key file>                  print the public key of an existing key file

The signature is Ed25519 over updates.SIGN_DOMAIN + the file's bytes, and is checked again here with the app's own verifier
before it is written. Attach the .sig to the release beside the zip. The private key is never printed. Standard library only.

Key file: the 32-byte private seed, either raw (the file must be readable by you alone, mode 0600) or protected by a passphrase
(scrypt-derived mask and a keyed check, asked for at the prompt). A key file inside this repository is refused, whatever its name,
and so is one reached through a link that leads into it: keep the key offline, on a drive that is not synced or committed.

Key loss or compromise (runbook; nothing here is automatic):
- Lost key, nobody else has it: no old copy of clark can ever be updated by a release signed with a new key, because each copy
  trusts only the public key built into it (RELEASE_PUBLIC_KEY in src/clark/updates.py).
- Compromised key (or one that may have been): treat every .sig made with it as worthless. Make a new key with `keygen`, put its
  public key in RELEASE_PUBLIC_KEY, and ship that build as a MANUAL INSTALL release, never as an update: people download it from
  the releases page and replace the clark folder by hand.
- Put the new public key's SHA-256 digest (hashlib.sha256(public key bytes).hexdigest()) in that release's notes, so anyone can
  confirm the key their copy now trusts. Say plainly in the notes that the old key is retired and why.
- From then on sign with the new key only. Delete or destroy the old key file. Copies that were never moved to the manual install
  keep trusting the old key and refuse the new signatures: that is the safe failure, and the notes should say so.
"""
import getpass
import hashlib
import hmac
import os
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(HERE), str(REPO / "src"), str(REPO / "vendor")]
import ed25519_sign  # noqa: E402
import ed25519_verify  # noqa: E402

MAGIC = b"CLARK-KEY-1\n"
SCRYPT = {"n": 2 ** 17, "r": 8, "p": 1, "maxmem": 256 * 1024 * 1024, "dklen": 64}
# The domain value is imported from src/clark/updates.py on purpose, so the signer and the verifier can never drift apart.
from clark import updates  # noqa: E402


class Refused(Exception):
    pass


def _inside_repo(path):
    here = Path(os.path.realpath(path))
    root = Path(os.path.realpath(REPO))
    return here == root or root in here.parents


def check_key_path(path):
    """Refuse a key file inside the repository (also through a link)."""
    parent = Path(os.path.realpath(Path(path).parent))
    if _inside_repo(path) or _inside_repo(parent):
        raise Refused("that key file is inside the clark repository; keep the private key outside it")


def _mask(passphrase, salt):
    key = hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, **SCRYPT)
    return key[:32], key[32:]


def protect(seed, passphrase, salt=None):
    salt = salt or os.urandom(16)
    mask, mac_key = _mask(passphrase, salt)
    body = bytes(a ^ b for a, b in zip(seed, mask))
    return MAGIC + salt + body + hmac.new(mac_key, salt + body, "sha256").digest()


def unprotect(blob, passphrase):
    raw = blob[len(MAGIC):]
    if len(raw) != 16 + 32 + 32:
        raise Refused("that key file is damaged")
    salt, body, tag = raw[:16], raw[16:48], raw[48:]
    mask, mac_key = _mask(passphrase, salt)
    if not hmac.compare_digest(hmac.new(mac_key, salt + body, "sha256").digest(), tag):
        raise Refused("wrong passphrase, or the key file is damaged")
    return bytes(a ^ b for a, b in zip(body, mask))


def load_seed(path, ask=getpass.getpass):
    check_key_path(path)
    st = os.stat(path)
    if not stat.S_ISREG(st.st_mode):
        raise Refused("the key file is not a regular file")
    blob = Path(path).read_bytes()
    if blob.startswith(MAGIC):
        return unprotect(blob, ask("Key passphrase: "))
    if len(blob) != 32:
        raise Refused("the key file must be a 32-byte seed or a protected key file")
    if st.st_mode & 0o077:
        raise Refused("the key file can be read by other people; run: chmod 600 <key file>")
    return blob


def keygen(path, passphrase=None):
    """Write a new key file (never over an existing one, mode 0600); the public key bytes."""
    check_key_path(path)
    seed = ed25519_sign.new_seed()
    blob = protect(seed, passphrase) if passphrase else seed
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(blob)
    return ed25519_sign.public_key(seed)


def sign_zip(seed, zip_path):
    """Write `<zip>.sig`, after checking it verifies; the signature file's path."""
    data = Path(zip_path).read_bytes()
    sig = ed25519_sign.sign(seed, updates.SIGN_DOMAIN + data)
    if not ed25519_verify.verify(ed25519_sign.public_key(seed), updates.SIGN_DOMAIN + data, sig):
        raise Refused("the new signature did not verify; nothing was written")
    out = Path(str(zip_path) + updates.SIGNATURE_SUFFIX)
    out.write_bytes(sig)
    return out


def main(argv, ask=getpass.getpass):
    try:
        if len(argv) >= 2 and argv[0] == "keygen" and (len(argv) == 2 or argv[2:] == ["--passphrase"]):
            phrase = None
            if len(argv) == 3:
                phrase = ask("New passphrase: ")
                if not phrase or phrase != ask("Again: "):
                    raise Refused("the passphrases are empty or differ")
            print("public key:", keygen(argv[1], phrase).hex())
            return 0
        if len(argv) == 2 and argv[0] == "public":
            print("public key:", ed25519_sign.public_key(load_seed(argv[1], ask)).hex())
            return 0
        if len(argv) == 3 and argv[0] == "sign":
            out = sign_zip(load_seed(argv[1], ask), argv[2])
            print("wrote", out)
            return 0
    except (Refused, OSError) as e:
        print("Refused:", e if isinstance(e, Refused) else e.strerror or type(e).__name__)
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
