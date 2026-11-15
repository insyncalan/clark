"""Row 626: dev/tools/docker_smoke.py, the Docker smoke test. Its logic is run against a small stand-in server and a stand-in docker
command, so it needs no Docker; one test runs the real thing and is skipped unless docker is on the path.
Run: python3 dev/run_tests.py test_docker_smoke   (quick tier)"""
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dev" / "tools"))
import docker_smoke as smoke  # noqa: E402

TOKEN = "tok-123"


def make_handler(leak_host=False, leak_token=False, health_ok=True, no_token_in_page=False):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, status, body, kind="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def host_bad(self):
            return not leak_host and not (self.headers.get("Host") or "").startswith("127.0.0.1")

        def do_GET(self):
            if self.host_bad():
                return self.reply(403, {"ok": False})
            if self.path == "/health":
                return self.reply(200, {"ok": health_ok, "version": "1.0.0"})
            boot = "{}" if no_token_in_page else json.dumps({"token": TOKEN})
            self.reply(200, f'<script type="application/json" id="clark-boot">{boot}</script>'.encode(), "text/html")

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self.host_bad():
                return self.reply(403, {"ok": False})
            if not leak_token and self.headers.get(smoke.TOKEN_HEADER) != TOKEN:
                return self.reply(403, {"ok": False})
            self.reply(200, {"ok": True})
    return H


class Fake:
    """A stand-in server on a free port, and a stand-in docker command that notes what it was asked."""

    def __init__(self, test, up_rc=0, serve=True, **kw):
        self.calls = []
        self.up_rc = up_rc
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), make_handler(**kw))
        self.port = self.server.server_address[1]
        self.serving = serve
        if serve:
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
        test.addCleanup(self.stop)

    def stop(self):
        if self.serving:
            self.server.shutdown()
        self.server.server_close()

    def command(self, args, **kw):
        self.calls.append(args[-1] if args[-1] in ("down",) else args[-2:])
        rc = self.up_rc if args[-2:] == ["up", "-d"] else 0
        return subprocess.CompletedProcess(args, rc, "", "")

    def go(self, wait=3):
        lines = []
        rc = smoke.run(self.port, wait, command=self.command, pause=lambda s: None, say=lines.append)
        return rc, lines


class Logic(unittest.TestCase):
    def test_a_good_clark_passes_every_check_and_is_stopped(self):
        f = Fake(self)
        rc, lines = f.go()
        self.assertEqual(0, rc, lines)
        self.assertEqual(6, len(lines))
        self.assertTrue(all(l.startswith("PASS") for l in lines), lines)
        self.assertEqual(["up", "-d"], f.calls[0])
        self.assertEqual("down", f.calls[-1])

    def test_a_foreign_host_let_in_fails(self):
        rc, lines = Fake(self, leak_host=True).go()
        self.assertEqual(1, rc)
        self.assertEqual(2, sum(l.startswith("FAIL") and "foreign Host" in l for l in lines), lines)

    def test_a_change_without_a_token_let_in_fails(self):
        rc, lines = Fake(self, leak_token=True).go()
        self.assertEqual(1, rc)
        self.assertEqual(2, sum(l.startswith("FAIL") and "token is refused" in l for l in lines), lines)

    def test_health_not_ok_fails(self):
        rc, lines = Fake(self, health_ok=False).go()
        self.assertEqual(1, rc)
        self.assertTrue(lines[0].startswith("FAIL"), lines)

    def test_a_page_with_no_token_fails(self):
        rc, lines = Fake(self, no_token_in_page=True).go()
        self.assertEqual(1, rc)
        self.assertTrue(lines[1].startswith("FAIL"), lines)

    def test_compose_up_failing_is_2_and_still_runs_down(self):
        f = Fake(self, up_rc=1)
        rc, lines = f.go()
        self.assertEqual(2, rc)
        self.assertEqual("down", f.calls[-1])

    def test_a_clark_that_never_answers_is_2_and_is_stopped(self):
        f = Fake(self, serve=False)
        rc, lines = f.go(wait=2)
        self.assertEqual(2, rc)
        self.assertEqual("down", f.calls[-1])

    def test_compose_is_given_the_port_to_publish(self):
        f = Fake(self)
        ports = []
        orig = f.command
        f.command = lambda args, env=None, **kw: (ports.append(env["CLARK_PORT"]), orig(args, env=env, **kw))[1]
        f.go()
        self.assertEqual({str(f.port)}, set(ports))

    def test_the_data_folder_is_new_and_removed(self):
        f = Fake(self)
        seen = []
        orig = f.command
        f.command = lambda args, env=None, **kw: (seen.append(env["CLARK_DATA_DIR"]), orig(args, env=env, **kw))[1]
        f.go()
        self.assertEqual(1, len(set(seen)))
        self.assertFalse(Path(seen[0]).exists())


class Real(unittest.TestCase):
    @unittest.skipIf(shutil.which("docker") is None, "docker is not on the path")
    @unittest.skipUnless(os.environ.get("CLARK_SMOKE_DOCKER") == "1", "set CLARK_SMOKE_DOCKER=1 to run the real image")
    def test_the_real_image_passes(self):
        self.assertEqual(0, smoke.run(8799, 120))


if __name__ == "__main__":
    unittest.main()
