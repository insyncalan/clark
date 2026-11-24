"""#575: the free-port probe asks the address the server will bind. On a Mac that is 127.0.0.1; in the Docker container it is the
container's bind address, so a program listening on another of the container's addresses makes the port count as taken.
Run: python3 dev/run_tests.py test_port_probe_container
Reads and writes nothing on disk. Listens on this machine's loopback only (127.0.0.2 stands for "another address of the machine"; macOS has no such address, so the class skips there).
"""
import socket
import unittest
from unittest import mock

import _paths  # noqa: F401
from clark import __main__ as launcher, platform


class PortProbe(unittest.TestCase):
    def setUp(self):
        self.other = socket.socket()
        self.addCleanup(self.other.close)
        try:
            self.other.bind(("127.0.0.2", 0))            # a listener on an address that is not 127.0.0.1
        except OSError as e:                             # macOS has no 127.0.0.2; only the bind may skip, nothing else
            raise unittest.SkipTest("cannot bind 127.0.0.2 here: %s" % e)
        self.other.listen(1)
        self.port = self.other.getsockname()[1]

    def test_outside_the_container_only_127_0_0_1_is_asked(self):
        with mock.patch.object(platform, "container_mode", lambda: False):
            self.assertTrue(launcher.port_free(self.port))

    def test_in_the_container_a_listener_on_another_address_takes_the_port(self):
        with mock.patch.object(platform, "container_mode", lambda: True):
            self.assertFalse(launcher.port_free(self.port))

    def test_in_the_container_a_free_port_is_free(self):
        spare = socket.socket()
        self.addCleanup(spare.close)
        spare.bind(("127.0.0.1", 0))
        port = spare.getsockname()[1]
        spare.close()
        with mock.patch.object(platform, "container_mode", lambda: True):
            self.assertTrue(launcher.port_free(port))


class SkipsWhereThereIsNoSecondAddress(unittest.TestCase):
    def run_probe(self, bind_error):
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(PortProbe)
        result = unittest.TestResult()
        with mock.patch.object(socket.socket, "bind", side_effect=bind_error):
            suite.run(result)
        return result

    def test_a_failing_bind_skips_every_test(self):
        result = self.run_probe(OSError(49, "Can't assign requested address"))
        self.assertEqual((result.testsRun, len(result.skipped), len(result.errors), len(result.failures)), (3, 3, 0, 0))

    def test_only_an_oserror_skips(self):
        result = self.run_probe(RuntimeError("not a bind refusal"))
        self.assertEqual((len(result.skipped), len(result.errors)), (0, 3))


if __name__ == "__main__":
    unittest.main()
