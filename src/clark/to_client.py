"""To client: the logic of copying a published report into the client's folder (#43; BRD FR-80 to FR-83, BR-8).

Pure by design: no server, no database, no network, and no disk of its own. Every fact about the disk comes in through an `fs`
object (the same few methods, so a test can pass a fake that records what is written; RealFs is the real one), and the
caller supplies the paths, the finished file's bytes and the date. The route, the Save dialog and `Store.log_publication`
come later; this module gives them the decisions.

What is here (the spec is docs/handoff/design-43-to-client.md, the cases are tests/fixtures/to-client-cases.json):
- client_file_name(): {CODE}-report-{date}.html, made safe, with the date always kept (a deep folder shortens the code part).
- resolve_clash(): the taken-name choices (Add a number, Rename it, Overwrite, Cancel) as a function of the folder's listing.
- check_client_folder() / preflight(): is this folder one clark may copy into (before anything at all is written).
- check_copy(): the outside-address and other checks of #39, run on the bytes (publish.outside_addresses is #39's own scan).
- copy_to_client(): the byte copy with a read-back and a SHA-256 comparison; send_to_client() runs the whole sequence.
- validate_request(): what the publish request may say (only `to_client: true` can reach the client folder).
- new_dialog_state() / dialog_step() / to_client_dialog() / dialog_request(): the dialog as data, with no page in it.

Only this module writes into a client folder: RealFs.write_file is the one place that does, and a source test
(tests/test_to_client.py) fails if any other module in src/clark reaches it. Standard library only, Python 3.9.
"""
import hashlib
import json
import os
import stat
import html as htmllib
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePath

from clark import platform, publish

SETTING = "projects.publish_client"      # where the folder is kept (docs/handoff/data-model.md): an absolute path on this computer
CHOICES = ("number", "rename", "overwrite", "cancel")
KIND = "client"                          # the kind of publication this module logs
ALLOWED_KEYS = ("project", "to_client", "on_clash", "new_name", "confirmed", "section_style")
MIN_PREFIX = 2                           # a name that has to be shortened keeps at least this much of the code
EXT = ".html"

# The plain-words text. The first group is the catalogue in the fixtures (tests/fixtures/to-client-cases.json), word for word;
# a test fails if they drift apart. The rest follows the same rules: no technical words, "clark" in lower case.
MESSAGES = {
    "clash_title": "A file with that name is already in the client folder",
    "clash_choices": ["Add a number", "Rename it", "Overwrite the existing file", "Cancel"],
    "overwrite_note": "The client's copy is replaced. clark keeps no backup in the client folder, because OneDrive would upload it.",
    "done_new": "Published. Saved locally, and copied to the client folder as “{name}”. OneDrive uploads it from there; clark can't see when that finishes.",
    "done_numbered": "Published. Saved locally, and copied to the client folder as “{name}” because “{asked}” was already there. OneDrive uploads it from there; clark can't see when that finishes.",
    "done_replaced": "Published. Saved locally, and “{name}” in the client folder was replaced. OneDrive uploads it from there; clark can't see when that finishes.",
    "done_same": "Published locally. The client folder already has this exact file (“{name}”), so nothing was copied.",
    "folder_missing_nothing_written": "The client folder “{folder_name}” isn't there. Check that OneDrive is running and the folder is still synced, or choose another folder in Settings. Nothing was published.",
    "copy_failed_local_kept": "Saved locally, but not copied to the client folder: {reason} Nothing was added there.",
    "copy_differs": "Saved locally, but the copy in the client folder did not match the published file, so clark removed it. Try again.",
    "copy_differs_after_overwrite": "Saved locally, but the copy that replaced “{name}” in the client folder did not match the published file. Publish again to put it right.",
}
MESSAGES.update({
    # folder checks (the fixtures' folder cases)
    "not_saved": "No client folder yet. Set it in Settings.",
    "inside_data": "That folder is inside clark's own data folder, which holds the database. Files put there can't reach the client. Choose the folder OneDrive syncs for the client.",
    "holds_data": "That folder contains clark's own data folder, which holds the database. Choose a folder made for the client's files.",
    "is_backups": "That folder is where clark keeps its backups. Choose the folder OneDrive syncs for the client.",
    "is_local": "That is the Local folder. Choose the client's folder, a different one.",
    "missing": "The folder “{folder_name}” isn't there. Check that OneDrive is running and the folder is still synced, or choose another folder.",
    "not_a_folder": "“{folder_name}” is a file, not a folder. Choose a folder.",
    "not_writable": "“{folder_name}” can't be written to. Check you have permission to edit that folder, or choose another.",
    "not_onedrive": "This folder isn't one OneDrive syncs, so the client won't get files put here. It is saved; change it if that isn't what you meant.",
    "too_deep": "That folder is too deep for the report to be saved in it. Choose a folder nearer the top of the drive.",
    # the name choices
    "bad_name": "That name has a character clark can't use in a file name (a hidden or direction-changing character). Type another name.",
    "bad_path": "The saved client folder can't be used. Choose it again in Settings.",
    "empty_name": "Type a name for the file.",
    "folder_has_name": "A folder in the client folder has that name, so it can't be replaced. Add a number, or type another name.",
    "unknown_choice": "That choice isn't one clark offers. Choose one of: Add a number, Rename it, Overwrite the existing file, Cancel.",
    "cancelled": "Cancelled. Nothing was published.",
    "needs_confirm": "Overwriting needs your confirmation. Nothing was copied.",
    "name_appeared": "A file called “{name}” appeared in the client folder while clark was working. Nothing was copied; publish again to choose what to do.",
    "not_same_file": "The file to copy isn't the file that was published, so nothing was copied.",
    "unreadable_back": "Saved locally, but clark could not read the copy back to check it, so it was removed. Try again.",
    "copy_not_removed": "Saved locally, but the copy in the client folder did not match the published file, and clark could not remove it. Delete “{name}” from there, then try again.",
    "overwrite_too_big": "“{name}” in the client folder is too big for clark to keep safe while it replaces it, so it was not replaced. Nothing was copied.",
    "overwrite_unreadable": "“{name}” in the client folder could not be read first, so it was not replaced. Nothing was copied.",
    "restored": "Saved locally, but the copy that replaced “{name}” in the client folder {problem}, so clark put the previous file back. Try again.",
    "restore_failed": "Saved locally, but the copy that replaced “{name}” in the client folder {problem}, and the previous file could not be put back. {reason} “{name}” now holds the wrong copy there. Publish again to put it right.",
    "held_back": "Nothing was published. The report has something in it that must not go to the client ({what}).",
    "refused_nothing_published": "{reason} Nothing was published.",
    "folder_changed": "The client folder changed while clark was working (it is not the folder that was checked), so nothing was copied to it. Check the folder in Settings, then publish again.",
    "not_plain_file": "“{name}” in the client folder is a link or a special file, not an ordinary file, so it can't be replaced. Add a number, or type another name.",
    "name_ends_badly": "A file name can't end with a dot or a space. Type another name.",
    # the request
    "to_client_flag": "Something went wrong with the To client choice. Nothing was published. Restart clark and try again.",
    "confirmed_flag": "Something went wrong with the overwrite confirmation. Nothing was published. Restart clark and try again.",
    "overwrite_unconfirmed": "Overwriting needs your confirmation. Nothing was published. Restart clark and try again.",
    "names_a_folder": "Something went wrong with the folder choice. Nothing was published. Restart clark and try again.",
    "unknown_key": "Something went wrong with the publish. Nothing was published. Restart clark and try again.",
    "bad_project": "Say which project to publish.",
    # the dialog
    "dialog_local": "Local",
    "dialog_to_client": "To client",
    "button_local": "Publish locally",
    "button_client": "Publish and send to the client",
    "client_sees": "The client will see this page.",
    "numbered_preview": "saves as “{numbered}”",
    "working": "Publishing…",
    "rename_label": "New file name",
})

PART_NAME = re.compile(r"\.[^/\\]{1,200}\.html\.\d{1,10}\.[0-9a-f]{8}\.part")       # what platform._write_temp names a temporary file


# ===== The file name =====
def _limit(folder=None):
    """How long a file name may be in `folder`: what platform.safe_name allows (the 120 characters, and Windows' 260 for the
    whole path). Worked out by asking safe_name, so the rule stays in one place."""
    return len(platform.safe_name("x" * 400 + EXT, folder))


def client_file_name(code, week_ending, today, folder=None):
    """{CODE}-report-{week_ending or today}.html made safe (platform.safe_name). On a deep folder safe_name would cut the
    date off the end and two weeks would get the same name; here the code part is shortened instead (CODE-report-, then CODE,
    then its first characters) and the date and .html are always kept. A folder too deep even for that raises
    platform.PlatformError."""
    when = str(week_ending or today)
    tail = f"-{when}{EXT}"
    full = platform.safe_name(f"{code}-report{tail}", folder)
    if full.endswith(tail):
        return full
    room = _limit(folder) - len(tail)
    for prefix in (f"{code}-report", code):
        if len(platform.safe_name(prefix, None)) <= room:
            return platform.safe_name(prefix + tail, folder)
    prefix = platform.safe_name(code, None)[:room].rstrip(". ")
    if len(prefix) < min(MIN_PREFIX, len(code)):
        raise platform.PlatformError(MESSAGES["too_deep"].format(folder=platform.folder_name(folder)))
    return platform.safe_name(prefix + tail, folder)


# ===== A taken name =====
def _entry(e):
    if isinstance(e, str):
        return {"name": e, "kind": "file", "same_content": False}
    return {"name": e["name"], "kind": e.get("kind", "file"), "same_content": bool(e.get("same_content", False))}


def _key(name):
    """A name as the disk compares it: letter case ignored (macOS, OneDrive and SharePoint do), and an accented letter the
    same whether it was typed as one character or as a letter plus an accent (macOS stores the second). Every comparison of
    names in this module goes through here (file names, folder paths, and text searched for a path or a marker)."""
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", str(name)).casefold())


def _find(entries, name):
    """The folder entry with `name` (compared by _key), or None."""
    want = _key(name)
    return next((e for e in entries if _key(e["name"]) == want), None)


def _split(name):
    stem, dot, ext = name.rpartition(".")
    if not dot or not stem or len(ext) > 10:
        return name, ""
    return stem, "." + ext


def numbered_name(name, taken, folder=None):
    """`name` with the next free number: "Report.html" -> "Report (2).html", then (3). `taken` is every name in the folder
    (letter case ignored). The stem is shortened to fit the name limit; the number and the extension never are."""
    taken = {_key(t) for t in taken}
    stem, ext = _split(name)
    limit = _limit(folder)
    n = 2
    while True:
        suffix = f" ({n})"
        keep = max(1, limit - len(suffix) - len(ext))
        candidate = stem[:keep].rstrip(". ") + suffix + ext
        if _key(candidate) not in taken:
            return candidate
        n += 1


def _has_hidden_character(text):
    """Whether text holds a control or invisible formatting character (U+202E, which turns the name round, among them)."""
    return any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") or (unicodedata.category(ch) == "Zs" and ch != " ")
               for ch in str(text or ""))


def rename_target(new_name, folder=None):
    """The file name a typed Rename means: trimmed, ".html" added if it is missing, made safe (platform.safe_name). None if
    nothing but spaces (or only ".html") was typed."""
    typed = (new_name or "").strip()
    if not typed or _key(typed) == EXT or not _split(typed)[0].strip(". "):
        return None
    return platform.safe_name(typed if _key(typed).endswith(EXT) else typed + EXT, folder)


def resolve_clash(name, existing, choice=None, new_name=None, folder=None):
    """What to do with `name` given what is in the client folder. `existing` is a list of {name, kind: file|folder,
    same_content} (or plain names); same_content is only meaningful for the entry with the wanted name. `choice` is None
    (first look), "number", "rename", "overwrite" or "cancel". Returns one of
      {action: "write", name, replaces}    write `name`; replaces is True for Overwrite, which also carries
                                           needs_confirmation: True, so the dialog must confirm it, never silently
      {action: "ask", name, numbered, can_overwrite}   the name is taken: show the dialog (nothing is written)
      {action: "nothing_to_do", name}      the folder already has exactly this file
      {action: "cancel"}
      {action: "refuse", reason, message}  reason: empty_name, folder_has_name or unknown_choice
    Matching ignores letter case."""
    entries = [_entry(e) for e in existing]
    if choice is not None and choice not in CHOICES:
        return _refuse("unknown_choice")
    if choice == "cancel":
        return {"action": "cancel"}
    if choice == "rename":
        if _has_hidden_character(new_name):
            return _refuse("bad_name")
        name, choice = rename_target(new_name, folder), None
        if name is None:
            return _refuse("empty_name")
        if str(new_name).strip().endswith("."):        # "a.html." would be saved as a different name from the one typed
            # (spaces at the end are trimmed, as before: what is saved never ends with one)
            return _refuse("name_ends_badly")
    hit = _find(entries, name)
    if hit is None:
        return {"action": "write", "name": name, "replaces": False}
    if choice == "number":
        return {"action": "write", "name": numbered_name(name, [e["name"] for e in entries], folder), "replaces": False}
    if choice == "overwrite":
        if hit["kind"] == "folder":
            return _refuse("folder_has_name")
        if hit["kind"] != "file":              # a link or a special file is never written over
            return {"action": "refuse", "reason": "not_plain_file", "message": MESSAGES["not_plain_file"].format(name=hit["name"])}
        return {"action": "write", "name": name, "replaces": True, "needs_confirmation": True}
    if hit["kind"] == "file" and hit["same_content"]:
        return {"action": "nothing_to_do", "name": name}
    return {"action": "ask", "name": name, "numbered": numbered_name(name, [e["name"] for e in entries], folder),
            "can_overwrite": hit["kind"] == "file"}


def _refuse(reason):
    return {"action": "refuse", "reason": reason, "message": MESSAGES[reason]}


# ===== The folder =====
def _parts(path):
    return tuple(_key(p) for p in PurePath(path).parts)


def _inside(path, root):
    """path is root or below it, compared by whole names (so clark-old is not inside clark) and without letter case."""
    a, b = _parts(path), _parts(root)
    return len(a) >= len(b) and a[:len(b)] == b


def check_client_folder(path, *, data_dir, onedrive_roots, local_folder, exists, is_dir, writable, backups_dir=None,
                        real_path=None):
    """Whether `path` is a folder clark may copy a report into. Pure: the facts about the disk come in as arguments.
    Returns {ok: True, folder, warning} or {ok: False, message}. Checked in this order: none saved; inside or equal to the
    data folder; containing it; inside or equal to the backups folder; the Local folder; missing; not a folder; not
    writable. A folder outside every OneDrive root passes with a warning (the roots are suggestions only). `real_path` is
    where a link in `path` really leads; the OneDrive warning is about that place."""
    if not path:
        return {"ok": False, "message": MESSAGES["not_saved"]}
    if "\0" in str(path) or not PurePath(path).is_absolute():
        return {"ok": False, "message": MESSAGES["bad_path"]}
    name = platform.folder_name(path)
    if _inside(path, data_dir):
        return {"ok": False, "message": MESSAGES["inside_data"]}
    if _inside(data_dir, path):
        return {"ok": False, "message": MESSAGES["holds_data"]}
    if backups_dir and (_inside(path, backups_dir) or _inside(backups_dir, path)):
        return {"ok": False, "message": MESSAGES["is_backups"]}
    if local_folder and _parts(path) == _parts(local_folder):
        return {"ok": False, "message": MESSAGES["is_local"]}
    if not exists:
        return {"ok": False, "message": MESSAGES["missing"].format(folder_name=name)}
    if not is_dir:
        return {"ok": False, "message": MESSAGES["not_a_folder"].format(folder_name=name)}
    if not writable:
        return {"ok": False, "message": MESSAGES["not_writable"].format(folder_name=name)}
    where = real_path or path
    synced = any(_inside(where, root) for root in onedrive_roots)
    return {"ok": True, "folder": str(path), "warning": None if synced else MESSAGES["not_onedrive"]}


def _preflight_facts(fs, path, *, data_dir, onedrive_roots, local_folder, backups_dir=None):
    """check_client_folder with the facts read from `fs`. A folder that is a link is checked twice, as saved and as it
    really is (a link out to clark's data folder, or the backups, is refused). Reads only: nothing is created or written."""
    if not path:
        return check_client_folder(path, data_dir=data_dir, onedrive_roots=onedrive_roots, local_folder=local_folder,
                                   exists=False, is_dir=False, writable=False, backups_dir=backups_dir)
    if "\0" in str(path) or not PurePath(path).is_absolute():
        return {"ok": False, "message": MESSAGES["bad_path"]}
    facts = {"exists": fs.exists(path), "is_dir": fs.is_dir(path), "writable": fs.writable(path)}
    real = fs.realpath(path) if facts["exists"] else path
    first = check_client_folder(path, data_dir=data_dir, onedrive_roots=onedrive_roots, local_folder=local_folder,
                                backups_dir=backups_dir, real_path=real, **facts)
    if not first["ok"] or _parts(real) == _parts(path):
        return first
    second = check_client_folder(real, data_dir=fs.realpath(data_dir), onedrive_roots=[fs.realpath(r) for r in onedrive_roots],
                                 local_folder=fs.realpath(local_folder) if local_folder else None,
                                 backups_dir=fs.realpath(backups_dir) if backups_dir else None, **facts)
    return second if not second["ok"] else first


def _where(fs, path):
    """(real path, device and inode or None) of `path` as the disk says now; None when it can't be looked at."""
    try:
        return fs.realpath(path), (fs.dir_identity(path) if hasattr(fs, "dir_identity") else None)
    except OSError:
        return None


def checked_folder(fs, path, *, data_dir, onedrive_roots, local_folder, backups_dir=None):
    """preflight, and an ok answer also says `real` (where the folder really is: the copy goes there, never to the saved
    spelling, which a link swapped in later could point anywhere) and `identity` (device and inode). The place is read before
    and after the checks and must be the same, so a folder swapped during the check is refused."""
    if not path or "\0" in str(path) or not PurePath(path).is_absolute():
        return _preflight_facts(fs, path, data_dir=data_dir, onedrive_roots=onedrive_roots, local_folder=local_folder,
                                backups_dir=backups_dir)
    before = _where(fs, path)
    out = _preflight_facts(fs, path, data_dir=data_dir, onedrive_roots=onedrive_roots, local_folder=local_folder,
                           backups_dir=backups_dir)
    if not out["ok"]:
        return out
    after = _where(fs, path)
    if before is None or after is None:
        return {"ok": False, "message": MESSAGES["missing"].format(folder_name=PurePath(path).name or str(path))}
    if before != after:
        return {"ok": False, "message": MESSAGES["folder_changed"]}
    return dict(out, real=after[0], identity=after[1])


def preflight(fs, path, *, data_dir, onedrive_roots, local_folder, backups_dir=None):
    """check_client_folder with the facts read from `fs`. A folder that is a link is checked twice, as saved and as it
    really is (a link out to clark's data folder, or the backups, is refused). Reads only: nothing is created or written."""
    return _preflight_facts(fs, path, data_dir=data_dir, onedrive_roots=onedrive_roots, local_folder=local_folder,
                            backups_dir=backups_dir)


# ===== Checks on the bytes =====
def sha256_of(data):
    return hashlib.sha256(data).hexdigest()


def _spellings(marker):
    """A marker as it can be written in the file: plain, lower case, HTML-escaped (two ways) and JSON-escaped (two ways)."""
    ascii_json = json.dumps(marker)[1:-1]
    for ch in "<>&":                  # the data block writes these as \\u escapes (publish.data_block)
        ascii_json = ascii_json.replace(ch, "\\u%04x" % ord(ch))
    return {marker, marker.lower(), htmllib.escape(marker), htmllib.escape(marker, quote=False), ascii_json,
            json.dumps(marker, ensure_ascii=False)[1:-1]}


def markers_found(data, markers, *, text=None, low=None):
    """The markers whose text is in these bytes, in order. The file is decoded and folded once; each marker is then one
    look-up, so the time grows with the number of markers, not with markers times the size of the file."""
    if text is None:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return []
    if low is None:
        low = _key(text)
    return [m for m in markers if any(s and (s in text or _key(s) in low) for s in _spellings(m))]


def check_copy(data, *, markers, folder=None):
    """What is wrong with these bytes as a file for the client, as a list of short phrases (empty when nothing). It runs
    #39's own scan for outside addresses (publish.outside_addresses) and adds three more: the server's token block, the
    client folder's own path, and any `markers` (text that must be absent, in its plain, lower-case, HTML-escaped and
    JSON-escaped spellings). What goes into the file was decided before it was made (publish.select); this is the
    second look at the finished bytes. `markers` has no default and there is no way to switch the check off (the Head's
    ruling on #43, Q5): the caller says what must be absent, even if that is nothing. Text is compared without letter case
    and in one Unicode form, so a marker typed one way is found written another."""
    if len(data) > publish.MAX_BYTES:
        return ["a file over the size limit"]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ["a file clark did not write as text"]
    found = list(publish.outside_addresses(text))
    if 'id="clark-boot"' in text:
        found.append("clark's own working data")
    low = _key(text)
    if folder and _key(folder) in low:
        found.append("the location of the client folder")
    if markers_found(data, markers, text=text, low=low):
        found.append("text that was meant to be left out")
    return found


# ===== The disk =====
def _kind_of(entry):
    """file, folder, link (a symbolic link, whatever it points to) or other (a pipe, device or socket), without following."""
    if entry.is_symlink():
        return "link"
    if entry.is_dir(follow_symlinks=False):
        return "folder"
    return "file" if entry.is_file(follow_symlinks=False) else "other"


class RealFs:
    """The real disk, for send_to_client. Reads use os; the one write goes through platform.write_file (a temporary file
    beside the new one, then a link or a rename, retrying while OneDrive holds a lock). This is the only code in clark that
    writes into a client folder."""

    def exists(self, path):
        return os.path.exists(path)

    def is_dir(self, path):
        return os.path.isdir(path)

    def writable(self, path):
        return os.access(path, os.W_OK | os.X_OK)         # asks; creates no test file in the client's folder

    def realpath(self, path):
        return os.path.realpath(path)

    def listdir(self, path):
        with os.scandir(path) as it:
            return [{"name": e.name, "kind": _kind_of(e)} for e in it]

    def read_bytes(self, path, limit=None):
        """The file's bytes; with `limit`, at most that many (so a caller can tell a file is bigger than it will hold). Only
        an ordinary file is read: a link is not followed and a pipe or device is never opened for reading (OSError)."""
        with open(path, "rb", opener=platform.open_plain_file) as f:
            return f.read() if limit is None else f.read(limit)

    def dir_identity(self, path):
        """Which folder this is, as the disk says now: device and inode (a link is followed, as a write would)."""
        st = Path(path).stat()
        return (st.st_dev, st.st_ino)

    def write_file(self, path, data, replaces):
        """True if written. With `replaces` False the name is linked into place (platform.write_file_unless_exists), so a file
        that appeared after the listing is never overwritten: False, and the folder is as it was. With `replaces` True it is
        platform.write_file (a temporary file beside the new one, then a rename). This is the only code in clark that writes
        into a client folder."""
        if replaces:
            platform.write_file(path, data)
            return True
        return platform.write_file_unless_exists(path, data)

    def identity(self, path):
        """Which file this is, as the disk says now: device, inode, size and the two change times in nanoseconds. An inode
        number alone is not enough (a freed number can be handed to the next file made under the same name), so a caller
        compares the whole of it, and the bytes, before taking a file back."""
        st = Path(path).stat()
        return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)

    def remove(self, path):
        os.unlink(path)

    def make_folder(self, path):
        """Make the one folder `path` (its parent must be there), as a section template's files folder (#96, "Report files" in the
        client folder). False if something is already called that; nothing is replaced."""
        try:
            os.mkdir(path)
        except FileExistsError:
            return False
        return True

    def stale_parts(self, folder, older_than=600):
        """The half-written temporary files an earlier publish left if clark was stopped part-way (`.NAME.html.PID.HEX.part`
        beside the copy, which OneDrive would upload): only files of exactly that shape, at least `older_than` seconds old."""
        now = time.time()
        found = []
        for p in Path(folder).iterdir():
            if not PART_NAME.fullmatch(p.name):
                continue
            try:
                st = p.lstat()                # lstat: a link is looked at, never followed
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode) and platform.is_mine(st) and st.st_size <= publish.MAX_BYTES \
                    and now - st.st_mtime >= older_than:
                found.append(p)
        return found


# ===== The copy =====
@dataclass
class ClientResult:
    """How a To client attempt ended. `action` is done, nothing_to_do, ask (the name is taken: clash holds the dialog's
    facts), confirm_overwrite, cancel, refused (nothing was written, Local included) or failed (Local stays; nothing, or only a
    removed copy, is left in the client folder). `log` is what Store.log_publication would take, only for a verified copy."""
    ok: bool
    action: str
    message: str
    name: str = None
    path: str = None
    sha256: str = None
    replaced: bool = False
    restored: bool = False           # an Overwrite that failed its check and the previous file was put back
    nothing_written: bool = True
    clash: dict = None
    log: dict = None


HELD_WORDS = {            # publish.outside_addresses' own labels, in the words a person reads
    "a <link> tag": "a web link built into the page",
    "a script loaded by address": "a program the page would fetch from the internet",
    "an attribute that names an outside address": "a link to a place outside the file",
    "a page refresh": "a page that reloads itself",
    "a stylesheet that imports another": "styling fetched from outside the file",
    "a stylesheet address that isn't embedded data": "styling fetched from outside the file",
    "a Google Fonts address": "a font fetched from the internet",
    "a link or source that is an outside address": "a link to a place outside the file",
    "an svg, math or CDATA section": "a drawing or formula section clark can't check",
    "a page or program inside the page": "a page or program built into the page",
    "a base address": "a base address that redirects links",
    "text too long or too tangled to check for outside addresses": "a file too large or tangled to check",
}


def held_words(problems):
    """check_copy's problems as one plain list, each wording once."""
    return ", ".join(dict.fromkeys(HELD_WORDS.get(p, p) for p in problems))


def _reason(error, doing="write to"):
    """Why a folder step failed, in a fixed plain sentence: the system's own text is never shown. A PlatformError is clark's own
    sentence (platform.py), so it is kept."""
    text = str(error) if isinstance(error, platform.PlatformError) else \
        f"clark could not {doing} the client folder. Check you can {'edit' if doing == 'write to' else 'open'} it."
    return text if text.rstrip().endswith((".", "!", "?")) else text.rstrip() + "."


def _log(project, name, digest, at, path):
    return {"project": project, "kind": KIND, "file_name": name, "sha256": digest, "at": at, "client_path": str(path)}


def folder_unchanged(fs, folder, guard):
    """None when `folder` is still the folder that was checked, else why not. Looked at just before a write: the folder must
    not be a link now (its real path is itself), must not be in or hold clark's data folder or the backups, and must be the
    same folder (device and inode) as at the check, `guard["identity"]`, when the disk can say."""
    try:
        folder = Path(folder)
        if _parts(fs.realpath(folder)) != _parts(folder) or not fs.is_dir(folder):
            return "changed"
        for own in (guard.get("data_dir"), guard.get("backups_dir")):
            if own:
                real = fs.realpath(own)
                if any(_inside(a, b) or _inside(b, a) for a in (folder, ) for b in (own, real)):
                    return "own"
        if guard.get("identity") is not None and hasattr(fs, "dir_identity") and fs.dir_identity(folder) != guard["identity"]:
            return "changed"
    except (OSError, ValueError):
        return "changed"
    return None


def copy_to_client(fs, folder, name, data, *, project, at, markers, replaces=False, confirmed=False, asked=None,
                   local_sha256=None, guard=None):
    """Put `data` (the finished file's bytes) in `folder` as `name`, read it back and compare SHA-256.
    Nothing is overwritten unless `replaces` is True and `confirmed` is True. A name that is taken when `replaces` is False
    is refused, and that holds at the write itself, not only at the listing: the file is linked into place, so one that
    appeared a moment ago is never replaced. The checks of check_copy (with `markers`, which cannot be left out) run on the
    bytes before anything is written, and on the copy read back. A new copy that differs is removed. An Overwrite keeps the
    old file's bytes in memory (not on disk: no backup goes beside the client's file) and, if the copy fails its check,
    writes them back and says so; if that fails too, both failures are reported. If `local_sha256` is given, the bytes must
    be the Local file's. `asked` is the name first wanted when `name` is a numbered or renamed one (for the words).
    `guard` ({data_dir, backups_dir, identity}, from the check that chose `folder`) makes the folder looked at again just
    before the write: a folder that has become a link, or clark's own folder, or another folder than the one checked, is
    refused and nothing is written."""
    digest = sha256_of(data)
    folder = Path(folder)
    dest = folder / name
    if local_sha256 and local_sha256 != digest:
        return ClientResult(False, "refused", MESSAGES["not_same_file"])
    problems = check_copy(data, folder=folder, markers=markers)
    if problems:
        return ClientResult(False, "refused", MESSAGES["held_back"].format(what=held_words(problems)))
    try:
        for stale in getattr(fs, "stale_parts", lambda folder: [])(folder):
            _remove(fs, stale, None, None, stale=True)
    except OSError:
        pass
    try:
        hit = _find([_entry(e) for e in fs.listdir(folder)], name)
    except OSError as e:
        return ClientResult(False, "failed", MESSAGES["copy_failed_local_kept"].format(reason=_reason(e)))
    if hit is not None and (not replaces or hit["kind"] == "folder"):
        return ClientResult(False, "refused", MESSAGES["name_appeared"].format(name=name))
    if hit is not None and hit["kind"] != "file":
        return ClientResult(False, "refused", MESSAGES["not_plain_file"].format(name=hit["name"]))
    if hit is not None and not confirmed:
        return ClientResult(False, "confirm_overwrite", MESSAGES["needs_confirm"], name=name,
                            clash={"name": name, "note": MESSAGES["overwrite_note"]})
    replaced = hit is not None
    old = None
    if replaced:                       # the old bytes, held in memory (up to the size limit) in case the copy fails its check
        try:
            old = fs.read_bytes(dest, limit=publish.MAX_BYTES + 1)
        except OSError:
            return ClientResult(False, "failed", MESSAGES["overwrite_unreadable"].format(name=name))
        if len(old) > publish.MAX_BYTES:
            return ClientResult(False, "failed", MESSAGES["overwrite_too_big"].format(name=name))
    if guard is not None and folder_unchanged(fs, folder, guard):
        return ClientResult(False, "refused", MESSAGES["folder_changed"])
    try:
        written = fs.write_file(dest, data, replaces=replaced)      # replace: temporary file then rename; new: linked into place
    except (OSError, platform.PlatformError) as e:
        return ClientResult(False, "failed", MESSAGES["copy_failed_local_kept"].format(reason=_reason(e)))
    if not written:
        return ClientResult(False, "refused", MESSAGES["name_appeared"].format(name=name))
    mine = _identity(fs, dest)          # which file this call wrote: only that one is ever taken back
    finished = False
    try:
        problem = None                 # what is wrong with the copy as it now stands, in words for a sentence
        try:
            back = fs.read_bytes(dest)
            if sha256_of(back) != digest or check_copy(back, folder=folder, markers=markers):
                problem = "did not match the published file"
        except OSError:
            back, problem = None, "could not be read back to check it"
        if problem:
            finished = True
            if replaced:
                return _put_back(fs, dest, name, old, problem)
            if back is None:
                _remove(fs, dest, mine, digest)
                return ClientResult(False, "failed", MESSAGES["unreadable_back"], nothing_written=False)
            if not _remove(fs, dest, mine, digest):
                return ClientResult(False, "failed", MESSAGES["copy_not_removed"].format(name=name), name=name, path=str(dest),
                                    nothing_written=False)
            return ClientResult(False, "failed", MESSAGES["copy_differs"], nothing_written=False)
        finished = True
    finally:
        if not finished:               # anything else went wrong between the write and the check (even a stop): take the copy back
            if replaced:
                try:
                    fs.write_file(dest, old, replaces=True)
                except BaseException:
                    pass
            else:
                _remove(fs, dest, mine, digest)
    if replaced:
        message = MESSAGES["done_replaced"].format(name=name)
    elif asked and _key(asked) != _key(name):
        message = MESSAGES["done_numbered"].format(name=name, asked=asked)
    else:
        message = MESSAGES["done_new"].format(name=name)
    return ClientResult(True, "done", message, name=name, path=str(dest), sha256=digest, replaced=replaced,
                        nothing_written=False, log=_log(project, name, digest, at, dest))


def _put_back(fs, dest, name, old, problem):
    """After an Overwrite whose copy failed its check: write the old file's bytes back, check they are what was there, and say
    what happened. If the write-back fails as well, both failures are in the message."""
    try:
        fs.write_file(dest, old, replaces=True)
        if fs.read_bytes(dest) != old:
            raise platform.PlatformError("what was written back did not read back the same.")
    except (OSError, platform.PlatformError) as e:
        return ClientResult(False, "failed", MESSAGES["restore_failed"].format(name=name, problem=problem, reason=_reason(e)),
                            name=name, path=str(dest), replaced=True, nothing_written=False)
    return ClientResult(False, "failed", MESSAGES["restored"].format(name=name, problem=problem), name=name, path=str(dest),
                        restored=True, nothing_written=True)


def _identity(fs, path):
    """Which file `path` is now (None when the disk can't say or it is not there)."""
    try:
        return fs.identity(path)
    except (AttributeError, OSError):
        return None


def _ours(fs, path, mine, digest):
    """True only when the file at `path` is the copy this call wrote: the same device and inode as `mine` (what _identity said
    right after the write) AND bytes whose SHA-256 is `digest`, the digest of what this call wrote. Both are needed in every
    case; the times, the size and the rest of the identity are never enough on their own (a number freed and handed to
    another file on a disk with coarse times can match all of them), and a sync tool that only moves the times does not
    change the answer. `digest` has no default: leaving it out is a TypeError, never a fall back to the disk's metadata."""
    now = _identity(fs, path)
    if mine is None or now is None or now[:2] != mine[:2]:
        return False
    try:
        return sha256_of(fs.read_bytes(path, limit=publish.MAX_BYTES + 1)) == digest
    except Exception:                  # bytes that cannot be read cannot be proven ours: leave the file and say so
        return False


def _remove(fs, path, mine, digest, *, stale=False):
    """Take back the copy this publish made; True if it is gone or is no longer ours (a file someone else put there is left
    alone). `mine` and `digest` are required: a file is taken back only when _ours proves it, and when the disk could not say
    which file was written (`mine` is None) nothing is removed and False is returned. `stale=True` is only for the half-written
    temporary files the disk itself lists as clark's (stale_parts), which have no identity to prove."""
    if not stale and not _ours(fs, path, mine, digest):
        return mine is not None
    try:
        fs.remove(path)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _same_content(fs, path, digest):
    """Whether the file at `path` holds exactly the bytes with SHA-256 `digest`. Never more than the report size limit is read
    (a bigger file is not the same), and a file that can't be read as an ordinary file (a link, a pipe) is simply not the same."""
    try:
        data = fs.read_bytes(path, limit=publish.MAX_BYTES + 1)
    except OSError:
        return False
    return len(data) <= publish.MAX_BYTES and sha256_of(data) == digest


def plan_client_copy(fs, *, saved_folder, data, project, today, week_ending, data_dir, onedrive_roots, local_folder,
                     backups_dir=None, choice=None, new_name=None, at=None):
    """Everything send_to_client decides before it writes, and nothing written: preflight the saved folder, read its names and
    resolve a taken name. Returns (kind, value): ("stop", ClientResult) for a refusal, a question (ask) or a Cancel;
    ("same", ClientResult) when the client folder already holds this exact file; ("copy", plan) when the copy may go ahead, with
    plan = {folder, name, replaces, asked}. The route calls this first, writes Local, then calls copy_to_client; so a folder
    that has gone, or a name that needs asking about, leaves Local unwritten too."""
    pre = checked_folder(fs, saved_folder, data_dir=data_dir, onedrive_roots=onedrive_roots, local_folder=local_folder,
                         backups_dir=backups_dir)
    if not pre["ok"]:
        name = PurePath(saved_folder).name if saved_folder else ""
        if saved_folder and pre["message"] == MESSAGES["missing"].format(folder_name=name):
            return "stop", ClientResult(False, "refused", MESSAGES["folder_missing_nothing_written"].format(folder_name=name))
        return "stop", ClientResult(False, "refused", MESSAGES["refused_nothing_published"].format(reason=pre["message"]))
    folder = Path(pre.get("real") or saved_folder)       # the real place the copy will go, as the check found it
    try:
        wanted = client_file_name(project, week_ending, today, folder)
    except platform.PlatformError as e:
        return "stop", ClientResult(False, "refused", MESSAGES["refused_nothing_published"].format(reason=_reason(e)))
    digest = sha256_of(data)
    try:
        existing = [dict(e) for e in fs.listdir(folder)]
        names = {_key(n) for n in (wanted, rename_target(new_name, folder)) if n}
        for e in existing:           # only the names that could be written to are read, to see if the file is already there
            e["same_content"] = e["kind"] == "file" and _key(e["name"]) in names and _same_content(fs, folder / e["name"], digest)
    except OSError as e:
        return "stop", ClientResult(False, "refused", MESSAGES["refused_nothing_published"].format(reason=_reason(e, "read")))
    plan = resolve_clash(wanted, existing, choice, new_name, folder)
    action = plan["action"]
    if action == "cancel":
        return "stop", ClientResult(False, "cancel", MESSAGES["cancelled"])
    if action == "refuse":
        return "stop", ClientResult(False, "refused", plan["message"])
    if action == "ask":
        return "stop", ClientResult(False, "ask", MESSAGES["clash_title"], name=plan["name"],
                                    clash=dict(plan, note=MESSAGES["overwrite_note"]))
    if action == "nothing_to_do":
        return "same", ClientResult(True, "nothing_to_do", MESSAGES["done_same"].format(name=plan["name"]), name=plan["name"],
                                    path=str(folder / plan["name"]), sha256=digest, nothing_written=True,
                                    log=_log(project, plan["name"], digest, at or today, folder / plan["name"]))
    return "copy", {"folder": folder, "name": plan["name"], "replaces": plan["replaces"], "asked": wanted,
                    "identity": pre.get("identity")}


def send_to_client(fs, *, saved_folder, data, project, at, week_ending, today, data_dir, onedrive_roots, local_folder,
                   backups_dir=None, choice=None, new_name=None, confirmed=False, markers, local_sha256=None):
    """The whole To client step on the finished bytes: plan_client_copy (nothing written until every check before the copy has
    passed, so a missing or forbidden folder, a taken name that needs asking about, a Cancel and an unconfirmed Overwrite all
    leave the client folder, and Local, which the caller writes after this says go, untouched), then copy and verify.
    `markers` (what must be absent from the file; no default, and no way to turn the check off) is checked on the bytes before
    the copy and on the copy read back. Returns a ClientResult."""
    kind, got = plan_client_copy(fs, saved_folder=saved_folder, data=data, project=project, today=today,
                                 week_ending=week_ending, data_dir=data_dir, onedrive_roots=onedrive_roots,
                                 local_folder=local_folder, backups_dir=backups_dir, choice=choice, new_name=new_name, at=at)
    if kind != "copy":
        return got
    return copy_to_client(fs, got["folder"], got["name"], data, project=project, at=at, replaces=got["replaces"],
                          confirmed=confirmed, asked=got["asked"], markers=markers, local_sha256=local_sha256,
                          guard={"data_dir": data_dir, "backups_dir": backups_dir, "identity": got.get("identity")})


# ===== The request =====
def validate_request(body, saved_client_folder):
    """The publish request's body, checked. Returns {status: 200, to_client} or {status: 400, message}. Only `project`,
    `to_client` (exactly true or false when given), `on_clash`, `new_name`, `confirmed` and `section_style` (one of the four section
    styles, else Slim gaps) may be sent: a request never names a
    folder or a file, and the client folder is always the one saved in Settings. An Overwrite (`on_clash: "overwrite"`) is
    allowed only with `"confirmed": true`, the boolean itself: missing, false, "true" and 1 are all refused, so a script
    can't pass for the dialog's confirm step. The answer carries `confirmed` (True only for that exact value)."""
    if not isinstance(body, dict):
        return {"status": 400, "message": MESSAGES["unknown_key"]}
    extra = [k for k in body if k not in ALLOWED_KEYS]
    if extra:
        named = any(k in ("client_folder", "folder", "path", "file", "file_name", "dest", "client_path", "local_path") for k in extra)
        return {"status": 400, "message": MESSAGES["names_a_folder" if named else "unknown_key"]}
    if "to_client" in body and not isinstance(body["to_client"], bool):
        return {"status": 400, "message": MESSAGES["to_client_flag"]}
    to_client = body.get("to_client", False)
    if "confirmed" in body and not isinstance(body["confirmed"], bool):
        return {"status": 400, "message": MESSAGES["confirmed_flag"]}
    confirmed = body.get("confirmed") is True
    if "project" in body and not isinstance(body["project"], str):
        return {"status": 400, "message": MESSAGES["bad_project"]}
    if body.get("on_clash") is not None and body["on_clash"] not in CHOICES:
        return {"status": 400, "message": MESSAGES["unknown_choice"]}
    if body.get("new_name") is not None and not isinstance(body["new_name"], str):
        return {"status": 400, "message": MESSAGES["empty_name"]}
    if to_client and not saved_client_folder:
        return {"status": 400, "message": MESSAGES["not_saved"]}
    if body.get("on_clash") == "overwrite" and not confirmed:
        return {"status": 400, "message": MESSAGES["overwrite_unconfirmed"]}
    return {"status": 200, "to_client": to_client, "confirmed": confirmed}


# ===== The dialog, as data =====
def folder_name(path):
    return PurePath(path).name or str(path) if path else ""


def new_dialog_state(saved_folder=None):
    """A dialog just opened. To client is never ticked on opening (it is not remembered, anywhere), whatever the last one was."""
    return {"saved_folder": saved_folder or None, "ticked": False, "phase": "choose", "clash": None, "choice": "number",
            "new_name": "", "message": None, "confirm_overwrite": False}


def dialog_step(state, event, value=None):
    """The next state after `event` (the old state is not changed). Events:
    tick (value True/False; ignored with no saved folder or while a question is open), folder (value: the saved path or
    None), publish (the button; ignored while the clash question is incomplete), choose (value: number, rename or
    overwrite), rename_text (value: the text), confirm (the user confirmed Overwrite, which needs its own step),
    result (value: a ClientResult or its dict), cancel (Esc or Cancel: ends the clash question, or the dialog)."""
    s = dict(state)
    phase = s["phase"]
    if event == "tick":
        if phase in ("choose", "error", "done"):
            s["ticked"] = bool(value) and bool(s["saved_folder"])
    elif event == "folder":
        s["saved_folder"] = value or None
        s["ticked"] = s["ticked"] and bool(s["saved_folder"])
    elif event == "publish":
        if phase in ("choose", "error", "done") or (phase == "clash" and _clash_ready(s)):
            s["phase"], s["message"] = "working", None
    elif event == "choose":
        if phase == "clash" and value in ("number", "rename", "overwrite"):
            s["choice"], s["confirm_overwrite"] = value, False
    elif event == "rename_text":
        s["new_name"] = str(value or "")
    elif event == "confirm":
        if phase == "clash" and s["choice"] == "overwrite":
            s["confirm_overwrite"] = True
    elif event == "cancel":
        if phase == "clash":
            s.update(phase="closed", clash=None, message={"kind": "info", "text": MESSAGES["cancelled"]})
        elif phase != "working":
            s["phase"] = "closed"
    elif event == "result":
        r = value if isinstance(value, dict) else vars(value)
        if r["action"] == "ask":
            s.update(phase="clash", clash=r["clash"], choice="number", confirm_overwrite=False, message=None)
        elif r["ok"]:
            s.update(phase="done", clash=None, message={"kind": "success", "text": r["message"]})
        else:
            s.update(phase="error", clash=None, message={"kind": "error", "text": r["message"]})
    else:
        raise ValueError(f"unknown dialog event {event!r}")
    return s


def _clash_ready(s):
    """Whether the clash question has an answer that can be sent: a Rename needs text, an Overwrite needs its confirmation."""
    if s["choice"] == "rename":
        return bool(s["new_name"].strip())
    return s["choice"] != "overwrite" or s["confirm_overwrite"]


def to_client_dialog(state):
    """What the Publish dialog shows for `state`, as plain data (no page): Local ticked and disabled, To client's tick and
    why it may be disabled, the button's words, the line for the client, the clash question when there is one, and any
    message. `focus_after_close` says where focus goes when the dialog ends (back to Publish)."""
    saved, ticked, phase = state["saved_folder"], state["ticked"] and bool(state["saved_folder"]), state["phase"]
    busy = phase == "working"
    model = {
        "setting": SETTING,
        "local": {"label": MESSAGES["dialog_local"], "ticked": True, "disabled": True},
        "to_client": {"label": MESSAGES["dialog_to_client"], "ticked": ticked, "disabled": busy or not saved or phase == "clash",
                      "folder_name": folder_name(saved), "hint": folder_name(saved) if saved else MESSAGES["not_saved"]},
        "line": MESSAGES["client_sees"] if ticked else None,
        "button": {"label": MESSAGES["button_client"] if ticked else MESSAGES["button_local"], "disabled": busy or phase in ("clash", "closed")},
        "busy": busy,
        "status": MESSAGES["working"] if busy else None,
        "clash": None,
        "message": state["message"],
        "closed": phase == "closed",
        "esc": "cancel",
        "focus_after_close": "publish",
    }
    if phase == "clash" and state["clash"]:
        c, choice = state["clash"], state["choice"]
        labels = MESSAGES["clash_choices"]
        options = [{"id": "number", "label": labels[0]}, {"id": "rename", "label": labels[1]}]
        if c.get("can_overwrite", True):
            options.append({"id": "overwrite", "label": labels[2]})
        for o in options:
            o["selected"] = o["id"] == choice
        typed = state["new_name"].strip()
        model["clash"] = {
            "title": MESSAGES["clash_title"], "name": c.get("name"), "options": options, "cancel": labels[3],
            "numbered": c.get("numbered"), "preview": MESSAGES["numbered_preview"].format(numbered=c["numbered"]) if c.get("numbered") else None,
            "rename": {"visible": choice == "rename", "label": MESSAGES["rename_label"], "value": state["new_name"], "needs_text": choice == "rename" and not typed},
            "note": MESSAGES["overwrite_note"] if choice == "overwrite" else None,
            "needs_confirmation": choice == "overwrite",
            "confirmed": state["confirm_overwrite"],
            "go": {"label": "OK", "disabled": not _clash_ready(state)},
        }
    return model


def dialog_request(state, project):
    """The body to send for the dialog's state: the project and to_client, and, once the clash question has been answered,
    the answer (on_clash, and new_name for a Rename). It never names a folder or a file of its own: the folder is the one
    saved in Settings. An Overwrite is only sent with `"confirmed": true`, and only after the dialog's own confirmation step."""
    body = {"project": project, "to_client": bool(state["ticked"] and state["saved_folder"])}
    if state["clash"] is not None:
        body["on_clash"] = state["choice"]
        if state["choice"] == "rename":
            body["new_name"] = state["new_name"].strip()
        if state["choice"] == "overwrite" and state["confirm_overwrite"]:
            body["confirmed"] = True
    return body
