"""#70: what dev/run_tests.py needs to run test files side by side (development only; standard library only).

Copied from creaite v2.6.11 `dev/tools/run_support.py` (BL-246), cut down to clark. Three things:
- **Tiers.** A test file is in the browser tier (it starts Chrome) when it, or a test helper it imports, drives Chrome
  (`chrome_path`, `--headless`, `--remote-debugging`, the Chrome app's name). Everything else is the quick tier. Read from
  the files, never a hand-kept list.
- **Finding Chrome** (`chrome_path`, creaite's `dev/tools/cdp.py`): CLARK_CHROME, then the PATH, then the macOS app.
- **A private temporary folder for each test file.** The runner points the file's TMPDIR at a folder of its own inside
  the run's folder, so everything the file makes lands there. The file's folder is deleted when it ends, pass or fail;
  the run's folder when the run ends or is stopped; and the folder of a run whose process is gone (killed outright) by
  the next run that starts. Each test file runs in a process group of its own, so stopping it stops what it started.

Left out from creaite (its vault and its many browser files need them; clark has neither): the machine-wide Chrome cap
(lock files in /tmp/creaite-chrome-slots), the orphaned live server and Chrome clean-up (`--clean`), the count of vaults
a file leaves behind (BL-172), and proc_guard's watchdog (here a plain process group, stopped by the runner).
"""
import ast
import functools
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
RUN_BASE = Path(os.environ.get("CLARK_RUN_BASE") or
                ("/tmp" if os.name == "posix" and os.access("/tmp", os.W_OK) else tempfile.gettempdir()))
RUN_PREFIX = "clark-test-run-"            # <temp>/clark-test-run-<pid>/<n>/: distinctive, so the clean-up (which deletes every folder
#                                           named <prefix><digits>) can never touch another program's folders; still short enough
#                                           for Chrome's socket path (macOS: 104 characters)
NOT_CHROME = {"run_support", "run_tests"}  # the runner's own tools name Chrome, never drive it
MARKERS = re.compile(r"chrome_path|chrome_command|start_chrome|--headless|--remote-debugging|Google Chrome|chromium|CLARK_CHROME")
MAC_CHROME_PATHS = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]


# ---------- finding Chrome ----------
def chrome_path():
    """The one way the tests find a browser (creaite `cdp.chrome_path`): CLARK_CHROME, then google-chrome / chromium /
    chromium-browser on the PATH (Linux, the CI runner), then the macOS app paths. None if there isn't one; a browser
    test that gets None fails, never skips."""
    env = os.environ.get("CLARK_CHROME")
    if env and os.path.exists(env):
        return env
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return next((p for p in MAC_CHROME_PATHS if os.path.exists(p)), None)


# ---------- starting Chrome (#104) ----------
# Every test that drives a browser starts it through chrome_command() and stop_chrome(). Without --use-mock-keychain and
# --password-store=basic a headless Chrome with a throwaway profile asks the macOS login Keychain for its "Chrome Safe
# Storage" key, and a "Keychain Not Found" dialog appears on the person's screen. tests/test_chrome_launch.py fails if a
# launch skips them.
KEYCHAIN_FLAGS = ("--use-mock-keychain", "--password-store=basic")
# A mouse, as on the Mac: headless Chrome on a Linux box with none reports (hover: none) and (pointer: none), and a page
# then (rightly) shows faint-at-rest controls at full strength. A Mac already reports a mouse, so this changes nothing there.
# The prototype's own runner (system/prototype/run_selftest.py) passes the same flag.
MOUSE_FLAG = "--blink-settings=primaryHoverType=2,availableHoverTypes=2,primaryPointerType=4,availablePointerTypes=4"
_LIVE = set()                       # Chrome processes this process started and has not yet stopped


def chrome_command(chrome, profile, *extra):
    """The command line for a headless Chrome with a fresh `profile`, driven over its DevTools pipe (fds 3 and 4). Both
    keychain flags and the mouse flag are always in it. `extra` flags (e.g. --allow-file-access-from-files) go before the pipe flag."""
    return [str(chrome), "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check", *KEYCHAIN_FLAGS, MOUSE_FLAG, *extra,
            "--remote-debugging-pipe", "about:blank"]


def start_chrome(command, to_r, from_w):
    """Start the Chrome `command` with the DevTools pipe ends (`to_r` is what Chrome reads, `from_w` what it writes) on its
    fds 3 and 4, in THIS process group, so the runner's group kill on a timeout takes it down too, and register it to be
    stopped when this process exits or is told to stop."""
    import subprocess

    def child_fds():                # move both ends clear of 3 and 4 first: os.pipe() may have used them
        a, b = os.dup2(to_r, 100), os.dup2(from_w, 101)
        os.dup2(a, 3)
        os.dup2(b, 4)

    proc = subprocess.Popen(command, preexec_fn=child_fds, close_fds=False, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    _LIVE.add(proc)
    _install_exit_hooks()
    return proc


def stop_chrome(proc):
    """Stop a Chrome started by start_chrome: ask, wait a moment, then kill, and always reap it."""
    _LIVE.discard(proc)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(5)
        except Exception:  # noqa: BLE001  (a timeout: it did not stop when asked)
            proc.kill()
    try:
        proc.wait(5)
    except Exception:  # noqa: BLE001
        pass


PROFILE_PREFIX = "clark-chrome-profile-"


def _check_profile(path):
    """Refuse any path that is not a temporary Chrome profile folder this test run could have made: it must sit directly in
    the system temporary folder, carry the profile prefix, and not be a link. Raises ValueError, naming the path."""
    p = Path(path)
    tmp = Path(tempfile.gettempdir()).resolve()
    if not p.name.startswith(PROFILE_PREFIX) or p.parent.resolve() != tmp:
        raise ValueError(f"remove_profile: {path} is not a {PROFILE_PREFIX}* folder in {tmp}; nothing removed")
    if p.is_symlink():
        raise ValueError(f"remove_profile: {path} is a link, not a folder; nothing removed")
    if p.exists() and not p.is_dir():
        raise ValueError(f"remove_profile: {path} is not a folder; nothing removed")


def remove_profile(path, tries=20, wait=0.25):
    """Delete a Chrome profile folder after Chrome has stopped, and only such a folder (see _check_profile; anything else
    raises ValueError and nothing is removed). Chrome's helper processes (GPU, crashpad, network) can outlive the main
    process by a moment and write into the profile while it is being removed ("Directory not empty: .../Default", seen on
    Linux), so try again a few times; if it still stays, say so on stderr and return False rather than fail the test."""
    _check_profile(path)
    for _ in range(tries):
        try:
            shutil.rmtree(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            time.sleep(wait)
    shutil.rmtree(path, ignore_errors=True)
    if Path(path).exists():
        print(f"remove_profile: could not remove {path} after {tries} tries; remove it by hand", file=sys.stderr)
        return False
    return True


def stop_all_chrome():
    """Stop every Chrome this process started that is still running."""
    for proc in list(_LIVE):
        stop_chrome(proc)


_HOOKED = []


def _install_exit_hooks():
    """On normal exit, and on SIGTERM or SIGINT, stop any Chrome still running, so none outlives its test."""
    if _HOOKED:
        return
    import atexit
    import signal
    import threading
    _HOOKED.append(True)
    atexit.register(stop_all_chrome)
    if threading.current_thread() is not threading.main_thread():
        return
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous = signal.getsignal(sig)

        def handler(signum, frame, previous=previous):
            stop_all_chrome()
            if callable(previous):
                previous(signum, frame)
            else:
                signal.signal(signum, signal.SIG_DFL)
                os.kill(os.getpid(), signum)

        signal.signal(sig, handler)


# ---------- tiers ----------
def _module(here, name):
    """The tests or dev/tools file for module `name`, or None (the standard library, clark's own modules) (creaite)."""
    if name in NOT_CHROME:
        return None
    for d in (here, TOOLS):
        p = d / f"{name}.py"
        if p.exists():
            return p.resolve()
    return None


@functools.lru_cache(maxsize=None)
def _tree(path):
    src = Path(path).read_text(encoding="utf-8", errors="replace")
    return src, ast.parse(src)


@functools.lru_cache(maxsize=None)
def _name_drives_chrome(path, name):
    """True when `name`, defined at the top of test file `path`, drives Chrome: its own code has a marker, or it is a
    class whose base does (followed through the imports) (creaite)."""
    src, tree = _tree(path)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Assign)) and name in _defined(node):
            if MARKERS.search(ast.get_source_segment(src, node) or ""):
                return True
            bases = [b.id for b in getattr(node, "bases", []) if isinstance(b, ast.Name)]
            return any(_imported_drives_chrome(path, b) for b in bases) or any(_name_drives_chrome(path, b) for b in bases)
    return _imported_drives_chrome(path, name)


def _defined(node):
    if isinstance(node, ast.Assign):
        return {t.id for t in node.targets if isinstance(t, ast.Name)}
    return {node.name}


def _imported_drives_chrome(path, name):
    """True when `name` is imported into `path` from a module that makes it drive Chrome (creaite)."""
    _, tree = _tree(path)
    here = Path(path).parent
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and any((a.asname or a.name) == name for a in node.names):
            src_name = next(a.name for a in node.names if (a.asname or a.name) == name)
            p = _module(here, node.module)
            return bool(p) and _from_drives_chrome(str(p), src_name)
    return False


def _from_drives_chrome(path, name):
    """A helper module (not a test file) counts whole; from a test file, only the name taken counts (creaite)."""
    if not Path(path).name.startswith("test_"):
        return _drives_chrome(path)
    return _name_drives_chrome(path, name)


@functools.lru_cache(maxsize=None)
def _drives_chrome(path):
    """True when this file drives Chrome itself, imports a helper module that does, or takes from another test file a
    class or function that does. Importing plain helpers from a browser test file doesn't count (creaite)."""
    src, tree = _tree(path)
    if MARKERS.search(src):
        return True
    here = Path(path).parent
    for node in ast.walk(tree):                 # imports inside a test method count too
        if isinstance(node, ast.Import):
            mods = [(a.name, None) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [(node.module, a.name) for a in node.names]
        else:
            continue
        for mod, name in mods:
            p = _module(here, mod)
            if p is None or p == Path(path).resolve():
                continue
            if name is None or not p.name.startswith("test_"):
                if _drives_chrome(str(p)):
                    return True
            elif _name_drives_chrome(str(p), name):
                return True
    return False


def is_chrome(f):
    """Whether the test file `f` belongs to the browser tier (creaite)."""
    return _drives_chrome(str(Path(f).resolve()))


# ---------- a test file's process group ----------
def spawn(cmd, **kw):
    """Popen `cmd` in a process group of its own, so `stop` ends it and everything it started (creaite proc_guard.spawn,
    without the watchdog)."""
    if os.name == "posix":
        kw["start_new_session"] = True
    else:
        kw["creationflags"] = kw.get("creationflags", 0) | subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(cmd, **kw)


def stop(p, grace=2):
    """End `p` and its process group: SIGTERM, then SIGKILL after `grace` seconds. Safe to call twice (creaite
    proc_guard.stop). The group is signalled even when `p` itself has ended, for what it left running."""
    if os.name != "posix":
        if p.poll() is None:
            p.kill()
        return
    _signal_group(p.pid, signal.SIGTERM)
    end = time.time() + grace
    while p.poll() is None and time.time() < end:
        time.sleep(0.05)
    _signal_group(p.pid, signal.SIGKILL)
    if p.poll() is None:
        p.wait()


def _signal_group(pgid, sig):
    try:
        os.killpg(pgid, sig)
    except OSError:
        pass                              # gone already


# ---------- private temporary folders ----------
def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:               # someone else's process: alive
        return True
    return True


def stale_folders():
    """The folders of earlier runs whose process has gone (creaite, the run folders only)."""
    found = []
    for d in RUN_BASE.glob(f"{RUN_PREFIX}[0-9]*"):
        pid = d.name[len(RUN_PREFIX):]
        if d.is_dir() and pid.isdigit() and not _alive(int(pid)):
            found.append(d)
    return found


def clean(say=print):
    """At the start of every run: remove the folders of runs that were killed outright. Returns how many (creaite
    `clean`, folders only). POSIX only: on Windows os.kill(pid, 0) would end the process."""
    if os.name != "posix":
        return 0
    folders = stale_folders()
    for d in folders:
        shutil.rmtree(d, ignore_errors=True)
    if folders:
        say(f"Cleaned up after earlier runs: {len(folders)} test folder{'s' if len(folders) != 1 else ''}.")
    return len(folders)


class RunDir:
    """This run's folder (<temp>/clark-test-run-<pid>) with one numbered folder per test file (creaite)."""

    def __init__(self):
        self.root = RUN_BASE / f"{RUN_PREFIX}{os.getpid()}"
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True)
        self.count = 0
        self.lock = threading.Lock()      # files start from several threads

    def for_file(self):
        """A new empty folder for one test file's TMPDIR."""
        with self.lock:
            self.count += 1
            d = self.root / str(self.count)
        d.mkdir()
        return d

    @staticmethod
    def finish(d):
        """Remove a test file's folder."""
        shutil.rmtree(d, ignore_errors=True)

    def close(self):
        """Remove the whole run folder."""
        shutil.rmtree(self.root, ignore_errors=True)
