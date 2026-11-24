"""Row 1295: where the slash commands of ask clark are kept: the store, one small JSON per slash command in an `ask-commands` folder of clark's own data folder
(ruled 20-11: JSON in the store). Unguarded; ask_commands_service.py routes to it. The rules are those of page/src/logic/askShortcuts.js, in the same words.

A file is `<name>.json` holding {name, menu, text, scope, result} (a person's own version of a built-in also has "replaces": that name; an
AI-written one has "ai": true). read() skips a file it cannot trust and lists it, so one damaged file never hides the rest. write() checks
every rule first, then writes to a side file and renames it over the real one, so a stop half way leaves the old file whole.
"""
import json
import os
import re
from pathlib import Path

FOLDER = "ask-commands"
MAX_SHORTCUTS = 20
NAME_MIN, NAME_MAX, MENU_MAX, TEXT_MAX = 2, 24, 70, 1000
SCOPES = ("anywhere", "item", "section", "usecase")
RESULTS = ("answer", "changes", "draft")
LOCKED = ("history", "new")
FIELDS = ("name", "menu", "text", "scope", "result")
FILE_LIMIT = 8 * 1024          # a valid file is at most about 1,200 characters; anything bigger is not one of ours
NAME_RE = re.compile(r"[a-z][a-z0-9-]*")


def readable_lines(path):
    """THE SEAM of row 1435 (Fix it with AI; the design is not decided): what a "line" of a damaged slash-command file is and which of them can be read.
    Returns (kept, left_out): `kept` the lines that can be read, as text in their order, `left_out` how many it could not read; or None when the file
    cannot be read this way, which makes the fix say it could not fix the file and change nothing. Until the design is decided it returns None."""
    return None


class Refused(Exception):
    """A change that breaks a rule; str() is the sentence to show. Nothing was written."""


def name_problem(name, taken=(), self_name="", builtins=()):
    n = name if isinstance(name, str) else ""
    if len(n) < NAME_MIN:
        return "The name needs at least %d characters." % NAME_MIN
    if len(n) > NAME_MAX:
        return "The name can be at most %d characters." % NAME_MAX
    if n != n.lower():
        return "Use lower case letters only in the name."
    if re.search(r"\s", n):
        return "The name cannot have spaces. Use a hyphen instead."
    if not re.match(r"[a-z]", n):
        return "The name must start with a letter."
    if not NAME_RE.fullmatch(n):
        return "The name can have only lower case letters, numbers and hyphens."
    if n == self_name:
        return ""
    if n in builtins:
        return "That name is used by a built-in slash command. Choose another."
    if n in taken:
        return "You already have a slash command with that name."
    return ""


def problems(rec, taken=(), self_name="", builtins=()):
    """Every plain-words problem with a record's fields (empty list when it can be saved)."""
    out = []
    if not isinstance(rec, dict):
        return ["That slash command could not be read."]
    if not rec.get("replaces"):
        p = name_problem(rec.get("name"), taken, self_name, builtins)
        if p:
            out.append(p)
    menu, text = rec.get("menu"), rec.get("text")
    menu = menu if isinstance(menu, str) else ""
    text = text if isinstance(text, str) else ""
    if len(menu) > MENU_MAX:
        out.append("The line in the menu can be at most %d characters." % MENU_MAX)
    if not menu.strip():
        out.append("Say what it does in the menu, in a few words.")
    if len(text) > TEXT_MAX:
        out.append("The instructions can be at most %s characters." % format(TEXT_MAX, ","))
    if not text.strip():
        out.append("Say what it should do, in plain words.")
    if rec.get("scope") not in SCOPES:
        out.append("Choose where it appears.")
    if rec.get("result") not in RESULTS:
        out.append("Choose what you get.")
    return out


class AskCommands:
    """`root` is the folder that holds `ask-commands` (clark's own data folder); `builtins` the names of the built-in slash commands."""

    def __init__(self, root, builtins=LOCKED, sub=""):
        """`sub` is a project's code: its commands are in a folder of their own inside `ask-commands` (the same names there win in that project)."""
        self.folder = Path(root) / FOLDER / sub
        self.builtins = tuple(builtins)

    def _file(self, name):
        if name_problem(name, (), name):           # a name that passes is only a-z, 0-9 and hyphen: no path can be built from it
            raise Refused("That is not a name a slash command can have.")
        return self.folder / (name + ".json")

    def read(self):
        """(records, damaged): the good records sorted by name, and the file names that were skipped."""
        good, damaged = [], []
        if not self.folder.is_dir():
            return good, damaged
        for f in sorted(self.folder.glob("*.json")):
            try:
                if f.is_symlink() or f.stat().st_size > FILE_LIMIT:
                    raise ValueError("size or link")
                rec = json.loads(f.read_text(encoding="utf-8"))
                keep = {k: rec[k] for k in FIELDS + ("replaces", "ai") if isinstance(rec, dict) and k in rec}
                if not isinstance(rec, dict) or problems(keep, (), keep.get("name"), self.builtins) \
                        or keep["name"] != f.stem or (keep.get("replaces") not in (None, keep["name"])):
                    raise ValueError("rules")
                if keep.get("replaces") and keep["name"] in LOCKED:
                    raise ValueError("locked")
                good.append(keep)
            except (OSError, ValueError, KeyError):         # json.JSONDecodeError and UnicodeDecodeError are ValueErrors
                damaged.append(f.name)
        return good, damaged

    def fix(self, fname):
        """Row 1435: the local fix of a file that does not read (no AI, nothing sent). The file's bytes are saved first as `<fname>.old`, then the file is
        rewritten with the lines `readable_lines` keeps. Returns (kept, left_out). Any failure raises Refused and leaves the file as it was."""
        if fname not in self.read()[1]:
            raise Refused("fix")
        target = self.folder / fname
        try:
            if target.is_symlink():
                raise Refused("fix")
            got = readable_lines(target)
            if got is None:
                raise Refused("fix")
            kept, left_out = got
            old = target.read_bytes()
            self._swap(target.with_name(fname + ".old"), old)
            self._swap(target, ("\n".join(kept) + "\n" if kept else "").encode("utf-8"))
        except OSError:
            raise Refused("fix")
        return len(kept), left_out

    def unfix(self, fname):
        """Undo of fix(): the `.old` copy comes back as the file, byte for byte, and the copy is removed."""
        copy = self.folder / (fname + ".old")
        try:
            if fname.endswith(".old") or not copy.is_file() or copy.is_symlink():
                raise Refused("fix")
            self._swap(self.folder / fname, copy.read_bytes())
            copy.unlink()
        except OSError:
            raise Refused("fix")

    def _swap(self, target, data):
        """Writes `data` to a side file and renames it over `target`, so a stop half way leaves the old file whole."""
        side = target.with_name(target.name + ".part")
        try:
            side.write_bytes(data)
            os.replace(side, target)
        except OSError:
            side.unlink(missing_ok=True)
            raise

    def write(self, rec, was=None):
        """Saves one slash command. `was` is the name it had when opened (a rename removes the old file after the new one is whole).
        A record with "replaces" is the person's version of a built-in; a locked built-in cannot be saved."""
        if not isinstance(rec, dict):
            raise Refused("That slash command could not be read.")
        keep = {k: rec[k] for k in FIELDS + ("replaces", "ai") if k in rec}
        rep = keep.get("replaces")
        if rep is not None:
            if rep in LOCKED:
                raise Refused("/%s is an action, not a question, so it cannot be edited." % rep)
            if rep not in self.builtins:
                raise Refused("No built-in slash command has that name.")
            keep["name"] = rep
            keep.pop("ai", None)
        elif not keep.get("ai"):
            keep.pop("ai", None)
        mine, _ = self.read()
        own = [m for m in mine if not m.get("replaces") and m["name"] != (was or keep.get("name"))]
        p = problems(keep, [m["name"] for m in own], "", self.builtins)
        if p:
            raise Refused(p[0])
        if rep is None and len(own) >= MAX_SHORTCUTS:
            raise Refused("You can keep %d slash commands in a project. Remove one to add another." % MAX_SHORTCUTS)
        target = self._file(keep["name"])
        self.folder.mkdir(parents=True, exist_ok=True)
        side = target.with_name(target.name + ".part")
        try:
            side.write_text(json.dumps(keep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            os.replace(side, target)
        except OSError:
            side.unlink(missing_ok=True)
            raise Refused("That slash command could not be saved. Nothing was changed.")
        if was and was != keep["name"] and rep is None:
            self._file(was).unlink(missing_ok=True)
        return keep

    def remove(self, name):
        """Removes one of the person's own slash commands."""
        mine, _ = self.read()
        if not any(m["name"] == name and not m.get("replaces") for m in mine):
            raise Refused("Only your own slash commands can be removed.")
        self._file(name).unlink(missing_ok=True)

    def reset(self, name):
        """Drops the person's version of a built-in; the built-in's own text comes back."""
        mine, _ = self.read()
        if any(m["name"] == name and m.get("replaces") for m in mine):
            self._file(name).unlink(missing_ok=True)
