"""#427: the container setting in src/clark/server.py (guarded). The default, with no setting, is the Mac's: 127.0.0.1 only.

Run: python3 dev/run_tests.py test_server_container
Only the one setting (CLARK_CONTAINER=1, inside a container) lets the server listen on 0.0.0.0 and trust the container's
gateway as a local peer. Nothing here starts a container or needs Docker.
"""
import http.client
import re
import threading
import unittest
from unittest import mock

from _paths import ROOT, SRC  # noqa: F401  (SRC puts src/ on the path)

from clark import server as sv

ROUTE = ("Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT\n"
         "eth0\t00000000\t010012AC\t0003\t0\t0\t0\t00000000\t0\t0\t0\n"
         "eth0\t000012AC\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0\n")      # default via 172.18.0.1


def in_container(gateway="172.18.0.1"):
    """The server as the shipped container runs it: the setting on, the marker file there, the gateway as given."""
    return (mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1"}),
            mock.patch("os.path.exists", lambda p: p == "/.dockerenv"),
            mock.patch.object(sv, "container_gateway", lambda: gateway))


class Handler:
    """Enough of a request handler for csp_local: a peer, a Host and some headers."""
    def __init__(self, peer, host="127.0.0.1:8766", headers=None):
        self.client_address = (peer, 50000)
        self.headers = {"Host": host, **(headers or {})}

    def host_ok(self):
        return sv.host_allowed(self.headers.get("Host"))


def local(handler):
    return sv.csp_local(handler)


class Default(unittest.TestCase):
    """With no setting nothing changes."""

    def test_it_is_not_container_mode(self):
        self.assertFalse(sv.container_mode())

    def test_only_loopback_peers_are_local(self):
        for peer in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
            self.assertTrue(sv.local_peer(peer), peer)
        for peer in ("172.18.0.1", "172.17.0.1", "192.168.1.10", "10.0.0.5", "0.0.0.0", ""):
            self.assertFalse(sv.local_peer(peer), peer)

    def test_the_gateway_is_not_trusted_without_the_setting(self):
        with mock.patch.object(sv, "container_gateway", lambda: "172.18.0.1"):
            self.assertFalse(sv.local_peer("172.18.0.1"))
            self.assertFalse(local(Handler("172.18.0.1")))

    def test_the_server_still_refuses_every_other_address(self):
        for address in ("0.0.0.0", "", "localhost", "::", "192.168.1.10"):
            with self.assertRaisesRegex(ValueError, "127.0.0.1 only"):
                sv.LocalServer((address, 0))

    def test_the_setting_alone_is_not_enough(self):
        """Set on a Mac (no container marker file): still the Mac's way."""
        with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1"}), mock.patch("os.path.exists", lambda p: False):
            self.assertFalse(sv.container_mode())
            with self.assertRaisesRegex(ValueError, "127.0.0.1 only"):
                sv.LocalServer(("0.0.0.0", 0))
            self.assertFalse(sv.local_peer("172.18.0.1"))

    def test_the_marker_file_alone_is_not_enough(self):
        with mock.patch("os.path.exists", lambda p: p == "/.dockerenv"):
            self.assertFalse(sv.container_mode())

    def test_any_other_value_is_off(self):
        for value in ("", "0", "true", "yes", "1 "):
            with mock.patch.dict("os.environ", {"CLARK_CONTAINER": value}), mock.patch("os.path.exists", lambda p: True):
                self.assertFalse(sv.container_mode(), repr(value))


class InAContainer(unittest.TestCase):
    def setUp(self):
        for patch in in_container():
            patch.start()
            self.addCleanup(patch.stop)

    def test_it_is_container_mode(self):
        self.assertTrue(sv.container_mode())

    def test_the_podman_marker_counts_too(self):
        with mock.patch("os.path.exists", lambda p: p == "/run/.containerenv"):
            self.assertTrue(sv.container_mode())

    def test_it_may_listen_on_0_0_0_0_and_nothing_else_new(self):
        sv.LocalServer(("0.0.0.0", 0)).server_close()
        sv.LocalServer(("127.0.0.1", 0)).server_close()
        for address in ("", "::", "192.168.1.10", "localhost"):
            with self.assertRaisesRegex(ValueError, "127.0.0.1 only"):
                sv.LocalServer((address, 0))

    def test_the_gateway_and_loopback_are_local_and_no_other_peer(self):
        self.assertTrue(sv.local_peer("172.18.0.1"))
        self.assertTrue(sv.local_peer("127.0.0.1"))
        for peer in ("172.18.0.5", "172.18.0.2", "172.17.0.1", "192.168.1.10", "10.0.0.5", ""):
            self.assertFalse(sv.local_peer(peer), peer)

    def test_no_gateway_means_loopback_only(self):
        with mock.patch.object(sv, "container_gateway", lambda: None):
            self.assertFalse(sv.local_peer("172.18.0.1"))
            self.assertFalse(sv.local_peer(""))
            self.assertFalse(sv.local_peer(None))
            self.assertTrue(sv.local_peer("127.0.0.1"))

    def test_the_host_and_origin_checks_are_unchanged(self):
        gateway = "172.18.0.1"
        self.assertTrue(local(Handler(gateway)))
        self.assertTrue(local(Handler(gateway, headers={"Origin": "http://127.0.0.1:8766"})))
        self.assertTrue(local(Handler(gateway, host="localhost:8766")))
        for host in ("evil.example", "172.18.0.1:8766", "0.0.0.0:8766", "127.0.0.1.evil.example", "", None):
            self.assertFalse(local(Handler(gateway, host=host)), repr(host))
        self.assertFalse(local(Handler(gateway, headers={"Origin": "http://evil.example"})))
        self.assertFalse(local(Handler(gateway, headers={"Origin": "http://127.0.0.1:9999"})))
        self.assertFalse(local(Handler(gateway, headers={"Sec-Fetch-Site": "cross-site"})))
        self.assertFalse(local(Handler("172.18.0.5")))


class Compose(unittest.TestCase):
    """The compose file's published port is a security control (see docs/handoff/design-427-docker-first-start.md)."""

    def test_every_published_port_is_on_127_0_0_1_only(self):
        text = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
        ports = re.findall(r'^\s*-\s*"?([0-9][^"\n]*:[0-9]+(?::[0-9]+)?(?:/\w+)?)"?\s*$', text, re.M)
        self.assertTrue(ports, "no published port found")
        for port in ports:
            self.assertTrue(port.startswith("127.0.0.1:"), port)

    def test_the_image_sets_the_container_setting_and_runs_as_a_user_that_is_not_root(self):
        text = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("CLARK_CONTAINER=1", text)
        self.assertRegex(text, r"(?m)^USER clark$")


class ComposeIsLanSafe(unittest.TestCase):
    """The compose file's 127.0.0.1 prefix is the whole defence against the LAN, so the file may say nothing that sidesteps it (#427)."""
    TEXT = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
    CODE = "\n".join(line.split("#", 1)[0] for line in TEXT.splitlines())        # the file without its comments

    def test_it_publishes_exactly_one_port_in_the_short_form_on_loopback(self):
        self.assertEqual(len(re.findall(r"(?m)^\s*ports:\s*$", self.CODE)), 1)
        listed = re.findall(r"(?m)^\s*-\s*(.+?)\s*$", self.CODE.split("ports:", 1)[1].split("volumes:", 1)[0])
        self.assertEqual([p.strip("\"'") for p in listed], ["127.0.0.1:8766:8766"])

    def test_nothing_in_it_can_put_the_container_on_the_hosts_network_or_another_address(self):
        for word in ("network_mode", "host_ip", "0.0.0.0", "expose:", "extra_hosts", "privileged", "pid:", "ipc:"):
            self.assertNotIn(word, self.CODE, word)
        ports_block = self.CODE.split("ports:", 1)[1].split("volumes:", 1)[0]
        for word in ("published:", "target:", "mode:"):                      # the long form of a port (the volume below has its own target)
            self.assertNotIn(word, ports_block, word)
        ports_line = next(line for line in self.CODE.splitlines() if "8766:8766" in line)
        self.assertNotIn("${", ports_line, "the address is not read from the environment")


class GetFromAnotherPeer(unittest.TestCase):
    """A real server, a real request: in container mode the page and /health answer this machine only (#427, a reader's finding:
    GET checked the Host header and nothing else, and the container's 0.0.0.0 bind lets in any peer on the Docker network)."""

    def get(self, path, peer_is_local, container):
        httpd = sv.LocalServer((sv.HOST, 0), page_html=lambda: "<html><head></head><body>ZQ-THE-PAGE</body></html>")
        self.addCleanup(httpd.server_close)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.shutdown)
        with mock.patch.object(sv, "container_mode", lambda: container), mock.patch.object(sv, "local_peer", lambda address: peer_is_local):
            conn = http.client.HTTPConnection(sv.HOST, httpd.server_port, timeout=10)
            try:
                conn.request("GET", path, headers={"Host": f"127.0.0.1:{httpd.server_port}"})
                answer = conn.getresponse()
                return answer.status, answer.read().decode("utf-8", "replace")
            finally:
                conn.close()

    def test_the_page_and_health_are_refused_to_a_peer_that_is_not_this_machine(self):
        for path in ("/", "/health"):
            status, body = self.get(path, peer_is_local=False, container=True)
            self.assertEqual(status, 403, path)
            self.assertNotIn("ZQ-THE-PAGE", body, "no page and no token reach it")
            self.assertNotIn(sv.TOKEN, body)

    def test_the_page_and_health_answer_this_machine_and_the_container_gateway(self):
        self.assertEqual(self.get("/health", peer_is_local=True, container=True)[0], 200)
        status, body = self.get("/", peer_is_local=True, container=True)
        self.assertEqual(status, 200)
        self.assertIn("ZQ-THE-PAGE", body)

    def test_outside_a_container_nothing_changes(self):
        self.assertEqual(self.get("/health", peer_is_local=False, container=False)[0], 200)


class GatewayRead(unittest.TestCase):
    def read(self, text):
        return mock.patch("builtins.open", mock.mock_open(read_data=text))

    def test_the_default_route_is_the_gateway(self):
        with self.read(ROUTE):
            self.assertEqual(sv.container_gateway(), "172.18.0.1")

    def test_a_table_with_no_default_route_is_none(self):
        with self.read(ROUTE.splitlines()[0] + "\n" + ROUTE.splitlines()[2] + "\n"):
            self.assertIsNone(sv.container_gateway())

    def test_nonsense_and_a_missing_file_are_none(self):
        for text in ("", "Iface\n", "Iface\neth0 00000000\n", "Iface\neth0 00000000 zz 0003\n"):
            with self.read(text):
                self.assertIsNone(sv.container_gateway(), repr(text))
        with mock.patch("builtins.open", side_effect=FileNotFoundError):
            self.assertIsNone(sv.container_gateway())


class Ipv4OnlyListener(unittest.TestCase):
    """#462 (1): the peer check is IPv4 only on purpose. The listener is an IPv4 socket, so no request has an IPv6 peer; if that
    ever changes, these fail and the change must add the IPv6 gateway (/proc/net/ipv6_route) with its own tests."""

    def test_the_listener_is_ipv4_only(self):
        import socket
        self.assertEqual(sv.LocalServer.address_family, socket.AF_INET)

    def test_an_ipv6_peer_is_refused_in_a_container(self):
        with mock.patch.object(sv, "container_mode", lambda: True), mock.patch.object(sv, "container_gateway", lambda: "172.18.0.1"):
            for peer in ("fe80::1", "fd00::1", "2001:db8::1", "::ffff:172.18.0.2"):
                self.assertFalse(sv.local_peer(peer), peer)
            self.assertTrue(sv.local_peer("172.18.0.1"))


if __name__ == "__main__":
    unittest.main()
