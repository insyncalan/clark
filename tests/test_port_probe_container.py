"""#575: the free-port probe asks the address the server will bind. On a Mac that is 127.0.0.1; in the Docker container it is the
container's bind address, so a program listening on another of the container's addresses makes the port count as taken.
Run: python3 dev/run_tests.py test_port_probe_container
Reads and writes nothing on disk. Listens on this machine's loopback only (127.0.0.2 stands for "another address of the machine"; macOS has no such address, so the class skips there).
"""
import errno
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


class FakeProbe:
    """Stands for the probe socket, so these run on a Mac too: records the bind address and whether it was closed."""
    made = []

    def __init__(self, bind_error=None):
        self.bind_error, self.address, self.closed = bind_error, None, 0
        FakeProbe.made.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def setsockopt(self, *a):
        pass

    def bind(self, address):
        self.address = address
        if self.bind_error:
            raise self.bind_error

    def close(self):
        self.closed += 1


class ProbeWithoutASecondAddress(unittest.TestCase):
    def probe(self, container, bind_error=None):
        FakeProbe.made = []
        with mock.patch.object(platform, "container_mode", lambda: container), \
                mock.patch.object(launcher.socket, "socket", lambda *a: FakeProbe(bind_error)):
            try:
                return launcher.port_free(8766), FakeProbe.made[0]
            finally:
                self.assertEqual(len(FakeProbe.made), 1)

    def test_in_the_container_the_address_asked_is_the_one_the_server_binds(self):
        free, sock = self.probe(True)
        self.assertEqual((free, sock.address), (True, (launcher.server.CONTAINER_BIND, 8766)))
        self.assertEqual(launcher.server.CONTAINER_BIND, "0.0.0.0")

    def test_outside_the_container_the_address_asked_is_127_0_0_1(self):
        free, sock = self.probe(False)
        self.assertEqual((free, sock.address), (True, ("127.0.0.1", 8766)))

    def test_a_port_in_use_is_not_free(self):
        free, sock = self.probe(False, OSError(errno.EADDRINUSE, "Address already in use"))
        self.assertFalse(free)

    def test_permission_denied_is_not_port_busy(self):
        for container in (False, True):
            with self.subTest(container=container):
                FakeProbe.made = []
                err = OSError(errno.EACCES, "Permission denied")
                with mock.patch.object(platform, "container_mode", lambda: container), \
                        mock.patch.object(launcher.socket, "socket", lambda *a: FakeProbe(err)):
                    with self.assertRaises(OSError) as ctx:
                        launcher.port_free(80)
                self.assertEqual(ctx.exception.errno, errno.EACCES)

    def test_the_probe_socket_is_closed_on_success_busy_and_error(self):
        for error in (None, OSError(errno.EADDRINUSE, "busy"), OSError(errno.EACCES, "denied")):
            with self.subTest(error=error):
                FakeProbe.made = []
                with mock.patch.object(platform, "container_mode", lambda: True), \
                        mock.patch.object(launcher.socket, "socket", lambda *a: FakeProbe(error)):
                    try:
                        launcher.port_free(8766)
                    except OSError:
                        pass
                self.assertEqual([s.closed for s in FakeProbe.made], [1])


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
