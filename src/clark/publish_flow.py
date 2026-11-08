"""Publish and To client as the server runs them (#43; BRD FR-80 to FR-83, BR-8). The routes in server.py call this and nothing else.

One class, Publisher, with three public methods (each returns (status, body) for the server to send):
- publish(body): POST /api/publish {project, to_client, on_clash?, new_name?, confirmed?}. The report is built once
  (publish.build). With To client ticked, everything that could stop the copy is decided first and nothing is written until it
  is all clear (the saved folder is still there and allowed, a taken name has been answered, the finished bytes hold nothing
  that was meant to be left out). Then the system's Save dialog chooses the Local file, Local is written and read back, the same
  bytes are copied into the client folder and read back (to_client.copy_to_client), and one `publications` row records it.
  The request never names a folder or a file: the client folder is the one saved in Settings (projects.publish_client).
- client_folder(body): POST /api/client-folder {project, action: "choose" | "clear" | "paste" | "choose_local" | "clear_local" (row 852: the Local
  folder, projects.publish_local, where the Save window opens), value (paste only)}. Saves or
  clears that folder as an ordinary step (so it is in history and can be undone). It never writes into the folder. A pasted
  folder (item 647) is a path on this computer (pasted_folder); it must be inside a OneDrive root and then gets exactly the
  checks a chosen one gets. A pasted link is refused by its form alone: it is never opened or matched to a folder.
- latest(code): GET /api/publication?project=. The date and kind of the latest publication, for the report bar; no path.

This is the only module besides to_client.py that may reach a client-folder writer (a test pins it). It opens its own short-lived
store for each call (the server answers from several threads), takes no network address, and sends nothing anywhere: OneDrive's
own sync does the upload.

Standard library only, Python 3.9.
"""
import getpass
import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import unicodedata
from pathlib import Path

from clark import changes, milestones, page, past_files, platform, publish, publish_pdf, section_files, to_client
from clark.store import Invalid, NumberTaken, open_store

PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")
CLIENT_WORKBOOK = True      # item 713: every file made here carries the client workbook (or the too-large sentence) in its data block
MIN_MARKER = 8                       # a shorter piece of text can't be searched for without finding it everywhere
TEXT_FIELDS = {"milestones": ("name", "description"), "actions": ("description",), "raid": ("description",),
               "decisions": ("decision",), "use_cases": ("title", "headline")}
NOTE_FIELDS = ("internal_note", "movement", "reasoning", "options", "response_action")      # working notes: never in a report
PICK_PROMPT = "Choose the folder OneDrive syncs for the client"
LOCAL_PROMPT = "Choose the folder to save this report in"
SAVE_PROMPT = "Save the report"
PREVIEW_KEEP = 4                     # previews waiting to be opened; the oldest goes first
PREVIEW_SECONDS = 120                # a preview that is not opened in this time is dropped
MAX_PASTE = 2000                     # a pasted folder or link longer than this is refused unread
# A pasted link, by its form only (item 647): a scheme (https://, http://, file://, ...) or a web host name before a slash, such as
# a SharePoint, OneDrive or 1drv.ms address without its https://. It is never opened or matched to a folder.
LINK_FORM = re.compile(r"(?i)[a-z][a-z0-9+.-]*://|(?:[a-z0-9-]+\.)+[a-z]{2,}(?::\d+)?[/?#]")

# What the route says, by stable `code`. The words are the product's (RULES.md): plain, "clark" in lower case. The messages of
# to_client.MESSAGES (the catalogue of the spec) are used as they are for everything that module decides.
MESSAGES = {
    "bad_project_code": "Give the project's code (3 to 7 capital letters or digits).",
    "project_not_found": "There is no project with that code.",
    "busy": "A publish is already running. Wait for it to finish, then try again.",
    "cancelled": to_client.MESSAGES["cancelled"],
    "dialog_failed": "{reason} Nothing was published.",
    "same_folder": "That is the client's folder. Save the local copy somewhere else. Nothing was published.",
    "local_not_html": "The local copy's name must end in .html. Nothing was published.",
    "local_clark_files": "That place is where clark keeps its own files. Save the local copy somewhere else. Nothing was published.",
    "local_failed": "{name} could not be saved. Check you can edit that folder and that the disk has room, then try again. Nothing was published.",
    "local_differs": "{name} was not saved as it was made (the folder may be syncing). Nothing was published. Try again.",
    "earlier_too_big": publish.EARLIER_TOO_BIG + " Nothing was published.",
    "not_made": "{reason} Nothing was published.",
    "not_recorded": "Published, but clark could not record it. The files are fine; publish again to record it.",
    "done_local": "Published (Publication {number}). Saved locally as “{name}”.",
    "number_taken": "Another publication was made at the same moment, so this one was not saved. Nothing was published. Publish again.",
    "look_at": " Look at: {items}.",
    "brand_link": " The web link comes from the brand's styling file, not from anything you wrote: ask whoever looks after the brand to remove it.",
    "folder_saved": "The client folder is saved.",
    "folder_cleared": "The client folder is cleared.",
    "folder_unchanged": "That is already the client folder.",
    "local_not_saved": "The local folder could not be saved. Nothing was changed. Try again.",
    "local_saved": "Local folder saved",
    "local_cleared": "Local folder cleared",
    "bad_action": "Say whether to choose a folder or clear it.",
    "paste_unknown": "That isn't a folder clark can find. Choose folder picks it for you.",
    "paste_not_synced": "That folder isn't one OneDrive syncs on this computer. Choose folder picks it for you.",
    "paste_link": "A link can't be used here. Choose folder picks the folder on this computer. Nothing was saved.",
    "client_folder_refused": "{reason}",
    "settings_failed": "The client folder could not be saved. Nothing was changed. Try again.",
    "brand_styling": "The brand's styling file has a web link in it, so the report can't go out. Ask whoever looks after the brand to remove it.",
    "brand_address": "The brand's styling file has a link to an address outside the report, so the report can't go out. Ask whoever looks after the brand to remove it.",
    "brand_picture": "The brand's styling file has a picture in a form clark cannot put in the report, so the report can't go out. Ask whoever looks after the brand to change it.",
    "page_shape": "Something is wrong inside clark. Nothing was published. Tell the clark team, and say what you were doing.",
    **{k: publish_pdf.MESSAGES[k] for k in ("bad_pdf_request", "no_chrome", "pdf_failed")},
    "db_unreadable": "The records could not be read. Restart clark and try again.",
    "preview_not_made": "The preview could not be made. {reason}",
    "preview_ready": "The preview is ready. This is the version kept on this computer, not the client's copy. It is not published.",
    "export_failed": "The workbook could not be made. Nothing was changed. Try again.",
}


# The start of each PublishError that is about clark's own page or the brand's styling, and the fixed words that stand for it.
_FAULTS = (("The brand's tokens.css uses @import", "brand_address"), ("The brand's tokens.css names a font or image by address", "brand_address"),
           ("The brand's tokens.css, or the page, embeds a picture", "brand_picture"), ("The brand's tokens.css", "brand_styling"), ("The page clark builds", "page_shape"),
           ("The page has a server token", "page_shape"))


def made_words(error):
    """What a PublishError says to a person. The database's own wording (it can carry a system error) and the wording about
    the brand's styling file or the shape of clark's page (internal names) are never shown: each has a fixed sentence."""
    text = str(error).rstrip()
    if text.startswith("The database could not be read"):
        return MESSAGES["db_unreadable"]
    for start, key in _FAULTS:
        if text.startswith(start):
            return MESSAGES[key]
    return text


def code_of(message):
    """The stable code for a to_client message: the name of its entry in to_client.MESSAGES (or "bad_request")."""
    for key, text in to_client.MESSAGES.items():
        if text == message:
            return key
    return "bad_request"


def _text(value):
    return value if isinstance(value, str) else None


class Markers(list):
    """The texts that must be absent, with `where`: for each, the ID of the item it came from (to name it in a refusal)."""
    where = None


def markers_for(store, code, published, template=""):
    """Text that must NOT be in the finished file, read from what the store holds and select() dropped or never carries: the ID
    and main text of every row that was left out (archived, the client flag off, hidden, a Sensitive or other excluded label),
    and every row's internal note, Movement and working notes. Texts shorter than MIN_MARKER are not used (they would be found
    anywhere); an ID always is. A note that is also in `template` (the bare page, which every file holds whatever the data)
    is not a marker either: it cannot tell a leak from the page's own words. A left-out row's text that is also part of something published (the same words in a kept
    row) is not a marker, because it may rightly be in the file. check_copy looks for each in its plain, lower-case, HTML-escaped
    and JSON-escaped spellings."""
    data = published["data"]
    kept_ids = {r["id"] for kind in publish.KINDS for r in data.get(kind, ()) if isinstance(r, dict) and "id" in r}
    kept_text = [v for kind in ("projects",) + publish.KINDS + ("workstreams",)
                 for r in ([data["project"]] if kind == "projects" else data.get(kind, ())) if isinstance(r, dict)
                 for v in r.values() if isinstance(v, str)]
    kept_text += [s.get("body") or "" for s in published.get("sections", ()) if isinstance(s, dict)]
    kept_text += [v for r in data.get("documents", ()) if isinstance(r, dict) for v in r.values() if isinstance(v, str)]     # #74: the links the client may see
    found, where = [], {}
    bare = to_client._key(template)

    def add(text, item):
        found.append(text)
        where.setdefault(text, item)
    for kind in publish.KINDS:
        for row in store.read(kind, project=code):
            for field in NOTE_FIELDS:
                if _text(row.get(field)) and len(row[field].strip()) >= MIN_MARKER and to_client._key(row[field].strip()) not in bare:
                    add(row[field].strip(), row.get("id"))
            if row.get("id") in kept_ids:
                continue
            add(row["id"], row["id"])
            for field in TEXT_FIELDS[kind]:
                value = (_text(row.get(field)) or "").strip()
                if len(value) >= MIN_MARKER and not any(value in text for text in kept_text):
                    add(value, row["id"])
    for row in store.read("documents", project=code):              # #74: a document's id, title and link are absent unless a kept document carries the same words (publish carries no id)
        add(row["id"], row["id"])
        for field in ("title", "url"):
            value = (_text(row.get(field)) or "").strip()
            if len(value) >= MIN_MARKER and not any(value in text for text in kept_text):
                add(value, row["id"])
    gantt_markers(store, code, published, add)
    out = Markers(dict.fromkeys(found))
    out.where = where
    return out


def gantt_markers(store, code, published, add):
    """Row 998: the Gantt markers are read from the RAW lines in the store, never from what publish.gantt_for_client produced, so a
    bug in its decision cannot blind the scan too. The policy is the same rules, read again here: the tab is in the file only when the
    project's show_gantt_client is exactly 1; a line is in it only when its `show` is exactly 1. A line that cannot be in the file
    (eye off, or no Gantt tab) is a marker by id, name and every column; a line that can be is a marker for each column the project's
    hidden list (publish._gantt_hidden) takes out. A value that is also in the published data other than the Gantt copy (the same
    words in a kept row) is not a marker, and neither is one shorter than MIN_MARKER; what the Gantt copy itself carries exempts nothing."""
    data = published["data"]
    kept = json.dumps({k: v for k, v in data.items() if k != "gantt"}, ensure_ascii=False, default=str)
    project = store.read("projects", ref=code) or {}
    tab = type(project.get("show_gantt_client")) is int and project["show_gantt_client"] == 1
    hidden = publish._gantt_hidden(project)
    columns = publish.PUBLISH_FIELDS["gantt_lines"][2:]                  # every column a line may carry, after id and name

    def text(v):
        return v.strip() if isinstance(v, str) else str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else ""
    rows = [(r, tab and type(r.get("show")) is int and r["show"] == 1) for r in store.read("gantt_lines", project=code)]
    shown = [r[f] for r, eyed in rows if eyed for f in ("id", "name") + columns if f in r and (f in ("id", "name") or f not in hidden)]
    kept += "\n" + "\n".join(text(v) for v in shown)                      # what a line that can be in the file may legitimately show
    for row, eyed in rows:
        if not eyed:
            add(row["id"], row["id"])
        for field in (tuple(f for f in columns if f in hidden) if eyed else ("name",) + columns):
            value = text(row.get(field))
            if len(value) >= MIN_MARKER and value not in kept:
                add(value, row["id"])


class Publisher:
    """The publish routes' logic. `db_path` is the database; `onedrive_roots` as the launcher's. Seams for tests: `fs` (the disk
    the client folder is on; to_client.RealFs), `choose_save_file` and `choose_folder` (the system's dialogs), `today` (a
    function giving YYYY-MM-DD), `by_user` (who is publishing) and `data_dir` (clark's own folder, which a client folder may
    never be in)."""

    def __init__(self, db_path, onedrive_roots=None, *, fs=None, choose_save_file=None, choose_folder=None, today=None,
                 by_user=None, data_dir=None, branding=None, backups_dir=None, choose_open_file=None):
        self.db_path = Path(db_path)
        self.onedrive_roots = list(platform.onedrive_roots() if onedrive_roots is None else onedrive_roots)
        self.fs = fs or to_client.RealFs()
        self.choose_save_file = choose_save_file or platform.choose_save_file
        self.choose_folder = choose_folder or platform.choose_folder
        self.choose_open_file = choose_open_file or platform.choose_open_file      # #96: a file for a section template
        self.today = today or milestones.today
        self.by_user = by_user or getpass.getuser
        self.data_dir = Path(data_dir) if data_dir else platform.data_dir()
        self.branding, self.backups_dir = branding, backups_dir
        self.add_section_file = changes.make_section_file(self.db_path, self.onedrive_roots, self.by_user)   # #96: the step that adds a copied file
        self.lock = threading.Lock()          # one publish at a time (and one file for a section: section_files.py)
        self.previews, self.preview_lock = {}, threading.Lock()      # {nonce: (bytes, time made)}: in memory only

    def store(self):
        return open_store(self.db_path, onedrive_roots=self.onedrive_roots)

    # ----- publish -----
    def publish(self, body):
        if not self.lock.acquire(blocking=False):
            return 409, self.fail("busy")
        try:
            store = self.store()
            self.pdf_step = None
            try:
                status, out = self._publish(store, body if isinstance(body, dict) else {})
                publish_pdf.finish(self.pdf_step, out, status)          # the PDF is saved only once the report is
                return status, out
            finally:
                store.close()
        finally:
            self.lock.release()

    def fail(self, code, status_message=None, **extra):
        return {"ok": False, "code": code, "message": status_message or MESSAGES[code], **extra}

    def _publish(self, store, body):
        pdf_req, body = publish_pdf.split(body)          # the PDF's keys are read here; the rest is as it always was
        if pdf_req["error"]:
            return 400, self.fail("bad_pdf_request")
        self.pdf_step = publish_pdf.Step(pdf_req, self)
        code = body.get("project")
        if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        row = store.read("projects", ref=code)
        if row is None:
            return 404, self.fail("project_not_found")
        saved = row.get("publish_client") or None
        asked = to_client.validate_request(body, saved)
        if asked["status"] != 200:
            return 400, self.fail(code_of(asked["message"]), asked["message"])
        want_client, confirmed = asked["to_client"], asked["confirmed"]
        today = str(self.today())
        last = store.last_publish_folder(code)
        try:       # item 713: the earlier reports are read from the folder last used here; the Save window's own folder is read again below
            built = publish.build(store, code, today, self.branding, body.get("section_style"), workbook=CLIENT_WORKBOOK,
                                  past_reports=past_files.listing(last, code) if last else None)
        except publish.PublishError as e:
            return 409, self.fail("not_made", MESSAGES["not_made"].format(reason=made_words(e)))
        week = built["project"]["week_ending"]
        body_bytes, digest = built["body"], built["sha256"]
        plan, same, markers = None, None, []
        self.folder_warning = None
        if want_client:
            early, plan, same, markers = self.client_plan(store, code, built, saved, last, today, week, body)
            if early is None and self.pdf_step.on and plan is not None:
                early = self.pdf_step.plan_client(self, plan, confirmed)         # a taken PDF name is asked about now too
            early = self.pdf_step.with_note(self, early, saved)
            if early is not None:
                return early
        # Nothing has been written. The system's own Save dialog chooses the Local file; Cancel cancels everything.
        default = publish.file_name(code, week, today)
        try:
            chosen = self.choose_save_file(SAVE_PROMPT, default, start=self.local_start(row, last))
        except platform.PlatformError as e:
            return 409, self.fail("dialog_failed", MESSAGES["dialog_failed"].format(reason=str(e).rstrip()))
        if chosen is None:
            return 200, self.fail("cancelled")
        if "\x00" in str(chosen):         # a file name cannot hold a NUL; said in words, not a fault
            return 409, self.fail("local_failed", MESSAGES["local_failed"].format(name="The file"))
        dest = Path(chosen)
        past = past_files.listing(dest.parent, code, dest.name)           # item 713: the folder the file is going to, not the one last used
        if past != built["past_reports"]:
            try:
                keep = built["number"] if store.next_publication(code) == built["number"] else None
                built = publish.build(store, code, today, self.branding, body.get("section_style"), keep, workbook=CLIENT_WORKBOOK,
                                      past_reports=past)
            except publish.PublishError as e:
                return 409, self.fail("not_made", MESSAGES["not_made"].format(reason=made_words(e)))
            body_bytes, digest, week = built["body"], built["sha256"], built["project"]["week_ending"]
        if want_client:
            # The Save window may have been open a while. What the client is to get is made again now, so a flag turned off
            # meanwhile is honoured; if anything differs, every check before the copy runs again on the new file.
            try:
                # #120: the same number while it is still the next one; else the file is made again with the new next number
                keep = built["number"] if store.next_publication(code) == built["number"] else None
                again = publish.build(store, code, today, self.branding, body.get("section_style"), keep, workbook=CLIENT_WORKBOOK,
                                       past_reports=past)
            except publish.PublishError as e:
                return 409, self.fail("not_made", MESSAGES["not_made"].format(reason=made_words(e)))
            # The client folder is checked again whether or not the file changed: it may have been swapped for a link (or
            # another folder) while the window was open, and the copy goes only to the real place this check finds.
            if again["sha256"] != digest or again["number"] != built["number"]:
                built = again
                body_bytes, digest = built["body"], built["sha256"]
                week = built["project"]["week_ending"]
            early, plan, same, markers = self.client_plan(store, code, built, saved, last, today, week, body)
            early = self.pdf_step.with_note(self, early, saved)
            if early is not None:
                return early
        if want_client and self.pdf_step.on and plan is not None:
            early = self.pdf_step.plan_client(self, plan, confirmed)
            if early is not None:
                return early
        if saved and self.inside_folder(dest.parent, saved):
            return 409, self.fail("same_folder")
        if dest.suffix.lower() != ".html":
            return 409, self.fail("local_not_html")
        if any(self.inside_folder(dest, own) for own in (self.data_dir, self.backups_dir) if own):
            return 409, self.fail("local_clark_files")
        try:
            earlier_local = self.earlier_bytes(dest)    # #120: a file this one replaces is put back if the record is refused
            earlier_link = self.earlier_link(dest) if earlier_local is None else None      # #480: so is a link it replaces (the link, not its target)
            earlier_client = None
            if plan is not None and plan["replaces"]:   # #120: an Overwrite's old file is put back if the record is refused, as Local's is
                earlier_client = self.earlier_bytes(Path(plan["folder"]) / plan["name"])
        except publish.PublishError:                    # #326: too big to keep a copy of: nothing has been written yet
            return 409, self.fail("earlier_too_big")
        if self.pdf_step.on:                  # made only after every refusal above; saved after the report (publish_pdf.finish)
            early = self.pdf_step.prepare(self, dest, built, today, store, code, markers if want_client else None, saved)
            if early is not None:
                return early
        written = self.write_local(dest, body_bytes, digest)
        if written is not None:
            return 409, written
        # Local is saved. The copy comes next; whatever happens to it, Local stays and the publish is logged.
        client = None
        if plan is not None:
            try:
                client = to_client.copy_to_client(
                    self.fs, plan["folder"], plan["name"], body_bytes, project=code, at=today, markers=markers,
                    replaces=plan["replaces"], confirmed=confirmed, asked=plan["asked"], local_sha256=digest,
                    guard={"data_dir": self.data_dir, "backups_dir": self.backups_dir, "identity": plan.get("identity")})
            except Exception:         # the copy was taken back by copy_to_client; Local stays and is recorded
                client = to_client.ClientResult(False, "failed", to_client.MESSAGES["copy_failed_local_kept"].format(
                    reason="something went wrong while checking it."), nothing_written=True)
        elif same is not None:
            client = same
        if client is not None and client.action in ("ask", "confirm_overwrite", "cancel"):
            # The name needed asking about after all (something appeared meanwhile): Local is saved, the copy is not made.
            client = to_client.ClientResult(False, "failed", to_client.MESSAGES["copy_failed_local_kept"].format(
                reason=client.message), nothing_written=True)
        client_path = client.path if client is not None and client.ok else None
        number = built["number"]
        try:
            seq = store.log_publication(code, dest, week, digest, self.by_user(), client_path=client_path, number=number)
        except NumberTaken:               # #120: the files say a number they do not have: take back what this call wrote, and only that
            self.take_back(dest, digest, earlier_local, earlier_link)
            if client_path is not None:
                self.take_back(client_path, digest, earlier_client)
            return 409, self.fail("number_taken")
        except (Invalid, OSError) as e:
            return 409, self.fail("not_recorded", MESSAGES["not_recorded"],
                                  local_saved=True, local_name=dest.name)
        self.pdf_step.record(store, seq)           # #269: the PDF is saved after this, and its name goes on this row then
        if client is None:
            return 200, {"ok": True, "code": "done", "action": "done",
                         "message": MESSAGES["done_local"].format(number=number, name=dest.name),
                         "local_name": dest.name, "to_client": False, "number": number, "publication": number}
        status, out = self.reply(client)
        out.update(local_saved=True, local_name=dest.name, to_client=True, number=number)
        if out.get("ok") is True:
            out["publication"] = number          # #120: the per-project number, for the dialog's success line
        if out.get("ok") and out["message"].startswith("Published."):
            out["message"] = f"Published (Publication {number})." + out["message"][len("Published."):]
        if self.folder_warning:
            out["warning"] = self.folder_warning
            out["message"] += " " + self.folder_warning
        return status, out

    def client_plan(self, store, code, built, saved, last, today, week, body):
        """Every check that stands before the copy, on the finished bytes. (early reply or None, plan, same, markers)."""
        body_bytes = built["body"]
        pre = to_client.preflight(self.fs, saved, data_dir=self.data_dir, onedrive_roots=self.onedrive_roots, local_folder=last,
                                  backups_dir=self.backups_dir)
        if not pre["ok"]:             # the folder's own message comes first, whatever the file holds
            kind, got = to_client.plan_client_copy(
                self.fs, saved_folder=saved, data=body_bytes, project=code, today=today, week_ending=week,
                data_dir=self.data_dir, onedrive_roots=self.onedrive_roots, local_folder=last, backups_dir=self.backups_dir,
                choice=body.get("on_clash"), new_name=body.get("new_name"), at=today)
            return self.reply(got), None, None, []
        self.folder_warning = pre.get("warning")
        markers = markers_for(store, code, built["published"], page.page_html(self.branding, view=True))
        problems = to_client.check_copy(body_bytes, markers=markers, folder=saved)
        if problems:
            held = to_client.MESSAGES["held_back"].format(what=to_client.held_words(problems))
            if "text that was meant to be left out" in problems:
                held += self.which_items(body_bytes, markers)
            return (409, self.result(False, "refused", held + (MESSAGES["brand_link"] if "a <link> tag" in problems else ""))), \
                None, None, markers
        kind, got = to_client.plan_client_copy(
            self.fs, saved_folder=saved, data=body_bytes, project=code, today=today, week_ending=week,
            data_dir=self.data_dir, onedrive_roots=self.onedrive_roots, local_folder=last, backups_dir=self.backups_dir,
            choice=body.get("on_clash"), new_name=body.get("new_name"), at=today)
        if kind == "stop":
            return self.reply(got), None, None, markers
        return (None, got, None, markers) if kind == "copy" else (None, None, got, markers)

    def which_items(self, body, markers):
        """" Look at: ID, ID." for the items whose left-out text is in the file (so the person can fix them), or ""."""
        where = getattr(markers, "where", None) or {}
        ids = []
        for m in to_client.markers_found(body, markers):      # one pass over the file, then a look-up for each marker
            if where.get(m) and where[m] not in ids:
                ids.append(where[m])
        return MESSAGES["look_at"].format(items=", ".join(ids[:10])) if ids else ""

    def inside_folder(self, a, b):
        """Whether folder `a` is `b` or below it (as written and with links followed; case and accent form ignored)."""
        try:
            return to_client._inside(a, b) or to_client._inside(self.fs.realpath(a), self.fs.realpath(b))
        except (OSError, ValueError):
            return False

    def write_local(self, dest, data, digest):
        """Write the Local file and read it back; None when it is good, else the failure to send."""
        try:
            platform.write_file(dest, data)
            if hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
                return self.fail("local_differs", MESSAGES["local_differs"].format(name=dest.name))
        except (OSError, platform.PlatformError) as e:
            return self.fail("local_failed", MESSAGES["local_failed"].format(name=dest.name))
        return None

    def earlier_bytes(self, path):
        """The bytes of a file already at `path`, else None: what a refused record puts back (#120). A file over 64 MB
        raises PublishError (#326): it could not be put back whole, so it is not replaced."""
        try:
            return publish.read_earlier(path)
        except OSError:
            return None

    def earlier_link(self, path):
        """#480: where a link at `path` points, else None: what a refused record puts back in place of the file this publish wrote."""
        try:
            return os.readlink(path)
        except OSError:
            return None

    def take_back(self, path, digest, earlier, earlier_link=None):
        """Remove a file this publish wrote, only while it still holds the bytes written; a file it replaced is put back, and
        so is a link it replaced (#480: publish.put_link_back, which never replaces anything that is not our file)."""
        try:
            if earlier is None and earlier_link is not None:
                publish.put_link_back(path, earlier_link, digest)
            elif publish.still_ours(path, digest):
                if earlier is None:
                    Path(path).unlink()
                else:
                    platform.write_file(Path(path), earlier)
        except (OSError, platform.PlatformError, publish.PublishError):
            pass

    def result(self, ok, action, message, **extra):
        return {"ok": ok, "code": action, "action": action, "message": message, **extra}

    def reply(self, r):
        """A ClientResult as (status, body). A question is 200 with `clash`; a refusal or failure is 409; success is 200."""
        out = self.result(r.ok, r.action, r.message)
        if r.name:
            out["name"] = r.name
        if r.action == "ask" and r.clash:
            c = r.clash
            out.update(clash=True, numbered=c.get("numbered"), can_overwrite=c.get("can_overwrite", True), note=c.get("note"))
            return 200, out
        if r.action == "cancel":
            return 200, out
        if r.ok:
            out["replaced"] = r.replaced
            return 200, out
        return 409, out

    def local_start(self, row, last):
        """Where the Save window opens (row 852): the Local folder saved in Settings while it is still a folder, else where the report was last saved."""
        saved = row.get("publish_local")
        return saved if saved and Path(saved).is_dir() else last

    # ----- the local folder setting (row 852) -----
    def local_folder(self, store, row, code, action):
        saved = row.get("publish_local") or None
        if action == "clear_local":
            return self.save_local(store, code, saved, None)
        try:
            picked = self.choose_folder(LOCAL_PROMPT, start=saved if saved and Path(saved).is_dir() else None)
        except platform.PlatformError as e:
            return 409, self.fail("dialog_failed", MESSAGES["dialog_failed"].format(reason=str(e).rstrip()).replace(" Nothing was published.", ""))
        if picked is None or not str(picked).strip():       # cancelled, or an empty answer: nothing chosen, nothing saved
            return 200, {"ok": True, "changed": False, "folder": saved}
        try:
            real = Path(picked).resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            return 409, self.fail("paste_unknown")
        if not real.is_dir() or not real.is_absolute():
            return 409, self.fail("paste_unknown")
        return self.save_local(store, code, saved, str(real))

    def undo_local(self, store, code, step):
        """Put the Local folder back as the step left it, only for a step that changed this project's publish_local and nothing else."""
        rows = store.step_rows(step)
        if not rows or not all(r["table"] == "projects" and r["key"] == code and r.get("field") in ("publish_local", "updated_at") for r in rows) \
                or not any(r.get("field") == "publish_local" for r in rows):
            return 409, self.fail("local_not_saved")
        try:
            done = store.undo(step, self.by_user(), place="menu")
        except Invalid:
            return 409, self.fail("local_not_saved")
        if not done.get("reversed"):
            return 409, self.fail("local_not_saved")
        return 200, {"ok": True, "changed": True, "folder": (store.read("projects", ref=code) or {}).get("publish_local") or None}

    def save_local(self, store, code, saved, folder):
        if folder == saved:
            return 200, {"ok": True, "changed": False, "folder": saved, "message": MESSAGES["local_saved" if folder else "local_cleared"]}
        try:
            with store.step("dashboard", self.by_user(), place="menu") as st:
                st.update("projects", code, {"publish_local": folder})
                apply_id = st.peek_apply_id()
        except Invalid:
            return 409, self.fail("local_not_saved")
        return 200, {"ok": True, "changed": True, "folder": folder, "folder_name": to_client.folder_name(folder) if folder else None,
                     "message": MESSAGES["local_saved" if folder else "local_cleared"], "apply_id": apply_id}

    # ----- the client folder setting -----
    def client_folder(self, body):
        body = body if isinstance(body, dict) else {}
        code, action = body.get("project"), body.get("action")
        if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        allowed = {"project", "action", "value"} if action == "paste" else {"project", "action", "apply_id"} if action == "undo_local" else {"project", "action"}
        if action == "undo_local" and (type(body.get("apply_id")) is not int or not 1 <= body["apply_id"] < 2 ** 63):
            return 400, self.fail("bad_action")
        if set(body) - allowed or action not in ("choose", "clear", "paste", "choose_local", "clear_local", "undo_local") or (action == "paste" and not isinstance(body.get("value"), str)):
            return 400, self.fail("bad_action")
        with self.lock:
            store = self.store()
            try:
                row = store.read("projects", ref=code)
                if row is None:
                    return 404, self.fail("project_not_found")
                if action == "undo_local":
                    return self.undo_local(store, code, body["apply_id"])
                if action.endswith("_local"):
                    return self.local_folder(store, row, code, action)
                saved = row.get("publish_client") or None
                if action == "clear":
                    return self.save_folder(store, code, saved, None)
                if action == "paste":
                    picked, refused = self.pasted_folder(body["value"])
                    if refused:
                        return 409, self.fail(refused)
                else:
                    try:
                        start = saved or next(iter(self.onedrive_roots), None)
                        picked = self.choose_folder(PICK_PROMPT, start=start)
                    except platform.PlatformError as e:
                        return 409, self.fail("dialog_failed", MESSAGES["dialog_failed"].format(reason=str(e).rstrip()).replace(
                            " Nothing was published.", ""))
                    if picked is None:
                        return 200, {"ok": True, "changed": False, "folder": saved}
                checked = to_client.preflight(self.fs, str(picked), data_dir=self.data_dir, onedrive_roots=self.onedrive_roots,
                                              local_folder=store.last_publish_folder(code) or row.get("publish_local"),
                                              backups_dir=self.backups_dir)
                if not checked["ok"]:
                    return 409, self.fail("client_folder_refused", checked["message"])
                return self.save_folder(store, code, saved, checked["folder"], checked.get("warning"))
            finally:
                store.close()

    # ----- a pasted client folder (item 647) -----
    def pasted_folder(self, value):
        """A pasted path as (the folder it names, resolved, None) or (None, the MESSAGES code of the refusal). The folder must
        already exist and be inside one of the OneDrive roots; client_folder then checks it exactly as a chosen one. Anything with
        the form of a link (LINK_FORM) is refused as one: it is never opened, and no folder is guessed from its words."""
        text = value.strip()
        if not text or len(text) > MAX_PASTE or any(unicodedata.category(ch) in ("Cc", "Cf") for ch in text):
            return None, "paste_unknown"
        if LINK_FORM.match(text):
            return None, "paste_link"
        if text.startswith("/") or text == "~" or text.startswith("~/"):
            return self.synced_folder(Path(text).expanduser())
        return None, "paste_unknown"            # a relative path, ~name and every other kind of text

    def synced_folder(self, path):
        if not path.is_absolute() or ".." in path.parts:
            return None, "paste_unknown"
        try:
            real = path.resolve(strict=True)    # links followed: where the folder really is is what must be inside a root
            if not real.is_dir():
                return None, "paste_unknown"
            roots = [Path(r).resolve() for r in self.onedrive_roots]
        except (OSError, RuntimeError, ValueError):
            return None, "paste_unknown"
        if not any(real == r or r in real.parents for r in roots):
            return None, "paste_not_synced"
        return real, None

    def save_folder(self, store, code, saved, folder, warning=None):
        if folder == saved:
            return 200, {"ok": True, "changed": False, "folder": saved, "message": MESSAGES["folder_unchanged" if folder else "folder_cleared"]}
        try:
            with store.step("dashboard", self.by_user(), place="menu") as st:
                st.update("projects", code, {"publish_client": folder})
        except Invalid as e:
            return 409, self.fail("settings_failed", MESSAGES["settings_failed"])
        return 200, {"ok": True, "changed": True, "folder": folder, "folder_name": to_client.folder_name(folder),
                     "warning": warning, "message": MESSAGES["folder_saved" if folder else "folder_cleared"]}

    # ----- a file for a section template (#96) -----
    def section_file(self, body):
        """POST /api/section-file {project, section}: the system's Open dialog, the copy into the client folder's "Report files"
        folder and the step that adds the file to the section (section_files.py has the rules)."""
        return section_files.attach(self, body)

    # ----- preview and export (#147) -----
    def preview(self, body):
        """POST /api/preview {project}: the published page as publish would make it (publish.build), kept in memory for one visit
        to the address in `url`. No publication is logged, no number is taken, and nothing is written to any folder."""
        code = body.get("project") if isinstance(body, dict) else None
        if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        refused = to_client.section_style_refusal(body)
        if refused:
            return 400, self.fail(code_of(refused), refused)
        store = self.store()
        try:
            if store.read("projects", ref=code) is None:
                return 404, self.fail("project_not_found")
            try:
                built = publish.build(store, code, str(self.today()), self.branding, body.get("section_style"), workbook=CLIENT_WORKBOOK)
            except publish.PublishError as e:
                return 409, self.fail("preview_not_made", MESSAGES["preview_not_made"].format(reason=made_words(e)))
        finally:
            store.close()
        nonce, now = secrets.token_urlsafe(24), time.monotonic()
        with self.preview_lock:
            for k in [k for k, v in self.previews.items() if now - v[1] > PREVIEW_SECONDS]:
                del self.previews[k]
            while len(self.previews) >= PREVIEW_KEEP:
                del self.previews[next(iter(self.previews))]
            self.previews[nonce] = (built["body"], now)
        return 200, {"ok": True, "code": "preview_ready", "message": MESSAGES["preview_ready"], "url": "/preview?id=" + nonce}

    def take_preview(self, nonce):
        """The page's bytes for an address from preview(), once; None when it is unknown, used or too old."""
        with self.preview_lock:
            got = self.previews.pop(nonce, None)
        return got[0] if got and time.monotonic() - got[1] <= PREVIEW_SECONDS else None

    def export(self, code):
        """GET /api/export?project=: the project's workbook (excel.export_project), made in a temporary folder that is removed
        afterwards. On success (200, {"name": "<CODE>-<date>.xlsx", "data": bytes}); a refusal is a plain sentence."""
        if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        from clark import excel         # here, not at the top: the launcher imports this module before the vendored openpyxl is reachable
        store = self.store()
        folder = None
        try:
            if store.read("projects", ref=code) is None:
                return 404, self.fail("project_not_found")
            today = str(self.today())
            folder = Path(tempfile.mkdtemp(prefix="clark-export-"))
            name, warnings = f"{code}-{today}.xlsx", []
            here = Path(self.db_path).parent                                      # beside clark.db, where the record is kept
            try:
                # The record of the export (what the import later compares with) is kept beside clark.db under the export id
                # inside the workbook and the project (the browser saves the download where clark can't see, and the
                # import finds the record by that id, from any folder and after an edit or a re-save); the workbook itself stays
                # in the temporary folder, which is removed. Each export has its own id, so neither replaces the other, and
                # save_state and prune_hash_records hold excel.STATE_LOCK, so two exports at once both keep their record.
                made = excel.export_project(store, code, folder / name, folder / "state.json", on=today, warnings=warnings, branding=self.branding,
                                       exported_by=self.by_user(), reuse=excel.latest_export(here / excel.STATE_FILE, code))      # the name publish records; the owner has no source yet (projects has none), so the Cover says "the person who sent it to you"
                data = Path(made).read_bytes()
                record = excel.load_state(folder / "state.json", made)
                key = (excel.id_key(code, record["export_id"]) if record.get("export_id")
                       else excel.hash_key(record.get("hash") or excel.file_hash(made)))
                with excel.STATE_LOCK:
                    before = excel.find_state(here / excel.STATE_FILE, key)[1]
                    if key.startswith("id:") and before.get("hash") == record.get("hash"):
                        # the same file exported again keeps its id (excel.export's reuse), and what its imports recorded
                        record.update({k: before[k] for k in ("imported_hash", "imported_step", "created") if k in before})
                    excel.save_state(here / excel.STATE_FILE, key, record)
                live = {r["code"] for r in store.read("projects") if not r.get("archived")}
                excel.prune_hash_records(here / excel.STATE_FILE, self.today(), live=live, keep=key)       # older than 30 days, over the cap, or an archived project's: gone (#181)
            except (excel.Refused, OSError, ValueError, platform.PlatformError):          # excel.TooBig is a Refused too
                return 409, self.fail("export_failed")
            return 200, {"name": name, "data": data, "warnings": warnings}
        finally:
            store.close()
            if folder is not None:
                shutil.rmtree(folder, ignore_errors=True)

    def template(self):
        """GET /api/export?template=1 (#454): the import template, an export's workbook with no rows (excel.template_bytes). It
        reads nothing from the store and takes nothing from the request, so no project, person or item is in it.
        (200, {"name", "data", "warnings"})."""
        from clark import excel         # here, not at the top: as export()
        return 200, {"name": excel.TEMPLATE_NAME, "data": excel.template_bytes(self.today()), "warnings": []}

    # ----- the report bar -----
    def latest(self, code):
        """The latest publication of the project, for the report bar: {"at", "to_client"} or {} (no paths, no hash), and (#437) the number the
        next one will have."""
        if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
            return 400, self.fail("bad_project_code")
        store = self.store()
        try:
            if store.read("projects", ref=code) is None:
                return 404, self.fail("project_not_found")
            last = store.latest_publication(code)
            following = store.next_publication(code)        # #437: the number the next publication will have, for the Publish dialog's line
        finally:
            store.close()
        return 200, {"ok": True, "latest": {"at": last["at"][:10], "to_client": last["to_client"]} if last else None,
                     "next": following, "pdf": publish_pdf.available()}
