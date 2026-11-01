"""#308: one shared way for a browser test to start the real server, with every store-backed route the launcher wires.

A test that built its server with only `change` and `undo` left every other route off (503 or 404), so a body edit, a picture
or a newer route was never exercised by it. `real_server(path)` starts test_server.Running with the same handlers the launcher
(clark/__main__.py main) builds over the data file: change, undo, section_image, sneak, people (write, undo, list), word_import,
word_export, activity, milestones, draft_email_sent, app_settings, ask_folders and safety. A test that needs to watch or break
a seam passes `seam(real, which)` (the tests' usual shape), which returns the function to put in place of the real "change" or
"undo" handler (`which` is that word); one that needs a route which is not made from the file alone (publisher, use_cases, movement, ask,
profile, logs) passes it as a keyword, as it would to Running.
"""
from _demo import USER
from clark import (activity_read, app_settings, ask_folders, changes, draft_email_feed, milestone_feed, safety, sneak,
                   word_route)
from test_server import Running


def real_handlers(path, data_for, who=USER, roots=None):
    """The launcher's handlers over the data file at `path`, by the name the server's keyword has."""
    roots = [] if roots is None else roots
    return {"change": changes.make_change(path, roots, who),
            "undo": changes.make_undo(path, roots, who),
            "section_image": changes.make_section_image(path, roots, who),
            "sneak": sneak.make_read(data_for),
            "people": changes.make_people(path, roots, who),
            "people_undo": changes.make_people_undo(path, roots, who),
            "people_list": changes.make_people_list(path, roots, who),
            "word_import": word_route.make_word_import(path, roots),
            "word_export": word_route.make_word_export(path, roots),
            "activity": activity_read.make_read(path, data_for),
            "milestones": milestone_feed.make_feed(data_for),
            "draft_email_sent": draft_email_feed.make_sent(path, roots, by_user=who),
            "app_settings": app_settings.AppSettings(path, roots),
            "ask_folders": ask_folders.AskFolders(path, roots, data_dir=path.parent),
            "safety": safety.Safety(path, roots)}


def real_server(path, data_for, who=USER, roots=None, seam=None, **kw):
    """A started Running (the caller closes it) whose routes are the real handlers over `path`; `kw` is what Running takes
    (page_html, projects, publisher, ...) and replaces a handler of the same name."""
    handlers = real_handlers(path, data_for, who, roots)
    if seam is not None:
        handlers = {k: seam(v, k) if k in ("change", "undo") else v for k, v in handlers.items()}
    handlers.update({k: kw.pop(k) for k in list(kw) if k in handlers})
    running = Running(data_for=data_for, **{k: handlers[k] for k in ("change", "undo")}, **kw)
    for name, handler in handlers.items():
        if name not in ("change", "undo"):
            setattr(running.httpd, name, handler)
    return running
