"""item 575: in the Docker container on the host's own network (--network host) clark says, once, that it listens on every address.
Assumption (ruling held): host networking is told by interfaces other than lo and ethN in /sys/class/net; the warning goes to stderr beside the start line.
Run: python3 dev/run_tests.py test_host_network_warning
Reads a temporary folder only.
"""
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from clark import __main__ as launcher, platform


class HostNetwork(unittest.TestCase):
    def nets(self, *names):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        for n in names:
            (Path(d.name) / n).touch()
        return d.name

    def check(self, container, *names):
        with mock.patch.object(platform, "container_mode", lambda: container):
            return platform.container_on_host_network(self.nets(*names))

    def test_a_bridge_container_is_not_on_the_host_network(self):
        self.assertFalse(self.check(True, "lo", "eth0"))
        self.assertFalse(self.check(True, "lo", "eth0", "eth1"))

    def test_other_interfaces_mean_the_host_network(self):
        for extra in ("docker0", "wlan0", "en0", "br-1a2b", "enp3s0"):
            self.assertTrue(self.check(True, "lo", "eth0", extra), extra)

    def test_tunnel_and_extra_pod_interfaces_are_not_the_host_network(self):
        self.assertFalse(self.check(True, "lo", "eth0", "tunl0", "sit0", "ip6tnl0"))
        self.assertFalse(self.check(True, "lo", "eth0", "net1", "net2"))
        self.assertTrue(self.check(True, "lo", "eth0", "tunl0", "wlan0"))

    def test_never_outside_a_container(self):
        self.assertFalse(self.check(False, "lo", "docker0"))

    def test_an_unreadable_list_is_not_a_warning(self):
        with mock.patch.object(platform, "container_mode", lambda: True):
            self.assertFalse(platform.container_on_host_network("/no/such/folder"))

    def line(self, on_host):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(platform, "container_on_host_network", lambda: on_host):
            w = launcher.ServerOutput(out, None, None, err)
            w.write("Open http://127.0.0.1:8766/ to use clark.\n")
            w.write("Open http://127.0.0.1:8766/ to use clark.\n")
        return err.getvalue()

    def test_the_warning_is_written_once_and_only_on_the_host_network(self):
        self.assertEqual(self.line(True).count(launcher.HOST_NETWORK_WARNING), 1)
        self.assertEqual(self.line(False), "")


if __name__ == "__main__":
    unittest.main()
