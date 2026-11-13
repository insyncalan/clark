"""Row 975: the launcher when a clark is already running on the port: it opens a window only on THIS folder's clark of THIS version.

Run: python3 dev/run_tests.py test_launch_running
launch.launch() runs in-process with fakes for starting clark, finding Chrome and opening a window (no Chrome, no window). The
"running clark" is a small stub server on a scratch port (8791-8795) with a scratch data folder; never port 8766, never real data.
"""
import http.server
import hashlib
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT, SRC  # noqa: F401

from clark import __version__, appfiles, launch, platform as pl, server

THIS = (__version__, appfiles.code_mark())
STOP = ("clark is already running, but it is not the copy you are trying to start (it may be from another folder, or an older "
        "version). Close the clark that is already open, then start clark again. "
        "If you can't find it, restart your computer.")
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
        self.assertEqual(self.said, ["It is already running. Opening its window.", "Opened clark in Chrome."])
        self.assertEqual(self.windows, [(f"http://clark.localhost:{self.port}/", "/stub/chrome")])
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

    def test_a_page_that_gives_no_answer_stops_on_the_page_words(self):
        # deliberate: a server that is this folder's and version but whose page does not answer is as unusable as one answering 500
        self.stub(version=THIS[0], folder=THIS[1])
        self.assertEqual(launch.launch(self.port, self.folder, self.said.append, {"PATH": "/bin"}, page=lambda p: None,
                                       start=lambda *a, **k: self.fail("started"), find_chrome=lambda e: "/stub/chrome",
                                       open_window=lambda u, c: self.windows.append((u, c)), open_browser=self.browser.append,
                                       finish=lambda f, say: True), 1)
        self.assertEqual(self.said, [launch.BROKEN_PAGE])
        self.assertEqual((self.started, self.windows, self.browser), ([], [], []))

    def test_ask_page_gives_none_when_nothing_answers(self):
        self.assertIsNone(launch.ask_page(self.port))

    def test_only_5xx_stops_the_page_status_boundary(self):
        for status in (404, 403, 499, 200):
            with self.subTest(status=status):
                self.said.clear(), self.windows.clear()
                s = self.stub(version=THIS[0], folder=THIS[1], page=status)
                self.assertEqual(self.go(), 0)
                self.assertEqual(self.said[0], "It is already running. Opening its window.")
                self.assertEqual(len(self.windows), 1)
                s.close()
        for status in (500, 503, 599):
            with self.subTest(status=status):
                self.said.clear(), self.windows.clear()
                s = self.stub(version=THIS[0], folder=THIS[1], page=status)
                self.stopped(launch.BROKEN_PAGE)
                s.close()

    def test_row_1030_the_words_do_not_send_anyone_to_a_terminal_window(self):
        for words in (launch.NOT_THIS_ONE, launch.BROKEN_PAGE):
            self.assertNotIn("Ctrl", words)
            self.assertNotIn("Terminal", words)
            self.assertIn("restart your computer", words)

    def test_row_1030_ours_problem_is_none_for_this_clark_and_a_word_for_the_rest(self):
        ok = lambda p, m: THIS
        self.assertIsNone(launch.ours_problem(1, "m", identity=ok, page=lambda p: 200))
        self.assertIsNone(launch.ours_problem(1, "m", identity=ok, page=lambda p: 404))
        self.assertEqual(launch.ours_problem(1, "m", identity=lambda p, m: ("0.0.1", THIS[1]), page=lambda p: 200), launch.NOT_THIS_ONE)
        self.assertEqual(launch.ours_problem(1, "m", identity=lambda p, m: (None, None), page=lambda p: 200), launch.NOT_THIS_ONE)
        self.assertEqual(launch.ours_problem(1, "m", identity=ok, page=lambda p: 500), launch.BROKEN_PAGE)
        self.assertEqual(launch.ours_problem(1, "m", identity=ok, page=lambda p: None), launch.BROKEN_PAGE)

    def test_row_1030_a_404_page_on_this_clark_is_no_problem_through_the_real_default_asks(self):
        self.stub(version=THIS[0], folder=THIS[1], page=404)
        self.assertIsNone(launch.ours_problem(self.port, self.mark))

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
    def ask(self, body):
        class Conn:
            def __init__(self, *a, **k):
                pass

            def request(self, *a, **k):
                pass

            def getresponse(self):
                return type("R", (), {"status": 200, "read": lambda s, n=None: body})()

            def close(self):
                pass
        return launch.ask_identity(1, "m", connect=Conn)

    def test_ask_identity_fails_closed_on_odd_fields_and_replies(self):
        self.assertEqual(self.ask(b'{"version": "1", "folder": "f"}'), ("1", "f"))
        self.assertEqual(self.ask(b'{"version": 1, "folder": "f"}'), (None, "f"))
        self.assertEqual(self.ask(b'{"version": "1", "folder": 5}'), ("1", None))
        self.assertEqual(self.ask(b'{"version": ["1"], "folder": {"a": 1}}'), (None, None))
        self.assertEqual(self.ask(b'{"version": null, "folder": true}'), (None, None))
        for raw in (b'[1, 2]', b'"text"', b'7', b'null', b'not json'):
            self.assertEqual(self.ask(raw), (None, None), raw)

    def test_the_real_entry_gives_the_server_its_folder_mark(self):
        from clark import __main__ as entry
        data, home = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(data, ignore_errors=True))
        self.addCleanup(lambda: __import__("shutil").rmtree(home, ignore_errors=True))
        seen = {}

        def serve(**kw):
            seen["answer"] = server.health_answer(appfiles.data_mark(data))
            return 0
        saved = (server.CODE_MARK, server.DATA_MARK, server.VERSION)
        self.addCleanup(lambda: (server.set_code_mark(saved[0]), server.set_data_mark(saved[1]), server.set_version(saved[2])))
        with mock.patch.object(pl, "system", return_value=pl.MAC):
            code = entry.main(["--data", str(data), "--port", "8792"], out=open(os.devnull, "w", encoding="utf-8"), err=open(os.devnull, "w", encoding="utf-8"),
                              serve=serve, home=home, is_free=lambda p: True, environ={"HOME": str(home)})
        self.assertEqual(code, 0)
        self.assertEqual(seen["answer"].get("folder"), appfiles.code_mark())
        self.assertEqual(seen["answer"].get("version"), __version__)
        self.assertTrue(seen["answer"]["this_data"])

    def test_the_server_tells_its_folder_only_when_asked_with_the_mark(self):
        with mock.patch.object(server, "CODE_MARK", "abc"), mock.patch.object(server, "DATA_MARK", "m"):
            self.assertEqual(server.health_answer("m")["folder"], "abc")
            self.assertNotIn("folder", server.health_answer(None))
        with mock.patch.object(server, "CODE_MARK", None), mock.patch.object(server, "DATA_MARK", "m"):
            self.assertNotIn("folder", server.health_answer("m"))

    def test_the_launcher_and_the_server_work_out_one_mark(self):
        st = os.stat(Path(launch.__file__).resolve().parents[2])      # #1031 s7: the folder's file identity, not its spelling
        self.assertEqual(appfiles.code_mark(), hashlib.sha256(f"{st.st_dev}:{st.st_ino}".encode("utf-8")).hexdigest()[:16])
        self.assertEqual(appfiles.code_mark(), appfiles.code_mark())
        self.assertRegex(appfiles.code_mark(), r"^[0-9a-f]{16}$")

    def test_ultrareview_105_7_two_spellings_of_one_folder_give_one_mark(self):
        """A case-insensitive file system names one folder two ways; the mark follows the folder, not the spelling."""
        with tempfile.TemporaryDirectory() as t:
            real = Path(t).resolve() / "Clark"
            (real / "src" / "clark").mkdir(parents=True)
            other = Path(t).resolve() / "clark"
            if other.exists() is False:
                self.skipTest("a case-sensitive file system: one folder has one spelling")
            fake = real / "src" / "clark" / "appfiles.py"
            alt = other / "src" / "clark" / "appfiles.py"
            with mock.patch.object(appfiles, "__file__", str(fake)):
                a = appfiles.code_mark()
            with mock.patch.object(appfiles, "__file__", str(alt)):
                b = appfiles.code_mark()
            self.assertEqual(a, b)

    def test_ultrareview_105_7_the_mark_is_not_the_hash_of_the_path(self):
        self.assertNotEqual(appfiles.code_mark(), appfiles.data_mark(Path(launch.__file__).resolve().parents[2]))

    def test_ultrareview_105_7_two_different_folders_give_two_marks(self):
        with tempfile.TemporaryDirectory() as t:
            marks = set()
            for n in ("a", "b"):
                (Path(t) / n / "src" / "clark").mkdir(parents=True)
                with mock.patch.object(appfiles, "__file__", str(Path(t) / n / "src" / "clark" / "appfiles.py")):
                    marks.add(appfiles.code_mark())
            self.assertEqual(len(marks), 2)

    def test_an_update_restart_does_not_go_through_the_launcher_check(self):
        text = (SRC / "clark" / "update_helper.py").read_text(encoding="utf-8")
        self.assertNotIn("ask_identity", text)
        self.assertNotIn("launch.launch", text)


if __name__ == "__main__":
    unittest.main()


class UltrareviewNitsSource(unittest.TestCase):
    """Ultrareview 105 #8, #9, #10: source checks (the grown set, the Dashboard's project key, the unused constant)."""
    PAGE = SRC / "clark" / "page" / "src"

    def test_the_grown_memory_is_one_set_per_project(self):
        # main's rule (test_motion_gantt_bars): one Set per project key, so a switch of project keeps what each has grown
        text = (self.PAGE / "gantt" / "components" / "GanttChart.jsx").read_text(encoding="utf-8")
        self.assertIn("const grown = new Map()", text)
        self.assertIn("grown.set(k, new Set())", text)

    def test_the_dashboard_gantt_passes_the_project_key_like_the_gantt_page(self):
        text = (self.PAGE / "components" / "GanttSection.jsx").read_text(encoding="utf-8")
        self.assertIn("projectKey=", text)

    def test_gantt_secret_fields_is_gone(self):
        for path in (SRC / "clark").glob("*.py"):
            self.assertNotIn("GANTT_SECRET_FIELDS", path.read_text(encoding="utf-8"), path.name)
