"""#836 step 4a: the setup service (design-836-setup-mode.md sections 5 and 6). Plain logic, no server, no page, no store.

What it does: runs the doctor's checks as data for a page; takes the answer of the system's folder window and checks it before
anything is kept; remembers the chosen folder in a one-line pointer file beside the default folder. The server routes
(server.py, guarded), the launcher hooks and the page words are later steps and are not here.

Every system call is in platform.py: the folder window is the `choose_folder` seam (default platform.choose_folder, which is
never named at import time and never run in a test); the pointer file is written with platform.write_file. A refusal carries the
doctor's own words, unchanged. This module imports neither the store nor anything that publishes. Standard library only.
"""
import argparse
import os
import sys
import threading
from pathlib import Path

from clark import cloud_folder, doctor, platform, setup_page

POINTER_NAME = "clark-data-folder"          # one line, beside the default data folder (not in it)
FOLDER_PROMPT = "Choose a folder for your clark data"      # the folder window's words (the owner's, #1017); the entry point gives it to Setup
MAX_PATH = 1000                             # the rule settings.set_backup_copy_folder applies to a typed folder

# Sentences borrowed from the folder picker of asking (ask_folders.MESSAGES, same keys), carried here because that module opens
# the store and this one may not. test_setup_mode pins them equal.
WORDS = {
    "cant_save": "That folder could not be saved. Try Choose folder again; if it keeps happening, close clark and start it again. "
                 "Nothing was changed.",
    "not_a_folder": "That isn't a folder on this computer. Nothing was changed.",
    # NEW sentence (no existing one says a window is already open): "The folder window" as platform._dialog and ask_folders'
    # dialog_failed say it, "Wait a moment and try again." as ask_folders and safety say it, the usual "Nothing was changed."
    "busy": "The folder window is already open. Wait a moment and try again. Nothing was changed.",
}


class Refused(Exception):
    """A folder (or a step) the service will not take. `code` is for the page, `words` is the doctor's own line."""

    def __init__(self, code, words, page=None):
        super().__init__(words)
        self.code, self.words = code, words
        self.page = words if page is None else page         # the same refusal said for a page (no "start clark again")


def _plain_path(text):
    """`text` as an absolute path of a sensible length with no control character, or None."""
    if not isinstance(text, str) or not text or len(text) > MAX_PATH:
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in text):
        return None
    path = Path(text)
    return path if path.is_absolute() else None


class Setup:
    def __init__(self, folder, home=None, on=None, choose_folder=None, onedrive_roots=None, pointer=None, checks=None,
                 environ=None, prompt=None, finish=None, kept=None):
        self.folder, self.home, self.on = Path(folder), home, on
        self.kept = kept or (lambda folder: None)       # told the chosen folder once it is kept, before its report (main: server_mark)
        self.choose_folder = choose_folder or platform.choose_folder
        self.onedrive_roots, self.environ = onedrive_roots, environ
        self.pointer = pointer or (lambda: Path(platform.data_dir(home, on=on)).parent / POINTER_NAME)
        self.checks = doctor.CHECKS if checks is None else checks
        self.prompt, self._finish = prompt, finish      # the folder window's words (the owner's; None: the folder route is not wired) and the update helper's finish
        self._dialog = threading.Lock()                 # one folder window at a time
        self._finishing = threading.Lock()              # one finish at a time
        self.done = False                               # true once api_done has answered restart: main then starts clark on self.folder

    def seen(self, folder=None):
        extra = {"onedrive_roots": self.onedrive_roots} if self.onedrive_roots else {}
        if self.environ is not None:
            extra["environ"] = self.environ
        return doctor.Seen(data=str(folder or self.folder), home=self.home, on=self.on, **extra)

    def report(self, folder=None):
        """The checks for the folder now in use, as data for a page. `ready` follows the doctor's own rule."""
        seen = self.seen(folder)
        container = platform.container_mode()           # #836: inside Docker the page also checks the Mac folder shared in, and cannot open a folder window
        results = doctor.run_checks(seen, tuple(self.checks) + ((doctor.Check("The Docker check", True, doctor.check_docker),) if container else ()))
        rows = [dict(row, required=check.required, page=setup_page.page_words(row["id"], row["status"], row["words"], seen))
                for row, (check, _) in zip(doctor.as_data(results), results)]
        ready = not any(check.required and line.kind in (doctor.FIX, doctor.NOT_CHECKED) for check, line in results)
        return {"ok": True, "ready": ready, "folder": seen.tilde(seen.folder()), "container": container, "checks": rows}

    def choose(self, prompt):
        """Open the system's folder window and check the answer. None on Cancel (nothing changes). On a good answer the folder
        is kept (pointer file written) and the new report is returned. Raises Refused (the folder's own words; code "busy" if a
        window is already open; "cant_save" if the pointer file could not be written; "dialog_failed" inside Docker, where the window
        needs the Mac: platform's own sentence, no system call) or lets a PlatformError out (the window could not be opened)."""
        if platform.container_mode():                       # #836: the page hides the button there; a direct POST meets the same answer here
            raise Refused("dialog_failed", platform.mac_only_in_docker("The folder dialog"))
        if not self._dialog.acquire(blocking=False):
            raise Refused("busy", WORDS["busy"])
        try:                                                # the answer is checked and kept under the same lock as the window
            answer = self.choose_folder(prompt)
            if answer is None:
                return None
            folder = self.accept(answer)
            self.remember(folder)
            self.folder = folder
            self.kept(folder)                               # the server's /health says the new folder before the port check asks it
            return self.report(folder)
        finally:
            self._dialog.release()

    def accept(self, answer):
        """The folder `answer` names if it passes, else Refused. The answer is untrusted text; nothing is written here. A refusal
        names the answer, never the folder now in use (that one was not refused); an answer that is not a path at all is refused
        in words that name nothing (it may be anything, any length, any character)."""
        path = _plain_path(str(answer) if isinstance(answer, Path) else answer)
        if path is None:
            raise Refused("folder_refused", WORDS["not_a_folder"])
        if path.is_symlink() or not path.is_dir():
            raise Refused("folder_refused", doctor.cant_save_line(self.seen(path)).words, self.cant_save_page(path))
        self.windows_check(str(path))
        self.cloud_check(path)
        try:
            resolved = platform.check_data_dir(path, self.onedrive_roots() if self.onedrive_roots else platform.onedrive_roots(
                self.home, on=self.on))
        except platform.PlatformError as e:
            raise Refused("folder_refused", str(e), self.onedrive_page(path))
        self.cloud_check(resolved)
        if not doctor._can_save_in(resolved):
            raise Refused("folder_refused", doctor.cant_save_line(self.seen(resolved)).words, self.cant_save_page(resolved))
        return resolved

    def windows_check(self, text):
        """On Windows, a path platform.windows_folder_problem refuses (a share, a device name, a bad character, too long...) is Refused:
        OneDrive in its own words, any other problem as a folder that can't be saved in. Nothing on other systems."""
        if (self.on or platform.system()) != platform.WINDOWS:
            return
        problem = platform.windows_folder_problem(text)
        if problem == "onedrive":
            raise Refused("folder_refused", self.onedrive_page(text), self.onedrive_page(text))
        if problem:
            raise Refused("folder_refused", doctor.cant_save_line(self.seen(text)).words, self.cant_save_page(text))

    def cloud_check(self, folder):
        """Refused if `folder` is inside Dropbox, iCloud Drive or Google Drive (cloud_folder's words, which name no step on the page)."""
        words = cloud_folder.cloud_warning(folder, platform.shown(folder, self.home))
        if words:
            raise Refused("folder_refused", words)

    def cant_save_page(self, folder):
        seen = self.seen(folder)
        return setup_page.page_cant_save(seen.tilde(seen.folder()))

    def onedrive_page(self, folder):
        seen = self.seen(folder)
        return setup_page.page_onedrive(seen.tilde(seen.folder()))

    def page_html(self):
        """The setup page the server sends for GET / and GET /setup (the server adds this run's token)."""
        return setup_page.html(self.on)

    def remember(self, folder):
        """Keep `folder` in the pointer file, making the pointer's own folder first (a fresh computer may not have it). A pointer
        that can't be written is Refused("cant_save") in plain words, never an OSError: the chosen folder is left alone, nothing is
        kept, and the person can choose again. (Kept but forgotten would put them back in setup at the next start.)"""
        pointer = Path(self.pointer())
        try:
            pointer.parent.mkdir(parents=True, exist_ok=True)
            platform.write_file(pointer, str(folder) + "\n")
        except (OSError, platform.PlatformError):
            raise Refused("cant_save", WORDS["cant_save"]) from None

    def remembered(self):
        """The folder in the pointer file if it still passes every check, else None. An unreadable, odd or refused value is
        ignored, never trusted."""
        try:
            text = Path(self.pointer()).read_text(encoding="utf-8")
        except (OSError, ValueError, platform.PlatformError, platform.NotBuiltYet):
            return None
        try:
            return self.accept(text.rstrip("\r\n"))       # only the line end: a folder's own edge spaces are part of its name
        except Refused:
            return None

    # What the server's setup routes ask for (server.py SetupHandler). Each answers (status, body); None means "not wired" (404).
    def api_checks(self):
        return 200, self.report()

    def api_folder(self):
        if not self.prompt:
            return None
        try:
            report = self.choose(self.prompt)
        except Refused as e:
            if e.code == "busy":
                return 409, _busy()
            return 409, {"ok": False, "code": e.code, "message": e.words, "page": e.page}
        except platform.PlatformError as e:                 # NotBuiltYet is one too; the system's own text is never in it
            return 409, {"ok": False, "code": "dialog_failed", "message": str(e)}
        if report is None:
            return 200, {"ok": True, "chosen": False}
        return 200, dict(report, chosen=True)

    def api_finish(self):
        if self._finish is None:
            return None
        if not self._finishing.acquire(blocking=False):
            return 409, _busy()
        try:
            finished, words = self._finish()
        finally:
            self._finishing.release()
        return 200, {"ok": True, "finished": bool(finished), "words": list(words)}

    def api_done(self):
        """Every check again, now. Nothing the page said is trusted."""
        report = self.report()
        if not report["ready"]:
            return 409, {"ok": False, "code": "not_ready", "ready": False, "checks": report["checks"]}
        refusal = start_refusal(self.folder)
        if refusal:                         # D1: python -m clark would refuse this folder, so the page is told now, not left waiting
            return 409, {"ok": False, "code": "start_refused", "message": refusal}
        self.done = True
        return 200, {"ok": True, "restart": True}


def start_refusal(folder):
    """The launcher's own line when clark would refuse to start on `folder` (an update left part way, files of mixed versions, a
    clark already open there or a lock that can't be checked), else None. The same checks as launch(), nothing is written."""
    from clark import same_version, update_helper
    from clark.launch import lock_refusal
    if update_helper.marker_path(folder).exists():
        return update_helper.MESSAGES["not_restored"].format(log=platform.with_tilde(update_helper.updates_dir(folder) / update_helper.LOG_NAME))
    if same_version.mixed():
        return same_version.MESSAGE
    return lock_refusal(folder)


def server_mark(folder):
    """What main gives Setup as `kept`: the server's /health now says the chosen folder's mark. Without this the port check for the
    chosen folder (doctor.check_port, which asks this very server) saw another clark with other data: FIX, ready false, and done
    refused for ever. With it the check sees clark running with this data, as it did for the first folder."""
    from clark import appfiles, server
    server.set_data_mark(appfiles.data_mark(folder))


def _busy():
    return {"ok": False, "code": "busy", "message": platform.TRY_AGAIN}        # existing words: a second try is the right thing


def main(argv=None, out=None, err=None, serve=None, environ=None, start=None, home=None, onedrive_roots=None):
    """`python3 -m clark.setup_mode --data FOLDER --port N` (what the launcher starts). Serves setup mode for FOLDER, which is
    neither made nor written to. When the page's done was accepted and the server has stopped, the normal clark is started on the
    folder now chosen (`start` is platform.start_detached's seam, `home` and `onedrive_roots` are Setup's; a refusal is said on `err`, exit 1). The exit code: 0 stopped,
    1 the port is taken or clark could not be started, 2 a bad argument (said on `err`)."""
    from clark import __version__, appfiles, idle, launch, server, update_helper
    out, err = out or sys.stdout, err or sys.stderr
    environ = os.environ if environ is None else environ
    parser = argparse.ArgumentParser(prog="clark.setup_mode", description="Start clark's setup page.")
    parser.add_argument("--data", required=True, metavar="FOLDER", help="the data folder that may not be used")
    parser.add_argument("--port", required=True, metavar="N", help="the port to listen on")
    try:
        args = parser.parse_args(argv)
        port = int(args.port)
        if not 1 <= port <= 65535:
            raise ValueError(args.port)
    except ValueError:
        print("The port must be a number from 1 to 65535.", file=err, flush=True)
        return 2
    except SystemExit as e:
        return 2 if e.code else 0
    folder = Path(args.data).expanduser()

    def finish():
        code, result = update_helper.finish(folder)
        return code == update_helper.OK, [result["message"]] if result else []

    server.set_idle(idle.Idle.from_environ(environ) if idle.launched(environ) else None)
    server.set_data_mark(appfiles.data_mark(folder))
    server.set_version(__version__)
    server.set_code_mark(appfiles.code_mark())
    service = Setup(folder, home=home, onedrive_roots=onedrive_roots, prompt=FOLDER_PROMPT, finish=finish, kept=server_mark)
    code = (serve or server.serve)(port=port, out=out, err=err, setup=service)
    if code or not service.done:
        return code
    chosen = Path(service.folder)
    env = {**environ, "CLARK_LAUNCHED": "1", "CLARK_PORT": str(port), "PYTHONPATH": str(launch.SRC)}
    try:
        (start or platform.start_detached)([sys.executable, "-m", "clark", "--data", str(chosen), "--port", str(port)], env,
                                           chosen / launch.LOG_NAME, cwd=str(chosen))
    except platform.PlatformError as e:
        print(str(e), file=err, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
