"""Put a mixed-version clark folder right, but only after the person types y (row 1017, CMD 088).

clark.command runs this file by path (python3 -I .app/src/clark/same_version_heal.py <clark folder> <data folder>) when a
terminal is attached, before the refusal of row 760. It is a script of its own: standard library only, Python 3.9, no clark
import, and the folder it was started in or its own folder never leads the path, so an older flat clark (src, vendor or clark
beside .app) cannot shadow anything it uses.

What it does, in order, and only when the folder is mixed:
  1. says which files differ from clark-release.json (up to three names, then a count) and which older folders are in the way;
  2. asks once whether to put back the files that differ, from a clark-*-mac.zip in Downloads or in the folder above, or from a
     set-aside .clark-old-* / .clark-update-* folder, and puts back a file ONLY if its SHA-256 is the one the record lists;
  3. asks once whether to move src, vendor and clark (the names an older flat version leaves beside .app) into one folder
     called "clark older files", by rename; nothing is deleted;
  4. when the folder is still mixed, or the person said no, or there was nothing right to put back: says the existing sentence
     of same_version.MESSAGE, then that the clark folder is open for the person, and returns 3; clark.command then opens the
     folder (a program start is only platform.py's, and this file imports nothing of clark's).
It changes something only after a typed y (any other key, an empty answer or no terminal is a no), never downloads, and never
touches the data folder, system, docker or any other name: only .app/*, clark.command and the three stale names (a stale name that is the data folder, or holds it, is left where it is; and with a
clark open on the data folder, no file is put back). An unfinished
update (the marker in the data folder) means it waits: the launcher finishes that first.

Exit codes: 0 = nothing for it to do, or the folder is right now (clark.command goes on); 3 = it has said the fallback (clark.command opens the folder and stops). Anything else (a crash) lets clark.command go on as it did before this file existed.
"""
import os
import sys

# Before any other import: drop the script's own folder and the folder it was started in from the path (python3 -I does this
# already; this keeps it true when the file is run any other way).
_HERE = os.path.dirname(os.path.abspath(__file__))
_DROP = {os.path.realpath(_HERE), os.path.realpath(os.getcwd())}
# realpath on both sides: a link to either folder (a symlinked clark folder or working folder, or /tmp and /var on a Mac, which
# are links to /private/...) cannot lead the path either, however the path entry and the folder are spelled.
sys.path[:] = [p for p in sys.path if os.path.realpath(p or os.getcwd()) not in _DROP]

import hashlib  # noqa: E402
import json  # noqa: E402
import zipfile  # noqa: E402
from pathlib import Path, PurePosixPath  # noqa: E402

# The words. EXISTING is same_version.MESSAGE (a test keeps the two equal).
EXISTING = ("These clark files are not all from the same version, so clark will not start. "
            "Move the clark folder aside (rename it) and unzip the download again.")
OPEN_LINE = "The clark folder is open for you."
COULD_NOT = "Clark could not put every file back."
FOLDER = "clark older files"

MANIFEST = "clark-release.json"
HIDDEN = ".app"
LAUNCHER = "clark.command"
STALE = ("src", "vendor", "clark")                 # the names an older flat version leaves beside .app
MAX_MANIFEST = 4 * 1024 * 1024
MAX_FILE = 64 * 1024 * 1024
FALLBACK = 3


def marker_path(data):
    """Where an unfinished update leaves its marker (the very path update_helper.marker_path gives)."""
    return Path(data) / "updates" / ".installing.json"


def _safe(name):
    """Whether a record's name stays inside the folder: relative, no .. part, no backslash, no drive letter, no NUL."""
    parts = PurePosixPath(name).parts
    return (bool(parts) and not PurePosixPath(name).is_absolute() and ".." not in parts and "\\" not in name
            and "\0" not in name and ":" not in parts[0])


def _wanted(name):
    return name == LAUNCHER or name.startswith(HIDDEN + "/")


def read_record(top):
    """The record's `files` ({name: entry}), None when there is no record; ValueError when it can't be read."""
    record = Path(top) / MANIFEST
    if not record.exists():
        return None
    try:
        if record.stat().st_size > MAX_MANIFEST:
            raise ValueError("record too large")
        files = json.loads(record.read_text(encoding="utf-8"))["files"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise ValueError("record")
    if not isinstance(files, dict):
        raise ValueError("record")
    for name, entry in files.items():
        if not isinstance(name, str) or not _safe(name) or not isinstance(entry, dict):
            raise ValueError("record")
        size, digest = entry.get("size"), entry.get("sha256")
        if not (isinstance(size, int) and not isinstance(size, bool) and isinstance(digest, str)):
            raise ValueError("record")
    return files


def _same(path, entry):
    """Whether the file at `path` has the size and SHA-256 `entry` records (the size first: most changes stop there)."""
    if not path.is_file() or path.stat().st_size != entry["size"]:
        return False
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest() == entry["sha256"]


def differing(top, files):
    """The program files (.app/*, clark.command) that are missing or differ from the record, sorted, as the record spells them."""
    top = Path(top)
    out = []
    for name in sorted(files):
        if _wanted(name):
            try:
                same = _same(top / name, files[name])
            except OSError:
                same = False
            if not same:
                out.append(name)
    return out


def _holds_data(top, name, data):
    """Whether the person's data folder is `name` beside .app, or is inside it (a relative `data` means from the clark folder,
    as clark.command's cd makes it). Compared by realpath on both sides, so a link or /var against /private/var cannot hide it."""
    if not data:
        return False
    mine = os.path.realpath(os.path.join(str(top), name))
    there = os.path.realpath(os.path.join(str(top), str(data)))
    return there == mine or there.startswith(mine.rstrip(os.sep) + os.sep)


def stale_names(top, data=None):
    """Which of src, vendor and clark are beside .app (a link counts: it is as much in the way). A name that is the data folder
    (or holds it) is not listed: moving it would move the person's data."""
    if _holds_data(top, FOLDER, data):
        return []                                                   # the data folder is called clark older files, or is inside it: nothing moves
    return [n for n in STALE if os.path.lexists(os.path.join(str(top), n)) and not _holds_data(top, n, data)]


def server_running(data):
    """Whether a clark has the data folder open: its lock file (platform.LOCK_NAME) is held by another process. Looked at
    without creating or writing anything; no lock file is no server. A lock that cannot be looked at counts as running."""
    if not data:
        return False
    try:
        import fcntl
    except ImportError:
        return False                                                # no file lock here (Windows): nothing to check
    try:
        fd = os.open(os.path.join(str(data), ".clark-lock"), os.O_RDONLY)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return True
    finally:
        os.close(fd)                                                # closing drops a lock this call just took
    return False


# --- where the right copies may be ---------------------------------------------------------------------------------------

def _shown(path, home):
    text = str(path)
    h = str(home)
    if h and (text == h or text.startswith(h + os.sep)):
        return "~" + text[len(h):]
    return text


class _Zip:
    def __init__(self, path, place):
        self.zip, self.place = zipfile.ZipFile(str(path)), place

    def get(self, name, entry):
        try:
            info = self.zip.getinfo("clark/" + name)
        except KeyError:
            return None
        if info.is_dir() or info.file_size != entry["size"] or info.file_size > MAX_FILE:
            return None
        data = self.zip.read(info)
        return data if hashlib.sha256(data).hexdigest() == entry["sha256"] else None

    def close(self):
        self.zip.close()


class _Folder:
    def __init__(self, path, place):
        self.path, self.place = Path(path), place

    def get(self, name, entry):
        path = self.path / name
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size != entry["size"] or entry["size"] > MAX_FILE:
                return None
            data = path.read_bytes()
        except OSError:
            return None
        return data if hashlib.sha256(data).hexdigest() == entry["sha256"] else None

    def close(self):
        pass


def _newest(paths):
    def mtime(p):
        try:
            return p.stat().st_mtime
        except OSError:
            return 0
    return sorted(paths, key=lambda p: (mtime(p), p.name), reverse=True)


def sources(top, home):
    """The places the right copies may be: zips named clark-*-mac.zip in Downloads and in the folder above, then set-aside
    folders in the clark folder. Newest first. Opened here, closed by the caller."""
    top = Path(top)
    found, seen = [], set()
    zips = []
    for folder in (Path(home) / "Downloads", top.parent):
        try:
            zips += [p for p in folder.glob("clark-*-mac.zip") if p.is_file() and not p.is_symlink()]
        except OSError:
            pass
    for path in _newest(zips):
        real = os.path.realpath(str(path))
        if real in seen:
            continue
        seen.add(real)
        try:
            found.append(_Zip(path, _shown(path.parent, home)))
        except (OSError, zipfile.BadZipFile):
            continue
    try:
        folders = [p for pat in (".clark-old-*", ".clark-update-*") for p in top.glob(pat) if p.is_dir() and not p.is_symlink()]
    except OSError:
        folders = []
    for path in _newest(folders):
        found.append(_Folder(path, path.name))
    return found


def find_copies(top, names, files, home):
    """{name: (bytes, place)} for each of `names` that a source holds with the SHA-256 the record lists."""
    found = {}
    providers = sources(top, home)
    try:
        for name in names:
            for provider in providers:
                try:
                    data = provider.get(name, files[name])
                except (OSError, zipfile.BadZipFile, RuntimeError, EOFError):
                    data = None
                if data is not None:
                    found[name] = (data, provider.place)
                    break
    finally:
        for provider in providers:
            provider.close()
    return found


# --- changing the folder (only after a y) -------------------------------------------------------------------------------

def _linked(top, rel):
    """Whether any part of top/rel below top is a link (a restored file never goes through one)."""
    here = Path(top)
    for part in PurePosixPath(rel).parts[:-1]:
        here = here / part
        if here.is_symlink():
            return True
    return False


def put_back(top, copies, files, data=None):
    """Write each copy beside where it belongs (a temporary name in the same folder), then rename it over the file. Returns how many.
    With a clark open on `data`, nothing is written (0)."""
    top, count = Path(top), 0
    if server_running(data):
        return 0
    for name, (data, _) in sorted(copies.items()):
        dest = top / name
        if _linked(top, name):
            continue
        tmp = dest.parent / (".clark-heal-%d.tmp" % os.getpid())
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(str(tmp), "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            try:
                mode = int(str(files[name].get("mode", "644")), 8) & 0o777
            except ValueError:
                mode = 0o644
            os.chmod(str(tmp), mode or 0o644)
            os.replace(str(tmp), str(dest))
            count += 1
        except OSError:
            try:
                os.unlink(str(tmp))
            except OSError:
                pass
    return count


def move_stale(top, names, data=None):
    """Rename each of `names` into the one folder "clark older files" beside .app. Returns the names moved. Never deletes."""
    top = Path(top)
    folder = top / FOLDER
    moved = []
    if _holds_data(top, FOLDER, data):
        return moved                                                # that name is the person's data: never move into it
    try:
        folder.mkdir(exist_ok=True)
        if not folder.is_dir() or folder.is_symlink():
            return moved
        for name in names:
            target, n = folder / name, 1
            while os.path.lexists(str(target)):
                n += 1
                target = folder / ("%s-%d" % (name, n))
            os.rename(str(top / name), str(target))
            moved.append(name)
    except OSError:
        pass
    return moved


# --- asking --------------------------------------------------------------------------------------------------------------

def tty_key():
    """One key typed at the terminal; "" when there is no terminal (so no terminal is a no)."""
    try:
        fd = sys.stdin.fileno()
        if not (os.isatty(fd) and os.isatty(sys.stdout.fileno())):
            return ""
        import termios
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] &= ~(termios.ICANON | termios.ECHO)
        new[6][termios.VMIN], new[6][termios.VTIME] = 1, 0
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        try:
            return os.read(fd, 1).decode("utf-8", "ignore")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:  # noqa: BLE001  nothing readable is a no
        return ""


def _terminal():
    try:
        return os.isatty(sys.stdin.fileno()) and os.isatty(sys.stdout.fileno())
    except (OSError, ValueError, AttributeError):
        return False


def run(top, data, key=None, out=None, err=None, home=None, tty=None):
    """Heal the clark folder `top` if it is mixed and the person types y. Returns 0 (go on) or FALLBACK (said and opened)."""
    top = Path(top)
    out, err = out or sys.stdout, err or sys.stderr
    interactive = _terminal() if tty is None else tty
    if not interactive or not (top / HIDDEN).is_dir():
        return 0
    if os.path.lexists(str(marker_path(data))):
        return 0                                                    # an unfinished update: the launcher finishes that first
    key = key or tty_key
    home = home if home is not None else Path.home()

    try:
        files = read_record(top)
    except ValueError:
        files = None                                                # unreadable: only the stale names can be dealt with
    differ = differing(top, files) if files else []
    stale = stale_names(top, data)
    if not differ and not stale:
        return 0

    def say(text, stream=None):
        print(text, file=stream or out, flush=True)

    def ask(text):
        say(text)
        answer = key()
        say("")
        return answer in ("y", "Y")

    def fallback(could_not=False):
        if could_not:
            say(COULD_NOT, err)
        say(EXISTING, err)
        say(OPEN_LINE, err)
        return FALLBACK                                             # clark.command opens the folder (only platform.py starts programs)

    if differ:
        shown = [n[len(HIDDEN) + 1:] if n.startswith(HIDDEN + "/") else n for n in differ]
        line = "These clark files are from different versions: " + ", ".join(shown[:3])
        if len(shown) > 3:
            line += " and %d more" % (len(shown) - 3)
        say(line + ".")
    if stale:
        say("Older clark files are in the way: " + ", ".join(stale) + ".")

    acted, restored, moved = False, 0, False
    if differ and server_running(data):
        return fallback()                                           # clark is open: no file is put back (nothing is written)
    if differ:
        copies = find_copies(top, differ, files, home)
        if copies:
            places = []
            for _, place in (copies[n] for n in sorted(copies)):
                if place not in places:
                    places.append(place)
            if not ask("Clark found the right copies in %s. Put %d files back? Your data is not touched. "
                       "Type y for yes, or any other key for no." % (" and ".join(places), len(copies))):
                return fallback()
            restored, acted = put_back(top, copies, files, data), True
    stale = stale_names(top, data)
    if stale:
        if not ask("Move the older files into a folder called clark older files? Nothing is deleted and your data is not touched. "
                   "Type y for yes, or any other key for no."):
            return fallback()
        moved, acted = bool(move_stale(top, stale, data)), True
    if not acted:
        return fallback()                                           # no right copy and nothing to move

    try:
        left = differing(top, read_record(top) or {})
    except ValueError:
        left = ["record"]
    if left or stale_names(top):                                   # a name that holds the data stays, so clark still would not start
        return fallback(could_not=True)
    if restored:
        say("Done. %d files put back. Starting clark." % restored)
    if moved:
        say("Done. The older files are in clark older files. Starting clark.")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        return 0
    return run(argv[0], argv[1])


if __name__ == "__main__":
    sys.exit(main())
