"""Everything that differs between Mac and Windows, in one place (#56).

clark runs on macOS first, built ready for Windows ("start with mac we can follow with windows but
ensure when we build for mac we make allowances for the future"). Only the Mac branch is written; each Windows branch
raises NotBuiltYet. No other module may start a program, call osascript or ctypes, or name a system folder: a source test
(tests/test_platform_source.py) fails if one does. See docs/handoff/portability-and-sharing.md.

Known gap: Windows has no data-folder lock yet (hold_data_lock checks nothing there), so two clarks can open one folder.

Standard library only, Python 3.9.
"""
import errno
import getpass
import os
import re
import secrets
import select
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

try:
    import fcntl               # the Mac's and Linux's file lock; there is none on Windows
except ImportError:
    fcntl = None

MAC = "darwin"
WINDOWS = "win32"
MAX_PATH = 260                  # Windows' default limit on a whole path, counted with its ending NUL
MAX_NAME = 120                  # clark keeps every file name it makes this short or shorter
RESERVED_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
                  *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10)),
                  *(f"{d}{n}" for d in ("COM", "LPT") for n in "\u00b9\u00b2\u00b3")}     # COM¹ COM² COM³ LPT¹ LPT² LPT³
REPLACE_ATTEMPTS = 5            # tries of os.replace before a locked file is reported
REPLACE_FIRST_WAIT = 0.05       # seconds; doubled after each failed try (0.05 + 0.1 + 0.2 + 0.4 = 0.75 s at most)
LOCKED = {errno.EACCES, errno.EPERM, errno.EBUSY}
NO_HARD_LINKS = {errno.EPERM, errno.EXDEV, errno.ENOTSUP, errno.ENOSYS}     # a disk (or network share) that can't link a file to a second name
CANCELLED = "-128"              # osascript's "User canceled." error number


class PlatformError(RuntimeError):
    """Something the system refused, in words a person can act on."""


class NotBuiltYet(PlatformError, NotImplementedError):
    """This system's branch isn't written yet (Windows follows the Mac)."""


def system():
    """The system clark is running on: MAC, WINDOWS or another sys.platform value."""
    return sys.platform


def container_mode():
    """item 427: True only when CLARK_CONTAINER=1 is set (by docker/compose.yaml) AND this really is a container (Docker's
    /.dockerenv or Podman's /run/.containerenv exists). Never true by the setting alone, or by a marker file alone."""
    return os.environ.get("CLARK_CONTAINER") == "1" and (os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv"))


def container_host_in_onedrive(environ=None):
    """item 427: inside the shipped container, the Mac folder that is shared in as the data folder, named by the compose file in
    CLARK_DATA_SOURCE, as a Path when it is in OneDrive (a part of the path is OneDrive's own folder, `OneDrive`, `OneDrive - <name>`
    or `OneDrive-<name>`, case ignored), else None. Never outside a container. Without that variable nothing is known, so nothing is
    refused here; the compose file always sets it. This reads a name, not the disk: it refuses a harmless folder that is merely named like OneDrive (safe), and it cannot see a
    link with another name that points into OneDrive (a data-safety limit; the Mac-side starter is where links are resolved)."""
    if not container_mode():
        return None
    host = (os.environ if environ is None else environ).get("CLARK_DATA_SOURCE")
    if not host:
        return None
    path = Path(host)
    for i, part in enumerate(path.parts):
        if part.lower().startswith("onedrive"):
            return Path(*path.parts[:i + 1])
    return None


# The one command a person types in Terminal, in the unzipped clark folder, to run clark on the Mac itself (docs: README.md and
# START-HERE.md; the launcher is clark.command). The Docker front only serves the page; what needs the Mac needs this server.
TERMINAL_COMMAND = "bash clark.command"


def needs_mac_words():
    """The one sentence every refusal says when clark runs in Docker (item 1100): what needs the Mac, and the exact command to
    paste in Terminal. Every route that meets a Mac-only refusal takes its words from here, never from its own text."""
    return f"This needs clark to run on the Mac itself; start it from Terminal: {TERMINAL_COMMAND}"


def refusal_words(error, fallback):
    """The words a person sees for a PlatformError `error`: the needs-the-Mac sentence when this system's branch is not there
    (NotBuiltYet), else `fallback`. Never a class name, and never the system's own text."""
    return str(error) if isinstance(error, NotBuiltYet) else fallback


def _only_mac(what, on=None):
    """Raise NotBuiltYet unless `on` (default: this system) is the Mac."""
    on = on or system()
    if on != MAC:
        if on == "linux" and container_mode():          # item 1100: said in the words of the person who started Docker
            raise NotBuiltYet(needs_mac_words())
        raise NotBuiltYet(f"{what} on {'Windows' if on == WINDOWS else on} is not built yet: clark runs on macOS for now")


# Who

def login_name():
    """The login name of the person at this machine: `by_user` for what they change in the report, until Settings has a
    profile that overrides it (#65). Never an email address. A system that can't say gives "This computer"."""
    try:
        name = getpass.getuser()
    except (KeyError, OSError, ImportError):
        name = ""
    return str(name).strip() or "This computer"


# Folders

def data_dir(home=None, on=None):
    """Where clark keeps its database and settings: ~/Library/Application Support/clark/ on the Mac. Not created here."""
    _only_mac("The data folder", on)
    return Path(home or Path.home()) / "Library" / "Application Support" / "clark"


def downloads_dir(home=None, on=None):
    """The Downloads folder, where a downloaded update is looked for: ~/Downloads on the Mac. Only read, never written."""
    _only_mac("The Downloads folder", on)
    return Path(home or Path.home()) / "Downloads"


def log_dir(home=None, on=None):
    """Where clark writes its daily log: ~/Library/Logs/clark/ on the Mac (#110). Not created here."""
    _only_mac("The log folder", on)
    return Path(home or Path.home()) / "Library" / "Logs" / "clark"


def log_folder(data=None, home=None, on=None):
    """The one place the daily log lives, for the log writer and the Settings card alike (issue 742). With a data folder other
    than clark's own default one (--data), the log goes inside it: <data>/logs. With no data folder, or the default one (the
    launcher and the updater always pass --data, even for a normal install), it stays log_dir(): ~/Library/Logs/clark/.
    The data folder is resolved first (.. and links), so the answer is always below the folder itself; a logs entry that is a
    link leading out of it is refused (PlatformError). Not created here."""
    if data is None:
        return log_dir(home, on)
    folder = Path(data).expanduser().resolve()
    try:
        default = data_dir(home, on).resolve()
    except PlatformError:                    # not the Mac (the container): there is no default folder, so any --data is explicit
        default = None
    if folder == default:
        return log_dir(home, on)
    logs = folder / "logs"
    if logs.is_symlink() and logs.resolve().parent != folder:
        raise PlatformError(f"{shown(logs)} is a shortcut to somewhere else. Replace it with a real folder, then try again.")
    return logs


def onedrive_roots(home=None, on=None):
    """The OneDrive folders on this machine, as suggestions only (the user still picks a folder): the OneDrive app's
    ~/Library/CloudStorage/OneDrive-<name>/ folders, and the older app's ~/OneDrive*/ folders. Sorted; may be empty.
    item 427: inside the shipped container (Linux and container_mode()) there is no OneDrive app to find, so the answer is an
    empty list. This is the one place Linux is let through: outside a container, Linux still raises NotBuiltYet. The cost is
    that the OneDrive refusal on the shared data folder cannot work in there; the Mac-side starter must check it first."""
    if (on or system()) == "linux" and container_mode():
        return []
    _only_mac("Finding OneDrive", on)
    home = Path(home or Path.home())
    found = list((home / "Library" / "CloudStorage").glob("OneDrive*")) + list(home.glob("OneDrive*"))
    return sorted(p for p in found if p.is_dir())


# The places clark never reads, whatever the person saved (#47b). creaite's reach.py names them as rows of (base, pattern,
# kind): "home" rows are below the home folder, "abs" rows are absolute paths; the pattern is matched one part at a time with
# shell wildcards and covers everything below it. They live here because seven name a folder under "Library/Application
# Support", and only this file may (tests/test_platform_source.py). creaite v2.6.9 reach.NEVER, the 39 rows that bar reading.
NEVER_READ = (
    ("home", ".ssh", "secret"), ("home", ".aws", "secret"), ("home", ".gnupg", "secret"),
    ("home", ".config/gcloud", "secret"), ("home", ".config/gh", "secret"), ("home", ".config/op", "secret"),
    ("home", ".kube", "secret"), ("home", ".docker", "secret"), ("home", ".netrc", "secret"),
    ("home", ".git-credentials", "secret"), ("home", ".npmrc", "secret"), ("home", ".pypirc", "secret"),
    ("home", ".password-store", "secret"), ("home", "Library/Keychains", "secret"),
    ("home", "Library/Group Containers/*1password*", "secret"), ("home", "Library/Application Support/1Password", "secret"),
    ("home", "Library/Application Support/Bitwarden", "secret"),
    ("home", "Library/Application Support/Google/Chrome", "secret"), ("home", "Library/Application Support/Firefox", "secret"),
    ("home", "Library/Application Support/Microsoft Edge", "secret"),
    ("home", "Library/Application Support/BraveSoftware", "secret"), ("home", "Library/Application Support/Arc", "secret"),
    ("home", "Library/Safari", "secret"), ("home", "Library/Containers/com.apple.Safari", "secret"),
    ("home", "Library/Cookies", "secret"), ("home", ".mozilla", "secret"), ("home", ".config/google-chrome", "secret"),
    ("home", ".claude.json", "secret"), ("home", ".claude/.credentials.json", "secret"),
    ("abs", "/System", "system"), ("abs", "/Library", "system"), ("abs", "/usr", "system"), ("abs", "/bin", "system"),
    ("abs", "/sbin", "system"), ("abs", "/etc", "system"), ("abs", "/private/etc", "system"), ("abs", "/opt", "system"),
    ("abs", "/Applications", "system"), ("abs", "/dev", "system"),
)


def never_read_places(on=None):
    """The places ask clark never reads, as (base, pattern, kind) rows: base "home" or "abs", kind "secret" or "system"
    (reach.py turns the kind into its plain-words reason). Windows' places are not written yet."""
    _only_mac("The list of places clark never reads", on)
    return NEVER_READ


def inside_onedrive(path, roots=None):
    """The OneDrive root that `path` is inside (after following links), or None."""
    path = Path(path).expanduser().resolve()
    for root in onedrive_roots() if roots is None else roots:
        root = Path(root).resolve()
        if path == root or root in path.parents:
            return root
    return None


def shown(path, home=None):
    """A folder or file as a person reads it in a message: under the home folder it is written from "~", so the user's name is
    never in a message that might be copied into a report or an email. The home folder itself is "~". A path that is not under
    the home folder, or is not an absolute path, is shown as it is (#696). A home folder of "/" (a container's) is no home folder:
    everything is under it, so nothing is written from "~"."""
    path, home = Path(path), Path(home or Path.home())
    if home == Path(home.anchor) or not path.is_absolute():
        return str(path)
    if path == home:
        return "~"
    try:
        return "~/" + path.relative_to(home).as_posix()
    except ValueError:
        return str(path)


def check_data_dir(path, roots=None, what="data"):
    """`path`, resolved, if clark may keep its database there. A folder inside OneDrive is refused with the reason:
    OneDrive syncs a database part-way through a write and can't lock it, so the data would be damaged. `what="backups"`
    words the refusal for the backups folder (#86), where "backups can still go to OneDrive" would read wrongly. The way to have copies in
    OneDrive is the separate copy folder (#622), which is never checked here: finished single files are safe there, a live database is not."""
    root = inside_onedrive(path, roots)
    if root is None and what == "data":
        root = container_host_in_onedrive()                  # item 427: inside the container the Mac's OneDrive can't be seen, so the Mac's path is told
        if root is not None:
            path = os.environ["CLARK_DATA_SOURCE"]           # and the Mac's folder is what the person must change, not the container's /data
    if root is not None:
        if what == "backups":
            raise PlatformError(f"Backups can't be kept in {shown(path)} because it is inside OneDrive ({root.name}). OneDrive "
                                "copies files while they are being written, which damages a database. Keep them beside the "
                                "database on this computer. To have a copy in OneDrive, choose it in Settings › Backups › Copy my "
                                "backups to.")
        raise PlatformError(f"Your data can't be kept in {shown(path)} because it is inside OneDrive ({root.name}). OneDrive "
                            "copies files while they are being written, which damages the database. Choose a folder on "
                            "this computer that OneDrive doesn't sync, and choose a backup folder in OneDrive instead (Settings › "
                            "Backups › Copy my backups to): backups can still go to OneDrive.")
    return Path(path).expanduser().resolve()


# Private files and folders (#86). Mode bits do nothing on Windows, where the user's profile permissions apply.

def private_folder(path):
    """`path` as a folder only this user can open (0700), made if it is not there and set right if it already was (it may
    have been made at the umask's 0755). A link is refused: setting its mode would change the folder it points to."""
    path = Path(path)
    if path.is_symlink():
        raise PlatformError(f"{shown(path)} is a shortcut, not a real folder. Replace it with a real folder, then try again.")
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(path, 0o700)
    return path


def private_file(path):
    """A new, empty file at `path` that only this user can read (0600) from the moment it exists, so a database written into
    it is never open to others, not even for a moment. Never replaces a file: it raises FileExistsError if `path` is taken."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)       # the umask can only remove bits
    os.close(fd)
    return Path(path)


# One clark to a data folder

LOCK_NAME = ".clark-lock"       # in the data folder; empty, and never written to
_HELD_LOCKS = {}                # data folder -> the open lock file; kept open for as long as this clark runs


def already_open(folder, restoring=False):
    """What a person reads when another clark has `folder` open. `restoring`: the words for `clark restore NAME`."""
    if restoring:
        return "Nothing was restored: clark is open with this data. Close its window, wait a minute for clark to stop, then run the restore again."
    return (f"Nothing was started: clark is already open with the data in {with_tilde(folder)}. Switch to its window. If you can't "
            "find it, wait a minute and try again: clark stops by itself a minute after its last window closes.")


def cant_check(folder, restoring=False):
    """What a person reads when the lock on `folder` can't be looked at (not when another clark holds it)."""
    nothing = "Nothing was restored" if restoring else "Nothing was started"
    return (f"{nothing}: clark can't check whether it is already open with the data in {with_tilde(folder)}. "
            "Check that you can save files there, then try again.")


def _busy(error):
    """True when `error` from the lock call means another clark holds it (and not that the lock can't be looked at)."""
    return isinstance(error, BlockingIOError) or error.errno in (errno.EAGAIN, errno.EWOULDBLOCK)



def _lock_file(folder):
    fd = os.open(str(Path(folder) / LOCK_NAME), os.O_RDONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        raise
    return fd


def hold_data_lock(folder, restoring=False):
    """Take the lock on `folder` for as long as this process lives. Raises PlatformError(already_open) if another clark has it,
    and PlatformError(cant_check) if the lock can't be looked at (no permission, or any other error): only a busy lock means
    "already open". The system drops the lock when the process ends, however it ends, so a crash leaves nothing stale. Where
    there is no file lock (Windows, not built yet) nothing is checked."""
    key = str(Path(folder).resolve())
    if fcntl is None:
        return
    if key in _HELD_LOCKS:
        raise PlatformError(already_open(folder, restoring))
    try:
        _HELD_LOCKS[key] = _lock_file(folder)
    except OSError as e:
        raise PlatformError(already_open(folder, restoring) if _busy(e) else cant_check(folder, restoring)) from None


def release_data_lock(folder):
    """Let go of the lock this process holds on `folder` (a clean stop; the system does it anyway at exit)."""
    fd = _HELD_LOCKS.pop(str(Path(folder).resolve()), None)
    if fd is not None:
        os.close(fd)


def data_lock_held(folder):
    """True when another clark holds the lock on `folder`; nothing is kept. False when there is no lock to check. Raises
    PlatformError(cant_check) when the lock can't be looked at, which is not the same as held."""
    if fcntl is None:
        return False
    try:
        if not (Path(folder) / LOCK_NAME).exists():
            return False
        os.close(_lock_file(folder))
    except OSError as e:
        if _busy(e):
            return True
        raise PlatformError(cant_check(folder)) from None
    return False


# Opening files and the system's own dialogs

def run_program(args, cwd=None, run=None):
    """Run a program from an argument list (never through a shell), wait, and return the finished process with its output
    as text. The page build uses it to run dev/tools/build_page.py in a source checkout."""
    return (run or subprocess.run)([str(a) for a in args], cwd=None if cwd is None else str(cwd), capture_output=True,
                                   text=True, check=False)


def _run(args, run=None):
    """Start a program from an argument list (never through a shell) and return the finished process."""
    return (run or subprocess.run)(list(args), capture_output=True, text=True, check=False)


def open_file(path, run=None, on=None):
    """Open `path` in the program the system uses for it (Finder's double-click)."""
    _only_mac("Opening a file", on)
    path = _existing(path)
    _checked(_run(["open", str(path)], run), f"{path.name} could not be opened")


CHROME = "Google Chrome"


def open_pdf_at(path, url, run=None, on=None):
    """#943: open the PDF `path` at the page named by `url` (pdf_link.pdf_url: file:///...#page=N) in Chrome, whose viewer takes
    #page=N. If Chrome is not there or refuses, open the file plainly (open_file) so the person still sees it, at its first page."""
    _only_mac("Opening a PDF at a page", on)
    path = _existing(path)
    url = str(url)
    if not re.match(r"file:///[^\s]+\Z", url) or not url.lower().split("#")[0].endswith(".pdf"):
        raise PlatformError("Only the address of a PDF file can be opened here.")
    if _run(["open", "-a", CHROME, url], run).returncode != 0:
        open_file(path, run=run, on=on)


def reveal_file(path, run=None, on=None):
    """Show `path` selected in its folder in Finder."""
    _only_mac("Showing a file in its folder", on)
    path = _existing(path)
    _checked(_run(["open", "-R", str(path)], run), f"{path.name} could not be shown in its folder")


def open_url(url, run=None, on=None):
    """Open a web address (http or https only) in the person's default browser."""
    _only_mac("Opening a web page", on)
    url = str(url)
    if not re.match(r"https?://[^\s]+\Z", url):       # also keeps a value starting with "-" from being read as an option
        raise PlatformError(f"Only web addresses starting http:// or https:// can be opened. You gave {url}.")
    done = _run(["open", url], run)
    if done.returncode != 0:
        raise PlatformError(f"The browser could not be opened. {TRY_AGAIN}")


def _existing(path):
    path = Path(path)
    if not path.exists():
        raise PlatformError(f"{path.name} isn't there any more.")
    return path.resolve()           # absolute, so a name starting with "-" is never read as an option


TRY_AGAIN = "Try again; if it keeps happening, restart clark."          # the system's own error text is never shown


def _checked(done, what):
    if done.returncode != 0:
        raise PlatformError(f"{what}. {TRY_AGAIN}")
    return done


# The scripts read the prompt, names and folders as arguments, so no text a person typed ever becomes part of a script.
FOLDER_SCRIPT = """on run argv
  if (count of argv) > 1 then
    return POSIX path of (choose folder with prompt (item 1 of argv) default location (POSIX file (item 2 of argv)))
  end if
  return POSIX path of (choose folder with prompt (item 1 of argv))
end run"""
ZIP_OPEN_SCRIPT = """on run argv
  if (count of argv) > 1 then
    return POSIX path of (choose file with prompt (item 1 of argv) of type {"zip", "public.zip-archive"} default location (POSIX file (item 2 of argv)))
  end if
  return POSIX path of (choose file with prompt (item 1 of argv) of type {"zip", "public.zip-archive"})
end run"""
SAVE_SCRIPT = """on run argv
  if (count of argv) > 2 then
    return POSIX path of (choose file name with prompt (item 1 of argv) default name (item 2 of argv) default location (POSIX file (item 3 of argv)))
  end if
  return POSIX path of (choose file name with prompt (item 1 of argv) default name (item 2 of argv))
end run"""

OPEN_SCRIPT = """on run argv
  if (count of argv) > 1 then
    return POSIX path of (choose file with prompt (item 1 of argv) default location (POSIX file (item 2 of argv)))
  end if
  return POSIX path of (choose file with prompt (item 1 of argv))
end run"""


def choose_folder(prompt, start=None, run=None, on=None):
    """The system's own folder dialog. The chosen folder, or None if the person cancelled."""
    _only_mac("The folder dialog", on)
    return _dialog(FOLDER_SCRIPT, [prompt] + ([str(start)] if start else []), run, "folder")


def choose_zip_file(prompt, start=None, run=None, on=None):
    """The system's own Open dialog, for one .zip file. The chosen file, or None if the person cancelled."""
    _only_mac("The Open dialog", on)
    return _dialog(ZIP_OPEN_SCRIPT, [prompt] + ([str(start)] if start else []), run, "Open")


def choose_save_file(prompt, default_name, start=None, run=None, on=None):
    """The system's own Save dialog, suggesting `default_name` (made safe). The chosen file, or None if cancelled."""
    _only_mac("The Save dialog", on)
    return _dialog(SAVE_SCRIPT, [prompt, safe_name(default_name)] + ([str(start)] if start else []), run, "Save")


def choose_open_file(prompt, start=None, run=None, on=None):
    """The system's own Open dialog, for one existing file (#96: a file for a section template). The chosen file, or None if the
    person cancelled. clark only learns the path; nothing is read here."""
    _only_mac("The Open dialog", on)
    return _dialog(OPEN_SCRIPT, [prompt] + ([str(start)] if start else []), run, "file")


def _dialog(script, args, run, which):
    done = _run(["osascript", "-e", script, *args], run)
    if done.returncode != 0:
        if CANCELLED in (done.stderr or ""):
            return None
        raise PlatformError(f"The {which} window could not be opened. {TRY_AGAIN}")
    return Path(done.stdout.strip())


# File names and replacing files

def safe_name(name, folder=None, max_name=MAX_NAME):
    """`name` made safe for Windows, OneDrive and SharePoint, applied on every system: reserved characters become "-",
    no trailing dot or space, a device name (CON, NUL, COM1...) gets "_" in front, and the name is shortened (keeping
    its extension) to `max_name` characters, and so the whole path in `folder` stays under Windows' 260-character limit."""
    name = RESERVED_CHARS.sub("-", str(name)).strip().rstrip(". ")
    if not name:
        name = "untitled"
    if name.split(".")[0].rstrip(" ").upper() in RESERVED_NAMES:      # Windows checks the name up to the first dot, minus spaces
        name = "_" + name
    limit = max_name
    if folder is not None:
        room = MAX_PATH - 1 - len(str(Path(folder))) - 1      # the NUL, and the separator before the name
        if room < 12:
            raise PlatformError("That folder is too deep for the report to be saved in it. Choose a folder nearer the top of the drive.")
        limit = min(limit, room)
    if len(name) > limit:
        stem, dot, ext = name.rpartition(".")
        if not dot or not stem or len(ext) > 10:
            stem, ext = name, ""
        keep = limit - (len(ext) + 1 if ext else 0)
        name = stem[:keep].rstrip(". ") + ("." + ext if ext else "")
    return name


def replace_file(source, dest, attempts=REPLACE_ATTEMPTS, first_wait=REPLACE_FIRST_WAIT, sleep=time.sleep,
                 replace=os.replace):
    """Move `source` over `dest` in one step. Another program (OneDrive, Word, antivirus) may hold `dest` for a moment,
    so a refused replace is retried with a short backoff; if it stays locked, the message names the file."""
    wait = first_wait
    for attempt in range(1, attempts + 1):
        try:
            replace(source, dest)
            return Path(dest)
        except OSError as e:
            if e.errno not in LOCKED and not isinstance(e, PermissionError):
                raise
            if attempt == attempts:
                raise PlatformError(f"{Path(dest).name} couldn't be saved because another program is using it or it "
                                    f"is locked ({shown(dest)}). Close it there and try again.") from e
            sleep(wait)
            wait *= 2


def open_plain_file(path, flags):
    """An `opener` for open(): opens `path` for reading without following a link and without waiting on a pipe, and only
    hands back the descriptor if it is an ordinary file (OSError otherwise). Used to read a file in a client's folder, where
    another program may have put a link or a pipe under the name."""
    fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(errno.EINVAL, "not an ordinary file")
    except BaseException:
        os.close(fd)
        raise
    return fd


def is_mine(st):
    """Whether a file's stat says it belongs to the user running clark (always True where the system has no owner numbers)."""
    return not hasattr(os, "getuid") or st.st_uid == os.getuid()


def _write_temp(dest, data):
    """Write `data` (bytes, or text as UTF-8) to a new temporary file beside `dest`; the temporary file's path.
    The name is unique per call, so threads never share one."""
    dest = Path(dest)
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.{secrets.token_hex(4)}.part")
    try:
        if isinstance(data, str):
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(data)
        else:
            with open(tmp, "wb") as f:
                f.write(data)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise
    return tmp


def write_file(dest, data, **retry):
    """Write `data` (bytes, or text written as UTF-8) to `dest` safely: to a temporary file beside it, then replace_file.
    Nothing half-written is ever left at `dest`, and the temporary file is removed if the replace fails. Two writers
    at once each use their own temporary file; the last replace wins."""
    dest = Path(dest)
    tmp = _write_temp(dest, data)
    try:
        return replace_file(tmp, dest, **retry)
    finally:
        if tmp.exists():
            tmp.unlink()


def move_unless_exists(src, dest, link=os.link, replace=replace_file, exists=os.path.lexists):
    """Move `src` to `dest` only if nothing is called `dest` yet. True if it was placed (and `src` is gone); False if the name
    was taken, in which case nothing at `dest` is touched and `src` is left where it was for the caller to remove.
    A rename replaces a file that appeared a moment ago; a hard link does not: os.link fails if `dest` exists, whatever
    made it, whenever it came. So the file is linked into place and then `src` is unlinked. A disk that can't link
    (errno EPERM, EXDEV, ENOTSUP or ENOSYS) gets a last look at whether `dest` exists and then replace_file, which leaves
    a very small gap that a link does not. Any other error is raised. `link`, `replace` and `exists` are for tests."""
    try:
        link(src, dest)
    except FileExistsError:
        return False
    except OSError as e:
        if e.errno not in NO_HARD_LINKS:
            raise
        if exists(dest):
            return False
        replace(src, dest)
        return True
    try:
        os.unlink(src)
    except OSError:
        pass                      # placed; a leftover temporary name is the caller's to remove (write_file_unless_exists does)
    return True


def write_file_unless_exists(dest, data, **kw):
    """write_file that never replaces: the bytes go to a temporary file beside `dest`, then move_unless_exists. True if
    written; False if a file or folder called `dest` is there, even if it came after this call began. The temporary file is
    always removed. `kw` is passed to move_unless_exists (link, replace, exists)."""
    dest = Path(dest)
    tmp = _write_temp(dest, data)
    try:
        return move_unless_exists(tmp, dest, **kw)
    finally:
        if tmp.exists():
            tmp.unlink()


# Starting clark and opening its window (#71). The launcher (launch.py) holds the logic; the system calls are here.

CHROME_MAC = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"     # also looked for in ~/Applications
LAUNCHER_MAC = "clark.command"          # the double-clickable file in clark's folder; Windows will have clark.cmd (#57)
LOG_LIMIT = 1024 * 1024                 # the server's log is started again when it is bigger than this


def launcher_name(on=None):
    """The file name a person double-clicks to start clark."""
    _only_mac("The launcher file", on)
    return LAUNCHER_MAC


def find_chrome(environ=None, home=None, exists=os.path.exists, on=None):
    """The Chrome program to open clark's window with, or None. CLARK_BROWSER names another program to use instead (the
    tests use a stub); if it isn't there, None, so the default browser is used."""
    _only_mac("Finding Chrome", on)
    environ = os.environ if environ is None else environ
    named = environ.get("CLARK_BROWSER")
    if named:
        return named if exists(named) else None
    for found in (CHROME_MAC, str(Path(home or Path.home()) / "Applications" / "Google Chrome.app" / "Contents" / "MacOS"
                                  / "Google Chrome")):
        if exists(found):
            return found
    return None


ROOT_NAME = "the top of the drive"


def folder_name(path):
    """The last part of `path`, for a message. A drive root (/ or C:\\) has no name, so it reads "the top of the drive"."""
    text = str(path).rstrip("/\\")
    name = os.path.basename(text.replace("\\", "/"))
    return name if name and not (len(name) == 2 and name[1] == ":") else ROOT_NAME


def folder_phrase(path, capital=False):
    """The folder as a sentence reads it: the folder “Reports”, or the top of the drive for a root (never an empty quote)."""
    name = folder_name(path)
    text = name if name == ROOT_NAME else f"the folder “{name}”"
    return text[0].upper() + text[1:] if capital else text


def with_tilde(path, home=None):
    """`path` as a person reads it: the home folder written ~, so a message never shows the account's folder name."""
    text, home = str(path), str(Path(home) if home else Path.home())
    return "~" + text[len(home):] if text == home or text.startswith(home.rstrip("/") + "/") else text


def start_detached(argv, env, log_path, cwd=None, popen=None, on=None):
    """Start `argv` (an argument list, never a shell) in a session of its own, so it keeps running when this program and its
    window end. Its output is added to `log_path` (started again first if it has grown past LOG_LIMIT). The process."""
    _only_mac("Starting clark in the background", on)
    log_path = Path(log_path)
    try:
        if log_path.exists() and log_path.stat().st_size > LOG_LIMIT:
            log_path.write_bytes(b"")
        with open(log_path, "ab") as log:
            return (popen or subprocess.Popen)(list(argv), cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                               start_new_session=True)
    except OSError as e:
        raise PlatformError(f"Nothing was started, because this Mac would not run clark. Close this window and try again. If it keeps happening, send the file {with_tilde(log_path)} to the clark team.") from e


def run_python_check(python, code, args=(), timeout=120, run=None):
    """Run `code` with the Python program `python` in a fresh, isolated interpreter (-I -B), from an argument list. Returns
    (exit status, what it wrote to stderr as text). The update helper's check that every part of a new version loads."""
    done = (run or subprocess.run)([str(python), "-I", "-B", "-c", code, *[str(a) for a in args]], capture_output=True,
                                   timeout=timeout, check=False)
    return done.returncode, (done.stderr or b"").decode("utf-8", "replace")


def open_app_window(url, chrome, popen=None, on=None):
    """Open `url` in a Chrome app window (no address bar or tabs). It is left running."""
    _only_mac("Opening an app window", on)
    url = str(url)
    if not re.match(r"https?://[^\s]+\Z", url):
        raise PlatformError(f"Only web addresses starting http:// or https:// can be opened. You gave {url}.")
    try:
        (popen or subprocess.Popen)([str(chrome), "--app=" + url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        raise PlatformError("Chrome could not be started, so clark's window did not open.") from e


# The Claude command (ask clark). Found on the PATH and started from an argument list. A .cmd or .bat is refused on every
# system: Windows passes its arguments through cmd.exe, which can turn text in an argument into a command
# (docs/handoff/portability-and-sharing.md).
CLAUDE = "claude"
NO_SCRIPTS = (".cmd", ".bat")


def find_claude(which=shutil.which):
    """The Claude command to run, or None if it isn't on the PATH. A .cmd or .bat file is refused with the reason."""
    found = which(CLAUDE)
    if found and Path(found).suffix.lower() in NO_SCRIPTS:
        raise PlatformError("The copy of Claude Code on this computer can't be used safely by ask clark. Install Claude "
                            "Code's own app (claude.exe), then start clark again.")
    return found or None


# A program started for a job that is waited for (the PDF export drives Chrome this way).

class Child:
    """A program this module started, with the few calls its users need: pid, poll, wait(timeout) (TimeoutError when it runs
    on), terminate and kill. Made by start_child, either by os.posix_spawn or, where that is not there, by subprocess."""

    def __init__(self, pid=None, popen=None):
        self.pid, self._popen, self.returncode = (popen.pid if popen else pid), popen, None

    def poll(self):
        if self._popen is not None:
            self.returncode = self._popen.poll()
        elif self.returncode is None:
            try:
                done, status = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                self.returncode = 0
                return 0
            if done:
                self.returncode = os.waitstatus_to_exitcode(status) if hasattr(os, "waitstatus_to_exitcode") else status
        return self.returncode

    def wait(self, timeout=None):
        end = None if timeout is None else time.monotonic() + timeout
        while self.poll() is None:
            if end is not None and time.monotonic() > end:
                raise TimeoutError("the program is still running")
            time.sleep(0.02)
        return self.returncode

    def terminate(self):
        self._send(15)

    def kill(self):
        self._send(9)

    def _send(self, sig):
        try:
            os.kill(self.pid, sig)
        except OSError:
            pass


def start_child(argv, pipe=None, env=None, **_unused):
    """Start `argv` (an argument list, never a shell) in a process group of its own, with nothing on its standard streams.
    With `pipe` = (read_fd, write_fd) (two descriptors of this program's), the child gets them as its descriptors 3 and 4 (what
    Chrome's --remote-debugging-pipe reads and writes) and they are closed in the child's other places. `env` (a dict) is the child's
    environment; none given, it has this program's own. Uses os.posix_spawn,
    which is safe in a program with threads (no code runs in the child before the program starts). Returns a Child; raises
    OSError if the program cannot be started."""
    if hasattr(os, "posix_spawn"):
        actions = [(os.POSIX_SPAWN_OPEN, 0, os.devnull, os.O_RDONLY, 0), (os.POSIX_SPAWN_OPEN, 1, os.devnull, os.O_WRONLY, 0),
                   (os.POSIX_SPAWN_OPEN, 2, os.devnull, os.O_WRONLY, 0)]
        if pipe:
            actions += [(os.POSIX_SPAWN_DUP2, pipe[0], 3), (os.POSIX_SPAWN_DUP2, pipe[1], 4),
                        (os.POSIX_SPAWN_CLOSE, pipe[0]), (os.POSIX_SPAWN_CLOSE, pipe[1])]
        args = [str(a) for a in argv]
        return Child(pid=os.posix_spawn(args[0], args, os.environ if env is None else env, file_actions=actions, setpgroup=0))
    if pipe:
        raise OSError("this system cannot pass descriptors to a program this way")
    return Child(popen=subprocess.Popen([str(a) for a in argv], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, env=env))


STOP_WAIT = 2.0          # seconds between the polite stop and the kill of a run_stoppable group


def _end_group(proc):
    """End `proc`'s whole process group: a polite stop, a short wait, then a kill. The program was started in a new session, so
    its group's id is its own pid, which still names the group after the leader itself has gone. Safe to call twice."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            return                              # no one is left in the group
        try:
            proc.wait(timeout=STOP_WAIT)
        except subprocess.TimeoutExpired:
            continue
        if sig == signal.SIGTERM:
            time.sleep(0.05)                    # a helper may outlive its leader by a moment; the kill that follows catches it


def _scratch_parent():
    """The folder run_stoppable makes its empty working folder in: the system's temporary folder, unless TMPDIR put that inside clark's
    own data folder (a working folder must never be there: the program could then see clark's database and backups through `..`), when
    it is /tmp."""
    parent = Path(tempfile.gettempdir()).resolve()
    try:
        mine = data_dir().resolve()
    except (OSError, RuntimeError, NotBuiltYet):
        return str(parent)
    if parent == mine or mine in parent.parents or parent in mine.parents:
        return "/tmp"
    return str(parent)


def scratch_parent():
    """The folder run_stoppable's working folders are made in (ai_codex.py names them in its sandbox rules)."""
    return _scratch_parent()


def run_stoppable(args, data, env, limit, max_out, stop=None, prefix="clark-run-", tmp_names=("TMPDIR",), merge_err=False):
    """Run one program from an argument list (never a shell) as the leader of its own process group, in a new empty folder of its
    own (removed afterwards), with exactly `env` as its environment, `data` on standard input, and read at most `max_out` bytes
    of standard output within `limit` seconds. `stop` (a threading.Event) ends it early. Returns (status, out, code): status is
    "ok" (exit code 0), "failed" (any other code, or it could not start), "slow", "too_much" or "stopped"; `out` is empty unless
    the program finished. Standard error is thrown away (it could hold what it was given), unless `merge_err` asks for it with standard
    output (a program that says its status there, given nothing to repeat). Whatever ends the run, the whole
    group is ended (anything the program started goes too). Each name in `tmp_names` is set in the program's environment to a
    second new folder of its own (0700, removed afterwards), so its temporary files are never shared with another run. Standard
    input reaches its end as soon as `data` is written; it is fed through a pipe end of clark's own that never blocks, so a
    program (or a helper) that holds standard input open without reading it can never hold this function up. Used by ask
    clark's provider (#47c); never raises for the program's own faults.
    Known limit: a helper that leaves the group (its own setsid) is not ended with it; it keeps only the pipes, which this
    function stops using when the run ends."""
    parent = _scratch_parent()
    work = tempfile.mkdtemp(prefix=prefix, dir=parent)
    tmp, proc, feeder = None, None, None
    try:
        tmp = tempfile.mkdtemp(prefix=prefix + "tmp-", dir=parent)
        env = dict(env)
        env.update({name: tmp for name in tmp_names})
        r, w = os.pipe()
        try:
            # close_fds and no pass_fds: only 0, 1 and 2 reach the program (nothing clark holds open); umask 077: what it writes is
            # the person's alone
            proc = subprocess.Popen(list(args), stdin=r, stdout=subprocess.PIPE, stderr=subprocess.STDOUT if merge_err else subprocess.DEVNULL, cwd=work,
                                    env=env, close_fds=True, pass_fds=(), start_new_session=True, shell=False, umask=0o077)
        except (OSError, ValueError, subprocess.SubprocessError):
            os.close(w)
            return "failed", b"", None
        finally:
            os.close(r)
        os.set_blocking(w, False)

        def feed():
            view, sent = memoryview(data), 0
            try:
                while sent < len(view) and not fed.is_set():
                    _r, ready, _x = select.select([], [w], [], 0.2)
                    if ready:
                        try:
                            sent += os.write(w, view[sent:sent + 65536])
                        except BlockingIOError:
                            pass
            except (OSError, ValueError):
                pass                            # the program closed its end: nothing more to give it
            finally:
                os.close(w)                     # the end of standard input
        fed = threading.Event()                 # set when the run is over: the feeder gives up at once
        feeder = threading.Thread(target=feed, daemon=True)
        feeder.start()
        deadline, out, status = time.monotonic() + limit, bytearray(), None
        fd = proc.stdout.fileno()
        while status is None:
            if stop is not None and stop.is_set():
                status = "stopped"
                break
            left = deadline - time.monotonic()
            if left <= 0:
                status = "slow"
                break
            ready, _w, _x = select.select([fd], [], [], min(0.2, left))
            if not ready:
                continue
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            out += chunk
            if len(out) > max_out:
                status = "too_much"
        if status is None:
            try:
                code = proc.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                status = "slow"
            else:
                _end_group(proc)                # helpers it left behind in its group go too
                return ("ok" if code == 0 else "failed"), bytes(out), code
        _end_group(proc)
        return status, b"", proc.returncode
    finally:
        if feeder is not None:
            fed.set()
            feeder.join(STOP_WAIT)
        if proc is not None:
            if proc.poll() is None:
                _end_group(proc)
            try:
                proc.stdout.close()
            except (OSError, ValueError, AttributeError):
                pass
        shutil.rmtree(work, ignore_errors=True)
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
