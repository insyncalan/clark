"""Publish a clean public copy of clark (#94; development only; this tool sends code off the laptop).

    python3 dev/tools/publish_public.py <tag or ref> --target <public repo> --dry-run
    python3 dev/tools/publish_public.py <tag or ref> --target <public repo> [--branch release-X.Y.Z]

Builds a snapshot of the files git tracks at <ref> (read from git's objects, never from the working folder, so
ignored and untracked files such as system/branding/ and comms/ can never be in it), takes out the internal working
notes (EXCLUDED; but a tracked file under comms/ or system/branding/ is a refusal, not a removal), swaps in the public
README (docs/public/README.md, which then stays out of the snapshot; the private README is never published), and
pushes the result as ONE new commit on the public repo's branch: `clark-public` (the default), `release-X.Y.Z` (the
release gate) or `main` (only with --publish-main). The commit is by a neutral "clark", never by
the local git settings, and goes on top of the branch's present tip, so the public history is a chain of snapshots.

It refuses, before anything is pushed, unless every check passes: the branch name; --target given (nothing is baked
in), with no password in it, not the private repo (read from this repo's `origin` at run time, never written in this file; compared by URL and by
name, every https/ssh/.git/case variant),
a public repo (asked of `gh`), and not rewritten by a git "insteadOf" rule; the ref is on main, holds the public
README, and its tests pass on both Pythons; nothing excluded remains; no file over 5 MB; no secret (keys, tokens, passwords, .env files); and the
whole snapshot, its paths, its Office parts, and the commit's author and message pass tests/test_no_real_names.py.
Names, hashes and secret values are never printed: a hit is shown as "file #N" in `git ls-tree -r --name-only <ref>`
(find it with: git ls-tree -r --name-only <ref> | sed -n 'Np').

--dry-run changes nothing and pushes nothing: it lists the files, runs the checks and says what it would commit. It
skips the long test run unless --with-tests is given. Exit 0 means every check that ran passed.
It never force-pushes, never makes or pushes a tag, never deletes, and never writes to your git settings.
--allow-local-target lets --target be a folder (the tests use it; a folder is not checked for being public, but one that
is, is inside, surrounds or shares the git store of this repo, such as another worktree of it, is still refused).
SIGTERM and SIGHUP stop it like Ctrl-C: the temporary folders are removed, and the exit code is 130. A second signal
while they are being removed is held off (and the removal run again if one gets in), so no folder is left behind.
--author-name / --author-email replace the neutral identity (not for normal use). Standard library only.
Read docs/publishing-the-public-copy.md first. New for clark: nothing here is copied from creaite.
"""
import argparse
import base64
import codecs
import hashlib
import html
import importlib
import io
import os
import posixpath
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUARD_DIR = REPO / "tests"

AUTHOR_NAME = "clark"
AUTHOR_EMAIL = "clark@users.noreply.github.com"
DEFAULT_PUBLIC_REMOTE = None                     # never a default target: --target is always given by a person
DEFAULT_BRANCH = "clark-public"
MAIN_BRANCH = "main"
RELEASE_BRANCH = re.compile(r"release-[0-9]+\.[0-9]+\.[0-9]+")        # used with fullmatch: $ lets a trailing newline through, \d lets other scripts' digits through
SNAPSHOT_BRANCH = "snapshot"                     # only inside the temporary repo

# Internal working notes that stay private (#94). A trailing slash means everything under that folder. Matched without
# regard to case. tests/test_publish_public.py pins this list to the issue.
EXCLUDED = (
    "dev/HEAD-LOG.md",
    "docs/DECISIONS.md",
    codecs.decode("qbpf/UNAQBIRE-EBZNABSS.zq", "rot13"),            # the two hand-over notes between the leads: ROT13 because
    codecs.decode("qbpf/ABGRF-SBE-GUR-BGURE-EBZNABSS.zq", "rot13"),  # the file names hold a person's name and this file is published
    "docs/TEAM-AND-ROLES.md",          # internal staffing; names a private repo (the Head, 28-10-2026)
    ".claude/",
    "comms/",
    "system/branding/",
)
# The public README lives in the private repo as PUBLIC_README_SOURCE; the snapshot's README.md is that file's bytes,
# and PUBLIC_SOURCE_DIR (its folder) is then left out of the snapshot. Not in EXCLUDED: it is the source, not a note.
PRIVATE_FOLDERS = ("comms/", "system/branding/")   # kept out of git by .gitignore: a tracked file here is a refusal, not a removal
PUBLIC_README_SOURCE = "docs/public/README.md"
PUBLIC_README = "README.md"
PUBLIC_SOURCE_DIR = "docs/public/"

MAX_BYTES = 5 * 1024 * 1024
HOST_ALIASES = {"www.github.com": "github.com", "ssh.github.com": "github.com"}
DEFAULT_MAIN_REF = "origin/main"
DEFAULT_PYTHONS = ("python3", "/usr/bin/python3")
MIN_PYTHON_VERSIONS = 2                          # the oldest and the newest: two different versions must pass
TEST_TIMEOUT = 3600
FILE_MODES = {"100644", "100755"}
HASH_CHUNK = 50                                  # paths per `git hash-object` call

# What a secret looks like. Names of kinds are printed; matches never are.
SECRET_PATTERNS = (
    ("a private key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP |ENCRYPTED )?PRIVATE KEY")),
    ("a GitHub token", re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,})")),
    ("an AWS access key", re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("a Slack token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{8,}")),
    ("a JSON web token", re.compile(rb"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("an Anthropic or OpenAI key", re.compile(rb"\bsk-(?:ant-|proj-|svcacct-|admin-)[A-Za-z0-9_-]{8,}|\bsk-[A-Za-z0-9]{32,}")),
    ("a Stripe live key", re.compile(rb"\b[sr]k_live_[A-Za-z0-9]{8,}")),
    ("a Google API key", re.compile(rb"\bAIza[0-9A-Za-z_-]{30,}")),
    ("an npm token", re.compile(rb"\bnpm_[A-Za-z0-9]{20,}|_authToken\s*=\s*[A-Za-z0-9][^\s$\x22']{15,}")),
    ("a PyPI token", re.compile(rb"\bpypi-[A-Za-z0-9_-]{20,}")),
    ("a password in an address", re.compile(rb"[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@[^/\s]")),
    ("an authorization header", re.compile(rb"(?i)authorization\s*[:=]\s*[\x22']?(?:bearer|basic|token)\s+[A-Za-z0-9._~+/=-]{8,}")),
)
GENERIC_SECRET = re.compile(rb"""(?i)(?:api[_-]?key|secret|token|passw(?:or)?d|pwd)["']?\s*[:=]\s*["']([^"'\s]{16,})["']""")
# The same names with a value that is not in quotes (an .env or shell line, a YAML or INI value). A value that starts or
# holds code (a call, a variable, a placeholder) is not read as a value. Passwords are shorter than keys, so they count from 8.
UNQUOTED_SECRET = re.compile(rb"""(?i)(?:api[_-]?key|secret|token|(passw(?:or)?d|pwd))\w*["']?[ \t]*[:=][ \t]*([^\s"'`$<>{}()\[\],;]{8,})""")
BASE64_RUN = re.compile(rb"[A-Za-z0-9+/_-]{24,}")
PRIVATE_KEY_HEADER = SECRET_PATTERNS[0][1]
MAX_ZIP_DEPTH = 4                                # zips inside zips inside a .docx: deeper than this can't be checked, so it is a refusal
MAX_ZIP_BYTES = 64 * 1024 * 1024                 # everything unpacked from one file, all levels together
SECRET_NAMES = re.compile(r"^(\.env(\..*)?|.*\.(pem|key|p12|pfx|keystore)|id_(rsa|dsa|ecdsa|ed25519).*|\.netrc|\.pgpass|"
                          r"\.git-credentials|credentials\.json)$", re.I)
# Test fixtures that may look like a secret, by exact path, each with its reason. Keep this empty unless a fixture
# really needs it; a path here is skipped by the secrets scan only (never by the name guard).
SECRET_SCAN_ALLOWED = {}

PASS, REFUSED, SKIPPED = "PASS", "REFUSED", "SKIPPED"
FORBIDDEN_GIT_ARGS = {"--force", "-f", "--mirror", "--tags", "--delete", "-d", "--prune", "--all", "--follow-tags",
                       "--force-with-lease", "--force-if-includes"}
KEPT_GIT_ENV = ("GIT_SSH", "GIT_SSH_COMMAND", "GIT_ASKPASS", "SSH_ASKPASS", "SSH_AUTH_SOCK")


class Unsafe(Exception):
    """A git command that could rewrite or delete public history was about to run."""


# --- running programs (argument lists only) ---------------------------------------------------------------------------

def git(args, *, cwd=None, env, data=None):
    """Run git with an argument list. Anything that could force, delete or tag is refused here, in one place."""
    for a in args:
        if a == "--" and "hash-object" in args:             # after it come file names only (hash-object never pushes)
            break
        if a in FORBIDDEN_GIT_ARGS or a.startswith("--force") or a.startswith("+") or a.startswith(":refs"):
            raise Unsafe("refusing to run git with %r" % a)
    return subprocess.run(["git"] + list(args), cwd=cwd, env=env, input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False)


def text(proc):
    return proc.stdout.decode("utf-8", "replace").strip()


def neutral_env(home, name, email, when):
    """The only environment commits are made in: no user or system git settings, a fixed identity, UTC."""
    stamp = "%d +0000" % when
    return {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(home), "XDG_CONFIG_HOME": str(home),
            "LC_ALL": "C", "TZ": "UTC", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": stamp,
            "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email, "GIT_COMMITTER_DATE": stamp}


def net_env():
    """The environment for talking to the target: your own settings (they hold your sign-in), no repo-steering GIT_*."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") or k in KEPT_GIT_ENV}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def safe_config(name, email):
    return ["-c", "user.name=" + name, "-c", "user.email=" + email, "-c", "commit.gpgsign=false",
            "-c", "tag.gpgsign=false", "-c", "core.hooksPath=" + os.devnull, "-c", "core.autocrlf=false",
            "-c", "core.safecrlf=false"]


def hide_password(line):
    """Never let a password in a URL reach the screen."""
    return re.sub(r"(://)[^/@\s]*@", r"\1***@", str(line))


# --- the target ------------------------------------------------------------------------------------------------------

class TargetError(Exception):
    pass


def normal_path(path):
    """owner/name, lower case, with every trailing ".git" and "/" taken off until nothing more changes."""
    path, before = urllib.parse.unquote(path).strip().lower(), None
    while path != before:                      # ".git.git", ".GIT/.git/", "%2egit" and "a/../b" all end up the same
        before = path
        path = path.strip("/")
        path = posixpath.normpath(path) if path else ""
        if path.endswith(".git"):
            path = path[:-4]
        path = urllib.parse.unquote(path).strip()
    return path.strip("/")


def parse_target(value, base=None):
    """('url', host, 'owner/name', has_credentials) for a remote URL, or ('local', realpath, None, False) for a folder."""
    value = value.strip()
    if not value or any(c in value for c in "\0\n\r") or value.startswith("-"):
        raise TargetError("the target is empty or not a plain URL or folder")
    if "://" in value:
        try:
            parts = urllib.parse.urlsplit(value)
            parts.port                              # noqa: B018  a bad port or a bracket that never closes raises ValueError here
        except ValueError:
            raise TargetError("the target is not a plain URL")
        scheme = parts.scheme.lower()
        if scheme == "file":
            return ("local", os.path.realpath(urllib.parse.unquote(parts.path)), None, False)
        if scheme not in ("https", "http", "ssh", "git") or not parts.hostname:
            raise TargetError("the target is not an https or ssh address")
        host = parts.hostname.lower()
        creds = parts.password is not None or (scheme in ("https", "http") and parts.username is not None)
        return ("url", HOST_ALIASES.get(host, host), normal_path(parts.path), creds)
    scp = re.match(r"^(?:[^@/:]+@)?([A-Za-z0-9.-]+):(?!//)(.+)$", value)
    if scp and not value.startswith((".", "/", "~")) and not os.path.isdir(value):
        host = scp.group(1).lower()
        return ("url", HOST_ALIASES.get(host, host), normal_path(scp.group(2)), False)
    path = Path(os.path.expanduser(value))
    if not path.is_absolute() and base is not None:
        path = Path(base) / path
    if value.startswith((".", "/", "~")) or path.exists():
        return ("local", os.path.realpath(str(path)), None, False)
    raise TargetError("the target is not a URL or a folder that exists")


def same_repo(a, b):
    """Whether two parsed targets name the same repository (any scheme, case, .git suffix, www or ssh host)."""
    if a[0] != b[0]:
        return False
    if a[0] == "url":
        return a[1] == b[1] and a[2] == b[2]
    return a[1] == b[1] or (file_id(a[1]) is not None and file_id(a[1]) == file_id(b[1]))   # by inode: letter case on APFS


def file_id(path):
    """(device, inode) of a path, or None when it does not exist. Two spellings of one folder (another letter case on a
    case-insensitive disk, a link, a bind) have the same id, which a string comparison of paths does not show."""
    try:
        st = os.stat(path)
    except (OSError, ValueError):
        return None
    return (st.st_dev, st.st_ino)


def id_chain(path):
    """The ids of a path and of each folder above it that exists, nearest first."""
    if not path:
        return []
    ids, here = [], os.path.abspath(path)
    while True:
        found = file_id(here)
        if found is not None:
            ids.append(found)
        above = os.path.dirname(here)
        if above == here:
            return ids
        here = above


def local_matches(path, repo, env):
    """How a local target folder is this repo (its folder, its .git, its git store, inside or around its working tree,
    or sharing its git store); [] when it is none. Everything is compared by (device, inode), never by path text, so a
    different letter case on APFS cannot get past it."""
    top = text(git(["-C", str(repo), "rev-parse", "--show-toplevel"], env=env))
    common = text(git(["-C", str(repo), "rev-parse", "--git-common-dir"], cwd=str(repo), env=env))
    common = (common if os.path.isabs(common) else os.path.join(str(repo), common)) if common else ""
    own = {i for i in (file_id(top) if top else None, file_id(os.path.join(top, ".git")) if top else None,
                       file_id(common) if common else None) if i is not None}
    mine, chain = file_id(path), id_chain(path)
    if mine is not None and mine in own:
        return ["this repo's own folder"]
    if own & set(chain[1:]) or (mine is not None and (mine in id_chain(top) or mine in id_chain(common))):
        return ["a folder inside, or around, this repo's working tree"]
    if os.path.isdir(path) and common:
        theirs = text(git(["-C", path, "rev-parse", "--git-common-dir"], env=env))
        theirs = (theirs if os.path.isabs(theirs) else os.path.join(path, theirs)) if theirs else ""
        if theirs and file_id(theirs) is not None and file_id(theirs) == file_id(common):
            return ["a worktree, clone or folder that shares this repo's git store"]
    return []


def remote_addresses(repo, env):
    """[(remote name, address)] for every `url` and `pushurl` of every remote in this repo's git settings, read now."""
    proc = git(["-C", str(repo), "config", "--null", "--get-regexp", r"^remote\..+\.(url|pushurl)$"], env=env)
    out = []
    for rec in proc.stdout.decode("utf-8", "replace").split("\0"):
        key, _, raw = rec.partition("\n")
        match = re.fullmatch(r"remote\.(.+)\.(?:url|pushurl)", key, re.I)
        if match and raw.strip():
            out.append((match.group(1), raw.strip()))
    return out


def private_matches(target, repo, env):
    """What the target is the same as, among the private repo's own addresses (every remote's url and pushurl, read now); [] when none."""
    found = []
    for name, raw in remote_addresses(repo, env):
        try:
            theirs = parse_target(raw, base=repo)
        except TargetError:
            continue
        label = "this repo's origin" if name == "origin" else "this repo's other remote"
        if same_repo(target, theirs):
            found.append(label)
        elif target[0] == "url" and theirs[0] == "url" and target[2] == theirs[2]:
            found.append(label + " name (on any host)")
    if target[0] == "local":
        found += local_matches(target[1], repo, env)
    return found


def rewrite_rules_hit(target_text, env, cwd):
    """git 'insteadOf' rules in your settings that would change where a push to this target really goes."""
    proc = git(["config", "--null", "--get-regexp", r"^url\..*\.(insteadof|pushinsteadof)$"], cwd=cwd, env=env)
    hits = 0
    for record in proc.stdout.decode("utf-8", "replace").split("\0"):
        if "\n" in record:
            _, value = record.split("\n", 1)
            if value and target_text.startswith(value):
                hits += 1
    return hits


def gh_is_public(owner, name):
    """True only when `gh api repos/<owner>/<name> --jq .private` says exactly `false`."""
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", owner) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", name):
        return False
    try:
        proc = subprocess.run(["gh", "api", "repos/%s/%s" % (owner, name), "--jq", ".private"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and proc.stdout.decode("utf-8", "replace").strip() == "false"


# --- the snapshot ----------------------------------------------------------------------------------------------------

class Entry:
    def __init__(self, index, mode, sha, size, path):
        self.index, self.mode, self.sha, self.size, self.path = index, mode, sha, size, path


def is_excluded(path):
    folded = unicodedata.normalize("NFC", path).casefold()
    for rule in EXCLUDED + (PUBLIC_SOURCE_DIR,):
        low = rule.casefold()
        if folded == low or (low.endswith("/") and folded.startswith(low)):
            return rule
    return None


def use_public_readme(entries, report):
    """The entries with README.md swapped for PUBLIC_README_SOURCE's file; None (and a REFUSED row) when it is missing."""
    source = next((e for e in entries if e.path == PUBLIC_README_SOURCE), None)
    if source is None or source.mode not in FILE_MODES:
        report.add("public README", REFUSED, "%s is missing from this commit (or is not a plain file), so there is no "
                   "public README to publish; the private one is never published" % PUBLIC_README_SOURCE)
        return None
    swap = Entry(source.index, source.mode, source.sha, source.size, PUBLIC_README)
    out, placed = [], False
    for e in entries:
        if e.path.casefold() == PUBLIC_README.casefold():
            if not placed:
                out.append(swap)
                placed = True
        else:
            out.append(e)
    if not placed:
        out.append(swap)
    report.add("public README", PASS, "README.md is %s (the private README is left out)" % PUBLIC_README_SOURCE)
    return out


def list_tree(repo, sha, env):
    """Every file in the commit's tree as Entry objects, numbered as `git ls-tree -r` lists them (from 1)."""
    proc = git(["-C", str(repo), "ls-tree", "-r", "-l", "-z", "--full-tree", sha], env=env)
    if proc.returncode != 0:
        raise TargetError("git could not list the commit")
    out = []
    for i, rec in enumerate([r for r in proc.stdout.split(b"\0") if r], 1):
        meta, _, path = rec.partition(b"\t")
        mode, kind, obj, size = (meta.split() + [b"", b"", b"", b"-"])[:4]
        out.append(Entry(i, mode.decode(), obj.decode(), int(size) if size.isdigit() else -1,
                         path.decode("utf-8", "surrogateescape")))
    return out


def unsafe_path(path):
    parts = path.split("/")
    return (not path or path.startswith("/") or "\\" in path or any(p in ("", ".", "..") or p.casefold() == ".git"
                                                                    for p in parts)
            or any(ord(c) < 32 or ord(c) == 127 or "\udc80" <= c <= "\udcff" for c in path))


def read_blobs(repo, entries, env):
    shas = [e.sha for e in entries]
    proc = git(["-C", str(repo), "cat-file", "--batch"], env=env, data=("\n".join(shas) + "\n").encode())
    data, pos, out = proc.stdout, 0, []
    for sha in shas:
        nl = data.find(b"\n", pos)
        head = data[pos:nl].split() if nl >= 0 else []
        if len(head) != 3 or head[0].decode() != sha or head[1] != b"blob":
            raise TargetError("git could not read a file of the commit")
        size = int(head[2])
        out.append(data[nl + 1:nl + 1 + size])
        pos = nl + 1 + size + 1
    return out


def write_repo(dest, entries, blobs, env, cfg):
    """git init in `dest`, write each file there byte for byte, and stage them exactly as the ref has them
    (hash-object without filters, update-index: no line-ending changes, no .gitignore, no attributes)."""
    dest = Path(dest)
    dest.mkdir(parents=True)
    try:
        return _write_repo(dest, entries, blobs, env, cfg)
    except OSError as err:                     # e.g. two paths that clash on this disk: never a traceback, never a name
        raise TargetError("a file could not be written out (%s)" % (err.strerror or "disk error"))


def _write_repo(dest, entries, blobs, env, cfg):
    if git(["init", "-q", "--template=", str(dest)], env=env).returncode != 0:
        raise TargetError("git could not start the temporary repo")
    git(["-C", str(dest), "symbolic-ref", "HEAD", "refs/heads/" + SNAPSHOT_BRANCH], env=env)
    for e, data in zip(entries, blobs):
        target = dest / e.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o755 if e.mode == "100755" else 0o644)
    shas = []
    for i in range(0, len(entries), HASH_CHUNK):        # paths as arguments after `--`: git never unquotes or splits them
        chunk = [e.path for e in entries[i:i + HASH_CHUNK]]
        proc = git(cfg + ["-C", str(dest), "hash-object", "-w", "--no-filters", "--"] + chunk, env=env)
        if proc.returncode != 0:
            raise TargetError("the files written out are not the files git holds for the ref")
        shas += proc.stdout.decode().split()
    if shas != [e.sha for e in entries]:
        raise TargetError("the files written out are not the files git holds for the ref")
    index = b"".join(("%s %s\t%s" % (e.mode, e.sha, e.path)).encode("utf-8") + b"\0" for e in entries)
    if git(["-C", str(dest), "update-index", "--add", "-z", "--index-info"], env=env, data=index).returncode != 0:
        raise TargetError("git could not stage the files")
    proc = git(["-C", str(dest), "write-tree"], env=env)
    if proc.returncode != 0:
        raise TargetError("git could not write the tree")
    return text(proc)


def text_forms(data):
    """The bytes, and (when they look like UTF-16: a byte-order mark, or many NULs) what they read as in UTF-16 either way
    round, as UTF-8, so the same patterns see a token in a Windows-saved file."""
    forms = [data]
    if data[:2] in (b"\xff\xfe", b"\xfe\xff") or data.count(b"\0") * 10 > len(data):
        for enc in ("utf-16-le", "utf-16-be"):
            forms.append(data.decode(enc, "ignore").encode("utf-8", "ignore"))
    return forms


def base64_kinds(data):
    """Kinds of secret found inside base64 runs (every alignment of the run is tried): a private key's header, or a token."""
    kinds = set()
    for m in BASE64_RUN.finditer(data):
        run = m.group().replace(b"-", b"+").replace(b"_", b"/")
        for offset in range(4):
            chunk = run[offset:]
            chunk = chunk[:len(chunk) - len(chunk) % 4]
            if len(chunk) < 24:
                continue
            try:
                plain = base64.b64decode(chunk)
            except ValueError:
                continue
            if PRIVATE_KEY_HEADER.search(plain):
                kinds.add("a private key (base64)")
            elif any(rx.search(plain) for kind, rx in SECRET_PATTERNS[1:]):
                kinds.add("a token (base64)")
    return kinds


def scan_secrets_in(data):
    kinds = set()
    for form in text_forms(data):
        for kind, rx in SECRET_PATTERNS:
            if rx.search(form):
                kinds.add(kind)
        if b"\0" not in form:
            for m in GENERIC_SECRET.finditer(form):
                value = m.group(1)
                if re.search(rb"[0-9]", value) and re.search(rb"[A-Za-z]", value):
                    kinds.add("a password, key or token value")
            for m in UNQUOTED_SECRET.finditer(form):
                value = m.group(2)
                if len(value) >= (8 if m.group(1) else 16) and re.search(rb"[0-9]", value) and re.search(rb"[A-Za-z]", value):
                    kinds.add("a password, key or token value")
        kinds |= base64_kinds(form)
    return kinds


def zip_findings(data, label, depth, budget, scan=None, check_names=False):
    """Findings for the parts of a zip, and (to MAX_ZIP_DEPTH levels) for zips inside it: ['part #1: ...', 'part #2.1: ...'].
    `scan(bytes)` gives the kinds found in a part (default: secrets); with `check_names` the part's own name is scanned too.
    `budget` is a one-item list: the bytes this file may still unpack. Whatever can't be read or is too deep is a finding."""
    scan = scan or scan_secrets_in
    found = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = [i for i in z.infolist() if not i.is_dir()]
            for j, info in enumerate(infos, 1):
                at = "%s.%d" % (label, j) if label else "part #%d" % j
                if check_names:
                    found += ["%s: a listed word in its name" % at for _ in [1] if scan(info.filename.encode("utf-8", "replace"))]
                try:
                    if info.file_size > MAX_BYTES or info.file_size > budget[0]:
                        raise ValueError("too big")
                    budget[0] -= info.file_size
                    part = z.read(info)
                except Exception:  # noqa: BLE001  encrypted, damaged, unsupported or too big to read here
                    found.append("%s: can't be read, so it can't be checked" % at)
                    continue
                found += ["%s: %s" % (at, k) for k in sorted(scan(part))]
                if part[:2] == b"PK":
                    if depth >= MAX_ZIP_DEPTH:
                        found.append("%s: zips are nested too deep, so it can't be checked" % at)
                    else:
                        found += zip_findings(part, at, depth + 1, budget, scan, check_names)
    except zipfile.BadZipFile:
        pass                                                # starts with PK but is not a zip: already scanned as bytes
    return found


def secret_findings(entries, blobs):
    """['file #N: a private key', 'file #N part #J: ...', 'file #N part #J.K: ...'] over the file names, the files, the parts
    inside Office files and the zips inside those."""
    found = []
    for e, data in zip(entries, blobs):
        if SECRET_NAMES.match(e.path.rsplit("/", 1)[-1]):
            found.append("file #%d: a file name that holds secrets (.env, key, credentials or certificate file)" % e.index)
        if e.path in SECRET_SCAN_ALLOWED:
            continue
        for kind in sorted(scan_secrets_in(data)):
            found.append("file #%d: %s" % (e.index, kind))
        if data[:2] == b"PK":
            found += ["file #%d %s" % (e.index, f) for f in zip_findings(data, "", 1, [MAX_ZIP_BYTES])]
    return found


# --- the scrub and the guard (#94: the public copy carries no private names) -----------------------------------------------
# The private tree is never edited. Between reading a file from git and writing it into the snapshot, scrub() rewrites the
# text that names people, private repos and boards, and a hosting detail; the guard then refuses the snapshot if any listed
# word is left anywhere (a path, a file, a part of a zip, UTF-16 text). The words are kept ROT13 below, so this file (which is
# published too) does not carry them; reveal() undoes it. Hits are reported by file number and kind, never by the word.

def reveal(word):
    return codecs.decode(word, "rot13")


# Every team first name and full persona name. A name that is not an English word counts in any case; a name that is one
# (and is also a surname or a first name in common use) counts only when capitalised and whole.
PEOPLE_ANY_CASE = tuple(reveal(w) for w in ("Nyna", "Wneivf", "Jnaqn", "Ebznabss", "Angnfun", "Znkvzbss", "Znuba"))
PEOPLE_CAPITALISED = tuple(reveal(w) for w in ("Onaare", "Ynat", "Cnexre", "Pnc", "Fgnex", "Fpbgg", "Crgre", "Oehpr", "Gbal",
                                               "Fgrir", "Ebtref"))
PRIVATE_NAMES = tuple(reveal(w) for w in ("pernvgr-pbasvqragvny", "pernvgr-cyna", "Grnz-Niratref", "pynex-cyna"))
HOSTING_WORDS = tuple(reveal(w) for w in ("Urgmare", "PNK41"))
REUSE_RECORD = reveal("ERHFR-SEBZ-PERNVGR")
# Where a listed word is allowed to remain, by exact path: {word: how many times}, with the reason. The count is pinned and
# is for that word only: one more, or another listed word there, fails the guard.
GUARD_ALLOWED = {
    "system/prototype/help.js": ({reveal("Onaare"): 1}, "a product feature that shares its name with a person"),
    "system/prototype/views.js": ({reveal("Onaare"): 1}, "a product feature that shares its name with a person"),
}
# The same word is also the name of one page template (a section type). The tool cannot tell a template from a person, so it
# allows exactly that many uses of the word in each file below (one each) and no more; a second use there, or the word in any
# other file, is refused. Add a path here (with its exact count) only when a file really needs the name.
TEMPLATE_NAME_PATHS = {"src/clark/page/src/help/helpContent.json": 1, "tests/test_help_content.py": 1,
                       "tests/test_help_shown.py": 1}
TEMPLATE_LIMIT_KIND = ("more uses of the page-template name than this file may hold (one). "
                       "Remove the extra use, or ask for the limit to be raised")
GUARD_ALLOWED.update({path: ({reveal("Onaare"): count}, "a page template that shares its name with a person")
                      for path, count in TEMPLATE_NAME_PATHS.items()})
# What a person or private repo becomes in prose (.md and .txt). Anyone not listed here is "a teammate".
ROLES = {reveal("Nyna").lower(): "the owner", reveal("Znuba").lower(): "the owner",
         reveal("Ebznabss").lower(): "the project lead", reveal("Angnfun").lower(): "the project lead",
         reveal("Wneivf").lower(): "the Head"}
TEAMMATE = "a teammate"
REPO_WORDS = {reveal("Grnz-Niratref").lower(): "the team repo", reveal("pynex-cyna").lower(): "the planning repo",
              reveal("pernvgr-pbasvqragvny").lower(): "a private repo", reveal("pernvgr-cyna").lower(): "a private repo"}
# Fixed phrases (regex, replacement), applied in every comment, docstring and line of prose.
SCRUB_PHRASES = (
    (re.compile(r"\s*\(" + re.escape(reveal("PNK41")) + r"\)"), ""),
    (re.compile(re.escape(reveal("Urgmare")) + r" Cloud"), "a Linux host"),
    (re.compile(re.escape(reveal("Urgmare"))), "a Linux machine"),
    (re.compile(re.escape(reveal("PNK41"))), "a Linux machine"),
)
SCRUB_SUFFIXES = {".md": "prose", ".txt": "prose", ".py": "python", ".js": "js", ".jsx": "js", ".css": "css", ".sql": "sql",
                  ".yml": "yaml", ".yaml": "yaml", ".html": "html", ".svg": "html"}       # anything else is guarded, not scrubbed
DROPPED = "\x00DROP\x00"

_NAME = "(?:(?i:" + "|".join(PEOPLE_ANY_CASE) + ")|" + "|".join(PEOPLE_CAPITALISED) + ")"
_WHO = _NAME + r"(?:(?:,\s*|\s+and\s+|\s*/\s*|,?\s+through\s+|,?\s+via\s+)" + _NAME + ")*"
_DATE = r"\d{1,2}-\d{1,2}-\d{4}(?:,?\s+\d{1,2}:\d{2})?"
_ATTR = _WHO + r"(?:,?\s+(?:" + _DATE + r"|\#\d+))?(?:,?\s+relayed by\s+" + _WHO + ")?"
ATTRIBUTION_RULES = (                                   # "(Owner, 11-10-2026, relayed by X: "words")" loses its attribution
    (re.compile(r"\((\#\d+)[;,]\s*" + _ATTR + r"\s*\)"), r"(\1)"),             # "(#69; Owner, 28-10-2026)" keeps its number
    (re.compile(r"[ \t]*\(\s*" + _ATTR + r"\s*\)"), ""),
    (re.compile(r"\(\s*" + _ATTR + r"\s*:\s*"), "("),
    (re.compile(r",?\s+relayed by\s+" + _WHO + r"\s*:\s*(?=[\"“'])"), ": "),
    (re.compile(r"(?<![\w-])" + _ATTR + r"\s*:\s*(?=[\"“'])"), ""),
    (re.compile(r"(?<=\| )" + _WHO + r"(?:,?\s+" + _DATE + r")?(?:,?\s+relayed by\s+" + _WHO + r")?(?= \|)"), ""),
    (re.compile(r"^(\s*(?:[-*]\s+)?)" + _DATE + r",\s*(?:\d{1,2}:\d{2},\s*)?" + _WHO + r"\s*:\s*", re.M), r"\1"),
    (re.compile(r",?\s+relayed by\s+" + _WHO), ""),
)
_REUSE_LINK = re.compile(r"\[([^\[\]]{0,1000})\]\([^)]{0,1000}" + re.escape(REUSE_RECORD) + r"[^)]{0,1000}\)", re.I)       # bounded: a run of "[" took time in proportion to its square
_REUSE_NAME = re.compile(r"`?(?<![\w./-])(?:[\w./-]*/)?" + re.escape(REUSE_RECORD) + r"(?:\.md)?`?", re.I)
# A name of five letters or more is found inside a longer word too ("<Name>Bot", "<Name>2"); a shorter one only as a whole word.
_LONG_NAME = 5
_SHORT_ANY = [w for w in PEOPLE_ANY_CASE if len(w) < _LONG_NAME]
_LONG_ANY = [w for w in PEOPLE_ANY_CASE if len(w) >= _LONG_NAME]
_PERSON_ANY = re.compile(r"(?i:(?<![A-Za-z0-9])(?:" + "|".join(_SHORT_ANY) + r")(?:s|'s|’s)?(?![A-Za-z0-9])|(?:" +
                         "|".join(_LONG_ANY) + r")(?:s|'s|’s)?)")
_PERSON_CAP = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(PEOPLE_CAPITALISED) + r")(?:'s|’s)?(?![A-Za-z0-9])")
_PERSON_WORD = re.compile(_PERSON_ANY.pattern + "|" + _PERSON_CAP.pattern)
_SEP_CHARS = r"[-_.\s\u00a0\u2010-\u2015\u2212\\*`+/]"          # between the words of a private name: any hyphen or dash, underscore, dot, space, backslash, Markdown mark, plus, slash
SEP = _SEP_CHARS + r"{1,6}"                                  # a run of them (a Markdown-escaped or bold hyphen is up to five)
SEP_RUN = _SEP_CHARS + "+"
_REPO_PATTERN = "|".join(SEP.join(re.escape(part) for part in w.split("-")) for w in PRIVATE_NAMES)
_REPO_WORD = re.compile(r"(?:\b[Tt]he\s+)?`?(?:(?<![\w-])[\w-]+/)?(?i:" + _REPO_PATTERN + r")(?![A-Za-z0-9])`?")      # a longer word ("<name>ning") is not the name
# A team's branch (`team-<first name>-<issue>-<slug>`, `origin/team-...`) and a lower-case pair of names ("<a> and <b>"):
# names that a capital letter would not give away. In prose and comments the branch keeps its shape with a plain word.
_ALL_FIRST_NAMES = "|".join(sorted(set(w.lower() for w in PEOPLE_ANY_CASE + PEOPLE_CAPITALISED), key=len, reverse=True))
_TEAM_BRANCH = re.compile(r"(?<![A-Za-z0-9])(team)([-_.])(?:" + _ALL_FIRST_NAMES + r")(?![A-Za-z])", re.I)
_NAME_PAIR = re.compile(r"(?<![A-Za-z0-9])(?:" + _ALL_FIRST_NAMES + r")(?:\s*,\s*|\s+and\s+|\s*&\s*|\s*/\s*)(?:" +
                        _ALL_FIRST_NAMES + r")(?![A-Za-z0-9])", re.I)
_QUOTED_PAIR = re.compile(r"[ \t]*\([^()\n]*[\"“][^\"”()\n]*" + _NAME_PAIR.pattern + r"[^\"”()\n]*[\"”][^()\n]*\)", re.I)
_HOST_WORD = re.compile("|".join(re.escape(w) for w in HOSTING_WORDS), re.I)
_INTERNAL_ONLY = re.compile(r"internal[ _-]?only", re.I)


def _starts_sentence(match):
    before = match.string[:match.start()].rstrip(" \t*_>|")
    return not before or before[-1] in ".!?\n" or bool(re.search(r"\n\s*(?:[-+*]|\d+[.)])$", before))


def _role(match):
    word = match.group(0)
    possessive = re.search(r"(?:'s|’s)$", word)
    base = word[:possessive.start()] if possessive else word
    tail = possessive.group(0) if possessive else ""
    plural = base.lower().endswith("s") and base.lower()[:-1] in ROLES
    if plural:
        base, tail = base[:-1], "s" + tail
    role = ROLES.get(base.lower(), TEAMMATE)
    if _starts_sentence(match):
        role = role[0].upper() + role[1:]
    after, behind = match.string[match.end():match.end() + 1], match.string[match.start() - 1:match.start()] if match.start() else ""
    return (" " if behind.isalnum() else "") + role + tail + (" " if after.isalnum() else "")     # "<Name>Bot" -> "the Head Bot"


def _repo(match):
    found = _REPO_WORD.match(match.group(0))
    word = re.sub(r"^[Tt]he\s+", "", found.group(0))
    key = re.sub(SEP_RUN, "-", word.strip("`").lower())              # a slash is a separator too, so an owner prefix is read off the end
    name = next((k for k in sorted(REPO_WORDS, key=len, reverse=True) if key == k or key.endswith("-" + k)), None)
    if name is None:
        return match.group(0)
    phrase = REPO_WORDS[name]
    return phrase[0].upper() + phrase[1:] if found.group(0).startswith("The") or _starts_sentence(match) else phrase


# a private repo's name, with a path inside that repo after it ("<repo> Projects/x/y.md"): the whole thing is one phrase
_REPO_AND_PATH = re.compile(_REPO_WORD.pattern + r"(?:[ \t]+(?:[\w.-]+/)+[\w.-]*)?")
_REPO_PHRASES = "|".join(sorted((re.escape(p) for p in set(REPO_WORDS.values())), key=len, reverse=True))
_REPO_REPEAT = re.compile(r"\b(" + _REPO_PHRASES + r")(?:,\s*|\s+and\s+|,\s+and\s+)\1\b", re.I)
_REPO_REPO = re.compile(r"\b(" + _REPO_PHRASES + r")(?:\s+repo)+\b", re.I)
_TEAM_WORD = re.compile(r"\bTeams?\s+(?=" + _NAME + r"(?![A-Za-z0-9]))")                # "Team <Name>'s agent" is "<role>'s agent"
_TEAMMATES = re.compile(r"\b(a teammate)(?:(?:,\s*|\s+and\s+|,\s+and\s+)a teammate)+\b", re.I)


_PERSON_FILE = re.compile(r"`?(?<![\w./-])(?:[\w.-]+/)*[\w.-]*(?:" + _PERSON_ANY.pattern.replace("(?<![A-Za-z0-9])", "").replace("(?![A-Za-z0-9])", "") +
                          r")[\w.-]*\.md`?")


def prose_rewrite(text):
    """Roles for people and plain phrases for private repos, in .md and .txt. A file name that holds a person's name is
    'an internal note'; 'Team <Name>' is the name's role; a list of the same role or repo is said once."""
    text = _PERSON_WORD.sub(_role, _REPO_AND_PATH.sub(_repo, _TEAM_WORD.sub("", _PERSON_FILE.sub("an internal note", text))))
    text = re.sub(r"\b(the project lead|the Head|the owner) \((?:project lead|the Head|the owner)\)", r"\1", text)
    text = re.sub(r"\b(the owner|the project lead|the Head|a teammate)(?: \1)+\b", r"\1", text, flags=re.I)    # a full name is one role
    text = _TEAMMATES.sub(lambda m: "teammates" if m.group(0)[0] == "a" else "Teammates", text)
    text = _REPO_REPO.sub(r"\1", text)
    while _REPO_REPEAT.search(text):                                   # "(a private repo, a private repo, the team repo)"
        text = _REPO_REPEAT.sub(r"\1", text)
    return text


def rewrite_region(text):
    """Attribution, the reuse record's name, and fixed phrases, in any comment, docstring or prose."""
    text = _REUSE_LINK.sub(r"\1", text)
    text = _REUSE_NAME.sub("the reuse record", text)
    text = _TEAM_BRANCH.sub(lambda m: m.group(1) + m.group(2) + "a", text)
    text = _REPO_AND_PATH.sub(_repo, text)                      # a private repo's name (and a path in it) is a plain phrase, also in a comment
    for rule, replacement in ATTRIBUTION_RULES + SCRUB_PHRASES:
        text = rule.sub(replacement, text)
    return _QUOTED_PAIR.sub("", text)


def names_listed_word(line, comment_in_fixture=False):
    """Whether a line still holds a listed word (a person, a private repo, a hosting detail, and 'internal only' in fixtures)."""
    return bool(_PERSON_WORD.search(line) or _TEAM_BRANCH.search(line) or _NAME_PAIR.search(line)
                or _REPO_WORD.search(line) or _HOST_WORD.search(line)
                or (comment_in_fixture and _INTERNAL_ONLY.search(line)))


# comment and docstring spans, per language: [(start, end)] of the text of each, in characters, without the comment marker of
# a block comment or the quotes of a docstring (a dropped line keeps them, so the file stays valid). Code is never inside one.
MAX_LOGICAL_TOKENS = 50000      # tokens in one statement; Python 3.9's parser crashes the whole program (not an error) on an expression about 250,000 levels deep


def _runaway_statement(text):
    import tokenize
    count = 0
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
                count = 0
            elif tok.type not in (tokenize.NL, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT):
                count += 1
                if count > MAX_LOGICAL_TOKENS:
                    return True
    except (tokenize.TokenError, SyntaxError, ValueError):
        return False
    return False


def python_spans(text):
    import ast
    import tokenize
    lines = text.splitlines(True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    spans = []
    in_statement = 0
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                spans.append((starts[tok.start[0] - 1] + tok.start[1], starts[tok.end[0] - 1] + tok.end[1]))
            elif tok.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
                in_statement = 0
            elif tok.type not in (tokenize.NL, tokenize.INDENT, tokenize.DEDENT):
                in_statement += 1
                if in_statement > MAX_LOGICAL_TOKENS:
                    return None                                  # too deep to parse safely: the file is left as it is and the guard decides
        tree = ast.parse(text)
    except (SyntaxError, ValueError, tokenize.TokenError, RecursionError, MemoryError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                def char_at(row, col):                        # ast columns are UTF-8 bytes
                    return starts[row - 1] + len(lines[row - 1].encode("utf-8")[:col].decode("utf-8"))
                a, b = char_at(first.lineno, first.col_offset), char_at(first.end_lineno, first.end_col_offset)
                m = re.match(r"[A-Za-z]{0,2}(\"\"\"|'''|\"|')", text[a:b])
                if m and text[a:b].endswith(m.group(1)) and len(text[a:b]) >= m.end() + len(m.group(1)):
                    spans.append((a + m.end(), b - len(m.group(1))))
    return sorted(set(spans))


def js_spans(text):
    """Comments in JavaScript, found with a small lexer: strings, template strings (with nested ${...}) and regular expression
    literals are skipped. A block comment is given without its /* and */, a line comment with its //."""
    spans, i, n, last = [], 0, len(text), ""
    stack = []                       # for ${ ... } inside a template string: the brace depth to come back to
    depth = 0
    regex_after = ("", "(", ",", "=", ":", "[", "!", "&", "|", "?", "{", "}", ";", "+", "-", "*", "%", "<", ">", "~", "^")
    keywords = {"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case", "do", "else", "yield",
                "await"}                              # a regular expression can follow each of these
    condition_words = {"if", "while", "for", "with"}  # ... and a ) that closes their condition
    parens, word_before_paren = [], ""                # for each open (: whether it opened an if / while / for / with condition

    def template(start):             # from just after a backtick or a closing brace: to the end or to the next ${
        j = start
        while j < n:
            if text[j] == "\\":
                j += 2
            elif text[j] == "`":
                return j + 1, False
            elif text[j] == "$" and text[j + 1:j + 2] == "{":
                return j + 2, True
            else:
                j += 1
        return n, False

    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            spans.append((i, j))
            i = j
        elif c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            spans.append((i + 2, n if j < 0 else j))
            i = n if j < 0 else j + 2
        elif c in "'\"":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            i, last = j + 1, c
        elif c == "`":
            i, opened = template(i + 1)
            if opened:
                stack.append(depth)
                depth = 0
            last = "`"
        elif c == "{":
            depth += 1
            i, last = i + 1, c
        elif c == "}":
            if stack and depth == 0:
                depth = stack.pop()
                i, opened = template(i + 1)
                if opened:
                    stack.append(depth)
                    depth = 0
                last = "`"
            else:
                depth -= 1
                i, last = i + 1, c
        elif c == "(":
            parens.append(word_before_paren in condition_words)
            i, last = i + 1, c
        elif c == ")":
            last = ")c" if parens and parens.pop() else c            # ")c": the end of an if / while / for / with condition
            i += 1
        elif c.isalpha() or c in "_$":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] in "_$"):
                j += 1
            word = text[i:j]
            word_before_paren = word
            last = "" if word in keywords else "a"
            i = j
        elif c == "/" and (last in regex_after or last == ")c"):
            j, in_class = i + 1, False                                      # a regular expression literal
            while j < n and text[j] != "\n":
                if text[j] == "\\":
                    j += 1
                elif text[j] == "[":
                    in_class = True
                elif text[j] == "]":
                    in_class = False
                elif text[j] == "/" and not in_class:
                    break
                j += 1
            i, last = j + 1, "/"
        else:
            if not c.isspace():
                last = c
                word_before_paren = ""
            i += 1
    return spans


def css_spans(text):
    return [(m.start() + 2, m.end() - 2) for m in re.finditer(r"/\*.*?\*/", text, re.S)]


def html_spans(text):
    return [(m.start() + 4, m.end() - 3) for m in re.finditer(r"<!--.*?-->", text, re.S)]


def sql_spans(text):
    spans = []
    for m in re.finditer(r"'(?:[^']|'')*'|(--[^\n]*)|/\*.*?\*/", text, re.S):
        if m.group(1):
            spans.append((m.start(), m.end()))
        elif m.group(0).startswith("/*"):
            spans.append((m.start() + 2, m.end() - 2))
    return spans


def yaml_spans(text):
    spans, pos = [], 0
    for line in text.splitlines(True):
        quote = None
        for k, ch in enumerate(line):
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "'\"":
                quote = ch
            elif ch == "#" and (k == 0 or line[k - 1] in " \t"):
                spans.append((pos + k, pos + len(line.rstrip("\n"))))
                break
        pos += len(line)
    return spans


SCRUB_NAMES = {".gitignore": "yaml", ".gitattributes": "yaml"}        # files with # comments and no suffix


def scrub_kind(path):
    return SCRUB_NAMES.get(posixpath.basename(path)) or SCRUB_SUFFIXES.get(posixpath.splitext(path)[1].lower())


def scrub_spans(path, text):
    """[(start, end)] of the text that is comment, docstring or prose in this file; None when the file is code only or unreadable here."""
    kind = scrub_kind(path)
    if kind == "prose":
        return [(0, len(text))]
    return {"python": python_spans, "js": js_spans, "css": css_spans, "sql": sql_spans, "yaml": yaml_spans,
            "html": html_spans}.get(kind, lambda _t: None)(text)


MAX_LINE = 5000                         # a line longer than this is not read by the prose rules (they can take a minute on one): it is left as it is. Two table rows of the reuse record are over 2,000
MAX_SCRUB_LINES = 20000                 # a file the scrub reads is refused (by file number) over this many lines or MAX_SCRUB_BYTES: the rules take time in proportion to both. The largest real file is about a tenth of each
MAX_SCRUB_BYTES = 1024 * 1024
_LONG_MARK = "\0long%d\0"                # stands in for such a line while the rules run (a file with a NUL is never scrubbed, so this cannot clash)


def _mask_long_lines(region):
    """(the region with each line over MAX_LINE characters replaced by a marker, those lines). The guard still reads them in full,
    so a listed word on one is refused by file number."""
    if len(region) <= MAX_LINE:
        return region, []
    long_lines, lines = [], []
    for line in region.split("\n"):
        if len(line) > MAX_LINE:
            lines.append(_LONG_MARK % len(long_lines))
            long_lines.append(line)
        else:
            lines.append(line)
    return "\n".join(lines), long_lines


_SPACE_RUN = re.compile(r"\s{64,}")
_SPACE_MARK = "\0space%d\0"


def _mask_space_runs(region):
    """(the region with each run of 64 or more white-space characters replaced by a marker, those runs). The rules read white
    space with \\s, which costs time in proportion to the run for every start point; no real match is that wide, and a listed
    word next to a run that was left alone is still refused by the guard."""
    runs = []

    def mark(match):
        runs.append(match.group(0))
        return _SPACE_MARK % (len(runs) - 1)
    return _SPACE_RUN.sub(mark, region), runs


def _too_long_to_scrub(path, data):
    if scrub_kind(path) is None or b"\0" in data:
        return False
    return len(data) > MAX_SCRUB_BYTES or data.count(b"\n") > MAX_SCRUB_LINES


def scrub_limit_findings(entries, blobs):
    """['file #N: ...'] for each file the scrub would read that is too long to read in a safe time. scrub() leaves such a file alone."""
    return ["file #%d: too long to scrub safely (over %d lines or %d KB)" % (e.index, MAX_SCRUB_LINES, MAX_SCRUB_BYTES // 1024)
            for e, data in zip(entries, blobs) if _too_long_to_scrub(e.path, data)]


def scrub_text(path, text, known=None):
    kind = scrub_kind(path)
    spans = scrub_spans(path, text)
    if spans is None:
        return text
    fixture = path.startswith("tests/") or kind == "sql"
    out, pos = [], 0
    for a, b in spans:
        if a < pos:
            continue
        out.append(text[pos:a])
        region, long_lines = _mask_long_lines(text[a:b])
        region, space_runs = _mask_space_runs(region)
        region = rewrite_region(region)
        if kind == "prose":
            region = prose_rewrite(region)
            if known is not None:
                region = dangling_links(path, region, known)
        region = "\n".join(DROPPED if names_listed_word(line, fixture) else line for line in region.split("\n"))
        for number, run in enumerate(space_runs):
            region = region.replace(_SPACE_MARK % number, run)
        for number, line in enumerate(long_lines):
            region = region.replace(_LONG_MARK % number, line)
        out.append(region)
        pos = b
    out.append(text[pos:])
    lines = "".join(out).split("\n")
    kept = []
    for line in lines:
        if DROPPED in line:
            line = line.replace(DROPPED, "").rstrip()
            if not line.strip() or re.fullmatch(r"\s*(?:/\*\s*\*/|<!--\s*-->)", line):    # nothing left but an empty comment
                continue
        kept.append(line)
    return "\n".join(kept)


def dangling_links(path, text, known):
    """A [text](relative path) link to a file that is not in the snapshot becomes its text."""
    def fix(match):
        target = match.group(2).split("#")[0].strip()
        if not target or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith("/"):
            return match.group(0)
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
        return match.group(0) if resolved in known else match.group(1)
    return re.sub(r"\[([^\[\]]{0,1000})\]\(([^)\s]{0,1000})[^)]{0,1000}\)", fix, text)    # bounded, and a "[" ends the text: a run of "[" took time in proportion to its square


def scrub(path, data, known=None):
    """The bytes of a file as the public copy gets them. Text files named by SCRUB_SUFFIXES are read as UTF-8 (a file that
    is not valid UTF-8, or has NULs, is left alone: the guard decides). The same input always gives the same output."""
    if scrub_kind(path) is None or b"\0" in data or _too_long_to_scrub(path, data):
        return data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    new = scrub_text(path, text, known)
    if path.lower().endswith(".py") and new != text and not _parses(new):
        return data                                                    # the scrub broke the file: keep the original, and the guard decides
    if scrub_kind(path) == "js" and new != text and not _js_same_code(text, new):
        return data                                                    # the scrub changed code (or esbuild could not check): keep the original; the guard refuses a listed word left in it
    return new.encode("utf-8")


def _minified(source):
    """The pinned esbuild's minified form of a JavaScript or JSX source (comments are gone), or None if esbuild is missing or fails."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            import esbuild
        finally:
            sys.path.pop(0)
        done = esbuild.run(["--minify", "--loader=jsx", "--legal-comments=none"], input=source.encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except Exception:                                  # missing binary, no network on first use, a timeout: nothing can be proved
        return None
    return done.stdout if done.returncode == 0 else None


def _js_same_code(before, after):
    """True when the pinned esbuild reads both sources as the same code (only comments differ). Regular expression or division,
    JSX text or comment: esbuild decides, so the scrub never has to guess."""
    a = _minified(before)
    return a is not None and a == _minified(after)


def _parses(source):
    import ast
    try:
        ast.parse(source)
        return True
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return False


def git_blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def scrub_entries(entries, blobs):
    """(entries, blobs, how many files changed) with every file scrubbed; each Entry carries the new size and blob id."""
    known = {e.path for e in entries}
    out_entries, out_blobs, changed = [], [], 0
    for e, data in zip(entries, blobs):
        new = scrub(e.path, data, known)
        if new != data:
            changed += 1
            e = Entry(e.index, e.mode, git_blob_sha(new), len(new), e.path)
        out_entries.append(e)
        out_blobs.append(new)
    return out_entries, out_blobs, changed


# the guard: any listed word left anywhere
_INVISIBLE = re.compile("[\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u3164\ufe00-\ufe0f\uffa0\U000e0100-\U000e01ef]")
_TAGS = re.compile(r"<[^<>]{0,500}>")      # bounded, and it stops at the next "<": a run of "<" with no ">" took time in proportion to its square
_ESCAPES = re.compile(r"\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})|&#x?[0-9a-fA-F]+;?")


def _decoded(text):
    """The text, and what it reads as with entities, percent-encoding and \\uXXXX / \\xNN escapes decoded (up to three layers)."""
    out, seen = [text], text
    for _ in range(3):
        step = urllib.parse.unquote(html.unescape(seen))
        step = _ESCAPES.sub(lambda m: chr(int(m.group(1) or m.group(2), 16)) if (m.group(1) or m.group(2)) else m.group(0), step)
        if step == seen:
            break
        out.append(step)
        seen = step
    return out


def _spellings(text):
    """The ways one text can be read: as it is, decoded, with compatibility forms folded (NFKC: full-width and styled letters,
    ligatures), with every format character and invisible mark taken out (zero-width, soft hyphen, bidi marks, joiners, variation
    selectors, the combining grapheme joiner), and with markup tags removed (a name split over a .docx's runs)."""
    found = []
    for base in _decoded(text):
        for form in (base, unicodedata.normalize("NFKC", base)):
            bare = _INVISIBLE.sub("", "".join(c for c in form if unicodedata.category(c) != "Cf"))
            found += [form, bare, _TAGS.sub("", bare), _TAGS.sub("", form)]
    return list(dict.fromkeys(found))


def _forms_of(data):
    forms = [data.decode("utf-8", "replace")]
    for raw in text_forms(data)[1:]:
        forms.append(raw.decode("utf-8", "replace"))
    if b"\0" in data:
        forms.append(data.replace(b"\0", b"").decode("utf-8", "replace"))
    return [spelling for f in forms for spelling in _spellings(f)]


def listed_word_counts(text):
    """{'people': n, 'repo': n, 'host': n, 'capitalised': {word: n}}: how many of each kind of listed word are in the text."""
    capitalised = {}
    for found in _PERSON_CAP.findall(text):
        word = re.sub(r"(?:'s|’s)$", "", found)
        capitalised[word] = capitalised.get(word, 0) + 1
    return {"people": len(_PERSON_ANY.findall(text)) + len(_TEAM_BRANCH.findall(text)) + len(_NAME_PAIR.findall(text)), "capitalised": capitalised,
            "repo": len(_REPO_WORD.findall(text)), "host": len(_HOST_WORD.findall(text))}


def guard_kinds(path, data):
    """Kinds of listed word in one file's bytes (not zips): ["a person's name", ...]."""
    allowed = GUARD_ALLOWED.get(path, ({}, ""))[0]
    kinds = set()
    for form in _forms_of(data):
        counts = listed_word_counts(form)
        over = [word for word, n in counts["capitalised"].items() if n > allowed.get(word, 0)]
        mixed = path in TEMPLATE_NAME_PATHS and b"\0" in data and reveal("Onaare") in counts["capitalised"]   # mixed encodings: no per-form count is safe
        if path in TEMPLATE_NAME_PATHS and not counts["people"] and (over or mixed) and all(w == reveal("Onaare") for w in (over or [reveal("Onaare")])):
            kinds.add(TEMPLATE_LIMIT_KIND)   # only the template word, over its one use: say so, never print it
        elif counts["people"] or over:
            kinds.add("a person's name")
        if counts["repo"]:
            kinds.add("a private repo or board name")
        if counts["host"]:
            kinds.add("a hosting detail")
    return kinds


def guard_findings(entries, blobs):
    """['file #N: a person's name', 'file #N part #J.K: ...'] for every listed word left in a path, a file, a part of a zip
    (to MAX_ZIP_DEPTH levels), text saved as UTF-16 or a file with NULs. Never the word."""
    found = []
    for e, data in zip(entries, blobs):
        if guard_kinds("", e.path.encode("utf-8", "surrogateescape")):
            found.append("file #%d: a listed word in its path" % e.index)
        for kind in sorted(guard_kinds(e.path, data)):
            found.append("file #%d: %s" % (e.index, kind))
        if data[:2] == b"PK":
            found += ["file #%d %s" % (e.index, f) for f in zip_findings(data, "", 1, [MAX_ZIP_BYTES],
                                                                           lambda part: guard_kinds("", part), True)]
    return found


def load_guard():
    """tests/test_no_real_names.py of THIS checkout: the same check the tests run."""
    sys.dont_write_bytecode = True
    if str(GUARD_DIR) not in sys.path:
        sys.path.insert(0, str(GUARD_DIR))
    return importlib.import_module("test_no_real_names")


# --- the checks ------------------------------------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.rows = []

    def add(self, name, status, *details):
        self.rows.append((name, status, [d for d in details if d]))

    def status(self, name):
        return next((s for n, s, _ in self.rows if n == name), None)

    @property
    def ok(self):
        return all(s != REFUSED for _, s, _ in self.rows)

    def lines(self):
        out = []
        for name, status, details in self.rows:
            out.append("  %-8s %s" % (status, name))
            out += ["           " + d for d in details]
        return out



def check_identity(values, report):
    """The author name, the author email and the commit message are read with the scrub's own list of listed words (a person, a
    private repo, a hosting detail), whatever else checks them later. Refused by flag number, never by value; True when all are clear."""
    bad = ["flag #%d (author name, author email, commit message, in that order) holds a listed word" % n
           for n, value in enumerate(values, 1)
           if value and (names_listed_word(value) or guard_kinds("", value.encode("utf-8", "surrogateescape")))]
    report.add("author and message are clear", REFUSED if bad else PASS, *bad)
    return not bad


def check_branch(args, report):
    branch = args.branch
    if branch == MAIN_BRANCH:
        if args.publish_main:
            report.add("branch name", PASS, "main (the published copy), as --publish-main says")
        else:
            report.add("branch name", REFUSED, "publishing to main needs --publish-main")
    elif branch == DEFAULT_BRANCH or RELEASE_BRANCH.fullmatch(branch):
        report.add("branch name", PASS, branch)
    else:
        report.add("branch name", REFUSED, "only clark-public, release-X.Y.Z (digits only) and main are allowed")


def check_target(args, repo, report, is_public):
    """Runs every target check; returns the parsed target when it is safe to talk to, else None."""
    raw = args.target or DEFAULT_PUBLIC_REMOTE
    if not raw:
        report.add("a target was given", REFUSED, "say where to publish with --target (nothing is built in)")
        return None
    report.add("a target was given", PASS)
    env = neutral_env(tempfile.gettempdir(), "x", "x@x", 0)
    try:
        target = parse_target(raw, base=os.getcwd())
    except TargetError as err:
        report.add("target is a plain address", REFUSED, str(err))
        return None
    if target[3]:
        report.add("target has no password in it", REFUSED, "use ssh keys or gh's sign-in, never a password in the URL")
        return None
    report.add("target has no password in it", PASS)
    safe = True
    same = private_matches(target, repo, env)
    if same:
        report.add("target is not the private repo", REFUSED, "it is the same as " + same[0])
        return None
    if not text(git(["-C", str(repo), "config", "--get", "remote.origin.url"], env=env)):
        report.add("target is not the private repo", REFUSED, "this repo has no origin to compare with, so it can't be proved")
        return None
    report.add("target is not the private repo", PASS, "different from origin, by address and by name")
    if target[0] == "local":
        if args.allow_local_target:
            report.add("target is a public repo", PASS, "a local folder, allowed by --allow-local-target (not checked)")
        else:
            report.add("target is a public repo", REFUSED, "a folder can't be shown to be public; --allow-local-target is for tests")
            safe = False
    elif target[1] != "github.com":
        report.add("target is a public repo", REFUSED, "only GitHub repos can be checked (with gh)")
        safe = False
    else:
        owner, _, name = target[2].partition("/")
        if "/" in name or not owner or not name:
            report.add("target is a public repo", REFUSED, "the address is not <owner>/<repo>")
            safe = False
        elif is_public(owner, name):
            report.add("target is a public repo", PASS, "gh says the repo is not private")
        else:
            report.add("target is a public repo", REFUSED, "gh could not show that the repo is public")
            safe = False
    hits = max(rewrite_rules_hit(c, net_env(), tempfile.gettempdir()) for c in {raw.strip(), target_arg(args, target)})
    if hits:
        report.add("no git rule rewrites the target", REFUSED,
                   "%d 'insteadOf' rule(s) in your git settings match the target and could send the push elsewhere" % hits)
        safe = False
    else:
        report.add("no git rule rewrites the target", PASS)
    return target if safe else None


def resolve_ref(repo, ref, env, report):
    if not ref or ref.startswith("-") or not re.fullmatch(r"[A-Za-z0-9._/@^~{}-]+", ref):
        report.add("ref exists", REFUSED, "that is not a tag or ref name")
        return None
    proc = git(["-C", str(repo), "rev-parse", "--verify", "-q", ref + "^{commit}"], env=env)
    if proc.returncode != 0:
        report.add("ref exists", REFUSED, "git does not know that tag or ref")
        return None
    sha = text(proc)
    report.add("ref exists", PASS, "commit " + sha[:7])
    return sha


def check_on_main(repo, sha, main_ref, env, report):
    proc = git(["-C", str(repo), "rev-parse", "--verify", "-q", main_ref + "^{commit}"], env=env)
    if proc.returncode != 0:
        report.add("ref is on main", REFUSED, "can't find %s here (run: git fetch origin)" % main_ref)
        return
    ancestor = git(["-C", str(repo), "merge-base", "--is-ancestor", sha, text(proc)], env=env).returncode
    if ancestor == 0:
        report.add("ref is on main", PASS, "reachable from " + main_ref)
    else:
        report.add("ref is on main", REFUSED, "only a commit that is on %s can be published" % main_ref if ancestor == 1
                   else "git could not compare the ref with " + main_ref)


def default_run_tests(python, checkout):
    """(passed, Python version) for dev/run_tests.py run by `python` in `checkout`."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        version = subprocess.run([python, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"], env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False).stdout.decode().strip()
        proc = subprocess.run([python, "dev/run_tests.py"], cwd=str(checkout), env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, check=False, timeout=TEST_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    lines = proc.stdout.decode("utf-8", "replace").strip().splitlines()
    return proc.returncode == 0, version or (lines[-1] if lines else "")


KEYCHAIN_FLAGS = ("--use-mock-keychain", "--password-store=basic")
DASHES = "-" * 2                               # built, not written: tests/test_chrome_launch.py treats a literal launch flag here as a Chrome launch
CHROME_LAUNCH = (DASHES + "headless", DASHES + "remote-debugging")
LAUNCH_TOKEN = re.compile(r"(?<![\w-])" + DASHES + r"(?:headless|remote-debugging)\b")
SCRIPT_SUFFIXES = (".py", ".sh", ".bash", ".zsh", ".command")
CHROME_FOLDERS = ("tests", "dev", "system", "src")


def _flag_present(flag, strings):
    return any(t == flag or re.search(r"(?<![\w-])" + re.escape(flag) + r"(?![\w=-])", t) for t in strings)


def chrome_rule_problems(checkout):
    """(launching, unreadable): the place numbers of files in the snapshot's tests/, dev/, system/ and src/ that start Chrome
    without both keychain flags, and of files that could not be read or parsed, so the rule could not be applied. A launch is
    a string that holds a launch flag, inside a Python string (docstrings apart) or anywhere in a shell script, so
    "google-chrome <flag> ..." counts as much as a list of arguments. Such a tree must not have its tests run here: a headless
    Chrome with a throwaway profile asks the macOS login Keychain, and a "Keychain Not Found" dialog appears on the person's
    screen (#104). The shared helper run_support.py holds the flags; a file that goes through the helper's command builder has no launch flag.
    Places are numbered in the order the files are scanned."""
    import ast
    bad, unreadable = [], []
    n = 0
    for base in CHROME_FOLDERS:
        found = sorted(p for p in (Path(checkout) / base).rglob("*") if p.suffix in SCRIPT_SUFFIXES and p.is_file())
        for path in found:
            if {"vendor", "node_modules", "__pycache__"} & set(path.parts):
                continue
            n += 1
            try:
                source = path.read_text(encoding="utf-8")
                if path.suffix == ".py":
                    if _runaway_statement(source):
                        raise MemoryError()                     # a statement too deep to parse safely is unreadable here
                    tree = ast.parse(source)
                    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                                  if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                                  and node.body and isinstance(node.body[0], ast.Expr)
                                  and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str)}
                    strings = [x.value for x in ast.walk(tree)
                               if isinstance(x, ast.Constant) and isinstance(x.value, str) and id(x) not in docstrings]
                else:
                    strings = [source]
            except (OSError, SyntaxError, ValueError, RecursionError, MemoryError):   # includes bad UTF-8 and NUL bytes
                unreadable.append(n)
                continue
            launches = any(LAUNCH_TOKEN.search(t) for t in strings)
            if launches and not all(_flag_present(flag, strings) for flag in KEYCHAIN_FLAGS):
                bad.append(n)
    return bad, unreadable


def chrome_without_keychain_flags(checkout):
    """The place numbers (see chrome_rule_problems) of files that start Chrome without the keychain flags, or that can't be read."""
    bad, unreadable = chrome_rule_problems(checkout)
    return sorted(bad + unreadable)


def check_tests(args, checkout, run_tests, report):
    if args.dry_run and not args.with_tests:
        report.add("tests pass on both Pythons", SKIPPED, "dry run: add --with-tests to run them")
        return
    bad, unreadable = chrome_rule_problems(checkout) if checkout is not None else ([], [])
    if bad or unreadable:
        report.add("tests pass on both Pythons", REFUSED,
                   *(["%d file(s) in the snapshot start Chrome without the keychain flags (--use-mock-keychain and "
                      "--password-store=basic), so its tests are not run: merge the Chrome fix (#104) first" % len(bad)] if bad else []),
                   *(["%d script(s) in the snapshot could not be read or parsed, so the Chrome keychain rule could not be "
                      "applied and its tests are not run" % len(unreadable)] if unreadable else []))
        return
    pythons = [p for p in args.pythons.split(",") if p]
    if len(pythons) < MIN_PYTHON_VERSIONS:
        report.add("tests pass on both Pythons", REFUSED, "name at least two Pythons (the oldest and the newest)")
        return
    versions, failed = set(), []
    for py in pythons:
        ok, version = run_tests(py, checkout)
        if ok:
            versions.add(version)
        else:
            failed.append(py)
    if failed:
        report.add("tests pass on both Pythons", REFUSED, "the tests failed or did not run with: " + ", ".join(failed))
    elif len(versions) < MIN_PYTHON_VERSIONS:
        report.add("tests pass on both Pythons", REFUSED, "those are the same Python version (%s)" % ", ".join(sorted(versions)))
    else:
        report.add("tests pass on both Pythons", PASS, "Python " + ", ".join(sorted(versions)))


# --- the run ---------------------------------------------------------------------------------------------------------

def run(args, *, repo=REPO, run_tests=None, is_public=None, banned=None, main_ref=DEFAULT_MAIN_REF, out=print, now=None):
    """Everything. Returns the exit code: 0 published, nothing to publish, or a dry run that passed; 1 refused or failed."""
    def say(line=""):
        out(hide_password(line))

    tmp = Path(tempfile.mkdtemp(prefix="clark-publish-"))
    before = _catch_signals()
    try:
        return _run(args, Path(repo), tmp, run_tests or default_run_tests, is_public or gh_is_public, banned, main_ref,
                    say, now)
    except (TargetError, Unsafe) as err:
        say("REFUSED: %s. Nothing was pushed." % err)
        return 1
    except OSError as err:                       # never a traceback, and never a file name (it could be a real name)
        say("REFUSED: the computer could not do a file step (%s). Nothing was pushed." % (err.strerror or "disk error"))
        return 1
    except (MemoryError, RecursionError):        # a file that is too big or too deeply nested for the computer to read: never a traceback
        say("REFUSED: a file was too large or too deeply nested to read. Nothing was pushed.")
        return 1
    except KeyboardInterrupt:                    # Ctrl-C, or SIGTERM / SIGHUP turned into the same thing
        say("INTERRUPTED: stopped before the end. The temporary folder is removed. If it was pushing, look at the target "
            "branch to see whether the push arrived.")
        return 130
    finally:
        quiet = _catch_signals(ignore=True)      # a second signal (Ctrl-C too) must not stop the clean-up...
        _remove_tree(tmp)                        # ...and one that gets in first only makes it start again
        _restore_signals({**quiet, **before})


SIGNALS = tuple(getattr(signal, n) for n in ("SIGTERM", "SIGHUP") if hasattr(signal, n))
CLEANUP_SIGNALS = SIGNALS + (signal.SIGINT,)         # all three are held off while the temporary folder is removed
CLEANUP_TRIES = 5


def _raise_interrupt(_signum, _frame):
    raise KeyboardInterrupt()


def _catch_signals(ignore=False):
    """Make SIGTERM and SIGHUP behave like Ctrl-C (so the `finally` clean-up runs), or ignore them; returns the old handlers."""
    old = {}
    for sig in CLEANUP_SIGNALS if ignore else SIGNALS:
        try:
            old[sig] = signal.signal(sig, signal.SIG_IGN if ignore else _raise_interrupt)
        except (ValueError, OSError):            # not the main thread: leave the handlers alone
            pass
    return old


def _restore_signals(old):
    for sig, handler in old.items():
        try:
            signal.signal(sig, handler if handler is not None else signal.SIG_DFL)
        except (ValueError, OSError):
            pass


def _remove_tree(tmp):
    """Remove the temporary folder. A signal that arrives before they are held off (or one that cannot be held off) stops
    the removal part way, so it is started again: the folder is never left behind by a second Ctrl-C."""
    for _ in range(CLEANUP_TRIES):
        try:
            shutil.rmtree(str(tmp), onerror=_make_writable)
            return
        except KeyboardInterrupt:
            continue
        except OSError:
            break
    shutil.rmtree(str(tmp), ignore_errors=True)


def _make_writable(func, path, _exc):
    os.chmod(path, stat.S_IRWXU)
    func(path)


def commit_message(args, sha):
    """`clark <ref> (<short sha>)`: the ref as typed only when it is plain and holds no listed word, else the short sha alone."""
    plain = re.fullmatch(r"[A-Za-z0-9._/-]+", args.ref) and not guard_kinds("", args.ref.encode("utf-8"))   # a listed word in a ref name never reaches the public log
    label = args.ref if plain else sha[:7]
    return "clark %s (%s)" % (label, sha[:7])


def _run(args, repo, tmp, run_tests, is_public, banned, main_ref, say, now):
    when = int(now() if now else time.time())
    name, email = args.author_name or AUTHOR_NAME, args.author_email or AUTHOR_EMAIL
    report = Report()
    if not check_identity((args.author_name, args.author_email, commit_message(args, "0" * 40) if args.ref else ""), report):
        name, email = AUTHOR_NAME, AUTHOR_EMAIL              # a refused identity is never used, so it is never printed or committed
    env = neutral_env(tmp / "home", name, email, when)
    (tmp / "home").mkdir()
    cfg = safe_config(name, email)
    say("publish_public: %s to branch %s" % ("dry run" if args.dry_run else "publishing", args.branch))

    check_branch(args, report)
    target = check_target(args, repo, report, is_public)
    sha = resolve_ref(repo, args.ref, env, report)
    if sha:
        check_on_main(repo, sha, main_ref, env, report)

    kept, blobs, files_shown, tree, parent, unchanged = [], [], None, None, None, False
    snap = tmp / "snapshot"
    message = commit_message(args, sha) if sha else ""
    if sha:
        entries = use_public_readme(list_tree(repo, sha, env), report)
        kept, private_ok = apply_exclusions(entries, report) if entries is not None else ([], False)
        content_ok = entries is not None and private_ok and check_files(kept, report)
    else:
        content_ok = False

    if content_ok:
        blobs = read_blobs(repo, kept, env)
        kept, blobs, scrubbed = scrub_entries(kept, blobs)         # in the snapshot only: the private repo is never edited
        report.add("private names scrubbed", PASS, "%d file(s) rewritten in the snapshot; the private repo is untouched" % scrubbed)
        left = guard_findings(kept, blobs)
        left = scrub_limit_findings(kept, blobs) + left
        report.add("no private names left", REFUSED if left else PASS, *left)
        found = secret_findings(kept, blobs)
        report.add("no secrets", REFUSED if found else PASS, *found)
        tree = write_repo(snap, kept, blobs, env, cfg)
        by_path = {e.path: e.index for e in kept}
        listed = git(["-C", str(snap), "ls-files", "-z"], env=env).stdout.decode("utf-8", "surrogateescape").split("\0")
        place = {i: p for i, p in enumerate([x for x in listed if x], 1)}
        check_nothing_excluded(snap, tree, kept, env, report)

        if target is not None:                                  # the new commit goes on top of the present tip
            parent = fetch_tip(args, snap, target_arg(args, target), net_env(), report)
        commit = make_commit(snap, tree, parent, message, cfg, env)
        if commit:
            git(["-C", str(snap), "update-ref", "HEAD", commit], env=env)
            commit_text = git(["-C", str(snap), "cat-file", "commit", commit], env=env).stdout.decode("utf-8", "replace")
            ident = "%s <%s> %d +0000" % (name, email, when)
            expected = "tree %s\n%sauthor %s\ncommitter %s\n\n%s\n" % (
                tree, "parent %s\n" % parent if parent else "", ident, ident, message)
            fresh = git(["-C", str(snap), "rev-list", "--count", commit] + (["^" + parent] if parent else []), env=env)
            if commit_text != expected or text(fresh) != "1":
                report.add("one neutral commit", REFUSED, "the commit is not exactly one new commit by %s at UTC" % name)
            else:
                report.add("one neutral commit", PASS, "author and committer %s <%s>, UTC, nothing from your git settings" % (name, email))
            check_names(snap, commit_text, by_path, place, banned, report)
            unchanged = bool(parent) and text(git(["-C", str(snap), "rev-parse", "HEAD^{tree}"], env=env)) == text(
                git(["-C", str(snap), "rev-parse", parent + "^{tree}"], env=env))
        else:
            report.add("one neutral commit", REFUSED, "git could not make the commit")
            report.add("no real names", SKIPPED, "not run: there is no commit")
        shown = names_clear(report)
        files_shown = [(by_path[p], p if shown and not guard_kinds("", p.encode("utf-8", "surrogateescape")) else None)
                       for p in place.values()]
    elif sha:
        for check in ("private names scrubbed", "no private names left", "no secrets", "snapshot holds nothing excluded", "one neutral commit", "no real names"):
            report.add(check, SKIPPED, "not run: fix the refusal above first")

    # the slow check last, and only when nothing has refused and there is something to publish
    if not (sha and report.ok and tree):
        report.add("tests pass on both Pythons", SKIPPED, "not run: another check has already refused")
    elif unchanged:
        report.add("tests pass on both Pythons", SKIPPED, "not needed: nothing new to publish")
    elif args.dry_run and not args.with_tests:
        check_tests(args, None, run_tests, report)
    else:
        tests_dir = tmp / "tests-checkout"
        tests_tree = write_repo(tests_dir, kept, blobs, env, cfg)
        git(["-C", str(tests_dir), "update-ref", "HEAD", make_commit(tests_dir, tests_tree, None, "tests", cfg, env)], env=env)
        check_tests(args, tests_dir, run_tests, report)

    # --- what it found
    shown = names_clear(report)
    if files_shown is not None:
        say("Snapshot: %d file(s)%s" % (len(files_shown), "" if shown else " (listed by number only: a name check has not passed)"))
        for index, path in files_shown:
            say("  #%d %s" % (index, path) if path else "  #%d" % index)
    say("Checks:")
    for line in report.lines():
        say(line)
    if tree:
        known = report.status("target can be read") == PASS
        say("Would commit: parent %s, author and committer %s <%s>, message: %s" % (
            (parent[:7] if parent else "none (a new branch)") if known else "unknown (target not read)",
            name, email, message if shown else "(shown once the name check passes)"))

    if not report.ok:
        say("REFUSED: nothing was pushed. See the REFUSED lines above%s." % (
            "" if args.dry_run else "; docs/publishing-the-public-copy.md says what to do"))
        return 1
    if unchanged:
        say("Nothing to publish: branch %s already holds exactly this snapshot." % args.branch)
        return 0
    if args.dry_run:
        say("Dry run: every check that ran passed. Nothing was pushed.")
        return 0
    return push(args, snap, target_arg(args, target), say)


def names_clear(report):
    """Whether both name checks have passed: only then may a path or the commit message be printed."""
    return report.status("no real names") == PASS and report.status("no private names left") == PASS


def apply_exclusions(entries, report):
    """(the entries that stay after the exclusion list, whether nothing private was tracked); says how many each rule took out.
    The notes files are expected in the private repo and are removed quietly. Anything tracked under comms/ or
    system/branding/ is not: those folders must never be in git at all, so it is a refusal (by place number only)."""
    removed, kept, wrong = {}, [], []
    for e in entries:
        rule = is_excluded(e.path)
        if rule:
            removed[rule] = removed.get(rule, 0) + 1
            if rule in PRIVATE_FOLDERS:
                wrong.append("file #%d is tracked under comms/ or system/branding/, which must stay out of git: "
                             "find out why in the private repo" % e.index)
        else:
            kept.append(e)
    # counts only: a rule or a path here can hold a person's name, and this line is printed before the name checks have run
    notes = ["%d file(s) taken out by %d rule(s) on the exclusion list" % (sum(removed.values()), len(removed))]
    report.add("internal notes removed", PASS, *(notes if removed else ["nothing on the exclusion list is tracked"]))
    report.add("nothing private is tracked", REFUSED if wrong else PASS, *wrong)
    return kept, not wrong


def parent_folders(path):
    """The folders above a path, folded the same way as the names are compared."""
    parts = unicodedata.normalize("NFC", path).casefold().split("/")
    return ["/".join(parts[:i]) for i in range(1, len(parts))]


def check_files(kept, report):
    """Plain files with safe, distinct paths and none over 5 MB; True when the content checks can go on."""
    folded = {}
    for e in kept:
        folded.setdefault(unicodedata.normalize("NFC", e.path).casefold(), []).append(e)
    clashes = [e for e in kept if any(parent in folded for parent in parent_folders(e.path))]
    problems = (["file #%d is a link or submodule" % e.index for e in kept if e.mode not in FILE_MODES]
                + ["file #%d has an unsafe path" % e.index for e in kept if unsafe_path(e.path)]
                + ["file #%d differs only by letter case from another" % v[1].index for v in folded.values() if len(v) > 1]
                + ["file #%d has the same name as a folder holding other files" % e.index for e in clashes])
    report.add("snapshot is plain files", REFUSED if problems else PASS, *problems)
    big = ["file #%d is over 5 MB" % e.index for e in kept if e.size > MAX_BYTES or e.size < 0]
    report.add("no file over 5 MB", REFUSED if big else PASS, *big)
    return not problems and not big


def check_nothing_excluded(snap, tree, kept, env, report):
    listing = git(["-C", str(snap), "ls-tree", "-r", "-z", "--name-only", tree], env=env).stdout
    paths = [p for p in listing.decode("utf-8", "surrogateescape").split("\0") if p]
    left = [p for p in paths if is_excluded(p)]
    if left or len(paths) != len(kept):
        report.add("snapshot holds nothing excluded", REFUSED,
                   "%d excluded path(s) remain, or the snapshot is not the ref's files" % len(left))
    else:
        report.add("snapshot holds nothing excluded", PASS, "%d files, none on the exclusion list" % len(kept))


def make_commit(snap, tree, parent, message, cfg, env):
    """The one commit (plumbing, so no setting can change it); its sha, or '' when git failed."""
    proc = git(cfg + ["-C", str(snap), "commit-tree", tree] + (["-p", parent] if parent else []) + ["-m", message], env=env)
    return text(proc) if proc.returncode == 0 else ""


def check_names(snap, commit_text, by_path, place, banned, report):
    """The real name guard over the snapshot's files and paths, and over the commit's author, committer and message."""
    guard = load_guard()
    banned = guard.BANNED if banned is None else banned
    if not banned:
        report.add("no real names", REFUSED, "the banned-name list is empty, so nothing can be checked")
        return
    hits = guard.findings(snap, banned) + guard.text_hits("the commit (author, committer, message)", commit_text, banned)
    hits = [re.sub(r"tracked file #(\d+)", lambda m: "file #%s" % by_path.get(place.get(int(m.group(1))), "?"), h) for h in hits]
    report.add("no real names", REFUSED if hits else PASS, *hits)


def target_arg(args, target):
    """What git is given: a folder as its full path, an address as typed."""
    return target[1] if target[0] == "local" else (args.target or DEFAULT_PUBLIC_REMOTE).strip()


def remote_tip(snap, target, branch, env):
    """(tip sha or None when the branch does not exist, error text or None)."""
    proc = git(["-C", str(snap), "ls-remote", "--heads", target, "refs/heads/" + branch], env=env)
    if proc.returncode != 0:
        return None, "the target could not be reached"
    for rec in text(proc).splitlines():
        sha, _, ref = rec.partition("\t")
        if ref == "refs/heads/" + branch:
            return sha, None
    return None, None


def fetch_tip(args, snap, target, env, report):
    """The public branch's present tip, fetched into the temporary repo; None for a branch that does not exist yet."""
    tip, err = remote_tip(snap, target, args.branch, env)
    if err:
        report.add("target can be read", REFUSED, err)
        return None
    if tip is None:
        report.add("target can be read", PASS, "branch %s does not exist yet: this will create it" % args.branch)
        return None
    proc = git(["-C", str(snap), "fetch", "--no-tags", "--no-recurse-submodules", "-q", target,
                "refs/heads/" + args.branch], env=env)
    got = text(git(["-C", str(snap), "rev-parse", "--verify", "-q", "FETCH_HEAD^{commit}"], env=env))
    if proc.returncode != 0 or got != tip:
        report.add("target can be read", REFUSED, "the branch's tip could not be fetched")
        return None
    report.add("target can be read", PASS, "branch %s is at %s" % (args.branch, tip[:7]))
    return tip


def push_reason(output):
    """A plain sentence for why a push failed, chosen by keyword; none of git's output is repeated."""
    low = output.decode("utf-8", "replace").lower()
    if "non-fast-forward" in low or "fetch first" in low or "stale info" in low:
        return "The branch has moved on since it was read. Run the tool again."
    if any(k in low for k in ("permission", "denied", "authentication", "could not read username", "403", "401")):
        return "The sign-in was refused or has no permission to write there. Check your sign-in (ssh key or gh)."
    if any(k in low for k in ("protected", "declined", "hook", "rejected")):
        return "The target refused the push (a branch rule or a hook there). Look at its settings."
    if any(k in low for k in ("could not resolve", "unable to access", "connection", "timed out", "network")):
        return "The target could not be reached. Check the network and the address."
    return "git gave an error; its output is not shown because it can hold addresses or tokens. Run the push by hand to see it."


def push(args, snap, raw, say):
    """The one push: a plain push of HEAD to the branch. A refusal by the remote (not a fast-forward) ends the run."""
    env = net_env()
    proc = git(["-c", "core.hooksPath=" + os.devnull, "-c", "push.default=nothing", "-C", str(snap), "push", "--porcelain",
                raw, "HEAD:refs/heads/" + args.branch], env=env)
    if proc.returncode != 0:
        # git's own words can hold the address, a token or a name: never print them, only a plain reason
        say("PUSH FAILED: nothing was changed on the target (never forced). %s" % push_reason(proc.stderr + proc.stdout))
        return 1
    tip, err = remote_tip(snap, raw, args.branch, env)
    head = text(git(["-C", str(snap), "rev-parse", "HEAD"], env=env))
    if err or tip != head:
        say("PUSHED, but the branch's tip could not be confirmed as the new commit: look at it by hand.")
        return 1
    say("Published one commit (%s) to branch %s." % (head[:7], args.branch))
    return 0


def parse_args(argv):
    p = argparse.ArgumentParser(prog="publish_public.py", description=__doc__.split("\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ref", help="a tag or ref that is on main")
    p.add_argument("--target", help="the public repo's address (https or ssh); there is no default")
    p.add_argument("--branch", default=DEFAULT_BRANCH, help="clark-public (default), release-X.Y.Z, or main")
    p.add_argument("--publish-main", action="store_true", help="allow --branch main")
    p.add_argument("--dry-run", action="store_true", help="check and show everything; push nothing")
    p.add_argument("--with-tests", action="store_true", help="with --dry-run: also run the tests on both Pythons")
    p.add_argument("--pythons", default=",".join(DEFAULT_PYTHONS), help="comma-separated interpreters for the tests")
    p.add_argument("--allow-local-target", action="store_true", help="for tests: --target may be a folder")
    p.add_argument("--author-name", help="replace the neutral author name (not for normal use)")
    p.add_argument("--author-email", help="replace the neutral author email (not for normal use)")
    return p.parse_args(argv)


def main(argv=None):
    return run(parse_args(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
