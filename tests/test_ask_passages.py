"""#47d: passages from the folders a person saved (src/clark/ask_passages.py, wired in ask_service.py).

Run: python3 dev/run_tests.py test_ask_passages
Every file is made in the test from made-up text. What is asserted: only the open project's own saved folders are read; a file
outside them, a link out of them, a secret file (.env, .pem), a file with two names and a hostile Word file never reach a
passage; a path swapped between listing and reading is refused when it is opened; PDF is a counted "not supported yet"; the 40,000
character budget holds; the reply says how many files were left out for safety; and the provider is sent nothing but the
published data and passages from the saved folders.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import test_ask_route as tr
import test_docx_read as tdx
from clark import ask, ask_passages, reach, store as st

MACRO = {"word/vbaProject.bin": b"\0\1\2"}


class Folders(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.data = self.d / "data"
        self.box = self.d / "saved"
        self.other = self.d / "elsewhere"
        for p in (self.data, self.box, self.other):
            p.mkdir()

    def put(self, folder, name, text, binary=False):
        p = Path(folder) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text if binary else text.encode())
        return p

    def run_it(self, question="plan", folders=None, **kw):
        return ask_passages.folder_data([str(f) for f in (folders or [self.box])], self.data, question, **kw)

    def text_of(self, got):
        return "\n".join(p.text for p in got.passages)

    def labels(self, got):
        return [p.label for p in got.passages]


class WhatIsRead(Folders):
    def test_text_and_word_files_become_labelled_passages(self):
        self.put(self.box, "notes/plan.md", "ZQ-TEXT the plan is on track")
        self.put(self.box, "weekly.docx", tdx.docx(tdx.P("ZQ-WORD the budget is agreed")), binary=True)
        got = self.run_it()
        self.assertIn("ZQ-TEXT", self.text_of(got))
        self.assertIn("ZQ-WORD", self.text_of(got))
        self.assertEqual(sorted(self.labels(got)), ["saved/notes/plan.md", "saved/weekly.docx"])
        for label in self.labels(got):
            self.assertFalse(label.startswith("/"), "a label is a name inside a folder, never a path")
            self.assertNotIn(str(self.d), label)
        self.assertEqual(got.safety, 0)

    def test_a_file_outside_the_saved_folder_is_never_read(self):
        self.put(self.other, "outside.txt", "ZQ-OUTSIDE")
        self.put(self.box, "in.txt", "ZQ-IN")
        got = self.run_it()
        self.assertNotIn("ZQ-OUTSIDE", self.text_of(got))
        self.assertIn("ZQ-IN", self.text_of(got))

    def test_a_link_out_of_the_folder_is_not_followed(self):
        target = self.put(self.other, "secret.txt", "ZQ-LINKED")
        (self.box / "file-link.txt").symlink_to(target)
        (self.box / "dir-link").symlink_to(self.other, target_is_directory=True)
        got = self.run_it()
        self.assertNotIn("ZQ-LINKED", self.text_of(got))
        self.assertGreaterEqual(got.safety, 2)

    def test_secret_files_are_left_out_and_counted(self):
        self.put(self.box, ".env", "ZQ-ENV=1")
        self.put(self.box, "prod.env", "ZQ-ENV2=1")
        self.put(self.box, "tls/server.pem", "ZQ-PEM")
        self.put(self.box, "ok.txt", "ZQ-OK")
        got = self.run_it()
        self.assertNotIn("ZQ-ENV", self.text_of(got))
        self.assertNotIn("ZQ-PEM", self.text_of(got))
        self.assertIn("ZQ-OK", self.text_of(got))
        self.assertGreaterEqual(got.safety, 3)

    def test_noise_and_lock_files_are_ignored_without_a_count(self):
        self.put(self.box, ".DS_Store", "ZQ-NOISE")
        self.put(self.box, "~$weekly.docx", "ZQ-LOCK")
        got = self.run_it()
        self.assertEqual((got.passages, got.safety), ((), 0))

    def test_a_file_with_two_names_is_left_out(self):
        a = self.put(self.box, "a.txt", "ZQ-HARD")
        os.link(a, self.box / "b.txt")
        got = self.run_it()
        self.assertNotIn("ZQ-HARD", self.text_of(got))
        self.assertGreaterEqual(got.safety, 2)

    def test_a_saved_folder_that_is_clarks_data_is_dropped(self):
        self.put(self.data, "clark.txt", "ZQ-DATA")
        got = self.run_it(folders=[self.data])
        self.assertEqual(got.passages, ())
        self.assertGreaterEqual(got.safety, 1)

    def test_a_hostile_word_file_is_refused_and_counted(self):
        self.put(self.box, "macro.docx", tdx.docx(tdx.P("ZQ-MACRO"), parts=MACRO), binary=True)
        self.put(self.box, "junk.docx", b"not a zip at all", binary=True)
        self.put(self.box, "fine.txt", "ZQ-FINE")
        got = self.run_it()
        self.assertNotIn("ZQ-MACRO", self.text_of(got))
        self.assertIn("ZQ-FINE", self.text_of(got))
        self.assertEqual(got.safety, 2)

    def test_pdf_is_counted_as_not_supported_and_never_opened(self):
        self.put(self.box, "scan.pdf", b"%PDF-1.4 ZQ-PDF", binary=True)
        self.put(self.box, "photo.png", b"\x89PNG", binary=True)
        real = reach.read_bytes
        opened = []
        with mock.patch.object(reach, "read_bytes", side_effect=lambda p, *a, **k: (opened.append(str(p)), real(p, *a, **k))[1]):
            got = self.run_it()
        self.assertEqual((got.pdf, got.other, got.passages), (1, 1, ()))
        self.assertEqual(opened, [], "neither is opened")

    def test_a_label_that_could_forge_a_line_is_left_out(self):
        self.put(self.box, "bad‮name.txt", "ZQ-BIDI")
        self.put(self.box, "good.txt", "ZQ-GOOD")
        got = self.run_it()
        self.assertNotIn("ZQ-BIDI", self.text_of(got))
        self.assertEqual(got.safety, 1)


class ReadAgain(Folders):
    """A listing is not an approval: the path is judged again when it is opened."""

    def swap_after_listing(self, victim, swap):
        real = reach.readable_files

        def listing(*a, **k):
            got = real(*a, **k)
            swap(victim)
            return got
        return mock.patch.object(reach, "readable_files", side_effect=listing)

    def test_a_file_swapped_for_a_link_after_listing_is_refused(self):
        target = self.put(self.other, "secret.txt", "ZQ-SWAPPED")
        victim = self.put(self.box, "doc.txt", "ZQ-ORIGINAL")

        def swap(p):
            p.unlink()
            p.symlink_to(target)
        with self.swap_after_listing(victim, swap):
            got = self.run_it()
        self.assertNotIn("ZQ-SWAPPED", self.text_of(got))
        self.assertNotIn("ZQ-ORIGINAL", self.text_of(got))
        self.assertEqual(got.safety, 1)

    def test_a_file_given_a_second_name_after_listing_is_refused(self):
        victim = self.put(self.box, "doc.txt", "ZQ-HARDSWAP")

        def swap(p):
            os.link(p, self.other / "copy.txt")
        with self.swap_after_listing(victim, swap):
            got = self.run_it()
        self.assertNotIn("ZQ-HARDSWAP", self.text_of(got))
        self.assertEqual(got.safety, 1)

    def test_a_file_removed_after_listing_is_counted_not_fatal(self):
        victim = self.put(self.box, "doc.txt", "ZQ-GONE")
        with self.swap_after_listing(victim, lambda p: p.unlink()):
            got = self.run_it()
        self.assertEqual((got.passages, got.safety), ((), 1))

    def test_a_folder_swapped_for_a_link_after_listing_is_refused(self):
        target = self.put(self.other, "secret.txt", "ZQ-DIRSWAP")
        sub = self.box / "sub"
        self.put(sub, "doc.txt", "ZQ-ORIGINAL")

        def swap(_p):
            shutil.rmtree(sub)
            sub.symlink_to(self.other, target_is_directory=True)
            self.put(self.other, "doc.txt", "ZQ-DIRSWAP")
        with self.swap_after_listing(sub, swap):
            got = self.run_it()
        self.assertNotIn("ZQ-DIRSWAP", self.text_of(got))
        self.assertTrue(target.exists())


class TheBudget(Folders):
    def test_the_budget_holds_and_the_rest_is_counted(self):
        for i in range(30):
            self.put(self.box, f"f{i:02d}.txt", ("word%d " % i) * 600)         # about 3,500 characters each
        got = self.run_it("word5")
        self.assertLessEqual(sum(len(p.text) for p in got.passages), ask.BUDGET)
        self.assertGreater(got.left_out, 0)
        self.assertIn("word5", self.text_of(got))

    def test_a_smaller_budget_is_kept(self):
        self.put(self.box, "a.txt", "alpha " * 600)
        got = self.run_it("alpha", budget=1500)
        self.assertLessEqual(sum(len(p.text) for p in got.passages), 1500)
        self.assertGreater(got.left_out, 0)

    def test_every_passage_fits_a_request(self):
        self.put(self.box, "long.txt", "x" * 50000)
        got = self.run_it("x")
        request = ask.build_request("x", got.passages)
        self.assertLessEqual(len(request.text), ask.MAX_REQUEST)


class OnTheRoute(tr.Base):
    def setUp(self):
        super().setUp()
        self.mine = Path(tempfile.mkdtemp(prefix="clark-mine-"))
        self.theirs = Path(tempfile.mkdtemp(prefix="clark-theirs-"))
        self.loose = Path(tempfile.mkdtemp(prefix="clark-loose-"))
        for p in (self.mine, self.theirs, self.loose):
            self.addCleanup(shutil.rmtree, p, True)
        (self.mine / "plan.txt").write_text(("ZQ-MINE the cutover is booked"), encoding="utf-8")
        (self.mine / ".env").write_text(("ZQ-ENVFILE=1"), encoding="utf-8")
        (self.theirs / "plan.txt").write_text(("ZQ-THEIRS other project folder"), encoding="utf-8")
        (self.loose / "plan.txt").write_text(("ZQ-LOOSE not saved anywhere"), encoding="utf-8")
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            s.create("source_folders", {"project": tr.CODE, "path": str(self.mine.resolve()), "sort_order": 1})
            s.create("source_folders", {"project": "OTH", "path": str(self.theirs.resolve()), "sort_order": 1})
        store.close()

    def test_only_the_open_projects_folder_and_the_published_data_are_sent(self):
        status, got = self.question("What is the cutover plan?")
        self.assertEqual(status, 200, got)
        (text,) = self.provider.sent
        self.assertIn("ZQ-MINE", text)
        for marker in ("ZQ-THEIRS", "ZQ-LOOSE", "ZQ-ENVFILE", "ZQ-OTHER-PROJECT"):
            self.assertNotIn(marker, text)
        self.assertNotIn(str(self.mine.resolve()), text, "no path")
        self.assertEqual(got["left_out_for_safety"], 1)
        self.assertTrue(any("left out for safety" in n for n in got["notes"]), got["notes"])

    def test_a_reply_can_cite_a_folder_passage(self):
        self.provider.reply = "Booked.\nCITE: P1"
        status, got = self.question("What is the cutover plan?")
        self.assertEqual(status, 200, got)
        labels = [s["label"] for s in got["sources"]]
        self.assertTrue(labels and all(not l.startswith("/") for l in labels), labels)

    def test_with_asking_off_no_folder_is_read(self):
        self.set_switch(False)
        with mock.patch.object(reach, "readable_files") as listing:
            status, got = self.question()
        self.assertEqual((status, got["code"]), (409, "asking_off"))
        listing.assert_not_called()
        self.assertEqual(self.provider.sent, [])

    def test_pdf_is_said_to_be_not_supported_yet(self):
        (self.mine / "scan.pdf").write_bytes(b"%PDF-1.4 ZQ-PDF")
        status, got = self.question("What is the cutover plan?")
        self.assertEqual(status, 200, got)
        self.assertNotIn("ZQ-PDF", self.provider.sent[0])
        self.assertTrue(any("PDF" in n and "not supported yet" in n for n in got["notes"]), got["notes"])


if __name__ == "__main__":
    unittest.main()
