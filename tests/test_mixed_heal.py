"""Row 1017 (CMD 088): a mixed-version clark folder is put right, but only after the person types y.

Run: python3 dev/run_tests.py test_mixed_heal

src/clark/same_version_heal.py is a standard-library script that clark.command runs by path (python3 -I) when a terminal is
attached, before the refusal. These tests build a small fake download in a temporary folder (the program files in .app, the
record clark-release.json beside it), put the person's own folders beside it (data, system, docker, a README, a data folder
with a relative path), and check that the heal:
  - says what differs, and what older files are in the way;
  - changes nothing without a typed y (any other key, an empty answer, no terminal);
  - puts back only the files whose SHA-256 is the one the record lists, from a zip in Downloads or the folder above, or a
    set-aside folder; moves src, vendor and clark (and nothing else) into one folder, by rename, never deleting;
  - never touches the data, system or docker folders, the update marker is waited for, nothing is downloaded;
  - leaves --check, restore and non-interactive starts exactly as they were.
The real clark.command is run in a pseudo-terminal with a stub python3 (it runs the real python for -c and -I, and only says
that it was asked to start clark otherwise) and a stub `open`; nothing is installed, started or opened for real.
"""
import hashlib
import importlib.util
import io
import json
import os
import pty
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from _paths import ROOT

from clark import release_files, same_version, updates

HEAL_PATH = ROOT / "src" / "clark" / "same_version_heal.py"
BASH = shutil.which("bash")

MESSAGE = ("These clark files are not all from the same version, so clark will not start. "
           "Move the clark folder aside (rename it) and unzip the download again.")
OPEN_LINE = "The clark folder is open for you."
COULD_NOT = "Clark could not put every file back."
ASK_MOVE = ("Move the older files into a folder called clark older files? Nothing is deleted and your data is not touched. "
            "Type y for yes, or any other key for no.")
DONE_MOVED = "Done. The older files are in clark older files. Starting clark."
OLDER = "clark older files"

APP_FILES = {
    ".app/src/clark/a.py": b"A = 1\n",
    ".app/src/clark/b.py": b"B = 'bee'\n",
    ".app/src/clark/c.py": b"C = [1, 2, 3]\n",
    ".app/src/clark/d.py": b"D = {'d': 4}\n",
    ".app/src/clark/e.py": b"E = 5.5\n",
    ".app/vendor/lib/x.py": b"X = 'vendored'\n",
    ".app/clark/__main__.py": b"print('stand-in')\n",
}
PERSON = {
    "data/clark.db": b"made-up database bytes",
    "data/src/keep.txt": b"a person's folder that happens to be called src",
    "system/branding/tokens.css": b":root { --x: 1; }\n",
    "docker/compose.yaml": b"services: {}\n",
    "README.md": b"read me\n",
    "meet clark/intro.txt": b"hello\n",
    "mydata/clark.db": b"a relative --data folder",
}
STALE_FLAT = {
    "src/clark/old.py": b"OLD = 'flat src'\n",
    "vendor/old_lib.py": b"OLD = 'flat vendor'\n",
    "clark/__init__.py": b"raise RuntimeError('OLD FLAT CLARK')\n",
}


def load_heal():
    spec = importlib.util.spec_from_file_location("same_version_heal_under_test", str(HEAL_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(folder):
    """{"/" name: bytes} of every file under `folder`, links not followed (a link is recorded by its target)."""
    base = Path(folder)
    out = {}
    for p in sorted(base.rglob("*")):
        if p.is_symlink():
            out[p.relative_to(base).as_posix()] = b"link:" + os.readlink(str(p)).encode()
        elif p.is_file():
            out[p.relative_to(base).as_posix()] = p.read_bytes()
        else:
            out[p.relative_to(base).as_posix() + "/"] = b""
    return out


def flip(data):
    """Different bytes, same size."""
    return bytes([data[0] ^ 1]) + data[1:]


class Fixture(unittest.TestCase):
    """One fake download per test: tmp/clark/.app/..., tmp/clark/clark.command, tmp/clark/clark-release.json, the person's folders."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="heal row "))             # a space in the path, as a real folder may have
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.home = self.tmp / "home"
        (self.home / "Downloads").mkdir(parents=True)
        self.top = self.tmp / "clark"
        self.top.mkdir()
        self.good = dict(APP_FILES)
        self.good["clark.command"] = (ROOT / "clark.command").read_bytes()
        self.good[".app/src/clark/same_version_heal.py"] = HEAL_PATH.read_bytes()      # a download carries it (release_files covers it)
        for name, data in {**self.good, **PERSON}.items():
            self.put(self.top / name, data)
        (self.top / "clark.command").chmod(0o755)
        self.data = self.tmp / "Application Support" / "clark"
        self.put(self.data / "clark.db", b"the real data folder")
        self.write_record()
        self.heal_module = load_heal()

    @staticmethod
    def put(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def write_record(self):
        files = {name: {"sha256": sha(data), "size": len(data), "mode": "755" if name == "clark.command" else "644"}
                 for name, data in sorted(self.good.items())}
        (self.top / "clark-release.json").write_text(json.dumps({"product": "clark", "version": "9.9.9", "files": files}, indent=2),
                                                      encoding="utf-8")

    def make_old(self, *names, same_size=True):
        for name in names:
            data = flip(self.good[name]) if same_size else self.good[name] + b"# older\n"
            self.put(self.top / name, data)

    def add_stale(self, *names):
        for name, data in STALE_FLAT.items():
            if name.split("/")[0] in names or not names:
                self.put(self.top / name, data)

    def zip_of(self, folder, files=None, name="clark-9.9.9-mac.zip"):
        path = Path(folder) / name
        with zipfile.ZipFile(str(path), "w") as z:
            for rel, data in sorted((files if files is not None else self.good).items()):
                z.writestr("clark/" + rel, data)
        return path

    def heal(self, keys="", tty=True, data=None):
        """Run the heal in this process. `keys` is what the person types, one character for each question (none left = an empty answer)."""
        typed = iter(keys)
        out, err = io.StringIO(), io.StringIO()
        code = self.heal_module.run(self.top, data if data is not None else self.data, key=lambda: next(typed, ""), out=out, err=err,
                                    home=self.home, tty=tty)
        return code, out.getvalue(), err.getvalue(), []

    def person(self):
        return {k: v for k, v in snapshot(self.top).items() if k.split("/")[0] in ("data", "system", "docker", "README.md", "meet clark", "mydata")}


class Words(Fixture):
    def test_the_existing_sentence_is_the_one_same_version_says(self):
        self.assertEqual(same_version.MESSAGE, self.heal_module.EXISTING)
        self.assertEqual(MESSAGE, self.heal_module.EXISTING)

    def test_differs_line_names_up_to_three_files_and_counts_the_rest(self):
        self.make_old(*[f".app/src/clark/{n}.py" for n in "abcde"])
        code, out, err, opened = self.heal("n")
        self.assertIn("These clark files are from different versions: src/clark/a.py, src/clark/b.py, src/clark/c.py and 2 more.\n", out)
        self.assertNotIn("src/clark/d.py", out)
        self.assertEqual(3, code)

    def test_differs_line_with_three_or_fewer_has_no_count(self):
        self.make_old(".app/src/clark/a.py", ".app/src/clark/b.py", ".app/src/clark/c.py")
        out = self.heal("n")[1]
        self.assertIn("These clark files are from different versions: src/clark/a.py, src/clark/b.py, src/clark/c.py.\n", out)
        self.make_old(".app/src/clark/a.py")
        self.assertNotIn(" more", out)

    def test_a_missing_file_is_a_file_that_differs(self):
        (self.top / ".app/src/clark/a.py").unlink()
        out = self.heal("n")[1]
        self.assertIn("different versions: src/clark/a.py.\n", out)

    def test_the_old_folders_line_names_the_older_folders_beside_app(self):
        self.add_stale("src", "vendor")
        out = self.heal("n")[1]
        self.assertIn("Older clark files are in the way: src, vendor.\n", out)
        self.assertNotIn("different versions", out)
        self.add_stale("clark")
        self.assertIn("Older clark files are in the way: src, vendor, clark.\n", self.heal("n")[1])

    def test_a_folder_that_matches_is_left_alone_and_says_nothing(self):
        before = snapshot(self.tmp)
        self.assertEqual((0, "", "", []), self.heal("y"))
        self.assertEqual(before, snapshot(self.tmp))


class NothingWithoutAYes(Fixture):
    def setUp(self):
        super().setUp()
        self.make_old(".app/src/clark/a.py", ".app/src/clark/b.py")
        self.add_stale()
        self.zip_of(self.home / "Downloads")
        self.before = snapshot(self.tmp)

    def test_any_other_key_or_empty_changes_nothing(self):
        for key in ("n", "N", "x", " ", "\n", "", "yes please"[1:], "1"):
            with self.subTest(key=key):
                code, out, err, opened = self.heal(key)
                self.assertEqual(3, code)
                self.assertEqual(self.before, snapshot(self.tmp))

    def test_a_no_to_the_second_question_keeps_what_the_first_yes_did_and_moves_nothing(self):
        code, out, err, opened = self.heal("yn")
        self.assertEqual(3, code)
        self.assertEqual(self.good[".app/src/clark/a.py"], (self.top / ".app/src/clark/a.py").read_bytes())     # the first yes was a yes
        for name in STALE_FLAT:
            self.assertEqual(STALE_FLAT[name], (self.top / name).read_bytes())
        self.assertFalse((self.top / OLDER).exists())

    def test_no_terminal_changes_nothing_asks_nothing_and_says_nothing(self):
        def never():
            raise AssertionError("asked a key with no terminal")
        out, err = io.StringIO(), io.StringIO()
        code = self.heal_module.run(self.top, self.data, key=never, out=out, err=err,
                                    home=self.home, tty=False)
        self.assertEqual((0, "", ""), (code, out.getvalue(), err.getvalue()))
        self.assertEqual(self.before, snapshot(self.tmp))

    def test_run_with_no_key_reader_and_no_terminal_changes_nothing(self):
        done = subprocess.run([sys.executable, "-I", str(HEAL_PATH), str(self.top), str(self.data)], stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=60, env=dict(os.environ, HOME=str(self.home)))
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual(self.before, snapshot(self.tmp))

    def test_the_question_is_asked_with_the_approved_words(self):
        out = self.heal("n")[1]
        self.assertIn("Clark found the right copies in ~/Downloads. Put 2 files back? Your data is not touched. "
                      "Type y for yes, or any other key for no.", out)


class Restore(Fixture):
    def test_yes_restores_only_files_whose_sha256_matches_the_record(self):
        self.make_old(".app/src/clark/a.py", ".app/src/clark/b.py", ".app/src/clark/c.py", ".app/src/clark/d.py")
        files = dict(self.good)
        files[".app/src/clark/c.py"] = flip(self.good[".app/src/clark/c.py"])           # the same size, wrong bytes
        del files[".app/src/clark/d.py"]                                              # not in the zip at all
        self.zip_of(self.home / "Downloads", files)
        before_c, before_d = (self.top / ".app/src/clark/c.py").read_bytes(), (self.top / ".app/src/clark/d.py").read_bytes()
        code, out, err, opened = self.heal("y")
        for n in "ab":
            self.assertEqual(self.good[f".app/src/clark/{n}.py"], (self.top / f".app/src/clark/{n}.py").read_bytes())
        self.assertEqual(before_c, (self.top / ".app/src/clark/c.py").read_bytes())
        self.assertEqual(before_d, (self.top / ".app/src/clark/d.py").read_bytes())
        self.assertIn("Put 2 files back?", out)
        self.assertEqual(3, code)

    def test_a_zip_with_wrong_bytes_is_never_used(self):
        self.make_old(".app/src/clark/a.py", ".app/src/clark/b.py")
        bad = {k: flip(v) for k, v in self.good.items()}                              # every file the right size, none the right bytes
        bad[".app/src/clark/b.py"] = self.good[".app/src/clark/b.py"] + b"longer"      # and one the wrong size
        self.zip_of(self.home / "Downloads", bad)
        self.zip_of(self.top.parent, bad)
        before = snapshot(self.tmp)
        code, out, err, opened = self.heal("yy")
        self.assertEqual(before, snapshot(self.tmp))
        self.assertNotIn("Put ", out)                                                  # nothing right to put back, so no question
        self.assertEqual(MESSAGE + "\n" + OPEN_LINE + "\n", err)
        self.assertEqual(3, code)

    def test_a_clean_run_restores_everything_and_starts(self):
        self.make_old(".app/src/clark/a.py", ".app/src/clark/b.py", ".app/vendor/lib/x.py")
        self.zip_of(self.home / "Downloads")
        code, out, err, opened = self.heal("y")
        self.assertEqual(0, code)
        self.assertEqual(self.good, {k: v for k, v in snapshot(self.top).items() if k in self.good})
        self.assertIn("Done. 3 files put back. Starting clark.\n", out)
        self.assertEqual("", err)
        self.assertEqual(0, self.heal("")[0])                                           # and now there is nothing to do

    def test_the_zip_in_the_folder_above_and_a_set_aside_folder_are_sources_too(self):
        self.make_old(".app/src/clark/a.py", ".app/src/clark/b.py", ".app/src/clark/c.py")
        self.zip_of(self.top.parent, {".app/src/clark/a.py": self.good[".app/src/clark/a.py"]})
        old = self.top / ".clark-old-20260101"
        self.put(old / ".app/src/clark/b.py", self.good[".app/src/clark/b.py"])
        self.put(old / ".app/src/clark/c.py", flip(self.good[".app/src/clark/c.py"]))   # wrong bytes there
        update = self.top / ".clark-update-20260102"
        self.put(update / ".app/src/clark/c.py", b"not it either")
        code, out, err, opened = self.heal("y")
        self.assertIn("Put 2 files back?", out)
        self.assertEqual(self.good[".app/src/clark/a.py"], (self.top / ".app/src/clark/a.py").read_bytes())
        self.assertEqual(self.good[".app/src/clark/b.py"], (self.top / ".app/src/clark/b.py").read_bytes())
        self.assertEqual(flip(self.good[".app/src/clark/c.py"]), (self.top / ".app/src/clark/c.py").read_bytes())      # left as it was
        self.assertEqual(3, code)

    def test_a_restored_file_keeps_the_mode_the_record_lists_and_leaves_no_temporary_file(self):
        (self.top / "clark.command").write_bytes(b"#!/bin/bash\n# an older launcher\n")
        (self.top / "clark.command").chmod(0o644)
        self.zip_of(self.home / "Downloads")
        code, out, err, opened = self.heal("y")
        self.assertEqual(0, code)
        self.assertEqual(self.good["clark.command"], (self.top / "clark.command").read_bytes())
        self.assertTrue(os.access(str(self.top / "clark.command"), os.X_OK))
        self.assertEqual([], [p.name for p in self.top.rglob("*") if p.name.endswith(".tmp")])

    def test_a_link_in_the_way_is_never_followed(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        shutil.rmtree(str(self.top / ".app/vendor"))
        os.symlink(str(outside), str(self.top / ".app/vendor"))
        self.zip_of(self.home / "Downloads")
        before = snapshot(outside)
        code, out, err, opened = self.heal("y")
        self.assertEqual(before, snapshot(outside))
        self.assertEqual(3, code)


class MoveOlderFiles(Fixture):
    def test_yes_moves_src_vendor_and_clark_into_one_folder_and_nothing_else(self):
        self.add_stale()
        before = snapshot(self.top)
        names_before = {p.name for p in self.top.iterdir()}
        code, out, err, opened = self.heal("y")
        self.assertEqual(0, code)
        self.assertIn(ASK_MOVE, out)
        self.assertIn(DONE_MOVED + "\n", out)
        after = snapshot(self.top)
        for name, data in STALE_FLAT.items():
            self.assertNotIn(name, after)
            self.assertEqual(data, after[OLDER + "/" + name], "renamed, not deleted: the bytes are all there")
        self.assertEqual((names_before - {"src", "vendor", "clark"}) | {OLDER}, {p.name for p in self.top.iterdir()})
        rest = {k: v for k, v in after.items() if k.split("/")[0] != OLDER}
        kept = {k: v for k, v in before.items() if k.split("/")[0] not in ("src", "vendor", "clark")}
        self.assertEqual(kept, rest)

    def test_data_system_docker_and_the_rest_are_byte_identical_after_everything(self):
        self.add_stale()
        self.make_old(".app/src/clark/a.py", ".app/vendor/lib/x.py")
        self.zip_of(self.home / "Downloads")
        person, data = self.person(), snapshot(self.data)
        for keys in ("yy", "yn", "n", ""):
            with self.subTest(keys=keys):
                self.heal(keys, data=str(self.data))
                self.heal(keys, data="mydata")                                      # a relative --data folder
                self.assertEqual(person, self.person())
                self.assertEqual(data, snapshot(self.data))
        self.assertEqual(person, self.person())

    def test_a_second_move_goes_into_the_same_folder_and_keeps_what_is_there(self):
        self.add_stale("src")
        self.heal("y")
        self.add_stale("src")
        self.put(self.top / "src/clark/another.py", b"another\n")
        self.heal("y")
        self.assertEqual([OLDER], [p.name for p in self.top.iterdir() if p.name.startswith("clark older")])
        kept = [p for p in (self.top / OLDER).rglob("*") if p.is_file()]
        self.assertEqual(3, len(kept), [str(p) for p in kept])


PERSON_TOP = {k.split("/")[0] for k in PERSON}


class Fallback(Fixture):
    def test_no_source_says_the_existing_sentence_and_opens_the_folder(self):
        self.make_old(".app/src/clark/a.py")
        before = snapshot(self.tmp)
        code, out, err, opened = self.heal("y")
        self.assertEqual(3, code)
        self.assertEqual(MESSAGE + "\n" + OPEN_LINE + "\n", err)
        self.assertEqual(before, snapshot(self.tmp))
        self.assertNotIn(COULD_NOT, out + err)

    def test_a_no_says_the_existing_sentence_and_opens_the_folder(self):
        self.make_old(".app/src/clark/a.py")
        self.zip_of(self.home / "Downloads")
        code, out, err, opened = self.heal("n")
        self.assertEqual(MESSAGE + "\n" + OPEN_LINE + "\n", err)

    def test_still_mixed_after_the_repair_says_it_could_not_put_every_file_back_first(self):
        self.make_old(".app/src/clark/a.py", ".app/src/clark/b.py")
        self.zip_of(self.home / "Downloads", {".app/src/clark/a.py": self.good[".app/src/clark/a.py"]})
        code, out, err, opened = self.heal("y")
        self.assertEqual(3, code)
        self.assertEqual(COULD_NOT + "\n" + MESSAGE + "\n" + OPEN_LINE + "\n", err)
        self.assertEqual(self.good[".app/src/clark/a.py"], (self.top / ".app/src/clark/a.py").read_bytes())


class Waits(Fixture):
    def test_the_update_marker_means_the_heal_waits(self):
        self.make_old(".app/src/clark/a.py")
        self.add_stale()
        self.zip_of(self.home / "Downloads")
        from clark import update_helper
        marker = update_helper.marker_path(self.data)
        marker.parent.mkdir(parents=True)
        marker.write_text("{}", encoding="utf-8")
        before = snapshot(self.tmp)

        def never():
            raise AssertionError("asked while an update was unfinished")
        out, err = io.StringIO(), io.StringIO()
        code = self.heal_module.run(self.top, self.data, key=never, out=out, err=err,
                                    home=self.home, tty=True)
        self.assertEqual((0, "", ""), (code, out.getvalue(), err.getvalue()))
        self.assertEqual(before, snapshot(self.tmp))

    def test_the_marker_path_is_the_one_the_update_code_writes(self):
        from clark import update_helper
        self.assertEqual(update_helper.marker_path(self.data), Path(self.data) / "updates" / ".installing.json")
        self.assertEqual(update_helper.marker_path(self.data), self.heal_module.marker_path(self.data))


class Agreement(Fixture):
    def test_the_list_of_differing_files_is_the_one_same_version_gives(self):
        app = self.top / ".app"
        self.assertEqual([], same_version.differing(app))
        self.make_old(".app/src/clark/b.py", ".app/vendor/lib/x.py")
        (self.top / ".app/src/clark/a.py").unlink()
        (self.top / "clark.command").write_bytes(b"older")
        mine = same_version.differing(app)
        self.assertEqual(sorted(mine), mine)
        self.assertEqual([".app/src/clark/a.py", ".app/src/clark/b.py", ".app/vendor/lib/x.py", "clark.command"], mine)
        record = self.heal_module.read_record(self.top)
        self.assertEqual(mine, self.heal_module.differing(self.top, record))
        self.assertTrue(same_version._mixed(app))

    def test_differing_is_none_without_a_download_or_a_readable_record(self):
        self.assertIsNone(same_version.differing(self.tmp / "checkout"))
        (self.top / "clark-release.json").write_text("not json", encoding="utf-8")
        self.assertIsNone(same_version.differing(self.top / ".app"))
        (self.top / "clark-release.json").unlink()
        self.assertIsNone(same_version.differing(self.top / ".app"))

    def test_message_and_refuse_are_unchanged(self):
        self.make_old(".app/src/clark/a.py")
        err = io.StringIO()
        same_version._ANSWERS.clear()
        self.assertTrue(same_version.refuse(err, self.top / ".app"))
        self.assertEqual(MESSAGE + "\n", err.getvalue())
        same_version._ANSWERS.clear()


class NoDownload(Fixture):
    def test_nothing_is_downloaded(self):
        self.make_old(".app/src/clark/a.py")
        self.add_stale()
        self.zip_of(self.home / "Downloads")

        def no(*a, **k):
            raise AssertionError("the heal reached for the network")
        with mock.patch.object(socket, "socket", no), mock.patch.object(socket, "create_connection", no), \
                mock.patch.object(socket, "getaddrinfo", no), mock.patch.object(socket, "gethostbyname", no):
            code = self.heal("yy")[0]
        self.assertEqual(0, code)

    def test_the_script_names_no_network_module(self):
        text = HEAL_PATH.read_text(encoding="utf-8")
        for word in ("socket", "urllib", "http", "ftplib", "ssl", "requests", "smtplib", "telnetlib"):
            self.assertNotIn("import " + word, text)
            self.assertNotIn("from " + word, text)

    def test_the_script_imports_only_the_standard_library_and_no_clark(self):
        import ast
        tree = ast.parse(HEAL_PATH.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        self.assertNotIn("clark", names)
        self.assertLessEqual(names, {"os", "sys", "hashlib", "json", "subprocess", "zipfile", "pathlib", "termios", "fcntl", "glob", "tempfile"})


class Guarded(unittest.TestCase):
    """The heal ships with the download as it is: no change to release_files, package or updates is needed."""

    def test_the_heal_script_is_covered_by_release_files_as_it_stands(self):
        import package
        placed = release_files.place("src/clark/same_version_heal.py")
        self.assertEqual(".app/src/clark/same_version_heal.py", placed)
        self.assertTrue(release_files.covers("mac", placed))
        self.assertIn("src/clark/", release_files.SHARED)
        built = package.files("mac")                                         # what git tracks of the list: the script is in the download
        self.assertIn("src/clark/same_version_heal.py", built)
        rels = [release_files.place(n) for n in built] + [release_files.START_HERE]
        updates.check_coverage("mac", rels)                                  # and the updater's own check still passes, with no change to it

    def test_the_script_is_a_tracked_file_under_src_clark(self):
        self.assertTrue(HEAL_PATH.is_file())
        self.assertEqual(ROOT / "src" / "clark", HEAL_PATH.parent)


# --- the real clark.command, in a terminal -----------------------------------------------------------------------------------

STUB_PYTHON = """#!/bin/sh
case "$1" in -c|-I) exec "{real}" "$@" ;; esac
echo "STUB-START $*"
exit 0
"""
STUB_OPEN = """#!/bin/sh
echo "OPEN $*" >> "{log}"
"""


@unittest.skipUnless(BASH, "needs bash")
class HostileNames(Fixture):
    """A record that names a file outside the folder (or in a form that could): nothing is written, nothing is asked, nothing changes."""

    NAMES = (".app/../../escaped.txt", ".app/../escaped.txt", "../escaped.txt", ".app/sub/../../../escaped.txt",
             "/escaped.txt", "//escaped.txt", ".app\\..\\escaped.txt", ".app/sub\\..\\escaped.txt", "\\\\server\\share\\escaped.txt",
             "\\escaped.txt", "C:\\escaped.txt", "C:/escaped.txt", "c:escaped.txt", ".app/x\x00y.txt", "")

    def record_with(self, name, data=b"PAYLOAD"):
        files = {n: {"sha256": sha(d), "size": len(d), "mode": "755" if n == "clark.command" else "644"}
                 for n, d in sorted(self.good.items())}
        files[name] = {"sha256": sha(data), "size": len(data), "mode": "644"}
        (self.top / "clark-release.json").write_text(json.dumps({"product": "clark", "version": "9.9.9", "files": files}),
                                                      encoding="utf-8")
        zpath = self.home / "Downloads" / "clark-9.9.9-mac.zip"
        with zipfile.ZipFile(str(zpath), "w") as z:
            for rel, d in sorted(self.good.items()):
                z.writestr("clark/" + rel, d)
            z.writestr("clark/" + name, data)

    def test_safe_refuses_every_hostile_name_and_keeps_the_good_ones(self):
        for name in self.NAMES:
            with self.subTest(name=name):
                self.assertFalse(self.heal_module._safe(name))
        for name in (".app/src/clark/a.py", "clark.command", ".app/a b/c.txt", ".app/..x/y", ".app/a..b"):
            with self.subTest(name=name):
                self.assertTrue(self.heal_module._safe(name))

    def test_a_record_naming_a_hostile_file_is_unreadable(self):
        for name in self.NAMES:
            with self.subTest(name=name):
                self.record_with(name)
                with self.assertRaises(ValueError):
                    self.heal_module.read_record(self.top)

    def test_a_hostile_name_writes_nothing_asks_nothing_and_changes_nothing(self):
        def never():
            raise AssertionError("asked a key for a record with a hostile name")
        for name in self.NAMES:
            with self.subTest(name=name):
                self.record_with(name)
                before = snapshot(self.tmp)
                outside = sorted(p for p in self.tmp.parent.glob("escaped.txt"))
                out, err = io.StringIO(), io.StringIO()
                code = self.heal_module.run(self.top, self.data, key=never, out=out, err=err, home=self.home, tty=True)
                self.assertEqual(0, code)
                self.assertEqual((("", "")), (out.getvalue(), err.getvalue()))
                self.assertNotIn("Put ", out.getvalue())
                self.assertEqual(before, snapshot(self.tmp))
                self.assertFalse((self.tmp / "escaped.txt").exists())
                self.assertEqual(outside, sorted(self.tmp.parent.glob("escaped.txt")))

    def test_a_hostile_name_with_an_older_folder_asks_only_to_move_it_and_still_writes_nothing(self):
        self.add_stale()
        self.record_with(".app/../../escaped.txt")
        asked = []
        out, err = io.StringIO(), io.StringIO()
        keys = iter("n")
        code = self.heal_module.run(self.top, self.data, key=lambda: (asked.append(1), next(keys, ""))[1], out=out, err=err,
                                    home=self.home, tty=True)
        self.assertEqual(3, code)
        self.assertNotIn("Put ", out.getvalue())
        self.assertFalse((self.tmp / "escaped.txt").exists())


@unittest.skipUnless(BASH, "needs bash")
class AllOrNothing(Fixture):
    A, B, C = ".app/src/clark/a.py", ".app/src/clark/b.py", ".app/vendor/v.py"

    def prepare(self):
        names = [n for n in (self.A, self.B) if n in self.good]
        self.assertEqual(2, len(names), "the fixture has two program files to put back")
        self.make_old(*names)
        self.zip_of(self.home / "Downloads")
        files = self.heal_module.read_record(self.top)
        copies = self.heal_module.find_copies(self.top, names, files, self.home)
        self.assertEqual(2, len(copies))
        return names, files, copies

    def test_a_rename_that_fails_part_way_puts_every_file_back_as_it_was(self):
        names, files, copies = self.prepare()
        before = snapshot(self.tmp)
        real = os.replace
        calls = []

        def replace(src, dst):
            calls.append(dst)
            if str(dst).endswith(names[1]) and ".clark-heal-" in str(src) and not str(src).endswith("-back.tmp"):
                raise OSError("disk full")
            return real(src, dst)
        with mock.patch.object(self.heal_module.os, "replace", replace):
            self.assertEqual(0, self.heal_module.put_back(self.top, copies, files, self.data))
        self.assertEqual(before, snapshot(self.tmp), "no file changed and no temporary file is left")

    def test_a_write_that_fails_changes_nothing_and_leaves_no_temporary_file(self):
        names, files, copies = self.prepare()
        before = snapshot(self.tmp)
        real = self.heal_module._stage

        def stage(path, blob, mode):
            if str(path).endswith("-1.tmp"):
                raise OSError("disk full")
            return real(path, blob, mode)
        with mock.patch.object(self.heal_module, "_stage", stage):
            self.assertEqual(0, self.heal_module.put_back(self.top, copies, files, self.data))
        self.assertEqual(before, snapshot(self.tmp))

    def test_one_copy_behind_a_link_puts_nothing_back(self):
        names, files, copies = self.prepare()
        outside = self.tmp / "outside"
        outside.mkdir()
        os.symlink(str(outside), str(self.top / ".app/zz"))
        copies = {names[0]: copies[names[0]], ".app/zz/n.py": (b"x", "here")}
        files = dict(files)
        files[".app/zz/n.py"] = {"mode": "644"}
        before = snapshot(self.tmp)
        self.assertEqual(0, self.heal_module.put_back(self.top, copies, files, self.data))
        self.assertEqual(before, snapshot(self.tmp))

    def test_a_partial_put_back_never_says_done(self):
        names, files, copies = self.prepare()
        real = os.replace

        def replace(src, dst):
            if str(dst).endswith(names[1]) and ".clark-heal-" in str(src) and not str(src).endswith("-back.tmp"):
                raise OSError("disk full")
            return real(src, dst)
        with mock.patch.object(self.heal_module.os, "replace", replace):
            code, out, err, opened = self.heal("y")
        self.assertNotIn("Done.", out)
        self.assertEqual(3, code)


class SourceGuards(Fixture):
    A = ".app/src/clark/a.py"

    def copies(self):
        files = self.heal_module.read_record(self.top)
        return self.heal_module.find_copies(self.top, [self.A], files, self.home)

    def test_a_zip_entry_whose_size_is_not_the_recorded_size_is_not_used(self):
        self.make_old(self.A)
        self.zip_of(self.home / "Downloads")
        record = json.loads((self.top / "clark-release.json").read_text(encoding="utf-8"))
        record["files"][self.A]["size"] += 1
        (self.top / "clark-release.json").write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual({}, self.copies())

    def test_a_zip_entry_larger_than_the_limit_is_not_used(self):
        self.make_old(self.A)
        self.zip_of(self.home / "Downloads")
        self.assertEqual(1, len(self.copies()))
        with mock.patch.object(self.heal_module, "MAX_FILE", 1):
            self.assertEqual({}, self.copies())

    def test_a_set_aside_file_that_is_a_link_is_not_used(self):
        self.make_old(self.A)
        real = self.tmp / "real-copy.py"
        real.write_bytes(self.good[self.A])
        folder = self.top / ".clark-old-1"
        (folder / ".app/src/clark").mkdir(parents=True)
        os.symlink(str(real), str(folder / self.A))
        self.assertEqual({}, self.copies())

    def test_a_set_aside_file_larger_than_the_limit_is_not_used(self):
        self.make_old(self.A)
        folder = self.top / ".clark-old-1"
        self.put(folder / self.A, self.good[self.A])
        self.assertEqual(1, len(self.copies()))
        with mock.patch.object(self.heal_module, "MAX_FILE", 1):
            self.assertEqual({}, self.copies())

    def test_a_zip_that_is_a_link_is_not_a_source(self):
        self.make_old(self.A)
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        real = self.zip_of(elsewhere)
        os.symlink(str(real), str(self.home / "Downloads" / "clark-9.9.9-mac.zip"))
        self.assertEqual({}, self.copies())


class ClarkCommand(Fixture):
    def setUp(self):
        super().setUp()
        self.stub = self.tmp / "stub-bin"
        self.stub.mkdir()
        self.open_log = self.tmp / "open.log"
        (self.stub / "python3").write_text(STUB_PYTHON.format(real=sys.executable), encoding="utf-8")
        (self.stub / "open").write_text(STUB_OPEN.format(log=self.open_log), encoding="utf-8")
        for name in ("python3", "open"):
            (self.stub / name).chmod(0o755)

    def env(self):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "CLARK_PORT", "CLARK_DATA_DIR")}
        env.update(HOME=str(self.home), PYTHONDONTWRITEBYTECODE="1", PATH=str(self.stub) + os.pathsep + os.environ["PATH"])
        return env

    def in_terminal(self, args, script, timeout=90):
        """Run clark.command with a terminal attached. `script` is [(text to wait for, what to type)]. Returns (code, output)."""
        master, slave = pty.openpty()
        proc = subprocess.Popen([BASH, str(self.top / "clark.command")] + list(args), stdin=slave, stdout=slave, stderr=slave,
                                cwd=str(self.top), env=self.env(), close_fds=True, start_new_session=True)
        os.close(slave)
        seen, step, mark, deadline = b"", 0, 0, time.time() + timeout
        try:
            while time.time() < deadline:
                ready, _, _ = select.select([master], [], [], 0.2)
                if ready:
                    try:
                        chunk = os.read(master, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    seen += chunk
                    if step < len(script) and script[step][0].encode() in seen[mark:]:
                        os.write(master, script[step][1].encode())
                        mark = len(seen)
                        step += 1
                elif proc.poll() is not None:
                    break
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            os.close(master)
        return proc.returncode, seen.decode("utf-8", "replace").replace("\r\n", "\n"), step

    def quiet(self, args=(), stdin=subprocess.DEVNULL):
        done = subprocess.run([BASH, str(self.top / "clark.command")] + list(args), cwd=str(self.top), env=self.env(), stdin=stdin,
                              capture_output=True, text=True, timeout=90)
        return done

    def test_no_terminal_is_exactly_as_it_was(self):
        self.add_stale()
        before = snapshot(self.tmp)
        done = self.quiet()
        self.assertEqual(1, done.returncode)
        self.assertEqual(MESSAGE + "\n", done.stderr)
        self.assertEqual("\n", done.stdout)
        self.assertEqual(before, snapshot(self.tmp))

    def test_check_and_restore_are_exactly_as_they_were_with_or_without_a_terminal(self):
        self.add_stale()
        self.make_old(".app/src/clark/a.py")
        self.zip_of(self.home / "Downloads")
        before = snapshot(self.tmp)
        for arg in ("--check", "restore"):
            with self.subTest(arg=arg, terminal=False):
                done = self.quiet([arg])
                self.assertEqual((1, MESSAGE + "\n", ""), (done.returncode, done.stderr, done.stdout))
            with self.subTest(arg=arg, terminal=True):
                code, output, step = self.in_terminal([arg], [("Type y", "y")], timeout=30)
                self.assertEqual(1, code)
                self.assertEqual(MESSAGE + "\n", output)
                self.assertEqual(0, step, "no question was asked")
            self.assertEqual(before, snapshot(self.tmp))
        self.assertFalse(self.open_log.exists())

    def test_check_or_restore_after_another_argument_skips_the_heal_too(self):
        self.add_stale()
        self.make_old(".app/src/clark/a.py")
        self.zip_of(self.home / "Downloads")
        before = snapshot(self.tmp)
        for args in (["--data", "x", "--check"], ["--data", "x", "restore"]):
            with self.subTest(args=args):
                code, output, step = self.in_terminal(args, [("Type y", "y")], timeout=30)
                self.assertEqual(0, step, "no question was asked")
                self.assertNotIn("Put ", output)
            self.assertEqual(before, snapshot(self.tmp))

    def test_yes_then_yes_puts_files_back_moves_the_older_folders_and_starts(self):
        self.add_stale()
        self.make_old(".app/src/clark/a.py", ".app/src/clark/b.py")
        self.zip_of(self.home / "Downloads")
        person = self.person()
        code, output, step = self.in_terminal([], [("Put 2 files back?", "y"), ("Move the older files", "y")])
        self.assertEqual(0, code, output)
        self.assertIn("Done. 2 files put back. Starting clark.", output)
        self.assertIn(DONE_MOVED, output)
        self.assertIn("STUB-START -m clark.launch", output)
        self.assertEqual(self.good[".app/src/clark/a.py"], (self.top / ".app/src/clark/a.py").read_bytes())
        self.assertFalse((self.top / "src").exists())
        self.assertEqual(STALE_FLAT["src/clark/old.py"], (self.top / OLDER / "src/clark/old.py").read_bytes())
        self.assertEqual(person, self.person())
        self.assertFalse(self.open_log.exists(), "a healed folder is not opened")

    def test_no_says_the_sentence_opens_the_folder_and_waits_for_a_key(self):
        self.add_stale()
        before = snapshot(self.top)
        code, output, step = self.in_terminal([], [("Move the older files", "n"), ("Press any key", " ")])
        self.assertEqual(1, code, output)
        self.assertIn(MESSAGE + "\n" + OPEN_LINE + "\n", output)
        self.assertNotIn("STUB-START", output)
        self.assertEqual(before, snapshot(self.top))
        self.assertEqual("OPEN " + str(self.top), self.open_log.read_text(encoding="utf-8").strip())

    def test_enter_alone_is_a_no(self):
        self.add_stale()
        before = snapshot(self.top)
        code, output, step = self.in_terminal([], [("Move the older files", "\n"), ("Press any key", " ")])
        self.assertEqual(1, code, output)
        self.assertEqual(before, snapshot(self.top))

    def test_the_heal_runs_by_path_when_a_flat_clark_and_poisoned_modules_shadow_it(self):
        self.add_stale()
        for name in ("json.py", "zipfile.py", "hashlib.py", "platform.py"):
            self.put(self.top / name, b"raise RuntimeError('SHADOWED')\n")
        env_extra = str(self.top)
        old_env = self.env
        self.env = lambda: dict(old_env(), PYTHONPATH=env_extra)         # the flat folder leads the path, as python3 -m does
        try:
            code, output, step = self.in_terminal([], [("Move the older files", "y")])
        finally:
            self.env = old_env
        self.assertNotIn("SHADOWED", output)
        self.assertNotIn("OLD FLAT CLARK", output)
        self.assertNotIn("Traceback", output)
        self.assertIn(DONE_MOVED, output)

    def test_the_script_run_without_isolation_still_ignores_the_folder_it_is_started_in(self):
        self.add_stale()
        for name in ("json.py", "zipfile.py", "hashlib.py"):
            self.put(self.top / name, b"raise RuntimeError('SHADOWED')\n")
        env = dict(self.env(), PYTHONPATH=str(self.top))
        done = subprocess.run([sys.executable, str(HEAL_PATH), str(self.top), str(self.data)], cwd=str(self.top), env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertNotIn("SHADOWED", done.stderr)

    def test_a_path_entry_that_is_a_link_to_the_folder_it_was_started_in_is_dropped_too(self):
        real = self.tmp / "started here"
        real.mkdir()
        link = self.tmp / "link to started here"
        link.symlink_to(real, target_is_directory=True)
        for name in ("json.py", "zipfile.py", "hashlib.py"):
            self.put(real / name, b"raise RuntimeError('SHADOWED')\n")
        env = dict(self.env(), PYTHONPATH=str(link))
        done = subprocess.run([sys.executable, str(HEAL_PATH), str(self.top), str(self.data)], cwd=str(real), env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertNotIn("SHADOWED", done.stderr)

    def test_a_path_entry_that_is_a_link_to_the_scripts_own_folder_is_dropped_too(self):
        link = self.tmp / "link to script folder"
        link.symlink_to(HEAL_PATH.parent, target_is_directory=True)
        out = subprocess.run([sys.executable, "-c",
                              "import sys, runpy; sys.argv = [sys.argv[0]]; sys.path.insert(0, %r);"
                              "g = runpy.run_path(%r, run_name='x'); print(sys.path)" % (str(link), str(HEAL_PATH))],
                             cwd=str(self.tmp), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        self.assertEqual(0, out.returncode, out.stderr)
        self.assertNotIn(str(link), out.stdout)


class BashSkip(unittest.TestCase):
    """The classes that run clark.command skip where bash is absent (Windows runners) and run where it exists."""

    def test_the_classes_that_run_clark_command_skip_only_without_bash(self):
        for cls in (ClarkCommand, HostileNames):
            self.assertEqual(not BASH, bool(getattr(cls, "__unittest_skip__", False)), cls.__name__)
            self.assertTrue(unittest.defaultTestLoader.loadTestsFromTestCase(cls).countTestCases() > 0, cls.__name__)


class DataAndServer(Fixture):
    """CMD 099: the data folder is never moved as a stale name, a clark that is open is never written under, realpath on both sides."""

    def open_lock(self, data):
        import fcntl
        Path(data).mkdir(parents=True, exist_ok=True)
        fd = os.open(str(Path(data) / ".clark-lock"), os.O_RDONLY | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(os.close, fd)

    def test_a_relative_data_that_is_a_stale_name_is_not_moved(self):
        self.add_stale()
        self.put(self.top / "vendor" / "my data.db", b"the person's data")
        before = snapshot(self.top / "vendor")
        code, out, err, _ = self.heal("yy", data="vendor")
        self.assertEqual(3, code, "vendor is still beside .app, so clark would not start: it is not said to be healed")
        self.assertNotIn("Starting clark", out)
        self.assertIn(MESSAGE + "\n" + OPEN_LINE + "\n", err)
        self.assertEqual(before, snapshot(self.top / "vendor"))
        self.assertEqual(b"the person's data", (self.top / "vendor" / "my data.db").read_bytes())
        self.assertFalse((self.top / OLDER / "vendor").exists())
        self.assertIn("Older clark files are in the way: src, clark.\n", out)
        self.assertFalse((self.top / "src").exists())

    def test_a_data_folder_called_clark_older_files_or_inside_it_is_never_used_as_the_place_to_move_to(self):
        self.add_stale()
        for data in (OLDER, OLDER + "/my data", "./" + OLDER + "/", "x/../" + OLDER + "/deeper/still"):
            with self.subTest(data=data):
                self.put(self.top / OLDER / "my data" / "clark.db", b"the person's data")
                (self.top / OLDER / "deeper" / "still").mkdir(parents=True, exist_ok=True)
                before = snapshot(self.top)
                code, out, err, _ = self.heal("yy", data=data)
                self.assertEqual((0, ""), (code, out), "nothing is asked: the name is the data's")
                self.assertNotIn(ASK_MOVE, out)
                self.assertEqual(before, snapshot(self.top), "src, vendor and clark stay, and nothing goes into the data folder")
        link = self.tmp / "linked data"
        link.symlink_to(self.top / OLDER, target_is_directory=True)
        before = snapshot(self.top)
        self.assertEqual((0, ""), self.heal("yy", data=str(link))[:2])
        self.assertEqual(before, snapshot(self.top))

    def test_move_stale_itself_refuses_when_the_data_folder_is_the_older_folder_or_inside_it(self):
        self.add_stale()
        self.put(self.top / OLDER / "my data" / "clark.db", b"the person's data")
        before = snapshot(self.top)
        for data in (OLDER, OLDER + "/my data"):
            with self.subTest(data=data):
                self.assertEqual([], self.heal_module.move_stale(self.top, ["src", "vendor", "clark"], data))
                self.assertEqual(before, snapshot(self.top))

    def test_the_older_folder_is_still_used_when_the_data_folder_is_somewhere_else(self):
        self.add_stale()
        self.put(self.top / "clark older files-not" / "x", b"x")                    # a name that only starts the same
        code, out, err, _ = self.heal("y", data=str(self.top / "clark older files-not"))
        self.assertEqual(0, code)
        self.assertIn(DONE_MOVED + "\n", out)

    def test_the_only_stale_name_being_the_data_folder_asks_and_changes_nothing(self):
        self.add_stale("vendor")
        before = snapshot(self.top)
        code, out, err, _ = self.heal("yy", data="vendor")
        self.assertEqual((0, ""), (code, out))
        self.assertEqual(before, snapshot(self.top))

    def test_data_spelled_with_dots_a_link_or_an_absolute_path_is_still_the_data(self):
        self.add_stale()
        link = self.tmp / "linked data"
        link.symlink_to(self.top / "src", target_is_directory=True)
        for data in ("./src/", "x/../src", str(self.top / "src"), str(link)):
            with self.subTest(data=data):
                self.assertNotIn("src", self.heal_module.stale_names(self.top, data))
                self.assertEqual(["vendor", "clark"], [n for n in self.heal_module.stale_names(self.top, data)])

    def test_data_inside_a_stale_name_keeps_that_name_too(self):
        self.add_stale()
        self.put(self.top / "clark" / "mine" / "clark.db", b"data")
        self.assertEqual(["src", "vendor"], self.heal_module.stale_names(self.top, "clark/mine"))
        self.assertEqual(["src", "vendor"], self.heal_module.stale_names(self.top, str(self.top / "clark" / "mine")))

    def test_a_data_folder_beside_the_stale_names_with_a_similar_name_does_not_hide_them(self):
        self.add_stale()
        self.assertEqual(["src", "vendor", "clark"], self.heal_module.stale_names(self.top, "mydata"))
        self.assertEqual(["src", "vendor", "clark"], self.heal_module.stale_names(self.top, "srcdata"))
        self.assertEqual(["src", "vendor", "clark"], self.heal_module.stale_names(self.top, str(self.data)))

    def test_put_back_refuses_and_writes_nothing_while_a_clark_is_open(self):
        self.make_old(".app/src/clark/a.py", ".app/src/clark/b.py")
        self.zip_of(self.home / "Downloads")
        self.open_lock(self.data)
        before = snapshot(self.tmp)
        files = self.heal_module.read_record(self.top)
        copies = self.heal_module.find_copies(self.top, [".app/src/clark/a.py", ".app/src/clark/b.py"], files, self.home)
        self.assertEqual(2, len(copies))
        self.assertEqual(0, self.heal_module.put_back(self.top, copies, files, self.data))
        self.assertEqual(before, snapshot(self.tmp))

    def test_put_back_goes_on_when_the_lock_file_is_not_held(self):
        self.make_old(".app/src/clark/a.py")
        self.zip_of(self.home / "Downloads")
        Path(self.data / ".clark-lock").write_bytes(b"")                  # left by a clark that has stopped
        files = self.heal_module.read_record(self.top)
        copies = self.heal_module.find_copies(self.top, [".app/src/clark/a.py"], files, self.home)
        self.assertEqual(1, self.heal_module.put_back(self.top, copies, files, self.data))
        self.assertEqual(self.good[".app/src/clark/a.py"], (self.top / ".app/src/clark/a.py").read_bytes())

    def test_a_running_clark_gets_the_existing_sentence_and_the_folder_opens_with_nothing_written(self):
        self.add_stale()
        self.make_old(".app/src/clark/a.py")
        self.zip_of(self.home / "Downloads")
        self.open_lock(self.data)
        before = snapshot(self.tmp)
        code, out, err, _ = self.heal("yy")
        self.assertEqual(3, code)
        self.assertIn(MESSAGE + "\n" + OPEN_LINE + "\n", err)
        self.assertNotIn("Put 1 files back", out)
        self.assertEqual(before, snapshot(self.tmp))

    def test_checking_for_a_clark_creates_nothing_in_the_data_folder(self):
        before = snapshot(self.data)
        self.assertFalse(self.heal_module.server_running(self.data))
        self.assertFalse(self.heal_module.server_running(self.tmp / "no such data"))
        self.assertEqual(before, snapshot(self.data))
        self.assertFalse((self.tmp / "no such data").exists())

    def test_a_path_that_is_spelled_through_a_link_cannot_lead_the_path(self):
        """A Mac's /var against /private/var: the program's folder reached through a link, the path entry given as its real place."""
        link = self.tmp / "linked clark"
        link.symlink_to(self.top, target_is_directory=True)
        here = self.top / ".app" / "src" / "clark"
        self.put(here / "json.py", b"raise RuntimeError('SHADOWED')\n")
        env = dict(self.env_plain(), PYTHONPATH=os.path.realpath(str(here)))
        done = subprocess.run([sys.executable, str(link / ".app" / "src" / "clark" / "same_version_heal.py"), str(self.top), str(self.data)],
                              cwd=str(self.tmp), env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertNotIn("SHADOWED", done.stderr)

    def test_the_started_in_folder_reached_through_a_link_cannot_lead_the_path_either(self):
        real = self.tmp / "started real"
        real.mkdir()
        link = self.tmp / "started link"
        link.symlink_to(real, target_is_directory=True)
        self.put(real / "json.py", b"raise RuntimeError('SHADOWED')\n")
        env = dict(self.env_plain(), PYTHONPATH=str(link))
        done = subprocess.run([sys.executable, str(HEAL_PATH), str(self.top), str(self.data)], cwd=str(link), env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertNotIn("SHADOWED", done.stderr)

    @staticmethod
    def env_plain():
        return {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}


if __name__ == "__main__":
    unittest.main()
