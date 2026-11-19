"""Row 1327: a test never reaches the real network by default.

The updater looks for the newest release on its own the first time the page asks for the status. Tests that build an Updater
without giving it a release_opener must not make that call: the shared test helper (tests/_paths.py) swaps the updater's default
opener for one that fails like an offline computer. Production keeps the real opener.

Run: python3 dev/run_tests.py test_no_network_in_tests_1327
"""
import socket
import tempfile
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401  (puts src/ on the path and blocks the network for the tests)
from clark import release_fetch, updater


class NoNetworkTest(unittest.TestCase):
    def test_the_default_opener_in_tests_is_not_the_real_one(self):
        self.assertIsNot(release_fetch.default_opener, release_fetch.real_opener)
        self.assertEqual("no_network", release_fetch.default_opener.__name__)

    def test_production_keeps_the_real_opener(self):
        self.assertTrue(callable(release_fetch.real_opener))
        self.assertEqual("real_opener", release_fetch.real_opener.__name__)

    def test_an_updater_without_an_opener_gets_the_blocked_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            up = updater.Updater(tmp, Path(tmp) / "clark.db", 8765)
            self.assertIs(release_fetch.default_opener, up.release_opener)

    def test_the_blocked_opener_fails_like_an_offline_computer_and_opens_no_socket(self):
        opened = []
        real = socket.socket.connect
        socket.socket.connect = lambda self, addr: opened.append(addr) or real(self, addr)
        try:
            with self.assertRaises(release_fetch.FetchError) as ctx:
                release_fetch.latest("mac", release_fetch.default_opener)
        finally:
            socket.socket.connect = real
        self.assertEqual("offline", ctx.exception.key)
        self.assertEqual([], opened)


if __name__ == "__main__":
    unittest.main()
