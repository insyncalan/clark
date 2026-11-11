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

    def test_another_fault_is_still_the_generic_500(self):
        class Service:
            def connect(self, body):
                raise ValueError("boom")
        self.rig.httpd.ai_connect = Service()
        status, got = self.rig.call("POST", "/api/providers/connect", {"provider": "claude"})
        self.assertEqual((status, got["code"]), (500, "server_error"))


if __name__ == "__main__":
    unittest.main()
