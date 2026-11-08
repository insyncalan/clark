"""#836 step 4a: the setup service (design-836-setup-mode.md sections 5 and 6). Plain logic, no server, no page, no store.

What it does: runs the doctor's checks as data for a page; takes the answer of the system's folder window and checks it before
anything is kept; remembers the chosen folder in a one-line pointer file beside the default folder. The server routes
(server.py, guarded), the launcher hooks and the page words are later steps and are not here.

Every system call is in platform.py: the folder window is the `choose_folder` seam (default platform.choose_folder, which is
never named at import time and never run in a test); the pointer file is written with platform.write_file. A refusal carries the
doctor's own words, unchanged. This module imports neither the store nor anything that publishes. Standard library only.
"""
import threading
from pathlib import Path

from clark import doctor, platform

POINTER_NAME = "clark-data-folder"          # one line, beside the default data folder (not in it)
MAX_PATH = 1000                             # the rule settings.set_backup_copy_folder applies to a typed folder


class Refused(Exception):
    """A folder (or a step) the service will not take. `code` is for the page, `words` is the doctor's own line."""

    def __init__(self, code, words):
        super().__init__(words)
        self.code, self.words = code, words


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
                 environ=None):
        self.folder, self.home, self.on = Path(folder), home, on
        self.choose_folder = choose_folder or platform.choose_folder
        self.onedrive_roots, self.environ = onedrive_roots, environ
        self.pointer = pointer or (lambda: Path(platform.data_dir(home, on=on)).parent / POINTER_NAME)
        self.checks = doctor.CHECKS if checks is None else checks
        self._dialog = threading.Lock()                 # one folder window at a time

    def seen(self, folder=None):
        extra = {"onedrive_roots": self.onedrive_roots} if self.onedrive_roots else {}
        if self.environ is not None:
            extra["environ"] = self.environ
        return doctor.Seen(data=str(folder or self.folder), home=self.home, on=self.on, **extra)

    def report(self, folder=None):
        """The checks for the folder now in use, as data for a page. `ready` follows the doctor's own rule."""
        seen = self.seen(folder)
        results = doctor.run_checks(seen, self.checks)
        rows = [dict(row, required=check.required) for row, (check, _) in zip(doctor.as_data(results), results)]
        ready = not any(check.required and line.kind in (doctor.FIX, doctor.NOT_CHECKED) for check, line in results)
        return {"ok": True, "ready": ready, "folder": seen.tilde(seen.folder()), "checks": rows}

    def choose(self, prompt):
        """Open the system's folder window and check the answer. None on Cancel (nothing changes). On a good answer the folder
        is kept (pointer file written) and the new report is returned. Raises Refused (the folder's own words; code "busy" if a
        window is already open) or lets a PlatformError out (the window could not be opened)."""
        if not self._dialog.acquire(blocking=False):
            raise Refused("busy", "")
        try:
            answer = self.choose_folder(prompt)
        finally:
            self._dialog.release()
        if answer is None:
            return None
        folder = self.accept(answer)
        self.remember(folder)
        self.folder = folder
        return self.report(folder)

    def accept(self, answer):
        """The folder `answer` names if it passes, else Refused. The answer is untrusted text; nothing is written here."""
        path = _plain_path(str(answer) if isinstance(answer, Path) else answer)
        if path is None or path.is_symlink() or not path.is_dir():
            raise Refused("folder_refused", doctor.cant_save_line(self.seen(path or self.folder)).words)
        try:
            resolved = platform.check_data_dir(path, self.onedrive_roots() if self.onedrive_roots else platform.onedrive_roots(
                self.home, on=self.on))
        except platform.PlatformError as e:
            raise Refused("folder_refused", str(e))
        if not doctor._can_save_in(resolved):
            raise Refused("folder_refused", doctor.cant_save_line(self.seen(resolved)).words)
        return resolved

    def remember(self, folder):
        platform.write_file(self.pointer(), str(folder) + "\n")

    def remembered(self):
        """The folder in the pointer file if it still passes every check, else None. An unreadable, odd or refused value is
        ignored, never trusted."""
        try:
            text = Path(self.pointer()).read_text(encoding="utf-8")
        except (OSError, ValueError, platform.PlatformError, platform.NotBuiltYet):
            return None
        try:
            return self.accept(text.strip())
        except Refused:
            return None
