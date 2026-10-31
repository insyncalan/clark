"""#43 (the pure part): To client. Every case in tests/fixtures/to-client-cases.json, and the rules around them.

Run: python3 tests/test_to_client.py
No server, no browser, no network. The disk is a fake that records what is written (FakeFs), except for two tests that copy a
real published file into a temporary folder. Names, folders and people are fictional.
"""
import ast
import hashlib
import inspect
import json
import re
import tempfile
import unittest
import unicodedata
from unittest import mock
from pathlib import Path, PurePath

from _paths import ROOT, SRC

import _publish_fixture as fx  # noqa: E402
from clark import page, platform, publish, to_client as tc  # noqa: E402

CASES = json.loads((ROOT / "tests" / "fixtures" / "to-client-cases.json").read_text(encoding="utf-8"))
CTX = CASES["context_for_folder_cases"]
DATA_DIR, ROOTS, LOCAL = CTX["data_dir"], CTX["onedrive_roots"], CTX["local_folder"]
CLIENT = ROOTS[0] + "/Client reports/Harbour Bridge"
DAY = "2026-10-28"
WEEK = "2026-10-23"
WANTED = "PUB-report-2026-10-23.html"
BODY = b'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"></head><body><p>Harbour Bridge weekly report</p></body></html>'
SHA = hashlib.sha256(BODY).hexdigest()
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")


def tearDownModule():
    Path(EMPTY_BRANDING).rmdir()


class FakeFs:
    """A disk in a dictionary. Every write and removal is recorded, so a test can say "nothing was written"."""

    def __init__(self, folders=(), files=None, links=None, unwritable=(), fail_write=None, corrupt_read=False, fail_read=0,
                 appears=None):
        """corrupt_read: True, or how many read-backs of a written file come back changed. fail_read: how many read-backs of
        a written file raise OSError. appears: {path: bytes} that turn up on the disk just before the next write (a file the
        client's OneDrive finished syncing between the listing and the write)."""
        self.dirs = {str(PurePath(f)) for f in folders}
        self.files = {str(PurePath(k)): v for k, v in (files or {}).items()}
        self.links = {str(PurePath(k)): str(PurePath(v)) for k, v in (links or {}).items()}
        self.unwritable = {str(PurePath(u)) for u in unwritable}
        self.fail_write = fail_write
        self.corrupt_left = float("inf") if corrupt_read is True else int(corrupt_read or 0)
        self.fail_read_left = int(fail_read)
        self.appears = {str(PurePath(k)): v for k, v in (appears or {}).items()}
        self.writes, self.removes = [], []

    def exists(self, path):
        return self.realpath(path) in self.dirs or self.realpath(path) in self.files

    def is_dir(self, path):
        return self.realpath(path) in self.dirs

    def writable(self, path):
        return self.realpath(path) in self.dirs and str(PurePath(path)) not in self.unwritable

    def realpath(self, path):
        path = str(PurePath(path))
        for link, target in self.links.items():
            if path == link or path.startswith(link + "/"):
                return str(PurePath(target + path[len(link):]))
        return path

    def listdir(self, path):
        path = self.realpath(path)
        out = [{"name": PurePath(k).name, "kind": "file"} for k in self.files if str(PurePath(k).parent) == path]
        return out + [{"name": PurePath(k).name, "kind": "folder"} for k in self.dirs if str(PurePath(k).parent) == path]

    def read_bytes(self, path, limit=None):
        data = self.files[str(PurePath(path))]            # KeyError would be a test bug; a missing file is FileNotFoundError
        if str(PurePath(path)) in self.written() and limit is None:      # the read-back; the proof it is ours (with a limit) is exact
            if self.fail_read_left:
                self.fail_read_left -= 1
                raise OSError(5, "Input/output error")
            if self.corrupt_left:
                self.corrupt_left -= 1
                data = data + b" "
        return data if limit is None else data[:limit]

    def written(self):
        return {p for p, _ in self.writes}

    def write_file(self, path, data, replaces):
        if self.fail_write:
            raise self.fail_write
        self.files.update(self.appears)                    # the race: a file turns up after the listing
        self.appears = {}
        key = str(PurePath(path))
        if not replaces and (key in self.files or key in self.dirs):
            return False                                   # linked into place: a taken name is never overwritten
        self.writes.append((key, data))
        self.files[key] = data
        return True

    def identity(self, path):
        key = str(PurePath(path))
        return (1, sum(key.encode()), len(self.files[key]), 0, 0)      # a stable inode for a name; the bytes decide the rest

    def remove(self, path):
        self.removes.append(str(PurePath(path)))
        if str(PurePath(path)) not in self.files:
            raise FileNotFoundError(path)
        del self.files[str(PurePath(path))]

    def names(self, folder=CLIENT):
        return sorted(e["name"] for e in self.listdir(folder))


def client_fs(**kw):
    files = {f"{CLIENT}/{n}": d for n, d in kw.pop("named", {}).items()}
    return FakeFs(folders=[CLIENT, DATA_DIR, LOCAL, *kw.pop("extra_dirs", [])], files=files, **kw)


def send(fs, **kw):
    args = dict(saved_folder=CLIENT, data=BODY, project="PUB", at=DAY, week_ending=WEEK, today=DAY, data_dir=DATA_DIR,
                onedrive_roots=ROOTS, local_folder=LOCAL, markers=())
    args.update(kw)
    return tc.send_to_client(fs, **args)


class TheCases(unittest.TestCase):
    def test_the_fixture_has_every_case(self):
        self.assertEqual({k: len(CASES[k]) for k in ("file_name_cases", "safe_name_cases", "clash_cases", "folder_cases",
                                                      "request_cases")},
                         {"file_name_cases": 7, "safe_name_cases": 9, "clash_cases": 17, "folder_cases": 11, "request_cases": 11})

    def test_file_name_cases(self):
        for c in CASES["file_name_cases"]:
            folder = "x" * c["folder_chars"]
            with self.subTest(c["id"]):
                if c["expect"].startswith("PlatformError: "):
                    with self.assertRaisesRegex(platform.PlatformError, re.escape(c["expect"].split(": ", 1)[1])):
                        tc.client_file_name(c["code"], c["week_ending"], c["today"], folder)
                else:
                    got = tc.client_file_name(c["code"], c["week_ending"], c["today"], folder)
                    self.assertEqual(got, c["expect"])
                    self.assertLessEqual(len(folder) + 1 + len(got), platform.MAX_PATH - 1)

    def test_safe_name_cases(self):
        for c in CASES["safe_name_cases"]:
            with self.subTest(c["id"]):
                self.assertEqual(platform.safe_name(c["input"]), c["expect"])

    def test_clash_cases(self):
        for c in CASES["clash_cases"]:
            with self.subTest(c["id"]):
                got = tc.resolve_clash(c["name"], c["existing"], c["choice"], c.get("new_name"))
                for key, value in c["expect"].items():
                    self.assertEqual(got.get(key), value, key)
                if c["expect"]["action"] == "refuse":
                    self.assertTrue(got["message"])
                if c["expect"]["action"] == "write" and c["expect"]["replaces"]:
                    self.assertTrue(got["needs_confirmation"])
                else:
                    self.assertFalse(got.get("needs_confirmation"))

    def test_folder_cases(self):
        for c in CASES["folder_cases"]:
            with self.subTest(c["id"]):
                got = tc.check_client_folder(c["path"], data_dir=DATA_DIR, onedrive_roots=ROOTS, local_folder=LOCAL,
                                             exists=c["exists"], is_dir=c.get("is_dir", False), writable=c.get("writable", False))
                self.assertEqual(got, c["expect"])

    def test_the_same_folder_cases_through_a_disk(self):
        for c in CASES["folder_cases"]:
            if not c["path"]:
                continue
            with self.subTest(c["id"]):
                fs = FakeFs(folders=[c["path"]] if c["is_dir"] else [], files={} if c["is_dir"] or not c["exists"] else {c["path"]: b""},
                            unwritable=[] if c["writable"] else [c["path"]])
                got = tc.preflight(fs, c["path"], data_dir=DATA_DIR, onedrive_roots=ROOTS, local_folder=LOCAL)
                self.assertEqual(got, c["expect"])
                self.assertEqual(fs.writes, [])

    def test_request_cases(self):
        for c in CASES["request_cases"]:
            with self.subTest(c["id"]):
                saved = None if c.get("setup") == "project has no publish_client" else CLIENT
                self.assertEqual(tc.validate_request(c["body"], saved), c["expect"])

    def test_the_messages_are_the_catalogue_word_for_word(self):
        for key, text in CASES["messages"].items():
            self.assertEqual(tc.MESSAGES[key], text, key)

    def test_every_message_is_plain(self):
        texts = []
        for value in tc.MESSAGES.values():
            texts += value if isinstance(value, list) else [value]
        self.assertGreater(len(texts), 40)
        for t in texts:
            self.assertNotRegex(t, r"(?i)\bSHA|\broute\b|errno|traceback|\bAPI\b|\bJSON\b|\bbytes?\b|report editor|exception")
            self.assertNotRegex(t, r"\bClark\b|\bUC\b")
            self.assertFalse(t.lower().startswith(("insert", "update", "delete", "create", "drop", "alter")), t)


class TheName(unittest.TestCase):
    def test_a_deep_folder_keeps_the_date_and_the_extension(self):
        for chars in range(150, 241, 5):
            name = tc.client_file_name("PUB", WEEK, DAY, "x" * chars)
            self.assertTrue(name.endswith("-2026-10-23.html"), (chars, name))
            self.assertLessEqual(chars + 1 + len(name), platform.MAX_PATH - 1)
        self.assertEqual(tc.client_file_name("PUB", WEEK, DAY, "x" * 150), WANTED)
        self.assertNotEqual(tc.client_file_name("PUB", "2026-10-23", DAY, "x" * 240), tc.client_file_name("PUB", "2026-10-30", DAY, "x" * 240))

    def test_the_date_is_todays_when_there_is_no_week_ending(self):
        self.assertEqual(tc.client_file_name("PUB", None, DAY, None), "PUB-report-2026-10-28.html")

    def test_it_is_the_name_the_local_file_gets_when_nothing_is_cut(self):
        self.assertEqual(tc.client_file_name("HBP2026", WEEK, DAY, "/x" * 20), publish.file_name("HBP2026", WEEK, DAY, "/x" * 20))

    def test_a_deep_folder_through_the_whole_step(self):
        deep = "/" + "/".join(["deep"] * 46)                     # 229 characters
        fs = FakeFs(folders=[deep, DATA_DIR], files={})
        done = send(fs, saved_folder=deep)
        self.assertTrue(done.ok, done.message)
        self.assertTrue(done.name.endswith("-2026-10-23.html"), done.name)
        self.assertEqual(list(fs.files), [deep + "/" + done.name])


class TheTakenName(unittest.TestCase):
    def existing(self, *names):
        return [{"name": n, "kind": "file", "same_content": False} for n in names]

    def test_numbering_ignores_case_and_keeps_the_number(self):
        taken = self.existing(WANTED, WANTED.replace("PUB", "pub").replace(".html", " (2).html"), "pub-REPORT-2026-10-23 (3).HTML")
        self.assertEqual(tc.resolve_clash(WANTED, taken, "number")["name"], "PUB-report-2026-10-23 (4).html")
        longer = "y" * 115 + ".html"
        got = tc.resolve_clash(longer, self.existing(longer, "y" * 111 + " (2).html"), "number")["name"]
        self.assertTrue(got.endswith(" (3).html"), got)
        self.assertLessEqual(len(got), platform.MAX_NAME)

    def test_numbering_reads_the_folders_room_into_the_limit(self):
        folder = "z" * 200                                     # 58 characters of room
        long_name = "w" * 50 + ".html"
        got = tc.resolve_clash(long_name, self.existing(long_name), "number", folder=folder)["name"]
        self.assertTrue(got.endswith(" (2).html"), got)
        self.assertLessEqual(len(folder) + 1 + len(got), platform.MAX_PATH - 1)

    def test_a_name_without_an_extension_gets_its_number_at_the_end(self):
        self.assertEqual(tc.resolve_clash("Notes", self.existing("Notes"), "number")["name"], "Notes (2)")

    def test_overwrite_is_never_silent(self):
        got = tc.resolve_clash(WANTED, self.existing(WANTED), "overwrite")
        self.assertEqual((got["action"], got["replaces"], got["needs_confirmation"]), ("write", True, True))
        fs = client_fs(named={WANTED: b"the client's older copy"})
        first = send(fs, choice="overwrite")                      # not confirmed: asks, writes nothing
        self.assertEqual((first.ok, first.action), (False, "confirm_overwrite"))
        self.assertEqual(fs.writes, [])
        self.assertEqual(fs.files[f"{CLIENT}/{WANTED}"], b"the client's older copy")
        self.assertIn("keeps no backup", first.clash["note"])
        again = send(fs, choice="overwrite", confirmed=True)
        self.assertTrue(again.ok, again.message)
        self.assertEqual((again.action, again.replaced), ("done", True))
        self.assertEqual(again.message, tc.MESSAGES["done_replaced"].format(name=WANTED))
        self.assertEqual(fs.files[f"{CLIENT}/{WANTED}"], BODY)
        self.assertEqual(fs.names(), [WANTED], "no backup, no temporary file, beside the client's file")
        self.assertEqual(fs.removes, [], "an overwrite never removes what it did not make")

    def test_a_copy_cannot_replace_a_file_it_was_not_told_to(self):
        fs = client_fs(named={WANTED: b"older"})
        done = tc.copy_to_client(fs, CLIENT, WANTED, BODY, project="PUB", at=DAY, markers=())          # replaces left False
        self.assertEqual((done.ok, done.action), (False, "refused"))
        self.assertEqual(fs.writes, [])
        self.assertEqual(fs.files[f"{CLIENT}/{WANTED}"], b"older")
        again = tc.copy_to_client(fs, CLIENT, WANTED, BODY, project="PUB", at=DAY, markers=(), replaces=True)   # replaces but not confirmed
        self.assertEqual((again.ok, again.action, fs.writes), (False, "confirm_overwrite", []))

    def test_a_taken_name_asks_and_writes_nothing(self):
        fs = client_fs(named={WANTED: b"older"})
        got = send(fs)
        self.assertEqual((got.ok, got.action, fs.writes), (False, "ask", []))
        self.assertEqual(got.clash["numbered"], "PUB-report-2026-10-23 (2).html")
        self.assertTrue(got.clash["can_overwrite"])
        self.assertEqual(got.message, tc.MESSAGES["clash_title"])

    def test_each_choice_ends_with_the_exact_listing(self):
        for choice, new_name, listing, message in (
                ("number", None, [WANTED, "PUB-report-2026-10-23 (2).html"], "done_numbered"),
                ("rename", "PUB weekly 23 Oct", [WANTED, "PUB weekly 23 Oct.html"], "done_numbered")):
            with self.subTest(choice):
                fs = client_fs(named={WANTED: b"older"})
                got = send(fs, choice=choice, new_name=new_name)
                self.assertTrue(got.ok, got.message)
                self.assertEqual(fs.names(), sorted(listing))
                self.assertEqual(fs.files[f"{CLIENT}/{WANTED}"], b"older", "the client's file is untouched")
                self.assertEqual(got.message, tc.MESSAGES[message].format(name=got.name, asked=WANTED))
        fs = client_fs(named={WANTED: b"older"})
        got = send(fs, choice="cancel")
        self.assertEqual((got.ok, got.action, fs.writes, fs.names()), (False, "cancel", [], [WANTED]))

    def test_the_same_file_is_already_there(self):
        fs = client_fs(named={WANTED: BODY})
        got = send(fs)
        self.assertEqual((got.ok, got.action, fs.writes), (True, "nothing_to_do", []))
        self.assertEqual(got.message, tc.MESSAGES["done_same"].format(name=WANTED))
        self.assertEqual(got.log["sha256"], SHA)

    def test_a_rename_that_is_taken_asks_again(self):
        fs = client_fs(named={WANTED: b"older", "Handover.html": b"other"})
        got = send(fs, choice="rename", new_name="handover")
        self.assertEqual((got.action, fs.writes), ("ask", []))
        self.assertEqual(got.clash["name"], "handover.html")
        self.assertEqual(got.clash["numbered"], "handover (2).html")

    def test_a_name_that_is_already_taken_by_a_folder(self):
        fs = client_fs(extra_dirs=[f"{CLIENT}/{WANTED}"])
        got = send(fs)
        self.assertEqual((got.action, got.clash["can_overwrite"], fs.writes), ("ask", False, []))
        refused = send(fs, choice="overwrite", confirmed=True)
        self.assertEqual((refused.ok, refused.action, fs.writes), (False, "refused", []))
        self.assertEqual(refused.message, tc.MESSAGES["folder_has_name"])
        late = tc.copy_to_client(fs, CLIENT, WANTED, BODY, project="PUB", at=DAY, markers=(), replaces=True, confirmed=True)
        self.assertEqual((late.ok, late.action, fs.writes), (False, "refused", []), "even if the copy step is asked directly")
        numbered = send(fs, choice="number")
        self.assertTrue(numbered.ok, numbered.message)
        self.assertEqual(numbered.name, "PUB-report-2026-10-23 (2).html")
        self.assertEqual(fs.writes[0][0], f"{CLIENT}/PUB-report-2026-10-23 (2).html")

    def test_windows_reserved_names_are_made_safe(self):
        for typed, expect in (("CON", "_CON.html"), ("nul", "_nul.html"), ("COM1.report", "_COM1.report.html"),
                              ("aux.html", "_aux.html"), ("LPT²", "_LPT².html"), ("a<b>c|d", "a-b-c-d.html"),
                              ("  Weekly: 23/10  ", "Weekly- 23-10.html")):
            with self.subTest(typed):
                got = tc.resolve_clash(WANTED, self.existing(WANTED), "rename", typed)
                self.assertEqual((got["action"], got["name"]), ("write", expect))

    def test_a_rename_with_nothing_in_it_is_refused(self):
        for typed in (None, "", "  ", ".html", "  .HTML "):
            with self.subTest(typed):
                got = tc.resolve_clash(WANTED, self.existing(WANTED), "rename", typed)
                self.assertEqual((got["action"], got["reason"]), ("refuse", "empty_name"))

    def test_folder_comparisons_ignore_letter_case_and_accent_form(self):
        composed = "/Users/sam.carter/Library/Application Support/Café Zürich/clark"
        decomposed = unicodedata.normalize("NFD", composed)
        self.assertNotEqual(composed, decomposed)
        folder_args = dict(onedrive_roots=ROOTS, exists=True, is_dir=True, writable=True)
        for label, saved, data_dir in (("composed vs decomposed", composed, decomposed), ("decomposed vs composed", decomposed, composed),
                                       ("case only", composed.upper(), composed), ("case and form", unicodedata.normalize("NFD", composed.lower()), composed)):
            with self.subTest("inside the data folder: " + label):
                got = tc.check_client_folder(saved + "/exports", data_dir=data_dir, local_folder=LOCAL, **folder_args)
                self.assertEqual(got, {"ok": False, "message": tc.MESSAGES["inside_data"]})
            with self.subTest("the data folder itself: " + label):
                self.assertEqual(tc.check_client_folder(saved, data_dir=data_dir, local_folder=LOCAL, **folder_args)["message"], tc.MESSAGES["inside_data"])
            with self.subTest("holds the data folder: " + label):
                self.assertEqual(tc.check_client_folder(str(PurePath(saved).parent), data_dir=data_dir, local_folder=LOCAL, **folder_args)["message"],
                                 tc.MESSAGES["holds_data"])
            with self.subTest("the Local folder: " + label):
                got = tc.check_client_folder(saved, data_dir=DATA_DIR, local_folder=data_dir, **folder_args)
                self.assertEqual(got["message"], tc.MESSAGES["is_local"])
            with self.subTest("the backups folder: " + label):
                got = tc.check_client_folder(saved, data_dir=DATA_DIR, local_folder=LOCAL, backups_dir=data_dir, **folder_args)
                self.assertEqual(got["message"], tc.MESSAGES["is_backups"])
        look_alike = tc.check_client_folder(composed + "-old", data_dir=decomposed, local_folder=LOCAL, **folder_args)
        self.assertTrue(look_alike["ok"], "clark-old is not inside clark, in any spelling")

    def test_a_onedrive_root_is_matched_whatever_the_spelling(self):
        root = "/Users/sam.carter/Library/CloudStorage/OneDrive-Café"
        got = tc.check_client_folder(unicodedata.normalize("NFD", root.upper()) + "/Reports", data_dir=DATA_DIR, onedrive_roots=[root],
                                     local_folder=LOCAL, exists=True, is_dir=True, writable=True)
        self.assertEqual((got["ok"], got["warning"]), (True, None))

    def test_file_names_are_the_same_name_whatever_case_or_accent_form(self):
        composed, decomposed = "Café Zürich.html", unicodedata.normalize("NFD", "Café Zürich.html")
        for existing, wanted in ((composed, decomposed), (decomposed, composed), (composed.upper(), composed), (decomposed.upper(), composed),
                                 (composed, unicodedata.normalize("NFD", composed.upper()))):
            with self.subTest(existing=existing, wanted=wanted):
                self.assertEqual(tc.resolve_clash(wanted, [existing])["action"], "ask")
                self.assertEqual(tc.resolve_clash(wanted, [existing], "overwrite")["replaces"], True)
                numbered = tc.numbered_name(wanted, [existing, tc.numbered_name(wanted, [existing])])
                self.assertTrue(numbered.lower().endswith("(3).html"), numbered)
                self.assertEqual(tc.resolve_clash(wanted, [{"name": existing, "kind": "file", "same_content": True}])["action"], "nothing_to_do")
        fs = client_fs(named={decomposed: b"older"})
        late = tc.copy_to_client(fs, CLIENT, composed.upper(), BODY, project="PUB", at=DAY, markers=())
        self.assertEqual((late.action, fs.writes), ("refused", []), "a copy step asked for a name that differs only in case or form")
        got = tc.resolve_clash(WANTED, [WANTED.upper()], "rename", "pub-REPORT-2026-10-23")
        self.assertEqual(got["action"], "ask", "a typed rename is compared the same way")

    def test_a_numbered_name_is_announced_only_when_the_name_really_differs(self):
        asked = unicodedata.normalize("NFD", "Café.html")
        got = tc.copy_to_client(client_fs(), CLIENT, "Café.html", BODY, project="PUB", at=DAY, markers=(), asked=asked)
        self.assertEqual(got.message, tc.MESSAGES["done_new"].format(name="Café.html"))

    def test_unicode_names(self):
        composed = "Rapport semaine 43 – Zürich 項目.html"
        decomposed = unicodedata.normalize("NFD", composed)
        self.assertNotEqual(composed, decomposed)
        fs = client_fs(named={decomposed: b"older"})              # macOS keeps the second spelling
        got = send(fs, choice="rename", new_name=composed)
        self.assertEqual((got.action, fs.writes), ("ask", []), "the accented name is the same name however it was typed")
        self.assertEqual(got.clash["numbered"], composed.replace(".html", " (2).html"))
        self.assertEqual(tc.resolve_clash("Été.html", self.existing("éTÉ.html"), "number")["name"], "Été (2).html")
        fresh = send(client_fs(), choice=None)
        self.assertTrue(fresh.ok)
        folder = ROOTS[0] + "/Clients/Café Zürich 項目"
        fs2 = FakeFs(folders=[folder, DATA_DIR])
        done = send(fs2, saved_folder=folder)
        self.assertTrue(done.ok, done.message)
        gone = send(FakeFs(folders=[DATA_DIR]), saved_folder=folder)
        self.assertIn("“Café Zürich 項目”", gone.message)
        model = tc.to_client_dialog(tc.new_dialog_state(folder))
        self.assertEqual(model["to_client"]["folder_name"], "Café Zürich 項目")


class ThePreflight(unittest.TestCase):
    def test_folder_missing_writes_nothing_at_all(self):
        gone = ROOTS[0] + "/Client reports/Gone"
        fs = FakeFs(folders=[DATA_DIR, LOCAL])
        got = send(fs, saved_folder=gone)
        self.assertEqual((got.ok, got.action, got.nothing_written), (False, "refused", True))
        self.assertEqual(got.message, tc.MESSAGES["folder_missing_nothing_written"].format(folder_name="Gone"))
        self.assertEqual((fs.writes, fs.removes, fs.files, got.log), ([], [], {}, None))

    def test_no_folder_saved_writes_nothing(self):
        fs = client_fs()
        got = send(fs, saved_folder=None)
        self.assertEqual((got.ok, got.message, fs.writes), (False, tc.MESSAGES["refused_nothing_published"].format(reason=tc.MESSAGES["not_saved"]), []))

    def test_clarks_data_and_backups_folders_are_refused(self):
        backups = ROOTS[0] + "/clark backups"
        for path in (DATA_DIR, DATA_DIR + "/exports", backups, backups + "/2026"):
            with self.subTest(path):
                fs = FakeFs(folders=[path, DATA_DIR, backups])
                got = send(fs, saved_folder=path, backups_dir=backups)
                self.assertEqual((got.ok, got.action, fs.writes), (False, "refused", []))
                self.assertTrue(got.message.endswith("Nothing was published."))

    def test_a_link_out_to_a_forbidden_place_is_refused(self):
        link = ROOTS[0] + "/Client reports/Shortcut"
        backups = ROOTS[0] + "/clark backups"
        for target in (DATA_DIR, DATA_DIR + "/exports", backups, LOCAL):
            with self.subTest(target):
                fs = FakeFs(folders=[target, DATA_DIR, backups, LOCAL], links={link: target})
                self.assertTrue(fs.is_dir(link))
                got = send(fs, saved_folder=link, backups_dir=backups)
                self.assertEqual((got.ok, got.action, fs.writes), (False, "refused", []))

    def test_a_link_to_a_good_folder_is_used(self):
        link = ROOTS[0] + "/Client reports/Shortcut"
        fs = FakeFs(folders=[CLIENT, DATA_DIR], links={link: CLIENT})
        got = send(fs, saved_folder=link)
        self.assertTrue(got.ok, got.message)
        self.assertEqual(fs.writes[0][0], f"{CLIENT}/{WANTED}", "the copy goes to the real place the check found, not the link")

    def test_a_link_to_somewhere_outside_onedrive_warns(self):
        link = ROOTS[0] + "/Shortcut"
        other = "/Users/sam.carter/Documents/Elsewhere"
        fs = FakeFs(folders=[other, DATA_DIR], links={link: other})
        got = tc.preflight(fs, link, data_dir=DATA_DIR, onedrive_roots=ROOTS, local_folder=LOCAL)
        self.assertTrue(got["ok"])
        self.assertEqual(got["warning"], tc.MESSAGES["not_onedrive"])

    def test_an_unwritable_folder_writes_nothing(self):
        fs = client_fs(unwritable=[CLIENT])
        got = send(fs)
        self.assertEqual((got.ok, fs.writes), (False, []))
        self.assertIn("“Harbour Bridge” can't be written to", got.message)

    def test_a_folder_too_deep_for_any_name_is_refused(self):
        deep = "/" + "/".join(["deep"] * 49)                     # 244 characters
        fs = FakeFs(folders=[deep, DATA_DIR])
        got = send(fs, saved_folder=deep)
        self.assertEqual((got.ok, fs.writes), (False, []))
        self.assertIn("too deep", got.message)
        self.assertNotIn("deep/deep", got.message, "no location is shown")


class TheCopy(unittest.TestCase):
    def test_a_new_file_is_copied_read_back_and_logged(self):
        fs = client_fs()
        got = send(fs, local_sha256=SHA)
        self.assertTrue(got.ok, got.message)
        self.assertEqual((got.action, got.name, got.sha256, got.replaced), ("done", WANTED, SHA, False))
        self.assertEqual(got.message, tc.MESSAGES["done_new"].format(name=WANTED))
        self.assertEqual(fs.files[f"{CLIENT}/{WANTED}"], BODY)
        self.assertEqual(fs.names(), [WANTED])
        self.assertEqual(got.log, {"project": "PUB", "kind": "client", "file_name": WANTED, "sha256": SHA, "at": DAY,
                                   "client_path": f"{CLIENT}/{WANTED}"})

    def test_the_sha256_read_back_mismatch_is_reported(self):
        fs = client_fs(corrupt_read=True)
        got = send(fs)
        self.assertEqual((got.ok, got.action, got.log, got.sha256), (False, "failed", None, None))
        self.assertEqual(got.message, tc.MESSAGES["copy_differs"])
        self.assertEqual(fs.names(), [], "the copy this publish made is removed")
        self.assertEqual(fs.removes, [f"{CLIENT}/{WANTED}"])

    def test_a_mismatch_after_an_overwrite_puts_the_previous_file_back(self):
        for kind, fs, problem in (("changed", client_fs(named={WANTED: b"older"}, corrupt_read=1), "did not match the published file"),
                                  ("unreadable", client_fs(named={WANTED: b"older"}, fail_read=1), "could not be read back to check it")):
            with self.subTest(kind):
                got = send(fs, choice="overwrite", confirmed=True)
                self.assertEqual((got.ok, got.action, got.log, got.restored, got.replaced), (False, "failed", None, True, False))
                self.assertEqual(got.message, tc.MESSAGES["restored"].format(name=WANTED, problem=problem))
                self.assertIn("put the previous file back", got.message)
                self.assertEqual(fs.files[f"{CLIENT}/{WANTED}"], b"older", "the client's own bytes are back")
                self.assertEqual([d for _, d in fs.writes], [BODY, b"older"])
                self.assertEqual(fs.names(), [WANTED], "no backup or temporary file beside it")
                self.assertEqual(fs.removes, [], "it cannot take back a file it did not make")

    def test_when_the_write_back_fails_too_both_failures_are_reported(self):
        fs = client_fs(named={WANTED: b"older"}, corrupt_read=True)          # every read-back is wrong, the restore's too
        got = send(fs, choice="overwrite", confirmed=True)
        self.assertEqual((got.ok, got.action, got.log, got.restored, got.replaced), (False, "failed", None, False, True))
        self.assertIn("did not match the published file", got.message)
        self.assertIn("the previous file could not be put back", got.message)
        self.assertIn("now holds the wrong copy", got.message)

        class Refuses(FakeFs):
            def write_file(self, path, data, replaces):
                if data == b"older":
                    raise PermissionError(13, "Permission denied")
                return super().write_file(path, data, replaces)
        fs2 = Refuses(folders=[CLIENT, DATA_DIR, LOCAL], files={f"{CLIENT}/{WANTED}": b"older"}, corrupt_read=1)
        got2 = send(fs2, choice="overwrite", confirmed=True)
        self.assertEqual((got2.restored, got2.replaced), (False, True))
        self.assertIn("clark could not write to the client folder. Check you can edit it.", got2.message)
        self.assertNotIn("Permission denied", got2.message)
        self.assertIn("did not match the published file", got2.message)

    def test_an_overwrite_keeps_the_old_bytes_only_in_memory(self):
        fs = client_fs(named={WANTED: b"older"})
        got = send(fs, choice="overwrite", confirmed=True)
        self.assertTrue(got.ok)
        self.assertEqual(fs.names(), [WANTED])

    def test_an_old_file_too_big_to_hold_or_unreadable_is_not_replaced(self):
        big = b"x" * (publish.MAX_BYTES + 1)
        fs = client_fs(named={WANTED: big})
        got = send(fs, choice="overwrite", confirmed=True)
        self.assertEqual((got.ok, got.action, fs.writes), (False, "failed", []))
        self.assertEqual(got.message, tc.MESSAGES["overwrite_too_big"].format(name=WANTED))
        self.assertEqual(fs.files[f"{CLIENT}/{WANTED}"], big)

        class Unreadable(FakeFs):
            def read_bytes(self, path, limit=None):
                if str(path).endswith(WANTED):
                    raise PermissionError(13, "Permission denied")
                return super().read_bytes(path, limit)
        fs2 = Unreadable(folders=[CLIENT, DATA_DIR, LOCAL], files={f"{CLIENT}/{WANTED}": b"older"})
        got2 = tc.copy_to_client(fs2, CLIENT, WANTED, BODY, project="PUB", at=DAY, markers=(), replaces=True, confirmed=True)
        self.assertEqual((got2.ok, fs2.writes), (False, []))
        self.assertEqual(got2.message, tc.MESSAGES["overwrite_unreadable"].format(name=WANTED))

    def test_a_file_that_appears_between_the_listing_and_the_write_is_refused_not_overwritten(self):
        theirs = b"the client's own file, synced a moment ago"
        fs = client_fs(appears={f"{CLIENT}/{WANTED}": theirs})              # not there at the listing, there at the write
        got = send(fs)
        self.assertEqual((got.ok, got.action, got.log, got.nothing_written), (False, "refused", None, True))
        self.assertEqual(got.message, tc.MESSAGES["name_appeared"].format(name=WANTED))
        self.assertEqual(fs.files[f"{CLIENT}/{WANTED}"], theirs, "their bytes are unchanged")
        self.assertEqual((fs.writes, fs.removes), ([], []))

    def test_the_same_race_on_the_real_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            theirs = b"the client's own file"
            real = tc.RealFs()
            listed = real.listdir(folder)
            self.assertEqual(listed, [])
            (folder / WANTED).write_bytes(theirs)                          # arrives after the listing
            self.assertIs(real.write_file(folder / WANTED, BODY, replaces=False), False)
            self.assertEqual((folder / WANTED).read_bytes(), theirs)
            self.assertEqual([p.name for p in folder.iterdir()], [WANTED], "no temporary file left behind")
            self.assertIs(real.write_file(folder / WANTED, BODY, replaces=True), True)
            self.assertEqual((folder / WANTED).read_bytes(), BODY)

    def test_the_real_disk_writes_a_new_name_by_linking(self):
        linked = []
        real_link = platform.os.link
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIs(platform.write_file_unless_exists(Path(tmp) / "a.html", BODY,
                                                            link=lambda a, b: (linked.append(b), real_link(a, b))), True)
            self.assertEqual(len(linked), 1)
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["a.html"])

    def _fs_with_identity(self, **kw):
        class Stat(FakeFs):
            """A disk that also says device, inode, size and change times. `meta` holds them per path; a write gives a new
            change time, and a test can put a different file under the same name with the same inode number."""
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.meta, self.clock, self.on_read = {}, 0, None

            def write_file(self, path, data, replaces):
                ok = super().write_file(path, data, replaces)
                if ok:
                    self.clock += 1
                    self.meta[str(PurePath(path))] = (1, 4242, len(data), self.clock, self.clock)
                return ok

            def identity(self, path):
                return self.meta[str(PurePath(path))]

            def read_bytes(self, path, limit=None):
                if self.on_read:
                    self.on_read, hook = None, self.on_read
                    hook(self, str(PurePath(path)))
                return super().read_bytes(path, limit)
        return Stat(folders=[CLIENT, DATA_DIR], **kw)

    def test_a_file_with_a_recycled_inode_number_is_not_taken_back(self):
        fs = self._fs_with_identity()

        def swap(disk, path):                       # someone deletes the copy and makes another file: same inode number
            disk.clock += 1
            disk.files[path] = b"someone else's file"
            disk.meta[path] = (1, 4242, len(b"someone else's file"), disk.clock, disk.clock)
        fs.on_read = swap
        got = send(fs)
        self.assertFalse(got.ok)
        self.assertEqual(fs.files[f"{CLIENT}/{WANTED}"], b"someone else's file")
        self.assertEqual(fs.removes, [])

    def test_the_copy_this_call_made_is_taken_back_when_it_fails_its_check(self):
        fs = self._fs_with_identity(corrupt_read=True)
        got = send(fs)
        self.assertFalse(got.ok)
        self.assertEqual(fs.removes, [f"{CLIENT}/{WANTED}"])
        self.assertNotIn(f"{CLIENT}/{WANTED}", fs.files)

    def test_the_same_inode_with_the_bytes_this_call_wrote_is_still_ours(self):
        fs = self._fs_with_identity(fail_read=1)

        def touch(disk, path):                      # a sync tool touches the file: change times move, bytes and inode do not
            disk.clock += 1
            disk.meta[path] = (1, 4242, disk.meta[path][2], disk.clock, disk.clock)
        fs.on_read = touch
        got = send(fs)
        self.assertFalse(got.ok)
        self.assertEqual(fs.removes, [f"{CLIENT}/{WANTED}"])

    def test_an_identical_identity_with_different_bytes_is_not_taken_back(self):
        fs = self._fs_with_identity()
        same = {}

        def swap(disk, path):                       # other bytes, and the disk says exactly what it said for our copy
            disk.files[path] = b"someone else's file"
            disk.meta[path] = same["tuple"]
        fs.on_read = swap
        real_write = fs.write_file

        def write(path, data, replaces):
            ok = real_write(path, data, replaces)
            same["tuple"] = fs.meta[str(PurePath(path))]
            return ok
        fs.write_file = write
        got = send(fs)
        self.assertFalse(got.ok)
        self.assertEqual(fs.files[f"{CLIENT}/{WANTED}"], b"someone else's file")
        self.assertEqual(fs.removes, [])

    def test_a_missing_digest_is_an_error_not_a_fall_back_to_the_times(self):
        fs = self._fs_with_identity()
        fs.files["x"] = b"a"
        fs.meta["x"] = (1, 1, 1, 1, 1)
        with self.assertRaises(TypeError):
            tc._ours(fs, "x", (1, 1, 1, 1, 1))
        with self.assertRaises(TypeError):
            tc._remove(fs, "x", (1, 1, 1, 1, 1))
        self.assertFalse(tc._ours(fs, "x", (1, 1, 1, 1, 1), tc.sha256_of(b"other")))
        self.assertTrue(tc._ours(fs, "x", (1, 1, 1, 1, 1), tc.sha256_of(b"a")))

    def test_a_disk_that_cannot_say_which_file_was_written_removes_nothing(self):
        class Blind(FakeFs):
            def identity(self, path):
                raise OSError("no identity")
        fs = Blind(folders=[CLIENT, DATA_DIR], corrupt_read=True)
        got = send(fs)
        self.assertEqual(fs.removes, [])
        self.assertEqual(got.message, tc.MESSAGES["copy_not_removed"].format(name=WANTED))

    def test_a_copy_that_cannot_be_removed_says_so(self):
        class Stuck(FakeFs):
            def remove(self, path):
                raise PermissionError("held by OneDrive")
        fs = Stuck(folders=[CLIENT, DATA_DIR], corrupt_read=True)
        got = send(fs)
        self.assertEqual(got.message, tc.MESSAGES["copy_not_removed"].format(name=WANTED))

    def test_a_refused_write_keeps_the_client_folder_as_it_was(self):
        for error, expect in ((platform.PlatformError("PUB couldn't be saved because another program is using it or it is locked. Close it there and try again."),
                               "another program is using it"),
                              (PermissionError(13, "Permission denied"), "clark could not write to the client folder. Check you can edit it.")):
            with self.subTest(type(error).__name__):
                fs = client_fs(fail_write=error)
                got = send(fs)
                self.assertEqual((got.ok, got.action, got.log, got.nothing_written), (False, "failed", None, True))
                self.assertTrue(got.message.startswith("Saved locally, but not copied to the client folder:"), got.message)
                self.assertTrue(got.message.endswith("Nothing was added there."))
                self.assertIn(expect, got.message)
                self.assertNotRegex(got.message, r"(?i)permission denied|errno|\(no reason|refused it \(")
                self.assertEqual((fs.names(), fs.removes), ([], []))

    def test_bytes_that_are_not_the_published_file_are_not_copied(self):
        fs = client_fs()
        got = send(fs, local_sha256="0" * 64)
        self.assertEqual((got.ok, got.action, fs.writes), (False, "refused", []))

    def test_something_that_reaches_outside_is_held_back_before_any_write(self):
        for body in (BODY.replace(b"<p>", b'<p><img src="https://x.invalid/a.png">'), BODY.replace(b"<body>", b'<body id="clark-boot">'),
                     BODY.replace(b"Harbour", CLIENT.encode("utf-8")), b"\xff\xfe not text"):
            with self.subTest(body[:60]):
                fs = client_fs()
                got = send(fs, data=body)
                self.assertEqual((got.ok, got.action, fs.writes), (False, "refused", []))
                self.assertIn("Nothing was published", got.message)

    def test_a_marker_that_must_be_absent_is_held_back_in_every_spelling(self):
        for spelled in ("ZQ-INTERNAL <1>", "zq-internal <1>", "ZQ-INTERNAL &lt;1&gt;", "ZQ-INTERNAL \\u003c1\\u003e"):
            fs = client_fs()
            got = send(fs, data=BODY.replace(b"</p>", spelled.encode("utf-8") + b"</p>"), markers=["ZQ-INTERNAL <1>"])
            self.assertEqual((got.ok, fs.writes), (False, []), spelled)

    def test_it_runs_the_scan_of_39(self):
        self.assertEqual(tc.check_copy(BODY, markers=()), [])
        self.assertIn("a <link> tag", tc.check_copy(b'<link rel="stylesheet" href="a.css">', markers=()))
        self.assertEqual(tc.check_copy(b'<script src="a.js"></script>', markers=()), publish.outside_addresses('<script src="a.js"></script>'))

    def test_a_fake_data_block_hides_nothing_from_the_copy_check(self):      # the same scan, the same place for the block (#106)
        opener = b'<script type="application/json" id="clark-data">'
        for bad in (b'<link rel="stylesheet" href="a.css">', b'<script src="a.js"></script>'):
            self.assertTrue(tc.check_copy(BODY.replace(b"<body>", b"<body>" + opener + bad + b"</script>", 1), markers=()), bad)
            self.assertTrue(tc.check_copy(opener + bad + b"</script>", markers=()), bad)
        self.assertTrue(tc.check_copy(b"<STYLE>@IMPORT 'a.css';</STYLE>", markers=()))
        self.assertEqual(tc.check_copy(BODY, markers=()), [], "and the real block is still left out")


class TheMarkerCheck(unittest.TestCase):
    """The run-time check for text that must be absent is always on: no parameter, flag or default turns it off (#43, Head's ruling on Q5)."""
    OFF_SWITCH = re.compile(r"(?i)skip|disable|bypass|ignore|unchecked|no_?check|check_?off|\boff\b|verify|validate|dry|force|trust|lenient|strict|enable|_check$|^check")

    def public_callables(self):
        for name, obj in vars(tc).items():
            if name.startswith("_") or getattr(obj, "__module__", None) != tc.__name__:
                continue
            if inspect.isfunction(obj):
                yield name, obj
            elif inspect.isclass(obj):
                for meth_name, meth in vars(obj).items():
                    if inspect.isfunction(meth) and not meth_name.startswith("_"):
                        yield f"{name}.{meth_name}", meth

    def test_no_signature_offers_a_way_to_turn_the_check_off(self):
        seen = 0
        for name, func in self.public_callables():
            for param in inspect.signature(func).parameters.values():
                seen += 1
                with self.subTest(f"{name}({param.name})"):
                    self.assertIsNone(self.OFF_SWITCH.search(param.name), "a parameter that sounds like an off switch")
        self.assertGreater(seen, 40)

    def test_the_markers_cannot_be_left_out(self):
        for func in (tc.check_copy, tc.copy_to_client, tc.send_to_client):
            param = inspect.signature(func).parameters["markers"]
            self.assertIs(param.default, inspect.Parameter.empty, func.__name__)
            self.assertEqual(param.kind, inspect.Parameter.KEYWORD_ONLY, func.__name__)
        with self.assertRaises(TypeError):
            tc.check_copy(BODY)
        with self.assertRaises(TypeError):
            tc.send_to_client(client_fs(), saved_folder=CLIENT, data=BODY, project="PUB", at=DAY, week_ending=WEEK, today=DAY,
                              data_dir=DATA_DIR, onedrive_roots=ROOTS, local_folder=LOCAL)

    def test_only_the_named_flags_are_booleans_with_a_default(self):
        flags = set()
        for name, func in self.public_callables():
            for param in inspect.signature(func).parameters.values():
                if isinstance(param.default, bool):
                    flags.add((name, param.name))
        self.assertEqual(flags, {("copy_to_client", "replaces"), ("copy_to_client", "confirmed"), ("send_to_client", "confirmed")})

    def test_a_leak_is_held_back_in_both_entry_points_and_on_the_copy_read_back(self):
        leak = BODY.replace(b"</p>", b" ZQ-INTERNAL</p>")
        for how in ("send", "copy"):
            fs = client_fs()
            if how == "send":
                got = send(fs, data=leak, markers=["ZQ-INTERNAL"])
            else:
                got = tc.copy_to_client(fs, CLIENT, WANTED, leak, project="PUB", at=DAY, markers=["zq-internal"])
            self.assertEqual((got.ok, got.action, fs.writes), (False, "refused", []), how)
            self.assertIn("meant to be left out", got.message)

        class Leaks(FakeFs):
            def read_bytes(self, path, limit=None):
                data = super().read_bytes(path, limit)
                return data.replace(b"</p>", b" ZQ-INTERNAL</p>") if str(path) in self.written() and limit is None else data
        fs2 = Leaks(folders=[CLIENT, DATA_DIR, LOCAL])
        got2 = send(fs2, markers=["ZQ-INTERNAL"])
        self.assertEqual((got2.ok, got2.action, fs2.names()), (False, "failed", []), "the copy that came back with it in is removed")

    def test_the_marker_check_on_the_read_back_matters_on_its_own(self):
        """Only the read-back differs, by a marker, and its hash is made to agree: the marker check alone must catch it."""
        class Leaks(FakeFs):
            def read_bytes(self, path, limit=None):
                data = super().read_bytes(path, limit)
                return data.replace(b"</p>", b" ZQ-INTERNAL</p>") if str(path) in self.written() else data
        fs = Leaks(folders=[CLIENT, DATA_DIR, LOCAL])
        with mock.patch.object(tc, "sha256_of", lambda data: "same"):
            got = send(fs, markers=["ZQ-INTERNAL"])
        self.assertEqual((got.ok, got.action, fs.names()), (False, "failed", []))

    def test_a_marker_is_found_whatever_its_letter_case_or_accent_form(self):
        marker = "Zürich-INTERNAL"
        for spelled in (marker, unicodedata.normalize("NFD", marker), marker.lower(), unicodedata.normalize("NFD", marker.upper())):
            body = BODY.replace(b"</p>", spelled.encode("utf-8") + b"</p>")
            self.assertIn("text that was meant to be left out", tc.check_copy(body, markers=[marker]), spelled)
            self.assertIn("text that was meant to be left out", tc.check_copy(body, markers=[unicodedata.normalize("NFD", marker)]), spelled)

    def test_the_folder_path_is_found_whatever_its_letter_case_or_accent_form(self):
        folder = "/Users/sam.carter/Library/CloudStorage/OneDrive-Harbourside/Café Zürich"
        for spelled in (folder, unicodedata.normalize("NFD", folder), folder.upper()):
            body = BODY.replace(b"</p>", spelled.encode("utf-8") + b"</p>")
            self.assertIn("the location of the client folder", tc.check_copy(body, folder=folder, markers=()), spelled)


class TheRequest(unittest.TestCase):
    def test_only_true_means_to_client(self):
        for value in (True, False, None, 0, 1, "true", "false", "yes", [], {}):
            got = tc.validate_request({"project": "PUB", "to_client": value}, CLIENT)
            self.assertEqual(got["status"] == 200, isinstance(value, bool), value)
            if got["status"] == 200:
                self.assertIs(got["to_client"], value)
        self.assertEqual(tc.validate_request({"project": "PUB"}, CLIENT), {"status": 200, "to_client": False, "confirmed": False})

    def test_a_request_never_names_a_folder_or_a_file(self):
        for key in ("client_folder", "folder", "path", "file", "file_name", "dest", "client_path"):
            got = tc.validate_request({"project": "PUB", "to_client": True, key: "/tmp/x"}, CLIENT)
            self.assertEqual(got, {"status": 400, "message": tc.MESSAGES["names_a_folder"]}, key)
        self.assertEqual(tc.validate_request({"project": "PUB", "colour": "red"}, CLIENT)["status"], 400)
        self.assertEqual(tc.validate_request("PUB", CLIENT)["status"], 400)

    def test_an_overwrite_needs_confirmed_true_exactly(self):
        base = {"project": "PUB", "to_client": True, "on_clash": "overwrite"}
        ok = tc.validate_request(dict(base, confirmed=True), CLIENT)
        self.assertEqual(ok, {"status": 200, "to_client": True, "confirmed": True})
        self.assertEqual(tc.validate_request(base, CLIENT), {"status": 400, "message": tc.MESSAGES["overwrite_unconfirmed"]}, "missing")
        self.assertEqual(tc.validate_request(dict(base, confirmed=False), CLIENT),
                         {"status": 400, "message": tc.MESSAGES["overwrite_unconfirmed"]}, "false")
        for value in ("true", 1, None, "yes", [], {}, 1.0):
            with self.subTest(repr(value)):
                self.assertEqual(tc.validate_request(dict(base, confirmed=value), CLIENT),
                                 {"status": 400, "message": tc.MESSAGES["confirmed_flag"]})

    def test_confirmed_is_never_inferred_and_never_widens_another_choice(self):
        for clash in (None, "number", "rename", "cancel"):
            body = {"project": "PUB", "to_client": True}
            if clash:
                body["on_clash"] = clash
            self.assertIs(tc.validate_request(body, CLIENT)["confirmed"], False, clash)
            self.assertIs(tc.validate_request(dict(body, confirmed=True), CLIENT)["confirmed"], True, clash)
        self.assertEqual(tc.validate_request({"project": "PUB", "to_client": True, "confirmed": "true"}, CLIENT)["status"], 400)

    def test_the_choices_are_checked(self):
        self.assertEqual(tc.validate_request({"project": "PUB", "to_client": True, "on_clash": "replace"}, CLIENT)["status"], 400)
        self.assertEqual(tc.validate_request({"project": "PUB", "to_client": True, "on_clash": "rename", "new_name": "x"}, CLIENT)["status"], 200)
        self.assertEqual(tc.validate_request({"project": "PUB", "to_client": True, "new_name": 3}, CLIENT)["status"], 400)


class TheDialog(unittest.TestCase):
    def test_defaults_with_no_folder(self):
        m = tc.to_client_dialog(tc.new_dialog_state(None))
        self.assertEqual(m["local"], {"label": "Local", "ticked": True, "disabled": True})
        self.assertEqual((m["to_client"]["ticked"], m["to_client"]["disabled"], m["to_client"]["hint"]),
                         (False, True, "No client folder yet. Set it in Settings."))
        self.assertEqual((m["button"]["label"], m["line"], m["setting"]), ("Publish locally", None, "projects.publish_client"))
        self.assertEqual((m["esc"], m["focus_after_close"]), ("cancel", "publish"))
        s = tc.dialog_step(tc.new_dialog_state(None), "tick", True)
        self.assertFalse(s["ticked"], "no folder, no tick")

    def test_ticking_changes_the_button_and_the_line(self):
        s = tc.new_dialog_state(CLIENT)
        m = tc.to_client_dialog(s)
        self.assertEqual((m["to_client"]["ticked"], m["to_client"]["disabled"], m["to_client"]["hint"]), (False, False, "Harbour Bridge"))
        m = tc.to_client_dialog(tc.dialog_step(s, "tick", True))
        self.assertEqual((m["button"]["label"], m["line"], m["to_client"]["ticked"]),
                         ("Publish and send to the client", "The client will see this page.", True))
        self.assertEqual(s["ticked"], False, "the old state is not changed")

    def test_to_client_is_never_remembered(self):
        ticked = tc.dialog_step(tc.new_dialog_state(CLIENT), "tick", True)
        done = tc.dialog_step(tc.dialog_step(ticked, "publish"), "result", {"ok": True, "action": "done", "message": "Published."})
        self.assertTrue(done["ticked"])
        self.assertFalse(tc.new_dialog_state(CLIENT)["ticked"])
        self.assertFalse(tc.to_client_dialog(tc.new_dialog_state(CLIENT))["to_client"]["ticked"])

    def test_clearing_the_folder_unticks(self):
        s = tc.dialog_step(tc.dialog_step(tc.new_dialog_state(CLIENT), "tick", True), "folder", None)
        self.assertEqual((s["ticked"], s["saved_folder"]), (False, None))

    def test_publishing_blocks_the_button(self):
        s = tc.dialog_step(tc.dialog_step(tc.new_dialog_state(CLIENT), "tick", True), "publish")
        m = tc.to_client_dialog(s)
        self.assertEqual((m["busy"], m["button"]["disabled"], m["to_client"]["disabled"], m["status"]), (True, True, True, "Publishing…"))
        self.assertEqual(tc.dialog_step(s, "publish"), s)
        self.assertEqual(tc.dialog_step(s, "cancel"), s, "Esc does not stop a publish half done")

    def test_the_request_the_dialog_sends(self):
        s = tc.dialog_step(tc.new_dialog_state(CLIENT), "tick", True)
        self.assertEqual(tc.dialog_request(s, "PUB"), {"project": "PUB", "to_client": True})
        self.assertEqual(tc.dialog_request(tc.new_dialog_state(CLIENT), "PUB"), {"project": "PUB", "to_client": False})
        self.assertEqual(tc.validate_request(tc.dialog_request(s, "PUB"), CLIENT)["status"], 200)

    def test_the_dialog_sends_confirmed_only_after_its_confirm_step(self):
        s = self.ask()
        s = tc.dialog_step(s, "choose", "overwrite")
        self.assertNotIn("confirmed", tc.dialog_request(s, "PUB"))
        self.assertEqual(tc.validate_request(tc.dialog_request(s, "PUB"), CLIENT)["status"], 400, "an unconfirmed overwrite is refused")
        s = tc.dialog_step(s, "confirm")
        body = tc.dialog_request(s, "PUB")
        self.assertIs(body["confirmed"], True)
        self.assertEqual(tc.validate_request(body, CLIENT), {"status": 200, "to_client": True, "confirmed": True})
        for choice in ("number", "rename"):
            self.assertNotIn("confirmed", tc.dialog_request(tc.dialog_step(tc.dialog_step(s, "choose", choice), "rename_text", "x"), "PUB"))

    def ask(self, **clash):
        s = tc.dialog_step(tc.dialog_step(tc.new_dialog_state(CLIENT), "tick", True), "publish")
        plan = {"name": WANTED, "numbered": "PUB-report-2026-10-23 (2).html", "can_overwrite": True}
        plan.update(clash)
        return tc.dialog_step(s, "result", {"ok": False, "action": "ask", "message": tc.MESSAGES["clash_title"], "clash": plan})

    def test_the_clash_question(self):
        m = tc.to_client_dialog(self.ask())["clash"]
        self.assertEqual(m["title"], "A file with that name is already in the client folder")
        self.assertEqual([(o["label"], o["selected"]) for o in m["options"]],
                         [("Add a number", True), ("Rename it", False), ("Overwrite the existing file", False)])
        self.assertEqual((m["cancel"], m["preview"]), ("Cancel", "saves as “PUB-report-2026-10-23 (2).html”"))
        self.assertFalse(m["rename"]["visible"])
        self.assertFalse(m["go"]["disabled"])
        self.assertEqual(tc.dialog_request(self.ask(), "PUB"), {"project": "PUB", "to_client": True, "on_clash": "number"})

    def test_rename_needs_text(self):
        s = tc.dialog_step(self.ask(), "choose", "rename")
        m = tc.to_client_dialog(s)["clash"]
        self.assertEqual((m["rename"]["visible"], m["rename"]["needs_text"], m["go"]["disabled"]), (True, True, True))
        self.assertEqual(tc.dialog_step(s, "publish"), s, "nothing is sent until there is a name")
        s = tc.dialog_step(s, "rename_text", "  PUB weekly  ")
        self.assertFalse(tc.to_client_dialog(s)["clash"]["go"]["disabled"])
        self.assertEqual(tc.dialog_request(s, "PUB"), {"project": "PUB", "to_client": True, "on_clash": "rename", "new_name": "PUB weekly"})

    def test_overwrite_needs_its_own_confirmation_and_says_there_is_no_backup(self):
        s = tc.dialog_step(self.ask(), "choose", "overwrite")
        m = tc.to_client_dialog(s)["clash"]
        self.assertTrue(m["needs_confirmation"] and m["go"]["disabled"] and not m["confirmed"])
        self.assertIn("keeps no backup", m["note"])
        self.assertEqual(tc.dialog_step(s, "publish"), s)
        s = tc.dialog_step(s, "confirm")
        self.assertFalse(tc.to_client_dialog(s)["clash"]["go"]["disabled"])
        self.assertEqual(tc.dialog_step(s, "choose", "number")["confirm_overwrite"], False, "changing the choice withdraws it")
        self.assertEqual(tc.dialog_step(s, "publish")["phase"], "working")
        self.assertEqual(tc.dialog_request(s, "PUB")["on_clash"], "overwrite")

    def test_a_folder_with_the_name_offers_no_overwrite(self):
        m = tc.to_client_dialog(self.ask(can_overwrite=False))["clash"]
        self.assertEqual([o["id"] for o in m["options"]], ["number", "rename"])

    def test_cancel_ends_the_question_and_the_dialog(self):
        s = tc.dialog_step(self.ask(), "cancel")
        self.assertEqual((s["phase"], s["clash"], s["message"]["text"]), ("closed", None, "Cancelled. Nothing was published."))
        m = tc.to_client_dialog(s)
        self.assertEqual((m["closed"], m["focus_after_close"]), (True, "publish"))
        self.assertTrue(tc.to_client_dialog(tc.dialog_step(tc.new_dialog_state(CLIENT), "cancel"))["closed"])

    def test_results_become_messages(self):
        s = tc.dialog_step(tc.dialog_step(tc.new_dialog_state(CLIENT), "tick", True), "publish")
        ok = tc.dialog_step(s, "result", send(client_fs()))
        self.assertEqual(tc.to_client_dialog(ok)["message"], {"kind": "success", "text": tc.MESSAGES["done_new"].format(name=WANTED)})
        bad = tc.dialog_step(s, "result", send(FakeFs(folders=[DATA_DIR])))
        m = tc.to_client_dialog(bad)
        self.assertEqual(m["message"]["kind"], "error")
        self.assertIn("Nothing was published", m["message"]["text"])
        self.assertFalse(m["button"]["disabled"], "the dialog stays open so To client can be unticked")
        self.assertTrue(tc.dialog_step(bad, "tick", False)["phase"] == "error")
        with self.assertRaises(ValueError):
            tc.dialog_step(s, "nonsense")

    def test_a_whole_clash_round_trip(self):
        fs = client_fs(named={WANTED: b"older"})
        s = tc.dialog_step(tc.dialog_step(tc.new_dialog_state(CLIENT), "tick", True), "publish")
        body = tc.dialog_request(s, "PUB")
        self.assertEqual(body, {"project": "PUB", "to_client": True})
        s = tc.dialog_step(s, "result", send(fs))
        self.assertEqual(s["phase"], "clash")
        s = tc.dialog_step(tc.dialog_step(s, "choose", "rename"), "rename_text", "Harbour weekly")
        s = tc.dialog_step(s, "publish")
        body = tc.dialog_request(s, "PUB")
        self.assertEqual(tc.validate_request(body, CLIENT)["status"], 200)
        done = send(fs, choice=body["on_clash"], new_name=body["new_name"])
        s = tc.dialog_step(s, "result", done)
        self.assertEqual((s["phase"], fs.names()), ("done", sorted([WANTED, "Harbour weekly.html"])))


class TheRealDisk(unittest.TestCase):
    """A real published file, copied with the real disk into a temporary folder (the only writes this file makes)."""

    @classmethod
    def setUpClass(cls):
        cls.plant = fx.load()
        pub = publish.select(fx.inputs(cls.plant))
        cls.text = publish.render(pub, page.page_html(EMPTY_BRANDING), cls.plant["as_at"], pub["data"]["project"]["name"])
        cls.bytes = cls.text.encode("utf-8")

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.client = self.root / "OneDrive-Fictional" / "Client reports" / "Harbour Bridge"
        self.client.mkdir(parents=True)
        self.data_dir = self.root / "clark-data"
        self.data_dir.mkdir()

    def real_send(self, **kw):
        args = dict(saved_folder=str(self.client), data=self.bytes, project="PUB", at=DAY, week_ending=WEEK, today=DAY,
                    data_dir=str(self.data_dir), onedrive_roots=[str(self.root / "OneDrive-Fictional")],
                    local_folder=str(self.root / "Local"), markers=list(self.plant["markers"].values())[:20])
        args.update(kw)
        return tc.send_to_client(tc.RealFs(), **args)

    def test_copy_is_byte_for_byte_and_listed_alone(self):
        got = self.real_send(local_sha256=hashlib.sha256(self.bytes).hexdigest())
        self.assertTrue(got.ok, got.message)
        self.assertEqual(sorted(p.name for p in self.client.iterdir()), [WANTED], "no .part file, no backup")
        self.assertEqual((self.client / WANTED).read_bytes(), self.bytes)
        self.assertEqual(hashlib.sha256((self.client / WANTED).read_bytes()).hexdigest(), got.sha256)
        self.assertEqual(sorted(got.log), ["at", "client_path", "file_name", "kind", "project", "sha256"])
        self.assertEqual(self.client_files_that_are_not_ours(), [])

    def client_files_that_are_not_ours(self):
        return [p for p in self.root.rglob("*") if p.is_file() and self.client not in p.parents]

    def test_the_copy_has_no_marker_and_no_outside_address(self):
        self.real_send()
        copy = (self.client / WANTED).read_bytes().decode("utf-8")
        self.assertEqual(publish.outside_addresses(copy), [])
        self.assertNotIn(str(self.client), copy)
        for key, marker in self.plant["markers"].items():
            for spelling in fx.spellings(marker) + [marker.split()[0]]:
                self.assertNotIn(spelling, copy, f"{key}: {spelling!r} is in the copy")
        for dropped in self.plant["dropped"]:
            self.assertNotIn(dropped, copy, dropped)
        self.assertEqual(tc.check_copy(copy.encode("utf-8"), folder=self.client,
                                       markers=[m for k, m in self.plant["markers"].items() if len(m) > 8][:20]), [])

    def test_a_second_publish_asks_and_then_numbers(self):
        self.real_send()
        asked = self.real_send(data=self.bytes + b"\n<!-- a later version -->")
        self.assertEqual(asked.action, "ask")
        self.assertEqual(sorted(p.name for p in self.client.iterdir()), [WANTED])
        numbered = self.real_send(data=self.bytes + b"\n<!-- a later version -->", choice="number")
        self.assertTrue(numbered.ok, numbered.message)
        self.assertEqual(sorted(p.name for p in self.client.iterdir()), sorted([WANTED, "PUB-report-2026-10-23 (2).html"]))
        same = self.real_send()
        self.assertEqual(same.action, "nothing_to_do")

    def test_a_missing_folder_leaves_the_disk_alone(self):
        gone = self.client.parent / "Gone"
        got = self.real_send(saved_folder=str(gone))
        self.assertEqual((got.ok, got.action), (False, "refused"))
        self.assertFalse(gone.exists())
        self.assertEqual(list(self.client.iterdir()), [])

    def test_a_real_link_into_the_data_folder_is_refused(self):
        link = self.client.parent / "Shortcut"
        link.symlink_to(self.data_dir, target_is_directory=True)
        got = self.real_send(saved_folder=str(link))
        self.assertEqual((got.ok, got.action), (False, "refused"))
        self.assertEqual(list(self.data_dir.iterdir()), [])

    def test_a_real_file_with_the_wanted_name_as_a_folder(self):
        (self.client / WANTED).mkdir()
        got = self.real_send()
        self.assertEqual((got.action, got.clash["can_overwrite"]), ("ask", False))
        self.assertEqual(list((self.client / WANTED).iterdir()), [])


class TheClientFolderIsHeldTo(unittest.TestCase):
    """#43 review: the folder that was checked is the folder written to, and what is in it is only ever read as an ordinary file.
    Real folders, links and a pipe in a temporary folder."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.onedrive = self.root / "OneDrive-Fictional"
        self.client = self.onedrive / "Client reports" / "Harbour Bridge"
        self.client.mkdir(parents=True)
        self.data_dir = self.root / "clark-data"
        self.data_dir.mkdir()
        (self.data_dir / "clark.db").write_bytes(b"the database")
        self.fs = tc.RealFs()

    def kw(self, **extra):
        args = dict(data_dir=str(self.data_dir), onedrive_roots=[str(self.onedrive)], local_folder=str(self.root / "Local"))
        args.update(extra)
        return args

    def send(self, **extra):
        return tc.send_to_client(self.fs, saved_folder=str(self.client), data=BODY, project="PUB", at=DAY, week_ending=WEEK,
                                 today=DAY, markers=(), **self.kw(**extra))

    def checked(self):
        pre = tc.checked_folder(self.fs, str(self.client), **self.kw())
        self.assertTrue(pre["ok"], pre)
        return pre

    def swap_for_link_to(self, target):
        self.client.rmdir()
        self.client.symlink_to(target, target_is_directory=True)

    def test_a_folder_swapped_for_a_link_after_the_check_is_not_written_to(self):
        pre = self.checked()
        guard = {"data_dir": str(self.data_dir), "backups_dir": None, "identity": pre["identity"]}
        self.swap_for_link_to(self.data_dir)
        got = tc.copy_to_client(self.fs, self.client, WANTED, BODY, project="PUB", at=DAY, markers=(), guard=guard)
        self.assertEqual((got.ok, got.action, got.message), (False, "refused", tc.MESSAGES["folder_changed"]))
        self.assertEqual(sorted(p.name for p in self.data_dir.iterdir()), ["clark.db"])

    def test_the_real_path_of_a_link_is_what_is_planned(self):
        other = self.onedrive / "Elsewhere"
        other.mkdir()
        self.client.rmdir()
        self.client.symlink_to(other, target_is_directory=True)
        kind, plan = tc.plan_client_copy(self.fs, saved_folder=str(self.client), data=BODY, project="PUB", today=DAY,
                                         week_ending=WEEK, **self.kw())
        self.assertEqual((kind, plan["folder"]), ("copy", other))

    def test_a_folder_replaced_by_another_real_folder_after_the_check_is_refused(self):
        pre = self.checked()
        guard = {"data_dir": str(self.data_dir), "backups_dir": None, "identity": pre["identity"]}
        moved = self.client.with_name("Moved")
        self.client.rename(moved)
        self.client.mkdir()                        # a different folder under the same name (another inode)
        got = tc.copy_to_client(self.fs, self.client, WANTED, BODY, project="PUB", at=DAY, markers=(), guard=guard)
        self.assertEqual((got.ok, got.message), (False, tc.MESSAGES["folder_changed"]))
        self.assertEqual(list(self.client.iterdir()) + list(moved.iterdir()), [])

    def test_a_folder_removed_after_the_check_fails_safe(self):
        pre = self.checked()
        guard = {"data_dir": str(self.data_dir), "backups_dir": None, "identity": pre["identity"]}
        self.client.rmdir()
        got = tc.copy_to_client(self.fs, self.client, WANTED, BODY, project="PUB", at=DAY, markers=(), guard=guard)
        self.assertEqual((got.ok, got.action in ("failed", "refused")), (False, True))
        self.assertFalse(self.client.exists())

    def test_a_link_to_the_data_folder_is_refused_at_the_check(self):
        self.swap_for_link_to(self.data_dir)
        got = self.send()
        self.assertEqual((got.ok, got.action), (False, "refused"))
        self.assertEqual(sorted(p.name for p in self.data_dir.iterdir()), ["clark.db"])

    # (a) the clean-up of stale temporary files
    def test_only_a_stale_temporary_file_of_the_exact_shape_is_removed(self):
        import os
        old = 1_000_000_000
        keep, remove = [], []
        good = self.client / f".{WANTED}.123.0a1b2c3d.part"
        good.write_bytes(b"half")
        remove.append(good)
        for name in (".notes.part", f".{WANTED}.123.0g1b2c3d.part", f".{WANTED}.12x.0a1b2c3d.part", f"{WANTED}.123.0a1b2c3d.part",
                     "." + "x" * 205 + ".html.1.0a1b2c3d.part"):
            (self.client / name).write_bytes(b"other")
            keep.append(self.client / name)
        (self.client / f".b.html.5.0a1b2c3d.part").symlink_to(self.data_dir / "clark.db")
        keep.append(self.client / ".b.html.5.0a1b2c3d.part")
        (self.client / f".c.html.5.0a1b2c3d.part").mkdir()
        keep.append(self.client / ".c.html.5.0a1b2c3d.part")
        big = self.client / ".d.html.5.0a1b2c3d.part"
        with open(big, "wb") as f:
            f.truncate(publish.MAX_BYTES + 1)
        keep.append(big)
        young = self.client / ".e.html.5.0a1b2c3d.part"
        young.write_bytes(b"new")
        keep.append(young)
        for p in remove + keep:
            if not p.is_symlink() and p is not young:
                os.utime(p, (old, old))
        got = self.send()
        self.assertTrue(got.ok, got.message)
        for p in remove:
            self.assertFalse(p.exists(), p)
        for p in keep:
            self.assertTrue(os.path.lexists(p), p)
        self.assertEqual((self.data_dir / "clark.db").read_bytes(), b"the database")

    # (b) reading what is at the destination
    def test_a_link_and_a_pipe_are_never_read(self):
        import os
        target = self.root / "outside.html"
        target.write_bytes(BODY)
        link = self.client / WANTED
        link.symlink_to(target)
        with self.assertRaises(OSError):
            self.fs.read_bytes(link)
        link.unlink()
        os.mkfifo(link)
        with self.assertRaises(OSError):
            self.fs.read_bytes(link)

    def test_a_link_with_the_same_bytes_is_not_the_same_file(self):
        target = self.root / "outside.html"
        target.write_bytes(BODY)
        (self.client / WANTED).symlink_to(target)
        got = self.send()
        self.assertEqual((got.ok, got.action), (False, "ask"))
        self.assertFalse(got.clash["can_overwrite"])

    def test_a_pipe_at_the_destination_is_asked_about_not_read(self):
        import os
        os.mkfifo(self.client / WANTED)
        got = self.send()
        self.assertEqual((got.ok, got.action), (False, "ask"))

    def test_same_content_reads_no_more_than_the_size_limit(self):
        seen = []

        class Spy(tc.RealFs):
            def read_bytes(self, path, limit=None):
                seen.append(limit)
                return super().read_bytes(path, limit)
        (self.client / WANTED).write_bytes(b"x" * (publish.MAX_BYTES + 1))
        self.fs = Spy()
        got = self.send()
        self.assertEqual((got.action, set(seen)), ("ask", {publish.MAX_BYTES + 1}))

    # (c) Overwrite on a link
    def test_overwrite_refuses_a_link_and_leaves_what_it_points_at(self):
        target = self.root / "outside.html"
        target.write_bytes(b"not the client's")
        (self.client / WANTED).symlink_to(target)
        got = self.send(choice="overwrite", confirmed=True)
        self.assertEqual((got.ok, got.action, got.message), (False, "refused", tc.MESSAGES["not_plain_file"].format(name=WANTED)))
        self.assertEqual(target.read_bytes(), b"not the client's")
        self.assertTrue((self.client / WANTED).is_symlink())

    def test_the_copy_step_itself_refuses_to_replace_a_link(self):
        target = self.root / "outside.html"
        target.write_bytes(b"not the client's")
        (self.client / WANTED).symlink_to(target)
        got = tc.copy_to_client(self.fs, self.client, WANTED, BODY, project="PUB", at=DAY, markers=(), replaces=True, confirmed=True)
        self.assertEqual((got.ok, got.action), (False, "refused"))
        self.assertEqual(target.read_bytes(), b"not the client's")

    # (d) a name that ends with a dot
    def test_a_rename_ending_with_a_dot_is_refused(self):
        for typed in ("a.html.", "a.", "report..", "a.html. "):
            with self.subTest(typed):
                got = tc.resolve_clash(WANTED, [WANTED], "rename", typed)
                self.assertEqual((got["action"], got["reason"]), ("refuse", "name_ends_badly"))
                self.assertEqual(got["message"], tc.MESSAGES["name_ends_badly"])
        self.assertEqual(tc.resolve_clash(WANTED, [WANTED], "rename", "a.html")["name"], "a.html")


class PlainWords(unittest.TestCase):
    """Nothing a person reads from the client copy is the system's own text, a location or request talk (#43)."""
    RAW = r"(?i)permission denied|errno|oserror|no such file|no reason|refused it|/Users|private key|\btag\b|attribute|stylesheet"

    def test_a_raw_os_error_is_a_fixed_sentence_whichever_step_fails(self):
        raw = OSError(13, "Permission denied")
        self.assertEqual(tc._reason(raw), "clark could not write to the client folder. Check you can edit it.")
        self.assertEqual(tc._reason(raw, "read"), "clark could not read the client folder. Check you can open it.")

        class Unreadable(FakeFs):
            def listdir(self, path):
                raise raw
        got = send(Unreadable(folders=[CLIENT, DATA_DIR, LOCAL]))
        self.assertEqual(got.message, "clark could not read the client folder. Check you can open it. Nothing was published.")

    def test_a_failed_put_back_says_so_in_words_without_the_system_text(self):
        class Refuses(FakeFs):
            def write_file(self, path, data, replaces):
                if data == b"older":
                    raise PermissionError(13, "Permission denied")
                return super().write_file(path, data, replaces)
        fs = Refuses(folders=[CLIENT, DATA_DIR, LOCAL], files={f"{CLIENT}/{WANTED}": b"older"}, corrupt_read=1)
        got = send(fs, choice="overwrite", confirmed=True)
        self.assertIn("the previous file could not be put back. clark could not write to the client folder. Check you can edit it.",
                      got.message)
        self.assertEqual(got.message.count("clark could not"), 1, "only one sentence starts with the product's name")
        self.assertNotRegex(got.message, self.RAW)

    def test_what_is_held_back_is_in_plain_words(self):
        for body, words in ((BODY.replace(b"<p>", b'<p><img src="https://x.invalid/a.png">'), "a link to a place outside the file"),
                            (BODY.replace(b"<body>", b'<body id="clark-boot">'), "clark's own working data"),
                            (b"\xff\xfe not text", "a file clark did not write as text"),
                            (BODY.replace(b"Harbour", CLIENT.encode("utf-8")), "the location of the client folder")):
            with self.subTest(words):
                got = send(client_fs(), data=body)
                self.assertIn(f"({words}", got.message)
                self.assertNotRegex(got.message, self.RAW)

    def test_the_publish_scans_own_labels_are_all_translated(self):
        for label in ("a <link> tag", "a script loaded by address", "an attribute that names an outside address", "a page refresh",
                      "a stylesheet that imports another", "a stylesheet address that isn't embedded data", "a Google Fonts address",
                      "a link or source that is an outside address"):
            self.assertIn(label, tc.HELD_WORDS)
            self.assertNotRegex(tc.held_words([label]), r"(?i)\btag\b|attribute|stylesheet|address|<")

    def test_every_label_the_scan_can_give_has_a_plain_wording(self):
        """#112: the labels come from publish itself, so one added or renamed there with no translation here fails."""
        from clark import publish
        labels = {publish.FOREIGN_FOUND, publish.TOO_BIG_FOUND, publish.IMPORT_FOUND, publish.ADDRESS_FOUND,
                  "a page or program inside the page", "a base address"}
        for label in sorted(labels):
            self.assertIn(label, tc.HELD_WORDS, label)
        jargon = r"(?i)\bsvg\b|\bmath\b|cdata|<|\btag\b|attribute|\bcss\b|\burl\b|\bhtml\b"
        for label, words in tc.HELD_WORDS.items():
            self.assertNotEqual(words, label, label)
            self.assertNotRegex(words, jargon, label)
            self.assertFalse(words.lower().startswith("clark"), label)
        for label in labels:
            self.assertNotRegex(tc.held_words([label]), jargon)
        with self.assertRaises(publish.PublishError) as caught:
            publish.check_brand("<svg></svg>")
        self.assertNotRegex(str(caught.exception), r"(?i)\bsvg\b|\bmath\b|cdata")

    def test_too_deep_and_bad_path_and_the_request_messages_have_no_location_or_request_talk(self):
        self.assertNotIn("{", tc.MESSAGES["too_deep"])
        for key in ("too_deep", "bad_path", "unknown_choice", "to_client_flag", "confirmed_flag", "names_a_folder", "unknown_key",
                    "overwrite_unconfirmed"):
            self.assertNotRegex(tc.MESSAGES[key], r"(?i)\bpath\b|\brequest\b|true or false", key)
        self.assertEqual(tc.MESSAGES["unknown_choice"], "That choice isn't one clark offers. Choose one of: Add a number, Rename it, "
                                                         "Overwrite the existing file, Cancel.")


class Tripwire(unittest.TestCase):
    """Only this module writes into a client folder, and only through one place. Read from the syntax trees of src/clark."""
    WRITERS = {"RealFs", "copy_to_client", "send_to_client"}
    ALLOWED_OUTSIDE = {"publish_flow.py"}      # modules that may use them: the publish route's logic (server.py only hands requests to it)
    DISK_CALLS = {"write_file", "replace_file", "remove", "unlink", "rename", "write_text", "write_bytes", "mkdir", "makedirs",
                  "rmdir", "copyfile", "copy2", "move", "symlink", "touch", "write_file_unless_exists", "move_unless_exists", "link"}

    def trees(self):
        for path in sorted((SRC / "clark").rglob("*.py")):
            yield path, ast.parse(path.read_text(encoding="utf-8"))

    def test_no_other_module_reaches_a_client_folder_writer(self):
        found = []
        for path, tree in self.trees():
            if path.name == "to_client.py" or path.name in self.ALLOWED_OUTSIDE:
                continue
            found += [f"{path.name}:{line}: {names}" for line, names in self.uses_writer(tree)]
        self.assertEqual(found, [])

    def uses_writer(self, tree):
        """(line, names) for every use of a client-folder writer: a bare name, an attribute, or an import."""
        out = []
        for node in ast.walk(tree):
            names = set()
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                names.update(a.name for a in node.names)
            if names & self.WRITERS:
                out.append((node.lineno, sorted(names & self.WRITERS)))
        return out

    def test_the_writer_names_are_still_in_to_client_py(self):
        tree = ast.parse((SRC / "clark" / "to_client.py").read_text(encoding="utf-8"))
        defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
        self.assertTrue(self.WRITERS <= defined, "the tripwire is watching names that exist")

    def test_to_client_py_writes_in_one_place_each(self):
        tree = ast.parse((SRC / "clark" / "to_client.py").read_text(encoding="utf-8"))
        parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
        found = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and (func.attr in self.DISK_CALLS or (isinstance(func.value, ast.Name) and func.value.id in ("os", "shutil"))):
                what = func.attr
            elif isinstance(func, ast.Name) and func.id == "open":
                what = "open"
                self.assertEqual(node.args[1].value, "rb", "the one open() reads")
            else:
                continue
            up = node
            while not isinstance(up, ast.FunctionDef):
                up = parents[up]
            owner = parents[up]
            found.add((owner.name if isinstance(owner, ast.ClassDef) else "", up.name, what))
        self.assertEqual(found, {("RealFs", "write_file", "write_file"),       # the two writes: platform.write_file (Overwrite, restore)
                                 ("RealFs", "write_file", "write_file_unless_exists"),     # and the link into place for a new name
                                 ("RealFs", "remove", "unlink"),               # taking back a copy this publish made
                                 ("RealFs", "writable", "access"), ("RealFs", "listdir", "scandir"),   # reads
                                 ("RealFs", "read_bytes", "open"),
                                 ("", "copy_to_client", "write_file"),         # through the injected fs
                                 ("", "_put_back", "write_file"),              # writing the old bytes back after a failed Overwrite
                                 ("", "_remove", "remove")})

    def test_to_client_py_has_no_network_program_or_database(self):
        tree = ast.parse((SRC / "clark" / "to_client.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertFalse(imported & {"socket", "urllib", "http", "ssl", "smtplib", "subprocess", "ctypes", "sqlite3", "requests"}, imported)
        source = (SRC / "clark" / "to_client.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"(?i)microsoft|graph\.|oauth|sharepoint\.com")

    def test_the_tripwire_sees_a_planted_caller(self):
        for source in ("from clark.to_client import copy_to_client\n", "to_client.send_to_client(fs)\n",
                       "x = clark.to_client.RealFs()\n", "from clark import to_client as t\nt.copy_to_client(1)\n"):
            self.assertTrue(self.uses_writer(ast.parse(source)), source)
        self.assertEqual(self.uses_writer(ast.parse("from clark.to_client import validate_request\n")), [])


class MarkersAreFoundInOnePass(unittest.TestCase):
    """#43: naming the left-out items reads the file once, then looks each marker up."""

    def file_and_markers(self, n):
        markers = tc_markers(n)
        body = ("<html><body>" + " ".join("<p>filler line %d</p>" % i for i in range(300)) + "".join(
            "<p>%s</p>" % m for m in markers[::7]) + "</body></html>").encode("utf-8")
        return body, markers

    def test_the_results_are_the_same_as_checking_each_marker_alone(self):
        body, markers = self.file_and_markers(60)
        markers += ["Internal <note> & \"quoted\" text", "NOT IN THE FILE AT ALL"]
        body += "<p>Internal &lt;note&gt; &amp; &quot;quoted&quot; text</p>".encode("utf-8")
        alone = [m for m in markers if tc.check_copy(body, markers=[m])]
        self.assertEqual(tc.markers_found(body, markers), alone)
        self.assertIn("Internal <note> & \"quoted\" text", alone)
        self.assertNotIn("NOT IN THE FILE AT ALL", alone)

    def test_the_file_is_folded_once_whatever_the_number_of_markers(self):
        body, markers = self.file_and_markers(3000)
        calls = []
        real = tc._key
        def counting(text):
            calls.append(len(text))
            return real(text)
        with mock.patch.object(tc, "_key", counting):
            tc.markers_found(body, markers)
        self.assertEqual(sum(1 for n in calls if n > 10000), 1, "the whole file was folded more than once")

    def test_which_items_never_runs_the_whole_check_again(self):
        from clark import publish_flow
        body, markers = self.file_and_markers(3000)
        markers = publish_flow.Markers(markers)
        markers.where = {m: "ITEM-%d" % i for i, m in enumerate(markers)}
        with mock.patch.object(tc, "check_copy", side_effect=AssertionError("check_copy called")):
            said = publish_flow.Publisher.which_items(None, body, markers)
        self.assertEqual(said, publish_flow.MESSAGES["look_at"].format(items=", ".join("ITEM-%d" % i for i in range(0, 70, 7))))


def tc_markers(n):
    return ["left out note number %d of the project" % i for i in range(n)]


if __name__ == "__main__":
    unittest.main()
