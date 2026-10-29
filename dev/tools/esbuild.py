"""The pinned esbuild bundler for the dashboard build (BL-231; development only, needs the internet once per machine).

Run: python3.14 dev/tools/esbuild.py -- --bundle main.js --format=iife

It downloads esbuild's native binary for this machine (`@esbuild/darwin-arm64`, `@esbuild/linux-x64` or
`@esbuild/linux-arm64`, version PINNED)
as the npm registry's tarball with urllib, checks the tarball against the SHA-256 written below, unpacks only
`package/bin/esbuild` into dev/.cache/esbuild/ and runs it with the arguments after `--`. No Node, no npm. A tarball whose
hash differs is refused and nothing is written. The build imports it: `binary()` returns the path, `run(args)` runs it.
Nothing in src/ may import or depend on this file: clark never installs anything when it runs.
To move to a new version: change PINNED and all three hashes (check each against the registry's `dist.integrity` sha512).
"""
import hashlib
import io
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

PINNED = "0.28.2"
SHA256 = {"darwin-arm64": "1980cde09749094452b20d36ff267585ccb3f72749c7bc97291cd9996ccf5a2a",
          "linux-x64": "9573bb2233aab0f9ea7647d5cca9726113cc1768de61d66b17267f4db84488f6",
          # linux-arm64, 25-10-2026: `npm pack` of the pinned version; its sha512 equals the registry's dist.integrity
          "linux-arm64": "a96dbfa41d3ef5dbd1ef22b1c10d5187be9267e86093a870f06402a7ec931596"}
MEMBER = "package/bin/esbuild"
CACHE = Path(__file__).resolve().parents[1] / ".cache" / "esbuild"


class EsbuildError(RuntimeError):
    """esbuild could not be provided: an unsupported platform, a failed download or a hash that doesn't match."""


def platform_key(system=None, machine=None):
    """The npm package suffix for this machine (`darwin-arm64`, `linux-x64` or `linux-arm64`); anything else is refused."""
    system = (system or sys.platform).lower()
    machine = (machine or platform.machine()).lower()
    if system == "darwin" and machine in ("arm64", "aarch64"):
        return "darwin-arm64"
    if system.startswith("linux") and machine in ("x86_64", "amd64"):
        return "linux-x64"
    if system.startswith("linux") and machine in ("arm64", "aarch64"):
        return "linux-arm64"
    raise EsbuildError("esbuild is pinned only for macOS on Apple silicon and Linux (x86-64 and arm64), "
                       f"not {system} {machine}")


def tarball_url(key):
    """The npm registry's tarball address for the pinned version of `@esbuild/<key>`."""
    return f"https://registry.npmjs.org/@esbuild/{key}/-/{key}-{PINNED}.tgz"


def fetch(url):
    """The bytes at `url`. Python first; if it can't verify the certificate (python.org's Python without its
    certificates), curl, which uses the system's trusted certificates. Verification stays on either way, and the hash
    is checked after (verify)."""
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            return r.read()
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" not in str(e):
            raise
    return subprocess.run(["curl", "-fsSL", "--max-time", "120", url], capture_output=True, check=True).stdout


def verify(data, key):
    """Refuse `data` unless its SHA-256 is the one pinned for `key`."""
    got = hashlib.sha256(data).hexdigest()
    if got != SHA256[key]:
        raise EsbuildError(f"@esbuild/{key} {PINNED}: SHA-256 {got} is not the pinned {SHA256[key]}; nothing was unpacked")


def target(key):
    """Where the binary for `key` lives in the cache (one folder per version and platform)."""
    return CACHE / PINNED / key / "esbuild"


def unpack(data, dest):
    """Write `package/bin/esbuild` from the tarball `data` to `dest`, executable, through a temporary file that is
    removed if anything fails, so no partial binary is ever left behind."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        try:
            member = tar.getmember(MEMBER)
        except KeyError:
            raise EsbuildError(f"the tarball has no {MEMBER}") from None
        if not member.isfile():
            raise EsbuildError(f"{MEMBER} in the tarball is not a plain file")
        body = tar.extractfile(member).read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    # A name of its own for every caller (clark: parallel test files can all fetch on a fresh machine, and a shared
    # ".part" name let one remove the file another was still writing), then one atomic move into place.
    fd, name = tempfile.mkstemp(prefix=dest.name + ".", suffix=".part", dir=str(dest.parent))
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(body)
        tmp.chmod(0o755)
        os.replace(tmp, dest)
    finally:
        if tmp.exists():
            tmp.unlink()
    return dest


def binary():
    """The path of the pinned esbuild binary for this machine, downloading and checking it on first use."""
    key = platform_key()
    dest = target(key)
    if dest.is_file() and os.access(dest, os.X_OK):
        return dest
    data = fetch(tarball_url(key))
    verify(data, key)
    return unpack(data, dest)


def run(args, **kwargs):
    """Run the pinned esbuild with `args` (a list of strings); extra keyword arguments go to subprocess.run."""
    return subprocess.run([str(binary()), *args], check=False, **kwargs)


def main(argv=None):
    """Command line: everything after an optional leading `--` is passed to esbuild; its exit code is returned."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--"]:
        args = args[1:]
    try:
        return run(args).returncode
    except EsbuildError as e:
        print(f"esbuild: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
