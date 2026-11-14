"""item 836 step 4b: the setup routes of the server (src/clark/server.py SetupHandler; guarded). Run: python3 dev/run_tests.py test_server_setup
A real LocalServer on a free port with SetupHandler and a real setup_mode.Setup over temporary folders. The folder window is always a
fake function. No store, no data folder, no browser."""
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT, SRC
from _real_server import Running, Stoppable   # the server harness, by way of the real-server helper (this file drives no browser)

from clark import __version__, appfiles, doctor, platform as pl, server as sv, setup_mode

SETUP_GET = ["/api/setup/checks"]
SETUP_POST = ["/api/setup/done", "/api/setup/finish", "/api/setup/folder"]


class SetupRunning(Running):
    def __init__(self, setup, **kw):
        self.httpd = Stoppable((sv.HOST, 0), handler=sv.SetupHandler, setup=setup, **kw)
        self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()


class Case(unittest.TestCase):
    answer = None

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-home-")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.default = self.home / "Library" / "Application Support" / "clark"
        self.default.parent.mkdir(parents=True)
        self.onedrive = self.home / "OneDrive - Work"
        self.onedrive.mkdir()
        self.good = self.home / "Elsewhere"
        self.good.mkdir()
        self.asked = []
        self.service = setup_mode.Setup(
            self.default, home=self.home, on=pl.MAC, choose_folder=self.choose, onedrive_roots=lambda: [self.onedrive],
            environ={}, prompt="Pick", finish=lambda: (True, ["done"]))
        self.s = self.start(self.service)

    def start(self, service, **kw):
        s = SetupRunning(service, **kw)
        self.addCleanup(s.close)
        return s

    def choose(self, prompt):
        self.asked.append(prompt)
        return self.answer

    def post(self, path, body=b"{}", **kw):
        status, _, data = self.s.api("POST", path, body, **kw)
        return status, json.loads(data)

    def get(self, path, **kw):
        status, _, data = self.s.api("GET", path, **kw)
        return status, json.loads(data)


class Routes(Case):
    def test_the_exact_route_lists(self):
        self.assertEqual(sorted(sv.SETUP_GET_ROUTES), SETUP_GET)
        self.assertEqual(sorted(sv.SETUP_POST_ROUTES), SETUP_POST)

    def test_the_normal_tables_are_not_edited(self):
        for table in (sv.GET_ROUTES, sv.POST_ROUTES):
            self.assertFalse([r for r in table if r.startswith("/api/setup")])

    def test_the_normal_handler_still_reads_its_own_table(self):
        self.assertIs(sv.Handler.post_route(None, "/api/change"), sv.POST_ROUTES["/api/change"])
        self.assertIs(sv.Handler.post_route(None, sv.HERE_ROUTE), sv.here_route)
        self.assertIsNone(sv.Handler.post_route(None, "/api/setup/done"))

    def test_the_default_server_has_no_setup(self):
        self.assertIsNone(sv.LocalServer((sv.HOST, 0)).setup)


class Pages(Case):
    def test_slash_and_setup_are_the_same_bytes_with_the_token(self):
        a, b = self.s.ask("GET", "/"), self.s.ask("GET", "/setup")
        self.assertEqual((a[0], b[0]), (200, 200))
        self.assertEqual(a[2], b[2])
        self.assertIn(json.dumps({"token": sv.TOKEN}).encode(), a[2])
        self.assertIn("text/html", a[1]["Content-Type"])
        self.assertIn("Content-Security-Policy", a[1])

    def test_a_service_without_a_page_is_given_the_stand_in(self):
        class NoPage:
            pass
        self.s.httpd.setup = NoPage()
        self.assertIn("clark is starting.", self.s.ask("GET", "/")[2].decode())

    def test_health_has_no_new_key(self):
        status, _, data = self.s.ask("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data), sv.health_answer(None))

    def test_health_knows_the_folders_mark(self):
        with mock.patch.object(sv, "DATA_MARK", "mark-1"):
            self.assertTrue(json.loads(self.s.ask("GET", "/health", {sv.MARK_HEADER: "mark-1"})[2])["this_data"])
            self.assertFalse(json.loads(self.s.ask("GET", "/health", {sv.MARK_HEADER: "other"})[2])["this_data"])

    def test_the_open_page_counts_as_here(self):
        seen = []
        idle = mock.Mock(here=lambda: seen.append(1))
        with mock.patch.object(sv, "IDLE", idle):
            self.s.ask("GET", "/")
            self.s.api("POST", sv.HERE_ROUTE, b"{}")
        self.assertEqual(len(seen), 2)


class Unreachable(Case):
    def test_no_normal_route_is_there(self):
        spies = {k: mock.Mock() for k in ("change", "undo", "publisher", "safety", "ask", "section_image", "word_export")}
        s = self.start(self.service, **spies)
        normal = [("GET", r) for r in sv.GET_ROUTES] + [("POST", r) for r in sv.POST_ROUTES if r != sv.HERE_ROUTE]
        for method, path in normal:
            body = b"{}" if method == "POST" else None
            self.assertEqual(s.ask(method, path, {} if method == "GET" else {"Content-Type": "application/json", "Content-Length": "2"}, body)[0], 403, path)
            self.assertEqual(s.api(method, path, body)[0], 404, path)
        for mock_ in spies.values():
            mock_.assert_not_called()
            self.assertEqual(mock_.mock_calls, [])

    def test_no_normal_page_is_there(self):
        for path in ("/past", "/preview", "/preview?id=x", "/assets/cover.png", "/manifest.webmanifest", "/sw.js", "/offline", "/app/icon.png",
                     "/setup/", "/nothing"):
            self.assertEqual(self.s.ask("GET", path)[0], 404, path)

    def test_the_report_endpoint_is_not_served(self):
        self.assertEqual(self.s.ask("POST", sv.CSP_REPORT_ROUTE, {"Content-Type": "application/json", "Content-Length": "2"}, b"{}")[0], 404)

    def test_the_server_object_has_no_seams(self):
        for name in ("change", "undo", "publisher", "safety", "updater", "movement", "section_body", "word_export"):
            self.assertIsNone(getattr(self.s.httpd, name), name)

    def test_the_service_reaches_no_store(self):
        code = ("import sys; sys.path.insert(0, %r); import clark.setup_mode, clark.server; "
                "bad = [m for m in sys.modules if m.split('.')[-1] in ('store', 'changes', 'updater') or m.startswith('clark.publish')]; "
                "sys.exit(1 if bad else 0)" % str(SRC))
        self.assertEqual(subprocess.run([sys.executable, "-I", "-c", code]).returncode, 0)


class Gates(Case):
    def all_routes(self):
        return [("GET", p) for p in SETUP_GET] + [("POST", p) for p in SETUP_POST + [sv.HERE_ROUTE]]

    def send(self, method, path, **kw):
        body = b"{}" if method == "POST" else None
        return self.s.api(method, path, body, **kw)

    def test_no_wrong_or_old_token(self):
        for method, path in self.all_routes():
            status, _, data = self.send(method, path, token="wrong")
            self.assertEqual(status, 403, path)
            self.assertTrue(json.loads(data).get("stale"))
            self.assertEqual(self.s.ask(method, path, {"Content-Type": "application/json", "Content-Length": "2"} if method == "POST" else {}, b"{}" if method == "POST" else None)[0], 403)
        self.assertEqual(self.asked, [])

    def test_a_restart_makes_the_old_page_stale(self):
        with mock.patch.object(sv, "TOKEN", "n" * len(sv.TOKEN)):
            status, body = self.get("/api/setup/checks", token=sv.TOKEN.replace("n", "o"))
        self.assertEqual((status, body["code"], body["message"]), (403, "stale", sv.STALE_PAGE))

    def test_another_host_other_origin_and_cross_site(self):
        for method, path in self.all_routes():
            for kw in ({"host": "evil.example"}, {"host": None}, {"extra": {"Origin": "http://evil.example"}},
                       {"extra": {"Origin": "null"}}, {"extra": {"Sec-Fetch-Site": "cross-site"}}):
                self.assertEqual(self.send(method, path, **kw)[0], 403, f"{path} {kw}")
        self.assertEqual(self.asked, [])

    def test_the_same_origin_passes(self):
        own = f"http://127.0.0.1:{self.s.port}"
        self.assertEqual(self.send("GET", "/api/setup/checks", extra={"Origin": own, "Sec-Fetch-Site": "same-origin"})[0], 200)

    def test_options_is_refused(self):
        for _, path in self.all_routes():
            self.assertEqual(self.s.ask("OPTIONS", path)[0], 403)

    def test_post_needs_json_a_length_and_a_body_that_reads(self):
        for path in SETUP_POST:
            self.assertEqual(self.s.api("POST", path, b"{}", ctype="text/plain")[0], 415, path)
            self.assertEqual(self.s.ask("POST", path, {sv.TOKEN_HEADER: sv.TOKEN, "Content-Type": "application/json"}, None)[0], 411, path)
            self.assertEqual(self.s.api("POST", path, b"{nope")[0], 400, path)
        self.assertEqual(self.asked, [])

    def test_a_body_that_is_not_exactly_empty_is_refused_on_every_setup_post(self):
        for path in SETUP_POST:
            for body in (b'{"path":"/tmp"}', b'{"a":1}', b"[]", b'"x"', b"null", b"1"):
                status, data = self.post(path, body)
                self.assertEqual((status, data["code"]), (400, "bad_request"), f"{path} {body!r}")
        self.assertEqual(self.asked, [])
        self.assertFalse((self.default.parent / setup_mode.POINTER_NAME).exists())

    def test_an_empty_request_body_is_taken_as_empty(self):
        self.answer = None
        self.assertEqual(self.post("/api/setup/folder", b"")[0], 200)

    def test_a_get_with_a_body_is_refused(self):
        status, _, _ = self.s.ask("GET", "/api/setup/checks", {sv.TOKEN_HEADER: sv.TOKEN, "Content-Length": "2"}, b"{}")
        self.assertEqual(status, 400)

    def test_a_bad_header_post_gets_one_answer_not_two(self):
        for path in ("/api/setup/folder", sv.CSP_REPORT_ROUTE):
            for dup in (b"Content-Length: 2\r\nContent-Length: 2\r\n", b"Host: 127.0.0.1\r\n"):
                raw = (b"POST " + path.encode() + b" HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n" % self.s.port + dup
                       + b"Content-Type: application/json\r\nConnection: close\r\n"
                       + (b"Content-Length: 2\r\n" if b"Content-Length" not in dup else b"") + b"\r\n{}")
                with socket.create_connection((sv.HOST, self.s.port), timeout=10) as c:
                    c.sendall(raw)
                    data = b""
                    while chunk := c.recv(65536):
                        data += chunk
                self.assertEqual(data.count(b"HTTP/1."), 1, (path, dup, data))
                self.assertTrue(data.startswith(b"HTTP/1.0 400") or data.startswith(b"HTTP/1.1 400"), (path, dup, data[:40]))

    def test_the_wrong_method_is_not_found(self):
        self.assertEqual(self.s.api("POST", "/api/setup/checks", b"{}")[0], 404)
        self.assertEqual(self.s.api("GET", "/api/setup/folder")[0], 404)

    def test_container_mode_refuses_a_stranger(self):
        with mock.patch.object(sv, "container_mode", lambda: True), mock.patch.object(sv, "local_peer", lambda a: False):
            self.assertEqual(self.s.ask("GET", "/")[0], 403)


class Checks(Case):
    def test_it_is_the_services_report(self):
        status, body = self.get("/api/setup/checks")
        self.assertEqual((status, body), (200, self.service.report()))
        self.assertTrue(body["ok"])


class Folder(Case):
    def test_cancel(self):
        self.assertEqual(self.post("/api/setup/folder"), (200, {"ok": True, "chosen": False}))
        self.assertEqual(self.asked, ["Pick"])

    def test_a_good_folder_is_kept(self):
        self.answer = str(self.good)
        status, body = self.post("/api/setup/folder")
        self.assertEqual((status, body["chosen"], body["folder"]), (200, True, "~/Elsewhere"))
        self.assertEqual((self.default.parent / setup_mode.POINTER_NAME).read_text(encoding="utf-8"), str(self.good) + "\n")

    def test_a_refused_folder_says_the_checks_words(self):
        inside = self.onedrive / "clark"
        inside.mkdir()
        self.answer = str(inside)
        status, body = self.post("/api/setup/folder")
        self.assertEqual((status, body["code"]), (409, "folder_refused"))
        self.assertIn("OneDrive", body["message"])
        self.assertEqual(list(inside.iterdir()), [])
        self.assertFalse((self.default.parent / setup_mode.POINTER_NAME).exists())

    def test_a_window_that_cannot_open(self):
        self.service.choose_folder = lambda prompt: (_ for _ in ()).throw(pl.PlatformError("The folder window could not be opened. " + pl.TRY_AGAIN))
        status, body = self.post("/api/setup/folder")
        self.assertEqual((status, body["code"]), (409, "dialog_failed"))

    def test_without_a_fake_the_stub_refuses_and_no_window_opens(self):
        opened = []

        def no_window(prompt):
            opened.append(prompt)
            raise pl.PlatformError("The folder window could not be opened. " + pl.TRY_AGAIN)
        service = setup_mode.Setup(self.default, home=self.home, on="linux", choose_folder=no_window,
                                   onedrive_roots=lambda: [], prompt="Pick")
        s = self.start(service)
        status, _, data = s.api("POST", "/api/setup/folder", b"{}")
        self.assertEqual((status, json.loads(data)["code"]), (409, "dialog_failed"))
        self.assertEqual(opened, ["Pick"])

    def test_inside_docker_a_direct_post_is_refused_and_no_window_opens(self):
        # the page only hides the button there; the route must refuse on its own, in platform's existing Docker words
        self.answer = str(self.good)
        with mock.patch.object(pl, "container_mode", return_value=True):
            status, body = self.post("/api/setup/folder")
        self.assertEqual((status, body["ok"], body["code"]), (409, False, "dialog_failed"))
        self.assertEqual(body["message"], "The folder dialog needs the Mac, so it is not available when clark runs in Docker. "
                                          "To use it, start clark with clark.command instead.")
        self.assertEqual(self.asked, [])
        self.assertFalse((self.default.parent / setup_mode.POINTER_NAME).exists())
        self.assertEqual(self.service.folder, self.default)

    def test_a_second_while_one_is_open_is_busy(self):
        inside, release = threading.Event(), threading.Event()

        def slow(prompt):
            inside.set()
            release.wait(5)
            return None
        self.service.choose_folder = slow
        first = threading.Thread(target=self.post, args=("/api/setup/folder",))
        first.start()
        self.assertTrue(inside.wait(5))
        status, body = self.post("/api/setup/folder")
        self.assertEqual((status, body["code"]), (409, "busy"))
        release.set()
        first.join(5)

    def test_an_open_window_keeps_the_idle_stop_waiting(self):
        inside, release, seen = threading.Event(), threading.Event(), []

        def slow(prompt):
            inside.set()
            release.wait(5)
            return None
        self.service.choose_folder = slow
        first = threading.Thread(target=self.post, args=("/api/setup/folder",))
        first.start()
        self.assertTrue(inside.wait(5))
        seen.append(sv.busy())
        release.set()
        first.join(5)
        self.assertEqual(seen, [True])

    def test_not_wired_without_a_prompt(self):
        self.service.prompt = None
        status, body = self.post("/api/setup/folder")
        self.assertEqual((status, body["code"]), (404, "not_found"))
        self.assertEqual(self.asked, [])


class Finish(Case):
    def test_the_helpers_words(self):
        self.assertEqual(self.post("/api/setup/finish"), (200, {"ok": True, "finished": True, "words": ["done"]}))

    def test_not_wired_without_a_seam(self):
        self.service._finish = None
        self.assertEqual(self.post("/api/setup/finish")[0], 404)


class Done(Case):
    def test_not_ready_keeps_the_server_going(self):
        self.service.folder = self.onedrive / "clark"
        status, body = self.post("/api/setup/done")
        self.assertEqual((status, body["code"], body["ready"]), (409, "not_ready", False))
        self.s.thread.join(0.3)
        self.assertTrue(self.s.thread.is_alive())
        self.assertEqual(self.get("/api/setup/checks")[0], 200)

    def test_ready_answers_first_then_the_server_stops(self):
        self.service.checks = []
        status, body = self.post("/api/setup/done")
        self.assertEqual((status, body), (200, {"ok": True, "restart": True}))
        self.s.thread.join(5)
        self.assertFalse(self.s.thread.is_alive())

    def test_a_page_from_before_the_restart_is_told_to_reload(self):
        old = sv.TOKEN
        with mock.patch.object(sv, "TOKEN", "n" * len(old)):
            self.assertEqual(self.get("/api/setup/checks", token=old)[1]["code"], "stale")


class ChosenFolderPort(Case):
    """Critical reader (CHANGES): the server's data mark was set once, from the first folder. After a folder was chosen the REAL port check
    (doctor.check_port asking this server's own /health with the new folder's mark) saw another clark with other data: FIX, ready false,
    done 409 not_ready, and the page could never finish. Here the real check runs against the real setup server on its own port."""

    def setUp(self):
        super().setUp()
        self.service = setup_mode.Setup(
            self.default, home=self.home, on=pl.MAC, choose_folder=self.choose, onedrive_roots=lambda: [self.onedrive],
            prompt="Pick", kept=setup_mode.server_mark, checks=[c for c in doctor.CHECKS if doctor.check_id(c) == "port"])
        self.s = self.start(self.service)
        self.service.environ = {"CLARK_PORT": str(self.s.port)}                  # the check asks THIS server
        for name, value in (("DATA_MARK", appfiles.data_mark(self.default)),     # as main sets them before serving; the port check also asks
                            ("VERSION", __version__), ("CODE_MARK", appfiles.code_mark())):   # who this clark is (row 1030)
            patch = mock.patch.object(sv, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def port_row(self):
        status, body = self.get("/api/setup/checks")
        self.assertEqual(status, 200)
        return body["ready"], [r for r in body["checks"] if r["id"] == "port"][0]

    def test_the_real_port_check_stays_ready_after_a_folder_is_chosen_so_done_is_accepted(self):
        ready, row = self.port_row()
        self.assertEqual((ready, row["status"]), (True, doctor.READY))
        self.answer = str(self.good)
        status, body = self.post("/api/setup/folder")
        self.assertEqual((status, body["chosen"], body["folder"]), (200, True, "~/Elsewhere"))
        ready, row = self.port_row()
        self.assertEqual((ready, row["status"]), (True, doctor.READY), row["words"])     # was FIX "...different data", ready False
        self.assertNotIn("different data", row["words"])
        self.assertEqual(sv.DATA_MARK, appfiles.data_mark(self.good))
        status, body = self.post("/api/setup/done")
        self.assertEqual((status, body), (200, {"ok": True, "restart": True}))
        self.s.thread.join(5)
        self.assertFalse(self.s.thread.is_alive())

    def test_a_refused_folder_leaves_the_mark_alone(self):
        inside = self.onedrive / "clark"
        inside.mkdir()
        self.answer = str(inside)
        self.assertEqual(self.post("/api/setup/folder")[0], 409)
        self.assertEqual(sv.DATA_MARK, appfiles.data_mark(self.default))
        self.assertEqual(self.port_row()[1]["status"], doctor.READY)


class Source(unittest.TestCase):
    def test_the_server_still_imports_nothing_from_clark(self):
        text = (ROOT / "src" / "clark" / "server.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"^[ \t]*(?:from|import)[ \t]+(?:clark|setup_mode)\b.*$", text, re.M), [])

    def test_the_movement_pins_are_untouched(self):
        text = (ROOT / "src" / "clark" / "server.py").read_text(encoding="utf-8")
        self.assertIn('"/api/movement": movement_route', text)


if __name__ == "__main__":
    unittest.main()
