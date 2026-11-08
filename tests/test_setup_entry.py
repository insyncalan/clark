"""#836 step 4d: setup mode really comes up. The launcher's start_setup runs `python3 -m clark.setup_mode`; here that command is
run for real (the process through tests/_real_server.py real_setup_start), on a free port, over a temporary folder that does not
exist. Run: python3 dev/run_tests.py test_setup_entry
No window, no folder dialog and no real data folder is touched: the launcher's window seams are fakes and the folder route is
never asked.
"""
import http.client
import json
import re
import socket
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
from _real_server import real_setup_start, stop_all
from test_launcher import Fakes

from clark import appfiles, launch


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get(port, path, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", path, headers=headers or {})
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()


class Entry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / "refused" / "clark"           # never made
        self.logs = self.root / "Logs"
        self.spawned = []
        self.addCleanup(stop_all, self.spawned)
        self.port = free_port()

    def start(self):
        f = Fakes([])
        self.f = f
        base = f.kw()
        ok = launch.start_setup(self.port, self.folder, "data_folder", f.said.append, {"HOME": str(self.root)},
                                real_setup_start(self.spawned), launch.ask_health, launch.wait_for_clark, base["find_chrome"],
                                base["open_window"], base["open_browser"], log_dir=lambda: self.logs)
        return ok

    def test_the_launcher_starts_it_for_real_and_it_answers_with_the_data_folders_mark(self):
        self.assertTrue(self.start(), (self.logs / "setup.log").read_text(encoding="utf-8") if (self.logs / "setup.log").exists() else "no log")
        self.assertEqual(launch.ask_health(self.port, appfiles.data_mark(self.folder)), launch.OURS)
        self.assertEqual(self.f.windows, [(f"http://127.0.0.1:{self.port}/", "/stub/browser")])
        self.assertIsNone(self.spawned[0].poll())

    def test_it_serves_the_setup_page_and_its_checks_and_nothing_is_made(self):
        self.assertTrue(self.start())
        status, page = get(self.port, "/", {"Host": f"127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)
        token = json.loads(re.search(rb'id="clark-boot">(.*?)</script>', page).group(1))["token"]
        status, body = get(self.port, "/api/setup/checks", {"Host": f"127.0.0.1:{self.port}", "X-Clark-Token": token})
        answer = json.loads(body)
        self.assertEqual((status, answer["ok"]), (200, True))
        self.assertEqual(answer["folder"].endswith("refused/clark"), True)
        self.assertFalse(self.folder.exists())
        self.assertFalse(self.folder.parent.exists())

    def test_the_normal_routes_are_not_served(self):
        self.assertTrue(self.start())
        host = {"Host": f"127.0.0.1:{self.port}"}
        self.assertEqual(get(self.port, "/past", host)[0], 404)
        self.assertEqual(get(self.port, "/api/projects", host)[0], 403)

    def test_a_bad_port_or_no_folder_stops_with_a_line_and_a_code(self):
        import subprocess, sys
        for args in (["--data", str(self.folder), "--port", "nope"], ["--port", "8800"], []):
            done = subprocess.run([sys.executable, "-m", "clark.setup_mode", *args], cwd=str(SRC), capture_output=True,
                                  text=True, encoding="utf-8", env={"PYTHONPATH": str(SRC)}, timeout=30, stdin=subprocess.DEVNULL)
            self.assertEqual(done.returncode, 2, args)
            self.assertNotIn("Traceback", done.stderr, args)
            self.assertTrue(done.stderr.strip(), args)


if __name__ == "__main__":
    unittest.main()
