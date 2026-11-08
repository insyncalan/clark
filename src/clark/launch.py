"""python3 -m clark.launch: start clark if it isn't running, then open it in a Chrome app window (#71).

    python3 -m clark.launch [--data FOLDER] [--port N]      (clark.command in clark's folder runs this)

It asks what is on the port first, and never takes over what isn't its own:
- nothing there: it starts clark (python3 -m clark) in the background, marked CLARK_LAUNCHED=1 so that it stops by itself a
  minute after the last clark window closes (idle.py), waits up to 15 seconds for it to answer, and opens the window
- clark with this data folder: it is already running; only the window is opened, but only if it is this folder's clark of this
  version and its page answers (row 975); otherwise it stops with a plain line and changes nothing
- clark with another data folder, or any other program (creaite also answers /health, without the mark): said in plain words,
  nothing started, nothing opened

The window is Chrome's app window (--app=<address>); if Chrome isn't found, the default browser, and it says so. The logic is
here and every system call is in platform.py, so a test runs it with fakes and a fake server. Copied from creaite v2.6.9
system/scripts/launch.py (BL-86, BL-212), cut down: no make-launcher, login agent, restart or starting-file. Standard library
only, Python 3.9.
"""
import argparse
import http.client
import json
import os
import sys
import time
from pathlib import Path

from clark import __version__, appfiles, doctor, platform, same_version, server, setup_mode, typed, update_helper
from clark.__main__ import Usage, free_port_near, port_free, port_number

NOTHING, OURS, OTHER_DATA, NOT_CLARK = "nothing", "ours", "other data folder", "not clark"
START_WAIT = 15.0               # seconds to wait for a started clark to answer
POLL = 0.1
ASK_TIMEOUT = 1.0
HEALTH_BYTES = 4096             # the most of an answer that is read
SRC = Path(__file__).resolve().parents[1]
LOG_NAME = "server.log"         # in the data folder
SETUP_LOG = "setup.log"         # in the log folder, never in a data folder that setup mode may be refusing
SETUP_REASONS = ("data_folder",)    # the only reason setup mode can mend; an update that stopped or a folder of mixed versions it cannot
SETUP_CHECKS = ("data_folder", "data_not_in_onedrive")      # the required checks a person can mend on the setup page (not Python, not the port)
DB_NAME = "clark.db"


def ask_health(port, mark, timeout=ASK_TIMEOUT, connect=http.client.HTTPConnection):
    """What is on `port` of 127.0.0.1, by asking /health with the data folder's mark: NOTHING (the connection is refused), OURS
    (clark, with the same data folder), OTHER_DATA (clark, another data folder) or NOT_CLARK (anything else that answers, or
    holds the port and doesn't answer in time, or says something that isn't clark's answer). Only clark's answer to the mark
    has a boolean "this_data": creaite answers {"ok": true} and so counts as not clark. No proxy is used."""
    conn = connect("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("GET", "/health", headers={appfiles.MARK_HEADER: mark})
        reply = conn.getresponse()
        raw = reply.read(HEALTH_BYTES + 1)
        status = reply.status
    except ConnectionRefusedError:
        return NOTHING
    except (OSError, http.client.HTTPException):
        return NOT_CLARK
    finally:
        conn.close()
    try:
        answer = json.loads(raw) if status == 200 and len(raw) <= HEALTH_BYTES else None
    except ValueError:
        answer = None
    if not isinstance(answer, dict) or answer.get("ok") is not True or not isinstance(answer.get("this_data"), bool):
        return NOT_CLARK
    return OURS if answer["this_data"] else OTHER_DATA


def ask_identity(port, mark, timeout=ASK_TIMEOUT, connect=http.client.HTTPConnection):
    """Row 975: who the clark on `port` is, as (version, folder mark) from /health asked with `mark`; a missing or odd field is
    None, so a server that cannot say (an older one) is never taken for this one. (None, None) if it does not answer."""
    conn = connect("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("GET", "/health", headers={appfiles.MARK_HEADER: mark})
        reply = conn.getresponse()
        raw = reply.read(HEALTH_BYTES + 1)
        answer = json.loads(raw) if reply.status == 200 and len(raw) <= HEALTH_BYTES else None
    except (OSError, http.client.HTTPException, ValueError):
        return None, None
    finally:
        conn.close()
    if not isinstance(answer, dict):
        return None, None
    version, folder = answer.get("version"), answer.get("folder")
    return (version if isinstance(version, str) else None), (folder if isinstance(folder, str) else None)


def ask_page(port, timeout=ASK_TIMEOUT * 5, connect=http.client.HTTPConnection):
    """Row 975: the status the page at / of `port` answers with, or None if it does not answer. Read only; nothing is changed."""
    conn = connect("127.0.0.1", port, timeout=timeout)
    try:
        conn.request("GET", "/")
        reply = conn.getresponse()
        reply.read(HEALTH_BYTES)
        return reply.status
    except (OSError, http.client.HTTPException):
        return None
    finally:
        conn.close()


NOT_THIS_ONE = ("clark is already running, but not from this folder or not this version. Nothing was changed. "
                "Quit it first (press Ctrl+C in its Terminal window), then start this one again.")
BROKEN_PAGE = ("clark is already running, but its page answers with an error. Nothing was opened or changed. "
               "Quit it first (press Ctrl+C in its Terminal window), then start this one again.")


def address(port):
    """Where clark's window opens. Always 127.0.0.1: Chrome offers to install an app only from a loopback address."""
    return f"http://127.0.0.1:{port}/"


def launcher_file():
    """The file a person double-clicks to start clark, or None off a Mac (where the name is not known)."""
    try:
        return platform.launcher_name()
    except platform.NotBuiltYet:
        return None


def try_another(port, free=port_free):
    """A second line for a person who can't close the other program: the command with a free number, or "" if none is near."""
    other = free_port_near(port, free)
    name = launcher_file()
    return (f"\nIf you can't close it, open Terminal in the clark folder and type: ./{name} --port {other}"
            if other and name else "")      # off a Mac there is no launcher file to type


def report(kind, port, folder, free=port_free):
    """The plain line for a port that isn't ours."""
    if kind == OTHER_DATA:
        return (f"Another copy of clark is already open with different data (this one uses {platform.with_tilde(folder)}). "
                f"Close that copy, then start clark again.{try_another(port, free)}")
    launcher = launcher_file() or "the clark launcher"          # the launcher file is the Mac's: general words elsewhere
    return ("Nothing was started: clark is already open in another Terminal window, or another program is using the connection it needs. "
            f"Close that Terminal window or program, then double-click {launcher} again.{try_another(port, free)}")


def wait_for_clark(port, mark, process, seconds=START_WAIT, health=ask_health, sleep=time.sleep, clock=time.monotonic):
    """Wait for the clark we started to answer with our data folder: what /health says at the end of the wait, or as soon as
    it answers or the process has gone (and one last look then: a second launch that won the port counts)."""
    end = clock() + seconds
    while True:
        seen = health(port, mark)
        if seen != NOTHING or clock() >= end:
            return seen
        if process.poll() is not None:
            return health(port, mark)
        sleep(POLL)


FINISH_CODE = ("import runpy, sys\n"
               "helper, data = sys.argv[1], sys.argv[2]\n"
               "sys.argv = [helper, '--finish', '--data', data]\n"
               "runpy.run_path(helper, run_name='__main__')\n")


def finish_update(folder, say=print, run=platform.run_python_check, python=None):
    """An update that stopped part way (its marker is still in the data folder): run the helper's --finish, from the copy the
    update put in the data folder, so the old version is back before clark starts. True when clark may start now."""
    marker = update_helper.marker_path(folder)
    if not marker.exists():
        return True
    updates_folder = update_helper.updates_dir(folder).resolve()
    try:
        doc = json.loads(marker.read_text(encoding="utf-8"))
        helper_dir = Path(doc.get("helper_dir") or "").resolve()
        wanted = doc.get("helper_sha")
        if not isinstance(wanted, dict) or any(update_helper.sha256_of(helper_dir / n) != wanted.get(n)
                                               for n in ("update_helper.py", update_helper.PLATFORM_COPY)):
            helper_dir = None                       # the copy is not the one that was written: the running copy is used instead
    except (OSError, ValueError, AttributeError):
        helper_dir = None
    helper = helper_dir / "update_helper.py" if helper_dir and helper_dir.parent == updates_folder \
        and helper_dir.name.startswith(update_helper.HELPER_PREFIX) else None
    if helper is None or not helper.is_file() or helper.is_symlink():
        helper = Path(update_helper.__file__).resolve()             # the helper of the copy that is running now
    try:
        status, _ = run(python or sys.executable, FINISH_CODE, [helper, folder], timeout=300)
    except Exception:  # noqa: BLE001  a helper that can't be run is said in words, never a traceback
        status = update_helper.NOT_RESTORED
    if status == update_helper.BUSY:
        say(update_helper.MESSAGES["busy"])
        return False
    result = update_helper.read_result(folder) or {}
    if status == update_helper.NOT_RESTORED or marker.exists():
        say(update_helper.MESSAGES["not_restored"].format(log=platform.with_tilde(updates_folder / update_helper.LOG_NAME)))
        return False
    if isinstance(result.get("message"), str):
        say(result["message"])
    return True


def lock_refusal(folder):
    """The plain line when no clark may be started on `folder` because one is open there, or because that can't be checked; else None."""
    try:
        return platform.already_open(folder) if platform.data_lock_held(folder) else None
    except platform.PlatformError as e:
        return str(e)


def data_problem(folder, environ=None):
    """The doctor's own words for the first required data check that fails for `folder` (one the setup page can mend), else None.
    A check that cannot run here is not a failure. Nothing is made or written."""
    seen = doctor.Seen(data=str(folder), environ=environ)
    for check in doctor.CHECKS:
        if check.required and doctor.check_id(check) in SETUP_CHECKS:
            line = doctor.run_check(check, seen)
            if line.kind == doctor.FIX:
                return line.words
    return None


def start_setup(port, folder, reason, say, environ, start, health, wait, find_chrome, open_window, open_browser, log_dir=None):
    """Row 836 step 4c: start setup mode (python3 -m clark.setup_mode, a process of its own, named by a string) for `folder` on
    `port` and open its window. True when it answered and the window was opened; False when it could not be started or did not
    answer, with nothing said and nothing left running, so the caller says its old line. `reason` ("data_folder", "update",
    "version") is the caller's for its own words; the setup page draws every check itself. The log goes to the log folder and the
    process runs in clark's own folder: `folder` is the one that may not be used, so it is neither made nor written to.
    A `reason` setup cannot mend (SETUP_REASONS) is False at once: it would show all ready, finish, and start clark into the same stop."""
    if reason not in SETUP_REASONS:
        return False
    mark = appfiles.data_mark(folder)
    env = {**environ, "CLARK_LAUNCHED": "1", "CLARK_PORT": str(port), "PYTHONPATH": str(SRC)}
    try:
        logs = Path(log_dir() if log_dir else platform.log_dir())
        logs.mkdir(parents=True, exist_ok=True)
        process = start([sys.executable, "-m", "clark.setup_mode", "--data", str(folder), "--port", str(port)], env,
                        logs / SETUP_LOG, cwd=str(SRC))
    except (platform.PlatformError, OSError):
        return False
    if wait(port, mark, process, health=health) != OURS:
        try:
            if process.poll() is None:
                process.terminate()
        except (OSError, AttributeError):
            pass
        return False
    return open_clark(address(port), say, environ, find_chrome, open_window, open_browser) == 0


def real_setup(say, environ, start, health, wait, find_chrome, open_window, open_browser):
    """The `setup` seam of launch() and main(), made from the same fakes or system calls as the launcher itself."""
    return lambda port, folder, reason: start_setup(port, folder, reason, say, environ, start, health, wait, find_chrome,
                                                    open_window, open_browser)


def launch(port, folder, say=print, environ=None, start=platform.start_detached, find_chrome=platform.find_chrome,
           open_window=platform.open_app_window, open_browser=platform.open_url, health=ask_health, wait=wait_for_clark,
           free=port_free, finish=finish_update, identity=ask_identity, page=ask_page, setup=None, data_problem=data_problem):
    """Start clark if nothing answers on `port`, then open its window. An update that stopped part way is finished first
    (always back to the version that was there). The exit code: 0 opened, 1 not (the reason is said).
    `setup` (off by default) is setup mode's start: setup(port, folder, reason) answers True when its window is open. Where a
    required data check, an interrupted update or a mixed folder stops the start, it is tried after the old line is said, and
    when it does not come up the old exit stays."""
    environ = os.environ if environ is None else environ
    folder = Path(folder)
    mark = appfiles.data_mark(folder)
    if not finish(folder, say):
        return 0 if setup is not None and setup(port, folder, "update") else 1
    if setup is None:
        if same_version.refuse():               # row 760: a folder of mixed versions never starts; after the recovery of an interrupted update, never before it
            return 1
    elif same_version.mixed():
        say(same_version.MESSAGE)
        return 0 if setup(port, folder, "version") else 1
    if setup is not None and (problem := data_problem(folder, environ)):
        say(problem)
        return 0 if setup(port, folder, "data_folder") else 1
    seen = health(port, mark)
    if seen in (OTHER_DATA, NOT_CLARK):
        say(report(seen, port, folder, free))
        return 1
    if seen == OURS:
        if identity(port, mark) != (__version__, appfiles.code_mark()):     # row 975: this data, but not this folder's clark or not this version
            say(NOT_THIS_ONE)
            return 1
        status = page(port)
        if status is None or status >= 500:         # it answers /health but not its own page: no window is opened on it
            say(BROKEN_PAGE)
            return 1
        say("It is already running. Opening its window.")
    elif (refusal := lock_refusal(folder)):     # clark is open on this folder (on another port), or that can't be checked: none is started
        say(refusal)
        return 1
    else:
        say("Starting clark...")
        log = folder / LOG_NAME
        env = {**environ, "CLARK_LAUNCHED": "1", "CLARK_PORT": str(port), "PYTHONPATH": str(SRC)}
        try:
            process = start([sys.executable, "-m", "clark", "--data", str(folder), "--port", str(port)], env, log, cwd=str(folder))
        except platform.PlatformError as e:
            say(str(e))
            return 1
        seen = wait(port, mark, process, health=health)
        if seen != OURS:
            if seen in (OTHER_DATA, NOT_CLARK):
                say(report(seen, port, folder, free))
            else:
                say("Nothing opened, because clark did not finish starting. Close this window, then double-click "
                    f"{launcher_file() or 'the clark launcher'} again. If it still does not start, send the file "
                    f"{platform.with_tilde(log)} to the clark team. It records what went wrong.")
            return 1
        say("A minute after the last window closes, clark stops by itself.")
    return open_clark(address(port), say, environ, find_chrome, open_window, open_browser)


def open_clark(url, say, environ, find_chrome, open_window, open_browser):
    """Open `url` in a Chrome app window; the default browser, with a line saying so, if Chrome isn't found."""
    chrome = find_chrome(environ)
    try:
        if chrome:
            open_window(url, chrome)
            say("Opened clark in its own window.")
        else:
            open_browser(url)
            say("Chrome wasn't found, so clark opened in your default browser. Install Chrome to give clark its own window.")
    except platform.PlatformError as e:
        say(f"{e} The clark server is still running. To use it, open this address in your browser: {url}")
        return 1
    return 0


def parser():
    p = argparse.ArgumentParser(prog=typed.launch(), description="Start clark if it isn't running, and open its window.")
    p.add_argument("--data", metavar="FOLDER", help="the folder for clark's data (default: clark's own folder for your system)")
    p.add_argument("--port", metavar="N", help=f"the port number clark listens on (advanced; default: the CLARK_PORT setting, or {server.DEFAULT_PORT})")
    return p


def remembered_folder(default, home=None, onedrive_roots=None):
    """The data folder the setup page kept (the pointer file beside the default folder), if it still passes every check; else None.
    This is the only place the pointer is read. A command-line --data never comes here."""
    roots = (lambda: list(onedrive_roots)) if onedrive_roots is not None else None
    return setup_mode.Setup(default, home=home, onedrive_roots=roots).remembered()


def main(argv=None, say=print, environ=None, home=None, onedrive_roots=None, **seams):
    """The command. `seams` are launch()'s fakes (start, health, find_chrome, ...)."""
    environ = os.environ if environ is None else environ
    args = parser().parse_args(argv)
    want, port, setup = None, None, seams.get("setup")
    try:
        port = port_number(args.port if args.port is not None else (environ.get("CLARK_PORT") or server.DEFAULT_PORT),
                           "--port" if args.port is not None else "CLARK_PORT")
        if args.data:
            want = Path(args.data).expanduser()
        else:
            want = platform.data_dir(home)
            want = remembered_folder(want, home, onedrive_roots) or want
        folder = platform.check_data_dir(want, onedrive_roots)
        folder.mkdir(parents=True, exist_ok=True)           # the log goes here; clark itself makes the database on first run
    except Usage as e:
        say(str(e))
        return 2
    except platform.PlatformError as e:
        say(str(e))
        return 0 if setup is not None and want is not None and setup(port, want, "data_folder") else 1
    except OSError as e:
        say(f"The data folder can't be made ({platform.with_tilde(want)}). Check you can save files there, then try again.")
        return 0 if setup is not None and setup(port, want, "data_folder") else 1
    return launch(port, folder, say, environ, **seams)


if __name__ == "__main__":
    sys.exit(main())
