"""The Projects overview's read (row 1299, slice S3): the logic of GET /api/projects-overview. Unguarded and read only; server.py only routes to it.

One row for each live (not archived) project with the values the overview table shows: Asking, Brand, Read folders, Review days, Client folder and
Last backup, each as it is in the store, and which of the three things worth a look the project has. `overview_rows` is the pure part (no file, no
clock, no store); `ProjectsOverview.read` gathers the values and hands them to it. It writes nothing: the store is opened to read and closed.

Where a value lives today. Asking is one switch for this computer (app_settings.ask_enabled), so every row shows the same answer. Read folders are
the project's own (source_folders) plus the ones for all projects. Brand and Review days are the project's own; a value is an override when it
differs from the default (brand "generic", Review days from install_defaults). The client folder is the project's publish_client. Last backup is the
newest backup of this computer (backups are not per project), as whole days; none at all is flagged too (no_backup).

Answer: (200, {ok, projects: [{code, name, asking, brand, brand_override, folders, review_days, review_override, client_folder, last_backup_days,
attention: [code, ...]}], attention_count, default_brand, default_review_days}) or (status, {ok: False, code, message}). `attention_count` is the number
of projects with at least one thing to look at. The page words everything; this module sends codes and numbers.
"""
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from clark import ask_folders, backup, timefmt
from clark.store import Invalid, open_store, review_days_for

BRAND_DEFAULT = "generic"       # projects.brand's default (schema.sql)
BACKUP_OLD_DAYS = 1             # a last backup older than this many whole days is something to look at (the mock-up's rule: more than one day)
NO_CLIENT_FOLDER, BACKUP_OLD, NO_BACKUP, ASKING_NO_FOLDERS = "no_client_folder", "backup_old", "no_backup", "asking_no_folders"
LIMIT = 500                     # as GET /api/projects
PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")

MESSAGES = {
    "busy": "The saved data could not be opened just now. Wait a moment and try again.",
}


def days_since(stamp, now, local=None):
    """Whole calendar days (on the user's own clock) from `stamp`, a backup's time, to `now`, an aware time; 0 when it is today or later.
    `local` turns the stamp into the user's own time by the zone's rules for that date (daylight saving); without it `now`'s own offset is used.
    None when `stamp` is not a time clark stores."""
    try:
        then = timefmt.parse(stamp)
        then = local(then) if local else then.astimezone(now.tzinfo or timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    return max(0, (now.date() - then.date()).days)


def attention_for(row):
    """The codes of what is worth a look in one overview row, in a fixed order."""
    out = []
    if not row["client_folder"]:
        out.append(NO_CLIENT_FOLDER)
    days = row["last_backup_days"]
    if days is None:
        out.append(NO_BACKUP)
    elif days > BACKUP_OLD_DAYS:
        out.append(BACKUP_OLD)
    if row["asking"] and row["folders"] == 0:
        out.append(ASKING_NO_FOLDERS)
    return out


def effective_folders(own, shared):
    """How many folders asking reads for a project: the ones for all projects first, then its own, the same path once, at most MAX_FOLDERS
    (the rule of AskService.folders_for)."""
    out = []
    for p in [*shared, *own]:
        if p not in out:
            out.append(p)
    return min(len(out), ask_folders.MAX_FOLDERS)


def overview_rows(projects, folder_counts, shared, asking, default_days, backup_days):
    """The overview's rows, one for each project row in `projects` (dicts from the store), in the order given, at most LIMIT.
    A row that is not a dict, or whose code is not a project code, is left out. `folder_counts` maps a code to the paths of the folders that project
    has of its own, `shared` is the paths of the folders all projects share, `asking` is this computer's switch, `default_days` the Review days default,
    `backup_days` the whole days since the newest backup (None: none)."""
    out = []
    for p in projects:
        if len(out) >= LIMIT:
            break
        if not isinstance(p, dict) or not isinstance(p.get("code"), str) or not PROJECT_CODE.fullmatch(p["code"]):
            continue
        name, brand, client = p.get("name"), p.get("brand"), p.get("publish_client")
        brand = brand if isinstance(brand, str) and brand else BRAND_DEFAULT
        days = review_days_for(p)
        row = {"code": p["code"], "name": name if isinstance(name, str) and name.strip() else p["code"], "asking": asking is True,
               "brand": brand, "brand_override": brand != BRAND_DEFAULT,
               "folders": effective_folders(folder_counts.get(p["code"], []), shared),
               "review_days": days, "review_override": days != default_days,
               "client_folder": client.strip() if isinstance(client, str) else "", "last_backup_days": backup_days}
        row["attention"] = attention_for(row)
        out.append(row)
    return out


class ProjectsOverview:
    """`db_path` is the database; `onedrive_roots` as the launcher's; `backups` is the folder of backups (beside the database unless given);
    `now` and `local` are seams for tests (a function giving an aware time; a function giving a time in the user's zone). Without `now`, the
    system's own rules for each date are used, so a backup from the other side of a daylight-saving change keeps its own day."""

    def __init__(self, db_path, onedrive_roots=None, *, backups=None, now=None, local=None):
        self.db_path = Path(db_path)
        self.backups = Path(backups) if backups is not None else self.db_path.parent / "backups"
        self.onedrive_roots = list(onedrive_roots or [])
        self.now = now or (lambda: datetime.now().astimezone())
        self.local = local or (None if now else (lambda t: t.astimezone()))
        self.lock = threading.Lock()

    def fail(self, code):
        return {"ok": False, "code": code, "message": MESSAGES[code]}

    def newest_backup_days(self, now):
        try:
            found = backup.entries(self.backups)
        except OSError:
            return None
        return days_since(max(e.stamp for e in found), now, self.local) if found else None

    def read(self):
        with self.lock:
            try:
                store = open_store(self.db_path, onedrive_roots=self.onedrive_roots)
            except Invalid:
                return 409, self.fail("busy")
            try:
                projects = store.read("projects", archived=False)
                counts = {}
                for r in store.read("source_folders"):
                    counts.setdefault(r["project"], []).append(r["path"])
                asking = store.ask_enabled()
                default_days = store.con.execute("SELECT review_days FROM install_defaults WHERE id = 1").fetchone()[0]
            finally:
                store.close()
        now = self.now()
        rows = overview_rows(sorted(projects, key=lambda p: p["code"]), counts, ask_folders.shared_folders(self.db_path.parent), asking,
                             default_days, self.newest_backup_days(now))
        return 200, {"ok": True, "projects": rows, "attention_count": sum(1 for r in rows if r["attention"]),
                     "default_brand": BRAND_DEFAULT, "default_review_days": default_days}
