"""#836 (Quit): POST /api/quit stops clark from the page, and nothing is left running.

Run: python3 dev/run_tests.py test_quit
Three parts, none opens a dialog or a real browser:
- the route, on a server in a thread (the stop is watched, not carried out): it needs the token, the Host and the Origin like every
  other POST; a good call answers first, then stops the server once; a refused call stops nothing; there is no way to quit with a GET;
- a real `python3 -m clark --demo` process: after a good call it ends by itself with exit code 0, its last line is "Stopped.", the
  port answers nothing, and the demo's temporary folder is gone (the same clean-up as Ctrl+C);
- the Settings card is in the Edit page only: the published page holds none of its words.
"""
import http.client
import json
import re
import socket
import threading
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401

from clark import server as sv
from test_main import Process, WAIT, free_port, get, post, port_of
from test_main import TempFolder
from test_server import Running

PAGES = Path(__file__).resolve().parents[1] / "src" / "clark" / "page"
CARD_WORDS = ("Quit clark", "Stopping clark. You can close this window.", "Quitting did not work. Try again.")


class Watched(Running):
    """A Running whose stop is recorded instead of carried out, so one server answers every case."""

    def __init__(self):
        super().__init__()
        self.stops = threading.Semaphore(0)
        self.count = 0
        real = self.httpd.shutdown

        def shutdown():
            self.count += 1
            self.stops.release()
        self.httpd.shutdown = shutdown
        self.real_shutdown = real

    def close(self):
        self.httpd.shutdown = self.real_shutdown
        super().close()


class Route(unittest.TestCase):
    def setUp(self):
        self.s = Watched()
        self.addCleanup(self.s.close)

    def quit(self, **kw):
        return self.s.api("POST", "/api/quit", b"{}", **kw)

    def not_stopped(self):
        return not self.s.stops.acquire(timeout=0.5)

    def test_a_good_call_answers_then_stops_the_server_once(self):
        status, _, body = self.quit()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True, "quit": True})
        self.assertTrue(self.s.stops.acquire(timeout=WAIT), "the server was told to stop")
        self.assertTrue(self.not_stopped(), "and only once")
        self.assertEqual(self.s.count, 1)

    def test_no_token_or_a_wrong_one_stops_nothing(self):
        self.assertEqual(self.quit(token="")[0], 403)
        self.assertEqual(self.quit(token="not-the-token")[0], 403)
        self.assertTrue(self.not_stopped())

    def test_a_host_that_is_not_this_machine_stops_nothing(self):
        for host in ("evil.example", f"evil.example:{self.s.port}", f"127.0.0.1.evil.example:{self.s.port}", "10.0.0.5"):
            self.assertEqual(self.quit(host=host)[0], 403, host)
        self.assertEqual(self.quit(host=None)[0], 403, "no Host at all is refused too")
        self.assertTrue(self.not_stopped())

    def test_a_page_on_another_site_stops_nothing(self):
        for origin in ("https://evil.example", "http://127.0.0.1.evil.example", "null"):
            self.assertEqual(self.quit(extra={"Origin": origin})[0], 403, origin)
        self.assertEqual(self.quit(extra={"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.s.api("OPTIONS", "/api/quit")[0], 403)
        self.assertTrue(self.not_stopped())

    def test_not_json_and_a_wrong_length_stop_nothing(self):
        self.assertEqual(self.s.api("POST", "/api/quit", b"{}", ctype="text/plain")[0], 415)
        self.assertEqual(self.s.api("POST", "/api/quit", b"{}", ctype="application/x-www-form-urlencoded")[0], 415)
        self.assertEqual(self.s.api("POST", "/api/quit", b"x" * 2000)[0], 400)
        self.assertTrue(self.not_stopped())

    def test_a_get_never_quits(self):
        for path in ("/api/quit", "/api/quit?now=1"):
            status = self.s.api("GET", path)[0]
            self.assertIn(status, (404, 405), path)
        self.assertEqual(self.s.ask("GET", "/api/quit")[0], 403, "and without the token it is refused first")
        self.assertTrue(self.not_stopped())

    def test_the_quit_call_is_not_a_still_here(self):
        """Quitting must not be mistaken for an open window: it is a POST route of its own, not the heartbeat."""
        self.assertIn("/api/quit", sv.POST_ROUTES)
        self.assertNotIn("/api/quit", sv.GET_ROUTES)
        self.assertNotEqual(sv.POST_ROUTES["/api/quit"], sv.here_route)


class AProcess(TempFolder):
    def test_a_good_call_ends_the_process_and_leaves_nothing_running(self):
        scratch = self.tmp / "scratch"
        scratch.mkdir()
        port = free_port()
        p = Process("--demo", "--port", str(port), home=self.tmp, env={"TMPDIR": str(scratch)})
        self.addCleanup(p.close)
        self.assertEqual(port_of(p.address_line()), port)
        self.assertTrue([f for f in scratch.iterdir()], "the demo's folder exists while it runs")
        page = get(port, "/")[1]
        token = json.loads(re.search(r'<script type="application/json" id="clark-boot">(.*?)</script>', page).group(1))["token"]
        self.assertEqual(post(port, "/api/quit", {}, {"X-Clark-Token": "wrong"})[0], 403)
        self.assertEqual(get(port, "/health")[0], 200, "a refused call leaves it running")
        status, body = post(port, "/api/quit", {}, {"X-Clark-Token": token})
        self.assertEqual((status, body), (200, {"ok": True, "quit": True}))
        code, seen, errors = p.finish()
        self.assertEqual(code, 0)
        self.assertEqual(errors, [])
        self.assertEqual(seen[-1], "Stopped.")
        with socket.socket() as probe:
            self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0, "nothing answers on the port")
        self.assertFalse([f for f in scratch.iterdir()], "the demo's folder is removed, as after Ctrl+C")
        self.assertFalse([f for f in self.tmp.iterdir() if f.name != "scratch"], "nothing was written into HOME")


class OnlyInEdit(unittest.TestCase):
    def read(self, name):
        return (PAGES / name).read_text(encoding="utf-8")

    def test_the_edit_page_holds_the_card_and_the_published_page_none_of_its_words(self):
        edit, view = self.read("page.html"), self.read("page-view.html")
        for words in CARD_WORDS:
            self.assertIn(words, edit)
            self.assertNotIn(words, view)
        self.assertIn("/api/quit", edit)
        self.assertNotIn("/api/quit", view)


if __name__ == "__main__":
    unittest.main()
