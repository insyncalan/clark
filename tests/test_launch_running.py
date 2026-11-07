"""Row 975: the launcher when a clark is already running on the port: it opens a window only on THIS folder's clark of THIS version.

Run: python3 dev/run_tests.py test_launch_running
launch.launch() runs in-process with fakes for starting clark, finding Chrome and opening a window (no Chrome, no window). The
"running clark" is a small stub server on a scratch port (8791-8795) with a scratch data folder; never port 8766, never real data.
"""
import http.server
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT, SRC  # noqa: F401

from clark import __version__, appfiles, launch, platform as pl, server

THIS = (__version__, appfiles.code_mark())
STOP = ("clark is already running, but not from this folder or not this version. Nothing was changed. "
        "Quit it first (press Ctrl+C in its Terminal window), then start this one again.")
PORTS = __import__("itertools").cycle(range(8791, 8796))


class Stub:
    """A running clark as far as the launcher can tell: /health (with this_data from the mark asked, and a version and folder as given) and /."""

    def __init__(self, port, mark, version=None, folder=None, page=200):
        stub = self
        self.hits = []

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                stub.hits.append(self.path)
                if self.path == "/health":
                    body = {"ok": True, "this_data": self.headers.get(appfiles.MARK_HEADER) == mark}
                    if version is not None:
                        body["version"] = version
                    if folder is not None:
                        body["folder"] = folder
                    data, code = json.dumps(body).encode(), 200
                else:
                    data, code = b"<html>clark</html>", page
                self.send_response(code)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class Running(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name) / "data"
        self.folder.mkdir()
        self.mark = appfiles.data_mark(self.folder)
        self.port = next(PORTS)
        self.said, self.started, self.windows, self.browser = [], [], [], []

    def stub(self, **kw):
        s = Stub(self.port, self.mark, **kw)
        self.addCleanup(s.close)
        return s

    def go(self):
        return launch.launch(self.port, self.folder, self.said.append, {"PATH": "/bin"},
                             start=lambda *a, **k: self.started.append(a) or self.fail("started"),
                             find_chrome=lambda e: "/stub/chrome", open_window=lambda u, c: self.windows.append((u, c)),
                             open_browser=self.browser.append, finish=lambda f, say: True)

    def stopped(self, say):
        self.assertEqual(self.go(), 1)
        self.assertEqual(self.said, [say])
        self.assertEqual((self.started, self.windows, self.browser), ([], [], []))

    def test_same_folder_same_version_opens_its_window(self):
        s = self.stub(version=THIS[0], folder=THIS[1])
        self.assertEqual(self.go(), 0)
        self.assertEqual(self.said, ["It is already running. Opening its window.", "Opened clark in its own window."])
        self.assertEqual(self.windows, [(f"http://127.0.0.1:{self.port}/", "/stub/chrome")])
        self.assertEqual(self.started, [])
        self.assertIn("/", s.hits)

    def test_another_folder_stops_with_the_words_and_changes_nothing(self):
        self.stub(version=THIS[0], folder="0" * 16)
        self.stopped(STOP)

    def test_another_version_on_the_same_data_stops(self):
        self.stub(version="0.0.1", folder=THIS[1])
        self.stopped(STOP)

    def test_a_server_that_says_no_version_stops(self):
        self.stub(folder=THIS[1])
        self.stopped(STOP)

    def test_a_server_that_says_no_folder_stops(self):
        self.stub(version=THIS[0])
        self.stopped(STOP)

    def test_the_exact_bug_an_old_server_in_a_renamed_folder_answering_500_is_stopped_on_the_folder_words(self):
        self.stub(version="1.0.3", page=500)
        self.stopped(STOP)

    def test_this_clark_whose_page_answers_500_says_so_and_opens_nothing(self):
        self.stub(version=THIS[0], folder=THIS[1], page=500)
        self.stopped(launch.BROKEN_PAGE)
        self.assertIn("error", launch.BROKEN_PAGE)

    def test_nothing_running_starts_as_today(self):
        started = []
        process = type("P", (), {"poll": lambda s: None})()
        code = self.start_fresh(started, process)
        self.assertEqual(code, 0)
        self.assertEqual(len(started), 1)
        self.assertEqual(self.said[0], "Starting clark...")
        self.assertEqual(len(self.windows), 1)

    def start_fresh(self, started, process):
        return launch.launch(self.port, self.folder, self.said.append, {"PATH": "/bin"},
                             start=lambda *a, **k: started.append(a) or process,
                             wait=lambda port, mark, p, health=None: launch.OURS,
                             find_chrome=lambda e: "/stub/chrome", open_window=lambda u, c: self.windows.append((u, c)),
                             finish=lambda f, say: True)


class Identity(unittest.TestCase):
    def test_the_server_tells_its_folder_only_when_asked_with_the_mark(self):
        with mock.patch.object(server, "CODE_MARK", "abc"), mock.patch.object(server, "DATA_MARK", "m"):
            self.assertEqual(server.health_answer("m")["folder"], "abc")
            self.assertNotIn("folder", server.health_answer(None))
        with mock.patch.object(server, "CODE_MARK", None), mock.patch.object(server, "DATA_MARK", "m"):
            self.assertNotIn("folder", server.health_answer("m"))

    def test_the_launcher_and_the_server_work_out_one_mark(self):
        self.assertEqual(appfiles.code_mark(), appfiles.data_mark(Path(launch.__file__).resolve().parents[2]))

    def test_an_update_restart_does_not_go_through_the_launcher_check(self):
        text = (SRC / "clark" / "update_helper.py").read_text(encoding="utf-8")
        self.assertNotIn("ask_identity", text)
        self.assertNotIn("launch.launch", text)


if __name__ == "__main__":
    unittest.main()
