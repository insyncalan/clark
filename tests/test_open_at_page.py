"""#943: open a saved folder's PDF at a page (src/clark/pdf_link.py, platform.open_pdf_at, POST /api/ask/open-source in ask_service.py).

Run: python3 dev/run_tests.py test_open_at_page
Nothing here starts a viewer: the opener is a stub that records its arguments, and platform's runner is a fake that records the
argument list. Every file is made in the test from made-up names. The page numbers inside passages come with #891; here the
structured `page` and `file` of a source exist and a page is None until then.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
from _real_server import real_server
from clark import ask, ask_passages, ask_service, pdf_link, platform as pl, reach, store as st

CODE = "PUB"


class FakeRun:
    def __init__(self, *codes):
        self.codes, self.calls = list(codes), []

    def __call__(self, args, **kw):
        self.calls.append(list(args))
        return mock.Mock(returncode=self.codes.pop(0) if self.codes else 0, stderr="")


class Tmp(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.box = self.d / "Saved Docs"
        self.box.mkdir()

    def pdf(self, name, folder=None):
        p = Path(folder or self.box) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"%PDF-1.4")
        return p


class TheAddress(Tmp):
    def test_a_page_is_a_fragment_and_the_name_is_percent_encoded(self):
        p = self.pdf("Plan #2 100% (v1)?.pdf")
        url = pdf_link.pdf_url(p, 7, [self.box])
        self.assertTrue(url.startswith("file:///"), url)
        self.assertTrue(url.endswith("Plan%20%232%20100%25%20%28v1%29%3F.pdf#page=7"), url)
        self.assertEqual(url.count("#"), 1)
        self.assertNotIn(" ", url)
        self.assertEqual(url.split("#")[0].count("%23"), 1)

    def test_no_page_has_no_fragment(self):
        self.assertNotIn("#page", pdf_link.pdf_url(self.pdf("a.pdf"), None, [self.box]))

    def test_bad_pages_are_refused(self):
        p = self.pdf("a.pdf")
        for page in (0, -1, True, "3", 2.0, 10 ** 9):
            with self.assertRaises(pdf_link.PdfLinkRefused, msg=repr(page)):
                pdf_link.pdf_url(p, page, [self.box])

    def test_not_a_pdf_a_link_or_outside_is_refused(self):
        txt = self.box / "a.txt"
        txt.write_text("x", encoding="utf-8")
        with self.assertRaises(pdf_link.PdfLinkRefused):
            pdf_link.pdf_url(txt, 1, [self.box])
        real = self.pdf("real.pdf")
        (self.box / "link.pdf").symlink_to(real)
        with self.assertRaises(pdf_link.PdfLinkRefused):
            pdf_link.pdf_url(self.box / "link.pdf", 1, [self.box])
        elsewhere = self.pdf("out.pdf", self.d / "elsewhere")
        (self.box / "dir").symlink_to(elsewhere.parent)
        with self.assertRaises(pdf_link.PdfLinkRefused):
            pdf_link.pdf_url(self.box / "dir" / "out.pdf", 1, [self.box])
        for bad in (elsewhere, self.box / ".." / "elsewhere" / "out.pdf", "", "a\x00.pdf"):
            with self.assertRaises(pdf_link.PdfLinkRefused, msg=repr(bad)):
                pdf_link.pdf_url(bad, 1, [self.box])
        with self.assertRaises(pdf_link.PdfLinkRefused):
            pdf_link.pdf_url(real, 1, [])
        sibling = self.pdf("x.pdf", self.d / "Saved Docs 2")
        with self.assertRaises(pdf_link.PdfLinkRefused):
            pdf_link.pdf_url(sibling, 1, [self.box])


class ThePlatformOpener(Tmp):
    def test_chrome_is_asked_with_an_argument_list(self):
        p = self.pdf("a b.pdf")
        url = pdf_link.pdf_url(p, 3, [self.box])
        run = FakeRun()
        pl.open_pdf_at(p, url, run=run, on=pl.MAC)
        self.assertEqual(run.calls, [["open", "-a", "Google " + "Chrome", url]])

    def test_without_chrome_the_file_is_opened_plainly(self):
        p = self.pdf("a.pdf")
        run = FakeRun(1, 0)
        pl.open_pdf_at(p, pdf_link.pdf_url(p, 3, [self.box]), run=run, on=pl.MAC)
        self.assertEqual(run.calls[1], ["open", str(p)])

    def test_every_start_has_a_wait_limit_and_a_stuck_one_is_said_plainly(self):
        """The opener must not wait for ever: both starts carry a timeout; a stuck Chrome falls back to the plain open; a stuck
        plain open is a PlatformError (the route says 409)."""
        p = self.pdf("a.pdf")
        url = pdf_link.pdf_url(p, 3, [self.box])
        seen = []

        def run(args, **kw):
            seen.append(kw.get("timeout"))
            return mock.Mock(returncode=0, stderr="")
        pl.open_pdf_at(p, url, run=run, on=pl.MAC)
        self.assertEqual(len(seen), 1)
        self.assertTrue(isinstance(seen[0], (int, float)) and 0 < seen[0] <= 60, seen)

        def stuck_first(args, **kw):
            seen.append(kw.get("timeout"))
            if len(seen) == 1:
                raise subprocess.TimeoutExpired(args, kw.get("timeout"))
            return mock.Mock(returncode=0, stderr="")
        del seen[:]
        pl.open_pdf_at(p, url, run=stuck_first, on=pl.MAC)
        self.assertEqual(len(seen), 2)
        self.assertTrue(all(isinstance(s, (int, float)) for s in seen), seen)

        def stuck(args, **kw):
            raise subprocess.TimeoutExpired(args, kw.get("timeout"))
        with self.assertRaises(pl.PlatformError):
            pl.open_pdf_at(p, url, run=stuck, on=pl.MAC)

    def test_windows_is_not_built_yet_and_a_bad_address_is_refused(self):
        p = self.pdf("a.pdf")
        with self.assertRaises(pl.NotBuiltYet):
            pl.open_pdf_at(p, "file:///x.pdf#page=1", run=FakeRun(), on=pl.WINDOWS)
        for bad in ("https://example.org/a.pdf", "file:///a.txt#page=1", "-a", "file:///a b.pdf"):
            run = FakeRun()
            with self.assertRaises(pl.PlatformError, msg=bad):
                pl.open_pdf_at(p, bad, run=run, on=pl.MAC)
            self.assertEqual(run.calls, [])


class TheSourceFields(Tmp):
    def test_a_folder_passage_carries_its_file_and_no_page(self):
        (self.box / "notes.txt").write_text("the cutover is booked\n" * 3, encoding="utf-8")
        with mock.patch.object(reach.platform, "system", return_value=reach.platform.MAC):
            got = ask_passages.folder_data([str(self.box)], self.d / "data", "cutover", home=self.d)
        self.assertTrue(got.passages)
        for p in got.passages:
            self.assertEqual(p.file, "Saved Docs/notes.txt")
            self.assertIsNone(p.page)
        self.assertIsNone(ask_service.page_of(ask.Passage("x", "y")))
        self.assertIsNone(ask_service.file_of(ask.Passage("x", "y")))
        self.assertEqual(ask_service.page_of(ask.Passage("x", "y", page=4)), 4)
        self.assertIsNone(ask_service.page_of(ask.Passage("x", "y", page=True)))


class OnTheRoute(Tmp):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(reach.platform, "system", return_value=reach.platform.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        (self.d / "data").mkdir()
        self.db = plant.build_db(self.d / "data" / "clark.db")
        self.opened = []
        self.service = ask_service.AskService(self.db, ask.StubProvider(reply="x"), [], home=self.d,
                                              open_pdf=lambda path, url: self.opened.append((str(path), url)))
        self.s = real_server(self.db, lambda code: None)
        self.s.httpd.ask = self.service
        self.addCleanup(self.s.close)
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            s.create("source_folders", {"project": CODE, "path": str(self.box), "sort_order": 1})
        store.close()

    def set_switch(self, on):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                s.update("app_settings", "1", {"ask_enabled": on})
        finally:
            store.close()

    def post(self, **body):
        import json
        status, _, raw = self.s.api("POST", "/api/ask/open-source", json.dumps(body).encode())
        return status, json.loads(raw)

    def test_a_saved_pdf_opens_at_its_page_through_the_opener_only(self):
        p = self.pdf("sub/Plan #1.pdf")
        status, got = self.post(project=CODE, file="Saved Docs/sub/Plan #1.pdf", page=5)
        self.assertEqual((status, got), (200, {"ok": True}))
        self.assertEqual(self.opened, [(str(p), pdf_link.pdf_url(p, 5, [self.box]))])
        self.assertTrue(self.opened[0][1].endswith("Plan%20%231.pdf#page=5"))
        self.assertEqual(self.post(project=CODE, file="Saved Docs/sub/Plan #1.pdf", page=None)[0], 200)
        self.assertNotIn("#page", self.opened[1][1])

    def test_everything_hostile_is_refused_and_nothing_is_opened(self):
        self.pdf("ok.pdf")
        (self.box / "t.txt").write_text("x", encoding="utf-8")
        out = self.pdf("out.pdf", self.d / "elsewhere")
        (self.box / "link.pdf").symlink_to(out)
        (self.box / "dir").symlink_to(out.parent)
        for name in ("Saved Docs/t.txt", "Saved Docs/link.pdf", "Saved Docs/dir/out.pdf", "Saved Docs/../elsewhere/out.pdf",
                     "Saved Docs/nope.pdf", "Elsewhere/out.pdf", str(out), "/etc/passwd", "ok.pdf", "Saved Docs//ok.pdf", "Saved Docs/./ok.pdf",
                     "Saved Docs/ok.pdf\x00.txt", "Saved Docs\\ok.pdf", ""):
            status, got = self.post(project=CODE, file=name, page=1)
            self.assertIn(status, (400, 409), name)
            self.assertFalse(got["ok"], name)
        self.assertEqual(self.opened, [])

    def test_bad_bodies_and_pages_are_refused(self):
        self.pdf("ok.pdf")
        for body in ({"project": CODE, "file": "Saved Docs/ok.pdf"}, {"project": CODE, "file": "Saved Docs/ok.pdf", "page": "2"},
                     {"project": CODE, "file": "Saved Docs/ok.pdf", "page": True}, {"project": CODE, "file": 3, "page": 1},
                     {"project": CODE, "file": "Saved Docs/ok.pdf", "page": 1, "extra": 1}):
            self.assertEqual(self.post(**body)[0], 400, body)
        self.assertEqual(self.post(project=CODE, file="Saved Docs/ok.pdf", page=0)[0], 409)
        self.assertEqual(self.post(project="lower", file="Saved Docs/ok.pdf", page=1)[0], 400)
        self.assertEqual(self.post(project="ZZZ", file="Saved Docs/ok.pdf", page=1)[0], 404)
        self.assertEqual(self.opened, [])

    def test_another_projects_folder_is_not_reached(self):
        other = self.d / "Theirs"
        self.pdf("t.pdf", other)
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            s.create("projects", {"code": "OTH", "name": "Other", "current_state": "x"})
            s.create("source_folders", {"project": "OTH", "path": str(other), "sort_order": 1})
        store.close()
        self.assertEqual(self.post(project=CODE, file="Theirs/t.pdf", page=1)[0], 409)
        self.assertEqual(self.post(project="OTH", file="Theirs/t.pdf", page=1)[0], 200)

    def test_a_viewer_that_fails_is_said_plainly(self):
        self.pdf("ok.pdf")
        def fail(path, url):
            raise pl.PlatformError("ok.pdf could not be opened")
        self.service.open_pdf = fail
        status, got = self.post(project=CODE, file="Saved Docs/ok.pdf", page=1)
        self.assertEqual((status, got["ok"], got["message"], got["code"]), (409, False, ask_service.MESSAGES["file_unavailable"], "file_unavailable"))
        self.assertEqual(got["message"], "That file can't be opened from here.")

    def test_an_opener_that_cannot_start_is_a_409_not_a_500(self):
        self.pdf("ok.pdf")
        def fail(path, url):
            raise FileNotFoundError(2, "No such file or directory: 'open'")
        self.service.open_pdf = fail
        status, got = self.post(project=CODE, file="Saved Docs/ok.pdf", page=1)
        self.assertEqual((status, got["code"], got["message"]), (409, "file_unavailable", "That file can't be opened from here."))

    def test_asking_off_refuses_before_anything_is_looked_at(self):
        self.pdf("ok.pdf")
        self.set_switch(False)
        for body in ({"project": CODE, "file": "Saved Docs/ok.pdf", "page": 1}, {"project": "ZZZ", "file": "Saved Docs/ok.pdf", "page": 1}):
            status, got = self.post(**body)
            self.assertEqual((status, got["code"]), (409, "asking_off"), body)
        self.assertEqual(self.opened, [])
        self.set_switch(True)
        self.assertEqual(self.post(project=CODE, file="Saved Docs/ok.pdf", page=1)[0], 200)

    def test_a_pdf_by_name_that_is_not_a_pdf_inside_is_refused(self):
        (self.box / "fake.pdf").write_bytes(b"MZ not a pdf at all")
        (self.box / "short.pdf").write_bytes(b"%PDF")
        (self.box / "empty.pdf").write_bytes(b"")
        for name in ("fake", "short", "empty"):
            status, got = self.post(project=CODE, file=f"Saved Docs/{name}.pdf", page=1)
            self.assertEqual((status, got["code"]), (409, "file_unavailable"), name)
        self.assertEqual(self.opened, [])
        (self.box / "real.pdf").write_bytes(b"%PDF-1.7\nrest")
        self.assertEqual(self.post(project=CODE, file="Saved Docs/real.pdf", page=1)[0], 200)

    def test_the_start_is_read_through_the_reach_check(self):
        """The five bytes come from reach.read_bytes (not a bare open), so a place clark keeps closed is not even read."""
        p = self.pdf("ok.pdf")
        calls = []
        real = reach.read_bytes

        def spy(path, folders, data, limit, home_dir=None):
            calls.append((str(path), limit))
            return real(path, folders, data, limit, home_dir)
        with mock.patch.object(reach, "read_bytes", spy):
            self.assertEqual(self.post(project=CODE, file="Saved Docs/ok.pdf", page=1)[0], 200)
        self.assertEqual(calls, [(str(p), 5)])


if __name__ == "__main__":
    unittest.main()
