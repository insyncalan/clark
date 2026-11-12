"""Item 1100, guarded part (server.py): the brand review and any Mac-only step no route caught say the needs-the-Mac sentence
(platform.needs_mac_words) in Docker, with a 409 and the code needs_mac, never the generic server fault.

Run: python3 dev/run_tests.py test_docker_words_guarded
Real server and real BrandLibrary; the only thing faked is that this is a Docker container on Linux. Nothing is opened or run.
"""
import sys
import unittest
from unittest import mock

from _brand_rig import make_dirs
from test_brand_routes import Rig

from clark import platform as pl, server as sv

WORDS = "This needs clark to run on the Mac itself; start it from Terminal: bash clark.command"


class Base(unittest.TestCase):
    def setUp(self):
        for patch in (mock.patch.object(sys, "platform", "linux"), mock.patch.object(pl, "container_mode", return_value=True)):
            patch.start()
            self.addCleanup(patch.stop)
        self.root, self.data, self.scratch = make_dirs(self)
        self.rig = Rig(self, library=False)
        self.rig.httpd.brands = sv.BrandLibrary(self.root, self.data)         # the real dialog and Downloads calls, as shipped

    def said(self, status_got):
        status, got = status_got
        self.assertEqual((status, got["ok"], got["code"], got["message"]), (409, False, "needs_mac", WORDS), got)
        for bad in ("NotBuiltYet", "PlatformError", "server_error"):
            self.assertNotIn(bad, repr(got))


class Brand(Base):
    def test_review_the_brand_in_downloads(self):
        self.said(self.rig.call("POST", "/api/brands/review", {"from": "downloads"}))

    def test_choose_a_brand_zip(self):
        self.said(self.rig.call("POST", "/api/brands/review", {"from": "file"}))


class Uncaught(Base):
    def test_a_route_that_lets_the_refusal_out_gets_the_same_words(self):
        class Service:
            def connect(self, body):
                return pl.choose_folder("x")                  # the real refusal, from the real platform call
        self.rig.httpd.ai_connect = Service()
        self.said(self.rig.call("POST", "/api/providers/connect", {"provider": "claude"}))

    def test_a_refusal_carrying_a_path_says_the_plain_words_not_its_own_text(self):
        leaky = "Open dialog failed at /Users/someone/Library/Secret Folder/clark.db"
        class Service:
            def connect(self, body):
                raise pl.NotBuiltYet(leaky)
        self.rig.httpd.ai_connect = Service()
        got = self.rig.call("POST", "/api/providers/connect", {"provider": "claude"})
        self.said(got)
        self.assertNotIn("Secret", repr(got))
        lib = self.rig.httpd.brands
        def boom(*_a, **_k):
            raise pl.NotBuiltYet(leaky)
        lib.choose = boom
        got = self.rig.call("POST", "/api/brands/review", {"from": "file"})
        self.said(got)
        self.assertNotIn("Secret", repr(got))

    def test_another_fault_is_still_the_generic_500(self):
        class Service:
            def connect(self, body):
                raise ValueError("boom")
        self.rig.httpd.ai_connect = Service()
        status, got = self.rig.call("POST", "/api/providers/connect", {"provider": "claude"})
        self.assertEqual((status, got["code"]), (500, "server_error"))

    def test_the_needs_mac_fault_is_found_by_its_class_name_with_no_import_in_the_except_clause(self):
        # server.py may not import clark at its top (the updater test forbids it), and an except clause that imports its class
        # lazily would raise the import error in place of the one being handled; so the class is matched by name.
        src = open(sv.__file__, encoding="utf-8").read()
        self.assertNotIn("from clark.platform import NotBuiltYet", src)
        self.assertNotIn('except importlib.import_module', src)
        self.assertEqual(src.count('type(e).__name__ != "NotBuiltYet"') + src.count('type(e).__name__ == "NotBuiltYet"'), 2)
        self.assertEqual(pl.NotBuiltYet.__name__, "NotBuiltYet")


if __name__ == "__main__":
    unittest.main()


class NotInDocker(unittest.TestCase):
    """Item 1100 follow-up: outside Docker a refused step never tells the person to start from the Mac's Terminal."""
    def setUp(self):
        for patch in (mock.patch.object(sys, "platform", "win32"), mock.patch.object(pl, "container_mode", return_value=False)):
            patch.start()
            self.addCleanup(patch.stop)
        self.root, self.data, self.scratch = make_dirs(self)
        self.rig = Rig(self, library=False)

    def test_a_not_built_refusal_outside_docker_says_the_plain_line(self):
        class Service:
            def connect(self, body):
                raise pl.NotBuiltYet("Open dialog on Windows is not built yet: clark runs on macOS for now")
        self.rig.httpd.ai_connect = Service()
        status, got = self.rig.call("POST", "/api/providers/connect", {"provider": "claude"})
        self.assertEqual((status, got["message"]), (409, "This step is not built for your system yet."), got)
        self.assertNotIn("Terminal", repr(got))
        self.assertNotIn("clark.command", repr(got))
