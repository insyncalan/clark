"""#308: one shared way for a browser test to start the real server, with every store-backed route the launcher wires.

A test that built its server with only `change` and `undo` left every other route off (503 or 404), so a body edit, a picture
or a newer route was never exercised by it. `real_server(path)` starts test_server.Running with the same handlers the launcher
(clark/__main__.py main) builds over the data file: change, undo, section_image, sneak, people (write, undo, list), word_import,
word_export, activity, as_at, milestones, draft_email_sent, app_settings, ask_folders and safety. A test that needs to watch or break
a seam passes `seam(real, which)` (the tests' usual shape), which returns the function to put in place of the real "change" or
"undo" handler (`which` is that word); one that needs a route which is not made from the file alone (publisher, use_cases, movement, ask,
profile, logs) passes it as a keyword, as it would to Running.
"""
import subprocess
import sys

from _demo import USER
from _paths import SRC
from clark import (activity_read, app_settings, as_at, ask_folders, changes, draft_email_feed, milestone_feed, safety, sneak,
                   word_route)
from test_server import Running, Stoppable  # noqa: F401 (Stoppable is re-used by test_server_setup)


def real_handlers(path, data_for, who=USER, roots=None, choose_folder=None):
    """The launcher's handlers over the data file at `path`, by the name the server's keyword has. RULE 14: the Word export's
    folder window is never the system's here: `choose_folder` (prompt -> folder or None) or, by default, Cancel."""
    roots = [] if roots is None else roots
    return {"change": changes.make_change(path, roots, who),
            "undo": changes.make_undo(path, roots, who),
            "section_image": changes.make_section_image(path, roots, who),
            "section_body": changes.make_section_body(path, roots, who),
            "sneak": sneak.make_read(data_for),
            "people": changes.make_people(path, roots, who),
            "people_undo": changes.make_people_undo(path, roots, who),
            "people_list": changes.make_people_list(path, roots, who),
            "word_import": word_route.make_word_import(path, roots),
            "word_export": word_route.make_word_export(path, roots, choose_folder=choose_folder or (lambda prompt: None)),
            "activity": activity_read.make_read(path, data_for),
            "as_at": as_at.AsAt(path),
            "milestones": milestone_feed.make_feed(data_for),
            "draft_email_sent": draft_email_feed.make_sent(path, roots, by_user=who),
            "app_settings": app_settings.AppSettings(path, roots),
            "ask_folders": ask_folders.AskFolders(path, roots, data_dir=path.parent),
            "safety": safety.Safety(path, roots)}


def real_server(path, data_for, who=USER, roots=None, seam=None, choose_folder=None, **kw):
    """A started Running (the caller closes it) whose routes are the real handlers over `path`; `kw` is what Running takes
    (page_html, projects, publisher, ...) and replaces a handler of the same name."""
    handlers = real_handlers(path, data_for, who, roots, choose_folder)
    if seam is not None:
        handlers = {k: seam(v, "change" if k == "section_body" else k) if k in ("change", "undo", "section_body") else v for k, v in handlers.items()}
    if "change" in kw and "section_body" not in kw:
        kw["section_body"] = kw["change"]          # #273: a section's content goes to its own route; a test that stands in for the change handler stands in for it too
    handlers.update({k: kw.pop(k) for k in list(kw) if k in handlers})
    running = Running(data_for=data_for, **{k: handlers[k] for k in ("change", "undo")}, **kw)
    for name, handler in handlers.items():
        if name not in ("change", "undo"):
            setattr(running.httpd, name, handler)
    return running


def real_setup_start(spawned):
    """item 836: the `start` seam of launch.start_setup made real: the argument list the launcher built is run as a process (the real
    `python3 -m clark.setup_mode`), its output added to the log the launcher named. Each process is put in `spawned` for the caller
    to stop. This is the only way a test starts setup mode for real."""
    def start(argv, env, log_path, cwd=None):
        with open(log_path, "ab") as log:
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        spawned.append(process)
        return process
    return start


def stop_all(spawned):
    for process in spawned:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
