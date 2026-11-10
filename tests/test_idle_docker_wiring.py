"""Row 1080, mutation sweep: the launcher's wiring of the idle watch (the one line of __main__ that gives server.set_idle a
watcher). With the launcher's mark in Docker the server is given no watcher at all; outside Docker the mark gives one, with the
environment's times; without the mark there is never one, in or out of Docker. Headless: server.serve and server.set_idle are
stood in for, the container check is patched, no port is probed.

Run: python3 dev/run_tests.py test_idle_docker_wiring
"""
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from clark import __main__ as launcher
from clark import idle


class FakeServe:
    """Stands in for server.serve: prints the server's own line (the launcher reads it) and returns 0."""

    def __call__(self, **kw):
        print("Open http://127.0.0.1:%d/ to use the report editor. Leave this window open; press Ctrl+C to stop." % kw["port"],
              file=kw["out"], flush=True)
        return 0


class IdleWiring(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def given(self, environ, in_container):
        """What main handed server.set_idle for a run with this environment, in or out of a container."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(launcher.platform, "container_mode", lambda: in_container), \
                mock.patch.object(launcher.server, "set_idle") as set_idle:
            code = launcher.main(["--data", str(self.tmp / "data"), "--port", "8123"], out=out, err=err, serve=FakeServe(),
                                 home=self.tmp, onedrive_roots=[], environ=environ, is_free=lambda port: True)
        self.assertEqual((code, err.getvalue()), (0, ""))
        (call,) = set_idle.call_args_list
        return call[0][0]

    def test_in_docker_the_launcher_mark_gives_no_watcher(self):
        self.assertIsNone(self.given({"CLARK_LAUNCHED": "1"}, in_container=True))

    def test_outside_docker_the_launcher_mark_gives_a_watcher_with_the_environments_times(self):
        watcher = self.given({"CLARK_LAUNCHED": "1", "CLARK_STOP_AFTER": "0.5", "CLARK_STOP_CHECK": "0.05"}, in_container=False)
        self.assertIsInstance(watcher, idle.Idle)
        self.assertEqual((watcher.stop_after, watcher.check), (0.5, 0.05))

    def test_without_the_mark_there_is_no_watcher_in_or_out_of_docker(self):
        self.assertIsNone(self.given({}, in_container=False))
        self.assertIsNone(self.given({"CLARK_LAUNCHED": "0"}, in_container=True))


if __name__ == "__main__":
    unittest.main()
