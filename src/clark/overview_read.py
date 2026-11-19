"""Row 1299 slice 2 (R2a): the read behind the Projects overview, GET /api/projects-overview. One reply with, for every live project, only
the few values the overview draws (name, brand, review days, client folder, how many folders asking reads), plus the two per-computer
values (asking on or off, the newest backup). It uses only the seams the server already carries (projects, data_for, ask_folders,
app_settings, safety), reads and never writes, and never hands on a work item. A seam that is missing, or a value that can't be read,
is None in the reply (never a made-up 0, "" or False): the page says "not known".

An empty client folder is "" (read, and nothing is set); None means it could not be read."""
import re

from clark import backup, store as clark_store, timefmt

LIMIT = 500                     # the same cap as GET /api/projects
NAME_LIMIT = 200
PATH_LIMIT = 1000
MAX_FOLDERS = 20                # what asking reads for one project (ask_folders.MAX_FOLDERS)
CODE = re.compile(r"[A-Z0-9]{3,7}")


def text_or_none(value, limit):
    return value[:limit] if isinstance(value, str) else None


def folder_count(service, code):
    """Own folders plus the folders for all projects, once each, at most MAX_FOLDERS (the same count asking reads), or None."""
    if service is None:
        return None
    try:
        status, body = service.read(code)
    except Exception:
        return None
    if status != 200 or not isinstance(body, dict):
        return None
    own, shared = body.get("folders"), body.get("shared")
    if not isinstance(own, list) or not isinstance(shared, list):
        return None
    seen = []
    for p in [*shared, *own]:
        if isinstance(p, str) and p not in seen:
            seen.append(p)
    return min(len(seen), MAX_FOLDERS)


def project_row(server, code, name):
    try:
        data = server.data_for(code)
    except Exception:
        data = None
    if data is None:
        return None                                      # the project went while we read: not listed
    proj = data.get("project") if isinstance(data, dict) else None
    proj = proj if isinstance(proj, dict) else {}
    folder = proj.get("publish_client") if "publish_client" in proj else None
    one = {"code": code, "name": name,
           "brand": text_or_none(proj.get("brand") or ("generic" if proj else None), 100),
           "review_days": clark_store.review_days_for(proj) if proj else None,
           "client_folder": "" if (proj and folder is None) else text_or_none(folder, PATH_LIMIT),
           "read_folders": folder_count(getattr(server, "ask_folders", None), code)}
    return one


def asking(server):
    service = getattr(server, "app_settings", None)
    if service is None:
        return None
    try:
        status, body = service.read_ask()
    except Exception:
        return None
    on = body.get("ask_enabled") if status == 200 and isinstance(body, dict) else None
    return on if type(on) is bool else None


def last_backup(server):
    """{"when": text, "days": whole days from the newest believed copy's local day to today's local day} or None."""
    safety = getattr(server, "safety", None)
    folder = getattr(safety, "folder", None)
    if folder is None:
        return None
    try:
        found = [e for e in backup.entries(folder) if not e.ahead]
        newest = max(found, key=lambda e: e.stamp)
        then = timefmt.parse(newest.stamp).astimezone()
        today = clark_store.clock().astimezone()
    except (OSError, ValueError, OverflowError):
        return None
    return {"when": timefmt.local_text(newest.stamp), "days": max(0, (today.date() - then.date()).days)}


def overview(server):
    """The reply body (the route sends it with 200). Raises what server.projects() raises (the route answers Busy)."""
    rows = []
    for row in server.projects():
        if len(rows) >= LIMIT:
            break
        try:
            code = str(row["code"])
        except (KeyError, TypeError, IndexError):
            continue
        if not CODE.fullmatch(code):
            continue
        name = row["name"] if isinstance(row, dict) and isinstance(row.get("name"), str) and row["name"].strip() else code
        one = project_row(server, code, name[:NAME_LIMIT])
        if one is not None:
            rows.append(one)
    try:
        archived = len(server.projects(archived=True))
    except Exception:
        archived = None
    return {"ok": True, "asking": asking(server), "last_backup": last_backup(server), "projects": rows, "archived_count": archived}
