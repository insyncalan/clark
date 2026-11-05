"""The earlier reports of one project in a publish folder (item 713), for the published page's Past reports menu.

`listing(folder, code, current)` reads the folder's own names, never a stored history, so a report that is gone is simply not listed.
A name counts only when it is exactly what publish.file_name makes for this project: `{CODE}-report-{YYYY-MM-DD}.html` (the code of
this project only, a real date, a plain regular file: no link, no folder). The file being written now (`current`) is left out. The
list is newest first (equal dates by name), at most MAX_LISTED long. A folder that cannot be listed gives an empty list.
Rows are {"week_ending": "YYYY-MM-DD", "file": "name.html"}. Standard library only."""
import os
import re
from datetime import date

MAX_LISTED = 20
MAX_NAME = 200


def listing(folder, code, current=None):
    pattern = re.compile(re.escape(str(code)) + r"-report-(\d{4}-\d\d-\d\d)\.html")
    found = []
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                name = entry.name
                m = pattern.fullmatch(name) if len(name) <= MAX_NAME else None
                if m is None or name == current:
                    continue
                try:
                    date.fromisoformat(m.group(1))
                    if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                        continue
                except (ValueError, OSError):
                    continue
                found.append((m.group(1), name))
    except (OSError, TypeError, ValueError):
        return []
    found.sort(key=lambda r: r[1])
    found.sort(key=lambda r: r[0], reverse=True)
    return [{"week_ending": week, "file": name} for week, name in found[:MAX_LISTED]]
