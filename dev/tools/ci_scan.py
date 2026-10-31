"""The CI scan (0.2.1): what a pull request or a push to the public copy changes, checked before it merges.

    python3 dev/tools/ci_scan.py --repo PR_CHECKOUT --base BASE_SHA [--head HEAD] [--fork]

Reuses dev/tools/publish_public.py (the same secret patterns, listed-word guard, size limit, file-mode and path rules that
guard publishing), over only the files `BASE..HEAD` changes. It reads a git checkout and nothing else: no network, no secrets,
no write. It prints counts, kinds and file numbers, never a matched word or secret; a path is printed only if it is itself
clear (a path that holds a listed word is shown as its number alone). Exit 0: pass. Exit 1: refused. Exit 2: could not scan
(a failure to scan is a refusal, never a pass).

In CI this file is run from the BASE branch's checkout, so a pull request cannot change THIS FILE's rules for its own run.
That is not the whole defence: a pull request can also edit the workflow that calls it. Branch rules must therefore require a
maintainer's review for changes to .github/** (CODEOWNERS or a ruleset), and the check "Scan" must be required.
`--fork` (a pull request from a fork) turns changes to the workflows or to the scan itself, deleted or moved files included,
from a notice into a refusal. CI_SCAN_IDENTITY=warn turns the commit-address rule into a notice.
"""
import argparse
import os
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import publish_public as pp  # noqa: E402

# Signatures no text file starts with; and ones plain text can start with ("MZ ratio"), so they count only with a NUL byte.
MAGIC = ((b"PK\x03\x04", "a zip or Office file"), (b"PK\x05\x06", "a zip"), (b"\x1f\x8b", "a gzip file"),
         (b"7z\xbc\xaf", "a 7z archive"), (b"Rar!\x1a\x07", "a RAR archive"), (b"\x7fELF", "a program"),
         (b"\xcf\xfa\xed\xfe", "a program"), (b"\xca\xfe\xba\xbe", "a program"), (b"\xfe\xed\xfa", "a program"),
         (b"%PDF", "a PDF"), (b"\xfd7zXZ", "an xz file")) + tuple((b"BZh%d1AY&SY" % n, "a bzip2 file") for n in range(1, 10))
MAGIC_WITH_NUL = ((b"MZ", "a program"), (b"BZh", "a bzip2 file"), (b"Rar!", "a RAR archive"))
ARCHIVE_SUFFIXES = (".zip", ".gz", ".tgz", ".tar", ".bz2", ".xz", ".7z", ".rar", ".jar", ".whl", ".egg", ".docx", ".xlsx",
                    ".pptx", ".exe", ".dll", ".so", ".dylib", ".pyc", ".pyd", ".class", ".bin", ".dmg", ".pkg", ".app")
PROTECTED = (".github/", "dev/tools/ci_scan.py", "dev/tools/publish_public.py", "tests/test_ci_scan.py", "tests/test_workflow.py",
             "tests/test_no_real_names.py", "tests/test_publish_public.py")       # the rules a change could loosen
NOREPLY = re.compile(r"^(?:\d+\+)?[A-Za-z0-9-]+@users\.noreply\.github\.com$|^noreply@github\.com$")
TRAILER_OK = re.compile(NOREPLY.pattern + r"|^noreply@anthropic\.com$")      # also fine in a message: the Co-Authored-By trailer
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RISKY_CONTEXT = re.compile(r"\$\{\{[^}]*(?:github\.head_ref|\.title|\.body|\.head\.ref|\.head\.label|\.message|\.email|"
                           r"\.author\.name|\.name\b[^}]*pull_request|\.ref\b)[^}]*\}\}")
SAFE_LINE = re.compile(r"^\s*(?:-\s+)?(?:if|name|run-name|group|[A-Z][A-Z0-9_]*):")        # an expression or an env value, never shell
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)")


# A picture or font is allowed only if it is well formed for its own extension and ENDS where its format says it ends, so a
# picture cannot carry an archive or a program after its end. (A comment segment inside it is still read by the content scans.)
PNG_TEXT_CHUNKS = (b"tEXt", b"zTXt", b"iTXt")     # a picture's own text: it may hold compressed bytes of any kind


def _png_ok(d):
    i = 8
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        return False
    while i + 12 <= len(d):
        size, kind = int.from_bytes(d[i:i + 4], "big"), d[i + 4:i + 8]
        if kind in PNG_TEXT_CHUNKS:               # anything could be hidden in here, so a picture carrying one is refused
            return False
        i += 12 + size
        if kind == b"IEND":
            return size == 0 and i == len(d)
    return False


_JPEG_IN_DATA = frozenset([0x00, 0xFF] + list(range(0xD0, 0xD8)))     # after FF, inside image data: a stuffed 0, a fill, a restart


def _jpeg_ok(d):
    i, n = 2, len(d)
    if d[:3] != b"\xff\xd8\xff":
        return False
    while i + 2 <= n:
        if d[i] != 0xFF:
            return False
        marker = d[i + 1]
        if marker == 0xFF:                                  # a fill byte
            i += 1
        elif marker == 0xD9:                                # the end of the image: nothing may follow
            return i + 2 == n
        elif marker == 0x01 or 0xD0 <= marker <= 0xD8:      # a marker with no length
            i += 2
        elif i + 4 > n:
            return False
        else:
            i += 2 + int.from_bytes(d[i + 2:i + 4], "big")
            if marker == 0xDA:                              # the image data runs to the next real marker
                while i + 1 < n and not (d[i] == 0xFF and d[i + 1] not in _JPEG_IN_DATA):
                    i += 1
    return False


def _gif_blocks(d, i):
    """The index after the data sub-blocks that start at i, or -1."""
    while i < len(d):
        size = d[i]
        i += 1 + size
        if size == 0:
            return i
    return -1


def _gif_ok(d):
    if d[:6] not in (b"GIF87a", b"GIF89a") or len(d) < 14:
        return False
    i = 13 + (3 << ((d[10] & 7) + 1) if d[10] & 0x80 else 0)
    while 0 <= i < len(d):
        if d[i] == 0x3B:                                    # the trailer: nothing may follow
            return i + 1 == len(d)
        if d[i] == 0x21:
            i = _gif_blocks(d, i + 2)
        elif d[i] == 0x2C and i + 10 <= len(d):
            i = _gif_blocks(d, i + 11 + (3 << ((d[i + 9] & 7) + 1) if d[i + 9] & 0x80 else 0))
        else:
            return False
    return False


MAX_PADDING = 3                                   # a format may round its length up; more than this is data, not padding


def _ends_at(d, length):
    """The file ends at `length`, give or take a few zero bytes of padding (which some writers add)."""
    return length <= len(d) <= length + MAX_PADDING and not d[length:].strip(b"\0")


def _webp_ok(d):
    return d[:4] == b"RIFF" and d[8:12] == b"WEBP" and _ends_at(d, int.from_bytes(d[4:8], "little") + 8)


def _woff_ok(magic):
    return lambda d: d[:4] == magic and len(d) >= 12 and _ends_at(d, int.from_bytes(d[8:12], "big"))


def _ico_ok(d):
    count = int.from_bytes(d[4:6], "little")
    if d[:4] != b"\0\0\1\0" or count == 0 or 6 + 16 * count > len(d):
        return False
    ends = [int.from_bytes(d[18 + 16 * k:22 + 16 * k], "little") + int.from_bytes(d[14 + 16 * k:18 + 16 * k], "little")
            for k in range(count)]                      # each entry: its offset plus its size
    return max(ends) == len(d)


PICTURES = {".png": _png_ok, ".jpg": _jpeg_ok, ".jpeg": _jpeg_ok, ".gif": _gif_ok, ".webp": _webp_ok, ".ico": _ico_ok,
            ".woff": _woff_ok(b"wOFF"), ".woff2": _woff_ok(b"wOF2")}     # edit here, in a reviewed change


class Scan:
    def __init__(self, repo, base, head, fork):
        self.repo, self.base, self.head, self.fork = repo, base, head, fork
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
        self.report = pp.Report()
        self.entries, self.blobs, self.deleted = [], [], []

    def git(self, *args):
        proc = pp.git(["-C", self.repo] + list(args), env=self.env)
        if proc.returncode != 0:
            raise RuntimeError("git %s failed" % args[0])
        return proc.stdout

    def load(self):
        changed, i = [], 0
        if self.base == "ALL":                      # a baseline of the whole tree, for a maintainer: --base ALL
            changed = [(e.mode, e.sha, e.path) for e in pp.list_tree(self.repo, self.head, self.env)]
            raw = []
        else:
            raw = self.git("diff", "--raw", "-z", "--no-renames", "--no-abbrev", self.base, self.head).split(b"\0")
        while i + 1 < len(raw) and raw[i].startswith(b":"):
            meta, path = raw[i].split(), raw[i + 1].decode("utf-8", "surrogateescape")
            i += 2
            if len(meta) < 5:
                raise RuntimeError("git diff output not understood")
            if meta[4].startswith(b"D"):
                self.deleted.append(path)                   # a moved file shows as a deletion and an addition
            else:
                changed.append((meta[1].decode(), meta[3].decode(), path))
        if self.base != "ALL" and (i != len(raw) - 1 or raw[-1] != b""):
            raise RuntimeError("git diff output not fully read")
        changed.sort(key=lambda c: c[2])
        shas = [c[1] for c in changed]
        sizes = {}
        for e in pp.list_tree(self.repo, self.head, self.env):
            sizes[e.path] = e.size
        self.entries = [pp.Entry(n, mode, sha, sizes.get(path, -1), path) for n, (mode, sha, path) in enumerate(changed, 1)]
        # Only files within the size limit are read. One over it is already refused by the size check below, and reading it
        # would pull its whole content into memory for nothing.
        regular = [e for e in self.entries if e.mode in pp.FILE_MODES and 0 <= e.size <= pp.MAX_BYTES]
        data = dict(zip((e.path for e in regular), pp.read_blobs(self.repo, regular, self.env) if regular else []))
        self.blobs = [data.get(e.path, b"") for e in self.entries]
        self.tree = pp.list_tree(self.repo, self.head, self.env)

    @staticmethod
    def clear(path):
        return not pp.guard_kinds("", path.encode("utf-8", "surrogateescape")) and not pp.unsafe_path(path)

    def label(self, e):
        """'file #3 (docs/a.md)', or 'file #3' when its path holds a listed word or is unsafe."""
        return "file #%d (%s)" % (e.index, e.path) if self.clear(e.path) else "file #%d" % e.index

    def add(self, name, problems, note=None):
        self.report.add(name, pp.REFUSED if problems else pp.PASS, *(problems or [note]))

    def checks(self):
        by_number = {e.index: e for e in self.entries}
        text = [(e, d) for e, d in zip(self.entries, self.blobs) if e.mode in pp.FILE_MODES]
        self.report.add("files changed", pp.PASS, "%d added or changed, %d deleted" % (len(self.entries), len(self.deleted)))
        self.add("plain files only (no links or submodules), safe paths",
                 ["%s is a link or submodule" % self.label(e) for e in self.entries if e.mode not in pp.FILE_MODES]
                 + ["file #%d has an unsafe path" % e.index for e in self.entries if pp.unsafe_path(e.path)])
        self.add("no file over 5 MB", ["%s is over 5 MB" % self.label(e) for e in self.entries if e.size > pp.MAX_BYTES or e.size < 0])
        tree = [e for e in self.tree if e.mode in pp.FILE_MODES]
        folded = {}
        for e in tree:
            folded.setdefault(pp.unicodedata.normalize("NFC", e.path).casefold(), []).append(e)
        self.add("no two paths differ only by letter case",
                 ["a changed path clashes in letter case with another" for e in self.entries
                  if len(folded.get(pp.unicodedata.normalize("NFC", e.path).casefold(), ())) > 1][:1])
        self.add("no private-only paths (notes, branding, assistant settings)",
                 ["%s is in a folder kept private" % self.label(e) for e in self.entries if pp.is_excluded(e.path)])
        bad = []
        for e, data in text:
            ext = os.path.splitext(e.path)[1].lower()
            binary = b"\0" in data[:8000] and not (data[:2] in (b"\xff\xfe", b"\xfe\xff"))
            kind = next((k for m, k in MAGIC if data.startswith(m)), None)
            if not kind and (binary or ext in ARCHIVE_SUFFIXES):          # short signatures count only with a NUL or a name
                kind = next((k for m, k in MAGIC_WITH_NUL if data.startswith(m)), None)
            if kind or ext in ARCHIVE_SUFFIXES or (binary and ext not in PICTURES):
                bad.append("%s is %s" % (self.label(e), kind or "a binary or archive file that is not on the allow-list"))
            elif ext in PICTURES and not PICTURES[ext](data):
                bad.append("%s has a picture or font name but is not a well-formed one, or has data after its end" % self.label(e))
        self.add("no archives, programs or unlisted binaries", bad)
        # A file over 5 MB is already refused above; its content is not read (the rules take time in proportion to its size).
        kept = [(e, d) for e, d in zip(self.entries, self.blobs) if 0 <= e.size <= pp.MAX_BYTES]
        scanned = ([e for e, _ in kept], [d for _, d in kept])
        self.add("no secrets", pp.secret_findings(*scanned))
        self.add("no listed words (people, private repos, hosting)", pp.guard_findings(*scanned))
        self.identity()
        self.workflows(text, by_number)

    def identity(self):
        """Every commit BASE..HEAD, merges included, is checked: addresses, then listed words in names, addresses, message."""
        if self.base == "ALL":
            out, expected = b"", 0
        else:
            span = "%s..%s" % (self.base, self.head)
            out = self.git("log", "--no-show-signature", "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B%x00%x01", span)
            expected = int(self.git("rev-list", "--count", span))
        bad, n = [], 0
        # A record ends with NUL then \x01, so a \x01 inside a message hides nothing; the record count must then equal git's own.
        for rec in out.decode("utf-8", "replace").split("\0\x01"):
            rec = rec.lstrip("\n")
            if not rec:
                continue
            parts = rec.split("\0", 5)
            if len(parts) < 6 or not re.fullmatch(r"[0-9a-f]{40}", parts[0]):
                raise RuntimeError("git log output not understood")
            n += 1
            _, an, ae, cn, ce, body = parts
            wrong = sorted({x for x in [ae, ce] if not NOREPLY.match(x)} | {x for x in EMAIL.findall(body) if not TRAILER_OK.match(x)})
            if wrong:
                bad.append("commit #%d holds %d address(es) that are not GitHub no-reply addresses" % (n, len(wrong)))
            if any(pp.guard_kinds("", s.encode("utf-8", "surrogateescape")) for s in (an, ae, cn, ce, body)):
                bad.append("commit #%d holds a listed word in a name, an address or a message" % n)
        if n != expected:
            raise RuntimeError("commit count differs from git's")
        if os.environ.get("CI_SCAN_IDENTITY") == "warn" and bad and all("address" in b for b in bad):
            self.report.add("commits use no-reply addresses", pp.SKIPPED, *["notice: " + b for b in bad])
        else:
            self.add("commits use no-reply addresses, no listed words", bad, "%d commit(s) checked" % n)

    def workflows(self, text, by_number):
        def guarded(path):
            return any(path == p or (p.endswith("/") and path.startswith(p)) for p in PROTECTED)
        # Deleted and moved files count too: a pull request that removes a guard must be read as closely as one that edits it.
        touched = [self.label(e) for e in self.entries if guarded(e.path)] + [
            "a deleted file (%s)" % d if self.clear(d) else "a deleted file" for d in self.deleted if guarded(d)]
        notes = ["%s is part of the workflows or the rules that guard this repository: a maintainer must read it" % t for t in touched]
        bad = []
        for e, data in text:
            if not e.path.startswith(".github/") or not e.path.endswith((".yml", ".yaml")):
                continue
            src = data.decode("utf-8", "replace")
            code = "\n".join(re.sub(r"\s+#\s.*$", "", ln) for ln in src.splitlines() if not ln.lstrip().startswith("#"))
            tag = e.index
            if re.search(r"pull_request_target|workflow_run", code):
                bad.append("file #%d: uses a trigger that runs with this repository's token on outside code" % tag)
            if re.search(r"secrets\.|secrets:\s|\bwrite\b|write-all|id-token", code):
                bad.append("file #%d: uses a secret or write access" % tag)
            if re.search(r"^\s*(?:self-hosted|runs-on:.*self-hosted)", code, re.M):
                bad.append("file #%d: runs on a self-hosted machine" % tag)
            for ln in code.splitlines():
                m = USES.match(ln)
                if m and not m.group(1).startswith("./") and not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", m.group(1)):
                    bad.append("file #%d: an action is not pinned to a full commit SHA" % tag)
                if RISKY_CONTEXT.search(ln) and not SAFE_LINE.match(ln):
                    bad.append("file #%d: outside text is put straight into a command line" % tag)
        bad = list(dict.fromkeys(bad))
        if self.fork:
            self.add("workflows and guard rules unchanged by a fork", notes + bad)
        else:
            self.add("workflow files follow the rules", bad)
            if notes:
                self.report.add("workflows and guard rules changed", pp.SKIPPED, *["notice: " + n for n in notes])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--fork", action="store_true", default=os.environ.get("CI_SCAN_FORK") == "1")
    args = ap.parse_args(argv)
    scan = Scan(args.repo, args.base, args.head, args.fork)
    try:
        scan.load()
        scan.checks()
    except Exception as exc:  # noqa: BLE001  a failure to scan is a refusal, never a pass
        print("CI scan could not run: %s" % type(exc).__name__)
        return 2
    print("\n".join(scan.report.lines()))
    print("CI scan: %s" % ("passed" if scan.report.ok else "REFUSED"))
    return 0 if scan.report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
