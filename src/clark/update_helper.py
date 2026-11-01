"""The update helper: swaps clark's own files for the new version's, and puts the old ones back if anything fails.

Standard library only, Python 3.9. It imports nothing from clark (the one lazy exception, in begin(), is the caller's own
check and runs inside the server), because begin() copies it into `<data>/updates/helper-<stamp>/` and it runs from there while
the app folder is being replaced. Beside it begin() puts a copy of platform.py as `clark_platform.py` (platform.py is standard
library only), and the helper loads that copy by its file path. So the helper starts no program itself: the new server and the
health check go through platform.start_detached and platform.run_python_check, the one place for that (tests/test_platform_source.py
still bars subprocess here). The copy is not called platform.py because the folder of a running script comes first on the import
path, and a file of that name would hide Python's own platform module. It is a guarded file (CODEOWNERS and the guarded list in dev/run_tests.py); read it as the riskiest part.

The caller (the server) has already read and hashed the update, checked the app folder, backed up and written the new files
into a staging folder inside the app folder (`.clark-update-<stamp>/`, laid out as the app folder is). The helper:

  begin(...)    the caller's call. Checks the app folder (updates.check_app_folder: no .git, no link, the record, writable) and that
                the update does not have an older data layout than the data, then writes the MARKER `<data>/updates/.installing.json` before anything else
                changes. The marker holds the stamp, the folders, the order of the swap, the server to wait for and a hash of
                every file that is there now. While the marker exists, an update is unfinished.
  run(marker)   the helper itself, started by the server (`update_helper.py --marker FILE`). Steps, in this order, each one a
                point where a test injects a fault or kills the process: ready, wait_server, verify_staged, prepare, then for
                each top-level entry swap:old:<entry> (the old one is renamed into `.clark-old-<stamp>/`) and swap:new:<entry>
                (the staged one is renamed into place), carry, verify_installed, health, start_new, commit. Entries are swapped in
                a fixed order: src, vendor, python, the rest, then the `clark/` stand-in and the launcher files, and the record
                (clark-release.json) last, so the stand-in and launcher stay the old ones until the end.
  rollback      any failed step puts everything back, from what is on disk and not from what was recorded (a crash can fall
                between a rename and the note about it). It is the same code whether it runs after a failure or after a crash,
                so running it twice does no harm. It ends by hashing the old files against the hashes in the marker.
  --finish      `update_helper.py --finish --data FOLDER`, run by the launcher before it asks /health when a marker exists. It
                never goes forward: it stops a new server that was started, puts the old version back, checks it and removes the
                marker. No marker: nothing to do. If the helper itself is still running, it says so and changes nothing.

Anything not in the old or the new release's file list (what the person added) is never removed: it stays where it is, and a
file inside a replaced folder is copied into the new folder (`carry`). `.clark-old-<stamp>/` is kept after a good update and
removed by cleanup_old() once the new version has answered; `update.log` in the updates folder has one line per step, with the
home folder written ~, and is started again past 1 MB.

The things that differ between computers are in one small class, Seams (here the Mac and Linux way): is_link, make_executable,
free_space, helper_python, rename, process_gone, port_free, stop_process, start_server, server_answers, check_install. The
platform module will fill the same names for Windows; tests pass their own. A sentence a person reads never starts with the
product name, and holds no file path except the log's, and none of the words zip, manifest or SHA.
"""
import argparse
import errno
import hashlib
import http.client
import importlib.util
import json
import os
import shutil
import signal
import socket
import stat
import sys
import time
from pathlib import Path

MARKER_NAME = ".installing.json"
PLATFORM_COPY = "clark_platform.py"
HELPER_PREFIX = "helper-"
LOG_NAME = "update.log"
RESULT_NAME = "last-result.json"
UPDATES = "updates"
MANIFEST = "clark-release.json"
OLD_PREFIX = ".clark-old-"
STAGING_PREFIX = ".clark-update-"
LOG_LIMIT = 1024 * 1024
WAIT_CLOSE_SECONDS = 30
WAIT_START_SECONDS = 15
FIRST = ("src", "vendor", "python")
LAST = ("clark", "clark.command", "clark.cmd")
SKIP_DIRS = {"__pycache__"}
SKIP_FILES = {".DS_Store"}
MARKER_VERSION = 1
# The same retry rule as platform.replace_file; a test keeps the two alike (this file imports nothing from clark).
REPLACE_ATTEMPTS = 5
REPLACE_FIRST_WAIT = 0.05
LOCKED = {errno.EACCES, errno.EPERM, errno.EBUSY}
SPACE_MARGIN = 1024 * 1024

# Exit codes of main(): installed or nothing to do; rolled back; not everything could be put back; still running.
OK, ROLLED_BACK, NOT_RESTORED, BUSY = 0, 1, 2, 3

MESSAGES = {
    "installed": "Version {to} is installed. One moment while clark restarts.",
    "rolled_back": "The update didn't install, and version {from_} has been restored. Your projects and settings are safe. {why}",
    "close": "The update couldn't start because clark didn't close in time. Nothing was changed. "
             "Close every clark window, open clark again and try again.",
    "held": "Another program is using one of clark's files, so the update stopped and the old version was put back. "
            "Close other programs, then try again.",
    "space": "There isn't enough room on the disk for this update, so nothing was changed. Free up some space, then try again.",
    "unsafe": "The update has something in it that could change things outside clark's own files, so it wasn't installed. "
              "Download it again from the clark releases page.",
    "damaged": "The update files were not complete, so the update wasn't installed. Download it again, then try again.",
    "no_start": "The new version didn't start. Try again later.",
    "generic": "Try again. If it keeps happening, send the file {log} to the clark team.",
    "not_restored": "The update didn't install, and not everything could be put back yet. Your projects and settings are safe. "
                    "Open clark again to finish putting it back. If that doesn't work, send the file {log} to the clark team.",
    "finished": "The last update stopped part way, so the old version was put back. Your projects and settings are safe. "
                "You can try the update again from Settings.",
    "busy": "An update is still being installed. Wait a minute, then open clark again.",
    "nothing": "No update is waiting to be finished.",
}
WHY = {"close": "close", "held": "held", "space": "space", "unsafe": "unsafe", "damaged": "damaged"}


class StepError(Exception):
    """A step failed. `key` picks the sentence a person reads; the text is for the log."""

    def __init__(self, key, text=""):
        self.key = key
        super().__init__(text or key)


def tilde(text, home=None):
    """`text` with the home folder written ~ wherever it appears (the log never shows the account's folder name)."""
    home = str(Path(home) if home else Path.home()).rstrip("/")
    return str(text).replace(home, "~") if home and home != "~" else str(text)


# --- the things that differ between computers -------------------------------------------------------------------------

def load_platform(folder=None):
    """The copy of platform.py that sits beside this file (clark_platform.py), loaded by its path. In the server's own tree,
    where there is no copy, it is platform.py beside this file. Raises OSError if there is neither."""
    here = Path(folder) if folder else Path(__file__).resolve().parent
    path = here / PLATFORM_COPY
    if not path.is_file():
        path = here / "platform.py"
    spec = importlib.util.spec_from_file_location("clark_platform_copy", str(path))
    if spec is None or spec.loader is None:
        raise OSError(f"{path.name} can't be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Seams:
    """The Mac and Linux way. The guarded platform module fills the same names for Windows; tests override single ones."""

    def __init__(self, sleep=time.sleep, clock=time.monotonic, platform=None):
        self.sleep = sleep
        self.clock = clock
        self._platform = platform

    @property
    def platform(self):
        """The platform functions, loaded the first time they are needed (a test that overrides the seams never loads them)."""
        if self._platform is None:
            self._platform = load_platform()
        return self._platform

    def _on(self):
        return self.platform.WINDOWS if sys.platform == self.platform.WINDOWS else self.platform.MAC     # Linux takes the Mac way

    def is_link(self, path):
        try:
            st = os.lstat(path)
        except OSError:
            return False
        return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & 0x400)

    def make_executable(self, path):
        os.chmod(path, 0o755)

    def free_space(self, path):
        return shutil.disk_usage(str(path)).free

    def helper_python(self):
        return sys.executable

    def rename(self, source, dest):
        os.rename(source, dest)

    def process_gone(self, pid):
        if not pid:
            return True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        return False

    def port_free(self, port):
        if not port:
            return True
        with socket.socket() as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", int(port))) != 0

    def identity(self, pid):
        """Who `pid` is right now: its start time (Linux: /proc; elsewhere `ps`, run through platform.run_python_check so this
        file starts no program). None when there is no such process or it can't be told. A recycled id has another start time."""
        if not pid:
            return None
        try:
            fields = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8", errors="replace").rsplit(")", 1)[1].split()
            return "proc:" + fields[19]
        except (OSError, IndexError, ValueError):
            pass
        code = ("import subprocess, sys\n"
                "r = subprocess.run(['ps', '-o', 'lstart=', '-p', sys.argv[1]], capture_output=True, text=True)\n"
                "sys.stderr.write(r.stdout.strip())\n")
        try:
            status, text = self.platform.run_python_check(self.helper_python(), code, [int(pid)], timeout=20)
        except Exception:                       # a timeout or a missing program: the identity can not be told
            return None
        text = text.strip()
        return "ps:" + text if status == 0 and text else None

    def stop_process(self, pid, ident=None):
        """End a server this helper started (a stopped update never leaves the new one running). Only if the process with this
        id is still the one that was recorded: after a crash or a restart the id may belong to an unrelated program, which is
        left alone (the old server counts as gone). With no recorded identity nothing is signalled."""
        if self.process_gone(pid):
            return
        if not ident or self.identity(pid) != ident:
            return
        os.kill(pid, signal.SIGTERM)
        end = self.clock() + 10
        while not self.process_gone(pid) and self.clock() < end:
            self.sleep(0.2)

    def start_server(self, app_dir, data_dir, port, log_path):
        """Start clark detached from the app folder's own files, as the launcher does. The process id."""
        env = {**os.environ, "CLARK_LAUNCHED": "1", "CLARK_PORT": str(port), "PYTHONPATH": str(Path(app_dir) / "src")}
        process = self.platform.start_detached([self.helper_python(), "-m", "clark", "--data", str(data_dir), "--port", str(port)],
                                               env, log_path, cwd=str(data_dir), on=self._on())
        return process.pid

    def server_answers(self, port, header, mark, timeout=2):
        """Whether clark answers /health on `port` for this data folder (the launcher's rule)."""
        conn = http.client.HTTPConnection("127.0.0.1", int(port), timeout=timeout)
        try:
            conn.request("GET", "/health", headers={header: mark})
            reply = conn.getresponse()
            answer = json.loads(reply.read(65536)) if reply.status == 200 else None
        except (OSError, http.client.HTTPException, ValueError):
            return False
        finally:
            conn.close()
        return isinstance(answer, dict) and answer.get("ok") is True and answer.get("this_data") is True

    def check_install(self, app_dir):
        """The second health check: every module under src/clark imports, in a fresh interpreter run with -I -B. Raises."""
        code = ("import importlib, pkgutil, sys\n"
                "src, vendor = sys.argv[1], sys.argv[2]\n"
                "sys.path[:0] = [src, vendor]\n"
                "import clark\n"
                "for m in pkgutil.iter_modules(clark.__path__):\n"
                "    importlib.import_module('clark.' + m.name)\n")
        app = Path(app_dir)
        status, errors = self.platform.run_python_check(self.helper_python(), code, [app / "src", app / "vendor"], timeout=120)
        if status != 0:
            raise StepError("damaged", "a module does not import: " + errors[-300:])


def rename_with_retry(source, dest, seams, attempts=REPLACE_ATTEMPTS, first_wait=REPLACE_FIRST_WAIT):
    """Rename, retrying a short while when another program holds a file (the rule of platform.replace_file)."""
    wait = first_wait
    for attempt in range(1, attempts + 1):
        try:
            seams.rename(source, dest)
            return
        except OSError as e:
            if e.errno not in LOCKED and not isinstance(e, PermissionError):
                raise
            if attempt == attempts:
                raise
            seams.sleep(wait)
            wait *= 2


# --- small file helpers -----------------------------------------------------------------------------------------------

def write_json(path, doc):
    """Write `doc` so that a reader sees the old file or the new one, never half of either."""
    path = Path(path)
    temp = path.with_name(path.name + ".part")
    data = json.dumps(doc, indent=1, sort_keys=True).encode("utf-8")
    with open(temp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def files_under(base, rel):
    """Every file at or under base/rel as a "/" name relative to base. Links are not followed (a link counts as a file)."""
    top = Path(base) / rel
    if not os.path.lexists(top):
        return []
    if not top.is_dir() or top.is_symlink():
        return [rel]
    found = []
    for folder, dirs, names in os.walk(top, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            if name in SKIP_FILES or name.endswith(".pyc"):
                continue
            found.append(Path(folder, name).relative_to(base).as_posix())
    return sorted(found)


def hash_tree(base, entries):
    """{name: sha256} for every file in the named top-level entries of `base`."""
    out = {}
    for entry in entries:
        for rel in files_under(base, entry):
            out[rel] = sha256_of(Path(base) / rel)
    return out


def updates_dir(data_dir):
    return Path(data_dir) / UPDATES


def marker_path(data_dir):
    return updates_dir(data_dir) / MARKER_NAME


def order_entries(names):
    """The fixed swap order: src, vendor, python, the rest (sorted), the stand-in and launchers, and the record last."""
    names = set(names)
    ordered = [n for n in FIRST if n in names]
    ordered += sorted(n for n in names if n not in FIRST and n not in LAST and n != MANIFEST)
    ordered += [n for n in LAST if n in names]
    return ordered + ([MANIFEST] if MANIFEST in names else [])


def stamp_of(now=None):
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now))


# --- the caller's side ------------------------------------------------------------------------------------------------

def begin(data_dir, app_dir, staging, stamp, from_version, to_version, installed_schema, server_pid, port, mark_header, mark,
          backup_dir="", check=True):
    """Write the marker. Call it with the new files already in `staging` and hashed, and the backup made. Nothing in the app
    folder has changed yet; if this raises, nothing was written. Returns the marker's path.

    It refuses a folder that holds .git, has a link in it, has no record of what it holds or can't be written to, and an update
    whose data layout is older than the data's, with the plain sentences of updates.py (an UpdateError)."""
    app, staging = Path(app_dir), Path(staging)
    if marker_path(data_dir).exists():           # an earlier update is unfinished: its marker holds what to put back, so it is never overwritten
        from clark import updates
        raise updates.UpdateError("unfinished", "a marker is there already")
    if check:
        from clark import updates            # the caller runs inside the server, where it can be imported; run() never does
        updates.check_app_folder(app)
    try:
        new = read_json(staging / MANIFEST)
        old = read_json(app / MANIFEST)
    except (OSError, ValueError):
        raise StepError("damaged", "a record of the files can't be read")
    if check and new.get("schema_version") < installed_schema:
        from clark import updates
        raise updates.UpdateError("newer_data", f"data layout {new.get('schema_version')}, installed {installed_schema}")
    from clark import updates                # the names come from files on disk: '', '..' and absolute names are refused
    updates.check_record_names(old)
    updates.check_record_names(new)
    shipped = sorted(set(old["files"]) | set(new["files"]) | {MANIFEST})
    names = order_entries({rel.split("/")[0] for rel in shipped})
    entries = [{"name": n, "had_old": os.path.lexists(app / n), "in_new": os.path.lexists(staging / n)} for n in names]
    marker = {
        "version": MARKER_VERSION, "stamp": stamp, "app_dir": str(app), "data_dir": str(data_dir), "staging": str(staging),
        "old_dir": str(app / (OLD_PREFIX + stamp)), "backup_dir": str(backup_dir), "from": from_version, "to": to_version,
        "entries": entries, "shipped": shipped, "new_files": {r: row for r, row in new["files"].items()},
        "manifest_sha": sha256_of(staging / MANIFEST), "before": hash_tree(app, names), "server_pid": server_pid, "port": port,
        "mark_header": mark_header, "mark": mark, "phase": "staged", "helper_pid": None, "new_pid": None, "done": [],
    }
    updates_dir(data_dir).mkdir(parents=True, exist_ok=True)
    marker["helper_dir"] = str(copy_helper(data_dir, stamp))
    write_json(marker_path(data_dir), marker)
    return marker_path(data_dir)


def copy_helper(data_dir, stamp, source=None):
    """Put the helper and a copy of platform.py (as clark_platform.py) in `<data>/updates/helper-<stamp>/`, where the helper is
    run from while the app folder is replaced. The folders of earlier updates are removed. The new folder's path."""
    here = Path(source) if source else Path(__file__).resolve().parent
    folder = updates_dir(data_dir) / (HELPER_PREFIX + stamp)
    for old in updates_dir(data_dir).glob(HELPER_PREFIX + "*"):
        if old != folder and old.is_dir() and not old.is_symlink():
            shutil.rmtree(old, ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(here / "update_helper.py", folder / "update_helper.py")
    shutil.copyfile(here / "platform.py", folder / PLATFORM_COPY)
    return folder


def cleanup_old(app_dir):
    """Remove the `.clark-old-*` and `.clark-update-*` folders in the app folder (clark's own, never anything else). The
    server calls it at start when there is no marker and the health check passed. Returns the names removed."""
    gone = []
    for e in sorted(os.scandir(app_dir), key=lambda x: x.name):
        if e.is_dir(follow_symlinks=False) and e.name.startswith((OLD_PREFIX, STAGING_PREFIX)):
            shutil.rmtree(e.path, ignore_errors=True)
            gone.append(e.name)
    return gone


def read_result(data_dir):
    """What the last run or finish ended with: {status, from, to, stamp, message, step, at}, or None."""
    try:
        return read_json(updates_dir(data_dir) / RESULT_NAME)
    except (OSError, ValueError):
        return None


# --- the helper -------------------------------------------------------------------------------------------------------

class Run:
    """One run of the helper, or of --finish: the marker, the log, the seams and the fault hook."""

    def __init__(self, marker_file, seams=None, fault=None, trace=None, home=None):
        self.marker_file = Path(marker_file)
        self.m = read_json(self.marker_file)
        self.seams = seams or Seams()
        self.fault = fault
        self.trace = trace
        self.home = home
        self.app = Path(self.m["app_dir"])
        self.data = Path(self.m["data_dir"])
        self.staging = Path(self.m["staging"])
        self.old = Path(self.m["old_dir"])
        self.log_file = updates_dir(self.data) / LOG_NAME

    def save(self, **changes):
        self.m.update(changes)
        write_json(self.marker_file, self.m)

    def log(self, step, ok, seconds, detail=""):
        line = " ".join(["%s" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), self.m["stamp"],
                         f"{self.m['from']}->{self.m['to']}", step, "ok" if ok else "failed", f"{seconds:.2f}s"])
        if detail:
            line += " " + tilde(detail, self.home).replace("\n", " ")[:300]
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            if self.log_file.exists() and self.log_file.stat().st_size > LOG_LIMIT:
                self.log_file.write_bytes(b"")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass                             # the log never stops an update

    def step(self, name, action, after=True):
        """Run one named step. The fault hook (tests only) is called just before it and, when `after`, just after it and
        before the marker notes it done, which is the window where a crash leaves a rename that nothing recorded."""
        if self.trace is not None:
            self.trace.append(name)
        began = self.seams.clock()
        try:
            if self.fault:
                self.fault(name)
            action()
            if after:
                if self.trace is not None:
                    self.trace.append(name + "+")
                if self.fault:
                    self.fault(name + "+")
            if after:
                self.m["done"].append(name)
                self.save()
        except Exception as e:
            self.log(name, False, self.seams.clock() - began, f"{type(e).__name__}: {e}")
            raise
        self.log(name, True, self.seams.clock() - began)

    def log_line(self):
        return tilde(self.log_file, self.home)

    def message(self, key, why=""):
        return MESSAGES[key].format(**{"to": self.m["to"], "from_": self.m["from"], "log": self.log_line(), "why": why}).rstrip()

    def result(self, status, message, step=""):
        doc = {"status": status, "from": self.m["from"], "to": self.m["to"], "stamp": self.m["stamp"], "message": message,
               "step": step, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        try:
            write_json(updates_dir(self.data) / RESULT_NAME, doc)
        except OSError:
            pass
        return doc

    # --- forward steps ---

    def at(self, name):
        return self.app / name

    def s_ready(self):
        self.save(phase="ready", helper_pid=os.getpid())

    def s_wait_server(self):
        end = self.seams.clock() + WAIT_CLOSE_SECONDS
        while not (self.seams.process_gone(self.m.get("server_pid")) and self.seams.port_free(self.m.get("port"))):
            if self.seams.clock() > end:
                raise StepError("close", "the old server did not stop in time")
            self.seams.sleep(0.2)

    def s_verify_staged(self):
        if sha256_of(self.staging / MANIFEST) != self.m["manifest_sha"]:
            raise StepError("damaged", "the staged record changed")
        wanted = set(self.m["new_files"]) | {MANIFEST}
        names = [e["name"] for e in self.m["entries"] if e["in_new"]]
        have = set()
        for n in names:
            have.update(files_under(self.staging, n))
        if have != wanted:
            raise StepError("damaged", "staged files differ from the list: " + ", ".join(sorted(have ^ wanted)[:5]))
        for rel, row in self.m["new_files"].items():
            if sha256_of(self.staging / rel) != row["sha256"]:
                raise StepError("damaged", f"hash of staged {rel} differs")

    def carried(self):
        """The person's own files inside folders that are about to be replaced: [name]."""
        shipped = set(self.m["shipped"])
        found = []
        for e in self.m["entries"]:
            if e["had_old"]:
                found += [r for r in files_under(self.old, e["name"]) if r not in shipped]
        return found

    def s_prepare(self):
        for e in self.m["entries"]:
            if e["in_new"] and self.seams.is_link(self.staging / e["name"]):
                raise StepError("unsafe", "a link in the staged files")
        for folder, dirs, names in os.walk(self.staging, followlinks=False):
            for n in dirs + names:
                if self.seams.is_link(Path(folder, n)):
                    raise StepError("unsafe", "a link in the staged files")
        for rel, row in self.m["new_files"].items():
            if row.get("mode") == "755":
                self.seams.make_executable(self.staging / rel)
        shipped = set(self.m["shipped"])
        need = SPACE_MARGIN + sum(os.path.getsize(self.app / r) for e in self.m["entries"] if e["had_old"]
                                  for r in files_under(self.app, e["name"]) if r not in shipped)
        if self.seams.free_space(self.app) < need:
            raise StepError("space", f"{need} bytes are needed")
        self.old.mkdir(parents=True, exist_ok=False)

    def move(self, source, dest):
        rename_with_retry(source, dest, self.seams)

    def swap_old(self, name):
        def go():
            self.move(self.at(name), self.old / name)
        return go

    def swap_new(self, name):
        def go():
            self.move(self.staging / name, self.at(name))
        return go

    def s_carry(self):
        for rel in self.carried():
            dest = self.app / rel
            if not os.path.lexists(dest):
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.old / rel, dest)

    def s_verify_installed(self):
        for rel, row in self.m["new_files"].items():
            if not (self.app / rel).is_file() or sha256_of(self.app / rel) != row["sha256"]:
                raise StepError("damaged", f"installed {rel} differs from the list")
        if sha256_of(self.app / MANIFEST) != self.m["manifest_sha"]:
            raise StepError("damaged", "the installed record differs")

    def s_health(self):
        self.seams.check_install(self.app)

    def s_start_new(self):
        self.save(phase="started")
        pid = self.seams.start_server(self.app, self.data, self.m["port"], self.data / "server.log")
        self.save(new_pid=pid, new_ident=self.seams.identity(pid))
        end = self.seams.clock() + WAIT_START_SECONDS
        while not self.seams.server_answers(self.m["port"], self.m["mark_header"], self.m["mark"]):
            if self.seams.clock() > end:
                raise StepError("no_start", "the new version did not answer")
            self.seams.sleep(0.5)

    def s_commit(self):
        self.result("installed", self.message("installed"))
        self.marker_file.unlink()

    def forward(self):
        steps = [("ready", self.s_ready), ("wait_server", self.s_wait_server), ("verify_staged", self.s_verify_staged),
                 ("prepare", self.s_prepare)]
        for e in self.m["entries"]:
            if e["had_old"]:
                steps.append((f"swap:old:{e['name']}", self.swap_old(e["name"])))
            if e["in_new"]:
                steps.append((f"swap:new:{e['name']}", self.swap_new(e["name"])))
        steps += [("carry", self.s_carry), ("verify_installed", self.s_verify_installed), ("health", self.s_health),
                  ("start_new", self.s_start_new)]
        for name, action in steps:
            self.step(name, action)
        self.step("commit", self.s_commit, after=False)       # the marker is gone when it ends: that is the point of no return
        shutil.rmtree(self.staging, ignore_errors=True)       # every entry was renamed out of it; what is left is clark's own

    # --- the way back ---

    def back_entry(self, entry):
        """Put one top-level entry back from what is on disk. Safe to run again."""
        name = entry["name"]
        here, kept, staged = self.at(name), self.old / name, self.staging / name
        if os.path.lexists(kept):                    # the old one was set aside
            if os.path.lexists(here):                # and the new one is in its place: send it back to staging
                if os.path.lexists(staged):
                    raise StepError("damaged", f"{name} is in two places")
                self.move(here, staged)
            self.move(kept, here)
        elif not entry["had_old"] and os.path.lexists(here) and not os.path.lexists(staged):
            self.move(here, staged)                  # an entry only the new version has

    def r_stop_new(self):
        if self.m.get("new_pid"):
            self.seams.stop_process(self.m["new_pid"], self.m.get("new_ident"))

    def r_verify(self):
        names = [e["name"] for e in self.m["entries"]]
        now = hash_tree(self.app, names)
        if now != self.m["before"]:
            odd = sorted(set(now) ^ set(self.m["before"]) | {r for r in now if r in self.m["before"] and now[r] != self.m["before"][r]})
            raise StepError("not_restored", "the old files do not match: " + ", ".join(odd[:5]))

    def r_cleanup(self):
        if self.staging.exists():
            shutil.rmtree(self.staging)
        if self.old.exists():
            try:
                self.old.rmdir()                     # only when empty: anything left in it is kept
            except OSError:
                pass

    def backward(self):
        self.save(phase="rolling_back")
        self.step("rollback:stop_new", self.r_stop_new)
        for e in reversed(self.m["entries"]):
            self.step(f"rollback:{e['name']}", lambda e=e: self.back_entry(e))
        self.step("rollback:verify", self.r_verify)
        self.step("rollback:cleanup", self.r_cleanup)


def failure_key(error):
    if isinstance(error, StepError):
        return error.key
    if isinstance(error, OSError) and (error.errno in LOCKED or isinstance(error, PermissionError)):
        return "held"
    return "generic"


def explain(run, key):
    """The plain sentences for a stopped update whose old version was put back."""
    if key in ("close", "held", "space", "unsafe", "damaged"):
        return run.message(key)
    return run.message("rolled_back", run.message("no_start") if key == "no_start" else run.message("generic"))


def run_update(marker_file, seams=None, fault=None, trace=None, restart=True, home=None):
    """Do the update described by the marker, or put everything back. Returns (exit code, the result dict)."""
    run = Run(marker_file, seams, fault, trace, home)
    try:
        run.forward()
        return OK, read_result(run.data)
    except Exception as e:
        key, text = failure_key(e), f"{type(e).__name__}: {e}"
    return rollback_and_report(run, key, text, restart)


def rollback_and_report(run, key, text, restart=True, finished=False):
    step = run.m["done"][-1] if run.m["done"] else ""
    try:
        run.backward()
    except Exception as e:                           # the way back failed too: keep everything and say so
        run.log("rollback", False, 0, f"{type(e).__name__}: {e}")
        return NOT_RESTORED, run.result("not_restored", run.message("not_restored"), step)
    try:
        run.marker_file.unlink()
    except OSError:
        pass
    message = run.message("finished") if finished else explain(run, key)
    result = run.result("rolled_back", message, step)
    run.log("rolled_back", True, 0, text)
    if restart:
        try:
            run.seams.start_server(run.app, run.data, run.m["port"], run.data / "server.log")
        except Exception as e:                       # the old version is back; the launcher can start it
            run.log("restart_old", False, 0, f"{type(e).__name__}: {e}")
    return ROLLED_BACK, result


def finish(data_dir, seams=None, fault=None, trace=None, home=None):
    """For the launcher, before it asks /health: complete or roll back an unfinished update, always back, never forward.
    Returns (exit code, the result dict or None). Running it again does nothing more."""
    marker_file = marker_path(data_dir)
    if not marker_file.exists():
        return OK, None
    try:
        run = Run(marker_file, seams, fault, trace, home)
    except (OSError, ValueError):
        return NOT_RESTORED, {"status": "not_restored", "message": MESSAGES["not_restored"].format(log=tilde(updates_dir(data_dir) / LOG_NAME, home))}
    pid = run.m.get("helper_pid")
    if pid and pid != os.getpid() and not run.seams.process_gone(pid):
        return BUSY, {"status": "busy", "message": MESSAGES["busy"]}
    return rollback_and_report(run, "finished", "finished after a stop", restart=False, finished=True)


def main(argv=None, seams=None, say=print):
    p = argparse.ArgumentParser(prog="update_helper.py", description="Install or finish a clark update.")
    p.add_argument("--marker", help="run the update this marker describes")
    p.add_argument("--finish", action="store_true", help="finish or undo an update that stopped part way")
    p.add_argument("--data", help="the data folder (with --finish)")
    args = p.parse_args(argv)
    if args.finish:
        if not args.data:
            p.error("--finish needs --data")
        code, result = finish(args.data, seams)
        say(result["message"] if result else MESSAGES["nothing"])
        return code
    if not args.marker:
        p.error("give --marker or --finish")
    code, result = run_update(args.marker, seams)
    say(result["message"] if result else "")
    return code


if __name__ == "__main__":
    sys.exit(main())
