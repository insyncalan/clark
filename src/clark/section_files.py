"""A file for a section template (#96, R2): the logic of POST /api/section-file {project, section}.

Files are links to the project's shared folder (the owner's decision 3 on #96): clark copies the chosen file into the client
folder (Settings › Publishing › Client folder, projects.publish_client), in its "Report files" folder, and the section keeps only
{name, rel, bytes}, where rel is "Report files/<name>": an address relative to the report, so the link opens from the client's copy
of the report, which sits in that folder. The steps, each refused in plain words with the next step, and nothing written until
all are clear:

1. The request: exactly {project, section}; the project is there and not archived; the section is this project's and is a
   template that holds a file (changes.FILE_TYPES); it has room for one more (its own add_file says so).
2. The client folder is saved and still one clark may copy into (to_client.preflight: there, a folder, writable, not clark's data
   or backups, not the Local folder). Without one: "Choose one in Settings ... then add the file again."
3. The system's Open dialog (platform.choose_open_file). Cancel changes nothing.
4. The chosen file: an ordinary file (a link is judged by where it leads, and not followed when read), not in a place clark never
   reads (reach.py: secrets, system folders, clark's own data), not a secret's name, at most MAX_FILE_BYTES.
5. The copy: "Report files" is made if it is not there (it must be a real folder inside the client folder, not a link out of it);
   the name is platform.safe_name's; a taken name gets a number ("Plan (2).pdf"); the bytes go to a temporary file beside it and
   are linked into place, so nothing is ever overwritten (to_client.RealFs.write_file, the one place clark writes into a client
   folder). A file already in "Report files" is used where it is, with no copy.
6. The section: changes.make_section_file adds the entry in one step with one Undo. If that fails, the copy just made is taken
   back; Undo later takes the file off the section and leaves it in the folder (clark never deletes a client's file).

Never logged: the file's name, its folder or its contents. Standard library only, Python 3.9.
"""
import json
import os
import re
import stat
from pathlib import Path

from clark import changes, platform, reach, section_bodies, to_client
from clark import store as clark_store
from clark.store import Invalid
from clark.section_kinds.doclinks import FILES_FOLDER, file_name

PROJECT_CODE = re.compile(r"[A-Z][A-Z0-9]{2,6}")
SECTION_ID = re.compile(r"[A-Za-z0-9|_-]{1,64}")
KEYS = ("project", "section")
MAX_FILE_BYTES = 100 * 1024 * 1024      # a report's paper, not a whole drive: the copy is read into memory once
MAX_NUMBER = 99                         # "Plan (2).pdf" ... "Plan (99).pdf", then the person is asked to rename
PROMPT = "Choose a file to add to the report"

MESSAGES = {
    "bad_request": "That request could not be read. Reload the page and try again.",
    "bad_project_code": "Use a project code of 3 to 7 capital letters or digits.",
    "project_not_found": changes.NO_PROJECT,
    "archived": changes.PROJECT_NOT_ACTIVE,
    "section_gone": "That section isn't in the report any more. Reload the page.",
    "no_file_here": changes.NO_FILE_HERE,
    "busy": "A publish or another file is being worked on. Wait for it to finish, then add the file again.",
    "no_client_folder": "This project has no client folder yet, so the file has nowhere to go. Choose one in Settings, under "
                        "Publishing, then add the file again.",
    "client_folder_refused": "{reason} Then add the file again.",
    "dialog_failed": "{reason}",
    "full": "{reason}",
    "not_a_file": "That isn't a file clark can copy. Choose an ordinary file, then try again.",
    "never_place": "That file is in a place clark never copies from, such as a folder of passwords or of the system. Choose "
                   "another file.",
    "too_big": f"That file is bigger than {MAX_FILE_BYTES // (1024 * 1024)} MB, too big to copy into the report's folder. Put it "
               "in the client's folder yourself and add a link to it instead.",
    "unreadable": "That file could not be read. Check it opens on this computer, then try again.",
    "files_folder": "The client folder has something called “Report files” that clark can't use as a folder. Rename it, then "
                    "add the file again.",
    "no_name": "That file's name can't be used in the client folder. Rename the file, then try again.",
    "names_taken": f"There are already {MAX_NUMBER} files with that name in the client folder's “Report files” folder. Rename "
                   "the file, then try again.",
    "copy_failed": "The file could not be copied into the client folder, and nothing was added. Check that OneDrive is running "
                   "and the folder can be written to, then try again.",
}
ADDED = ("“{name}” was copied into the client folder's “Report files” folder and added. OneDrive uploads it from there; Undo "
         "takes it off the section and leaves it in the folder.")
USED = "“{name}” is already in the client folder's “Report files” folder, so it was added without a copy."


class Refused(Exception):
    def __init__(self, code, status=409, **fmt):
        super().__init__(code)
        self.code, self.status = code, status
        self.message = MESSAGES[code].format(**fmt) if fmt else MESSAGES[code]


def fail(r):
    return r.status, {"ok": False, "code": r.code, "message": r.message}


def numbered(name, n):
    """`name` with ' (n)' before its ending: "Plan.pdf" -> "Plan (2).pdf"; a name with no ending gets it at the end."""
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem:
        return f"{name} ({n})"
    return f"{stem} ({n}).{ext}"


def _checked_request(body):
    if not isinstance(body, dict) or set(body) != set(KEYS):
        raise Refused("bad_request", 400)
    code, ref = body["project"], body["section"]
    if not isinstance(code, str) or not PROJECT_CODE.fullmatch(code):
        raise Refused("bad_project_code", 400)
    if not isinstance(ref, str) or not SECTION_ID.fullmatch(ref):
        raise Refused("section_gone", 400)
    return code, ref


def _before_the_dialog(pub, code, ref):
    """Steps 1 and 2, read only: the client folder to copy into."""
    store = pub.store()
    try:
        row = store.read("projects", ref=code)
        if row is None:
            raise Refused("project_not_found", 404)
        if clark_store.is_archived(store.con, code):
            raise Refused("archived")
        section = next((s for s in store.read("report_sections", code) or [] if s.get("id") == ref), None)
        if section is None:
            raise Refused("section_gone", 404)
        kind = next((t for t in changes.FILE_TYPES if t == section.get("type")), None)
        if kind is None:
            raise Refused("no_file_here", 400)
        try:                                                # room for one more (the step checks again: this only saves a dialog)
            text = clark_store.check_section_body(kind, section.get("body") or "")
            section_bodies.TEMPLATES[kind].add_file(json.loads(text) if text else None,
                                                    {"name": "a", "rel": f"{FILES_FOLDER}/a", "bytes": 0})
        except (Invalid, section_bodies.Bad) as e:
            raise Refused("full", reason=str(e)) from None
        saved = row.get("publish_client") or None
        if not saved:
            raise Refused("no_client_folder")
        checked = to_client.preflight(pub.fs, saved, data_dir=pub.data_dir, onedrive_roots=pub.onedrive_roots,
                                      local_folder=store.last_publish_folder(code) or row.get("publish_local"),
                                      backups_dir=pub.backups_dir)
        if not checked["ok"]:
            raise Refused("client_folder_refused", reason=checked["message"])
        return Path(checked["folder"])
    finally:
        store.close()


def _source(pub, chosen):
    """Step 4: the chosen file's real path and its bytes."""
    try:
        real = reach.real(str(chosen))
    except reach.BadPath:
        raise Refused("not_a_file") from None
    own = [reach.real(str(d)) for d in (pub.data_dir, pub.backups_dir) if d]          # resolved, as `real` is (/var is /private/var)
    if reach.never_reason(real, reach.home(), own[0]) or reach.secret_name(real.parts[1:]) or any(reach.inside(real, d) for d in own):
        raise Refused("never_place")
    try:
        st = os.stat(real)
    except OSError:
        raise Refused("unreadable") from None
    if not stat.S_ISREG(st.st_mode):
        raise Refused("not_a_file")
    if st.st_size > MAX_FILE_BYTES:
        raise Refused("too_big")
    try:
        data = pub.fs.read_bytes(str(real), limit=MAX_FILE_BYTES + 1)
    except OSError:
        raise Refused("unreadable") from None
    if len(data) > MAX_FILE_BYTES:
        raise Refused("too_big")
    return real, data


def _files_folder(pub, client):
    """Step 5's folder: "Report files" inside the client folder, made if it is not there, and a real folder inside it."""
    folder = client / FILES_FOLDER
    if not pub.fs.exists(str(folder)):
        try:
            pub.fs.make_folder(str(folder))
        except OSError:
            raise Refused("copy_failed") from None
    if not pub.fs.is_dir(str(folder)) or os.path.islink(folder):
        raise Refused("files_folder")
    if Path(pub.fs.realpath(str(folder))).parent != Path(pub.fs.realpath(str(client))):
        raise Refused("files_folder")
    return folder


def _identity(pub, path):
    """Which file `path` is, as the disk says right after this request wrote it; None if it cannot be read."""
    try:
        return pub.fs.identity(str(path))
    except (OSError, AttributeError):
        return None


def _copy(pub, folder, real, data):
    """Step 5's copy: the name the file is saved under in `folder` (it is used where it is when it is already there)."""
    if Path(pub.fs.realpath(str(real.parent))) == Path(pub.fs.realpath(str(folder))):
        try:
            return file_name(real.name), False, None
        except section_bodies.Bad:
            raise Refused("no_name") from None
    try:
        name = platform.safe_name(real.name.lstrip(". ") or "untitled", folder=folder)     # no leading dot first, so a device name is seen as one
        name = platform.safe_name(name.lstrip(". "), folder=folder)       # and the whole name checked again after all stripping
        name = file_name(name)
    except (platform.PlatformError, section_bodies.Bad):
        raise Refused("no_name") from None
    for n in range(1, MAX_NUMBER + 1):
        candidate = name if n == 1 else platform.safe_name(numbered(name, n), folder=folder)
        try:
            if pub.fs.write_file(str(folder / candidate), data, replaces=False):
                return candidate, True, _identity(pub, folder / candidate)
        except (OSError, platform.PlatformError):
            raise Refused("copy_failed") from None
    raise Refused("names_taken")


def attach(pub, body):
    """POST /api/section-file for the publisher `pub` (publish_flow.Publisher: its store, fs, dialogs, folders and the step that
    adds the entry). (status, body)."""
    try:
        code, ref = _checked_request(body)
    except Refused as r:
        return fail(r)
    if not pub.lock.acquire(blocking=False):
        return fail(Refused("busy"))
    try:
        try:
            client = _before_the_dialog(pub, code, ref)
            try:
                chosen = pub.choose_open_file(PROMPT)
            except platform.PlatformError as e:
                raise Refused("dialog_failed", reason=str(e).rstrip()) from None
            if chosen is None:
                return 200, {"ok": True, "cancelled": True}
            real, data = _source(pub, chosen)
            folder = _files_folder(pub, client)
            name, copied, made = _copy(pub, folder, real, data)
        except Refused as r:
            return fail(r)
        except Invalid:
            return fail(Refused("copy_failed", 503))
        entry = {"name": name, "rel": f"{FILES_FOLDER}/{name}", "bytes": len(data)}
        status, reply = pub.add_section_file({"project": code, "id": ref, "entry": entry})
        if status != 200:
            if copied and made is not None and _identity(pub, folder / name) == made:
                try:
                    pub.fs.remove(str(folder / name))          # the copy this request made a moment ago, and nothing else
                except OSError:
                    pass
            return status, reply
        return 200, {**reply, "file": entry, "message": (ADDED if copied else USED).format(name=name)}
    finally:
        pub.lock.release()
