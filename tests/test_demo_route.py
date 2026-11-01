"""#444 (guarded): POST /api/demo, Reset the demo data (src/clark/demo_route.py), and the launcher's rebuild, on a real demo database
in a temporary folder, and the route through the real server. Fictional data only. Run: python3 dev/run_tests.py test_demo_route

What is asserted: the state says demo only for clark's own demo folder; a reset of data that is not the demo folder is refused with
nothing touched, whatever the request says; a reset of the demo data puts it back as it started (a change is gone, a project
added is gone) and says the page should reload; a failing rebuild leaves the data as it was; a reset waits for no change (busy);
a request with anything but an op is refused; the route sits behind the same token, Host and Origin checks as every route.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _demo import DemoStore
from clark import __main__ as launcher, changes, demo_route, project_route, store as clark_store
from test_word_route import Up


class Demo(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix="clark-demo-"))
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.path = launcher.demo_database(self.folder)
        self.seam = demo_route.make_demo(self.path, self.folder, launcher.demo_rebuild)

    def codes(self):
        s = clark_store.open_store(self.path, onedrive_roots=[])
        try:
            return sorted(p["code"] for p in s.read("projects"))
        finally:
            s.close()

    def test_state_says_demo_for_the_demo_folder_only(self):
        self.assertEqual(self.seam({"op": "state"}), (200, {"ok": True, "demo": True}))
        other = DemoStore()
        self.addCleanup(other.close)
        for seam in (demo_route.make_demo(other.store.path, None, None), demo_route.make_demo(other.store.path, self.folder, launcher.demo_rebuild),
                     demo_route.make_demo(self.path, self.folder, None), demo_route.make_demo(self.path, None, launcher.demo_rebuild)):
            self.assertEqual(seam({"op": "state"}), (200, {"ok": True, "demo": False}))

    def test_a_reset_of_data_that_is_not_the_demo_folder_is_refused_and_touches_nothing(self):
        other = DemoStore()
        self.addCleanup(other.close)
        asked = []
        seam = demo_route.make_demo(other.store.path, None, lambda p: asked.append(p))
        before = Path(other.store.path).read_bytes()
        status, got = seam({"op": "reset"})
        self.assertEqual((status, got["ok"], got["code"], got["message"]), (409, False, "not_demo", demo_route.NOT_DEMO))
        self.assertEqual((asked, Path(other.store.path).read_bytes()), ([], before))
        seam = demo_route.make_demo(other.store.path, self.folder, lambda p: asked.append(p))          # a folder that is not the one the data is in
        self.assertEqual(seam({"op": "reset"})[1]["code"], "not_demo")
        self.assertEqual(asked, [])

    def test_a_reset_puts_the_demo_data_back_as_it_started(self):
        started = self.codes()
        who = project_route.make_project(self.path, [], "Dana Ellis")
        self.assertEqual(who({"op": "new", "code": "EXTRA", "name": "Extra"})[0], 200)
        s = clark_store.open_store(self.path, onedrive_roots=[])
        with s.step("dashboard", "Dana Ellis") as st:
            st.update("projects", "TUL", {"name": "Renamed"})
        s.close()
        self.assertEqual(self.codes(), sorted(started + ["EXTRA"]))
        status, got = self.seam({"op": "reset"})
        self.assertEqual((status, got["ok"], got["code"], got["reload"], got["message"]), (200, True, "reset", True, demo_route.DONE), got)
        self.assertEqual(self.codes(), started)
        s = clark_store.open_store(self.path, onedrive_roots=[])
        try:
            self.assertNotEqual(s.read("projects", ref="TUL")["name"], "Renamed")
        finally:
            s.close()
        self.assertEqual([n for n in os.listdir(self.folder) if n.startswith("clark-reset")], [])          # no half-made copy is left
        self.assertFalse((self.folder / "clark-reset.db").exists())
        self.assertEqual(self.seam({"op": "state"})[1]["demo"], True)

    def test_a_failing_rebuild_leaves_the_data_as_it_was_and_says_so_in_words(self):
        def boom(path):
            raise RuntimeError("/Users/someone/secret")
        seam = demo_route.make_demo(self.path, self.folder, boom)
        before = Path(self.path).read_bytes()
        status, got = seam({"op": "reset"})
        self.assertEqual((status, got["code"], got["message"]), (500, "reset_failed", demo_route.FAILED))
        self.assertNotIn("secret", json.dumps(got))
        self.assertEqual(Path(self.path).read_bytes(), before)

    def test_a_reset_while_a_change_is_running_is_busy_and_does_not_wait(self):
        asked = []
        seam = demo_route.make_demo(self.path, self.folder, lambda p: asked.append(p))
        with changes.LOCK:
            status, got = seam({"op": "reset"})
        self.assertEqual((status, got["code"], got["message"]), (409, "busy", demo_route.BUSY))
        self.assertEqual(asked, [])

    def test_a_real_rebuild_that_fails_midway_keeps_the_old_file(self):
        before = Path(self.path).read_bytes()
        real = launcher.demo_module()
        original = real.build

        def broken(out, now, onedrive_roots=None):
            Path(out).write_bytes(b"half")
            raise real.DemoError("stopped")
        real.build = broken
        try:
            seam = demo_route.make_demo(self.path, self.folder, launcher.demo_rebuild)
            self.assertEqual(seam({"op": "reset"})[0], 500)
        finally:
            real.build = original
        self.assertEqual(Path(self.path).read_bytes(), before)
        self.assertFalse((self.folder / "clark-reset.db").exists())

    def test_anything_but_an_op_is_refused(self):
        for req in ({}, {"op": "nope"}, {"op": "reset", "path": "/tmp"}, {"op": "state", "x": 1}, {"op": 5}, [], "x", None):
            status, got = self.seam(req)
            self.assertEqual((status, got["ok"]), (400, False), req)


class ThroughTheServer(unittest.TestCase):
    ROUTE = "/api/demo"

    def setUp(self):
        self.calls = []
        self.up = Up()
        self.up.httpd.demo = lambda r: (self.calls.append(r) or (200, {"ok": True}))
        self.addCleanup(self.up.close)

    def test_without_the_right_token_host_and_origin_the_seam_is_never_called(self):
        for token in (None, "", "wrong"):
            self.assertEqual(self.up.ask(self.ROUTE, b"{}", token=token)[0], 403, token)
        self.assertEqual(self.up.ask(self.ROUTE, b"{}", host="evil.example")[0], 403)
        for extra in ({"Origin": "https://evil.example"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.up.ask(self.ROUTE, b"{}", headers=extra)[0], 403, extra)
        self.assertEqual(self.up.ask(self.ROUTE, b"{}", method="GET")[0], 404)
        self.assertEqual(self.calls, [])

    def test_json_only_a_tiny_body_and_no_seam_is_503(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.up.port, timeout=10)
        conn.request("POST", self.ROUTE, b"{}", {self.up.sv.TOKEN_HEADER: self.up.sv.TOKEN, "Content-Type": "text/plain"})
        self.assertEqual(conn.getresponse().status, 415)
        conn.close()
        self.assertEqual(self.up.ask(self.ROUTE, b'{"op": "' + b"x" * 1100 + b'"}')[1]["code"], "too_large")
        self.assertEqual(self.calls, [])
        bare = Up()
        self.addCleanup(bare.close)
        status, body = bare.ask(self.ROUTE, b"{}")
        self.assertEqual((status, body["code"]), (503, "saving_off"))


if __name__ == "__main__":
    unittest.main()
