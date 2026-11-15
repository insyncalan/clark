"""item 511: the peer-recording tool (dev/tools/record_container_peer.py) and the rule it reports (server.py local_peer and
container_gateway, design 427). Run: python3 dev/run_tests.py test_record_container_peer
Nothing here needs Docker. What only a real container run can show (the peer Docker presents) is not tested here: it is
recorded by the tool and is on the hand-check sheet."""
import http.client
import io
import json
import socket
import threading
import unittest
from unittest import mock

from _paths import ROOT, SRC  # noqa: F401

import record_container_peer as rec
from clark import server as sv

ROUTE = ("Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT\n"
         "eth0\t00000000\t010012AC\t0003\t0\t0\t0\t00000000\t0\t0\t0\n"
         "eth0\t000012AC\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0\n")


class Rule(unittest.TestCase):
    def patched(self, container=True, gateway="172.18.0.1"):
        return (mock.patch.object(sv, "container_mode", lambda: container),
                mock.patch.object(sv, "container_gateway", lambda: gateway))

    def test_the_gateway_is_the_peer_a_published_port_presents(self):
        a, b = self.patched()
        with a, b:
            r = rec.record("172.18.0.1")
        self.assertEqual(r, {"peer": "172.18.0.1", "gateway": "172.18.0.1", "container_mode": True,
                             "is_gateway": True, "accepted": True})

    def test_any_other_address_is_refused_and_says_so(self):
        a, b = self.patched()
        with a, b:
            for peer in ("172.18.0.5", "192.168.65.1", "10.0.0.2", "::1x"):
                r = rec.record(peer)
                self.assertFalse(r["accepted"], peer)
                self.assertFalse(r["is_gateway"], peer)

    def test_loopback_is_accepted_but_is_not_the_gateway(self):
        a, b = self.patched()
        with a, b:
            r = rec.record("127.0.0.1")
        self.assertTrue(r["accepted"])
        self.assertFalse(r["is_gateway"])

    def test_outside_a_container_the_gateway_is_not_trusted(self):
        a, b = self.patched(container=False)
        with a, b:
            self.assertFalse(rec.record("172.18.0.1")["accepted"])

    def test_no_readable_default_route_refuses_everything_but_loopback(self):
        a, b = self.patched(gateway=None)
        with a, b:
            r = rec.record("172.18.0.1")
        self.assertFalse(r["accepted"])
        self.assertIsNone(r["gateway"])
        self.assertFalse(r["is_gateway"])

    def test_the_route_table_line_for_172_18_0_1_decodes_to_that_address(self):
        """010012AC read in this machine's byte order (little-endian on every machine clark runs on) is 172.18.0.1."""
        with mock.patch("builtins.open", lambda *a, **k: io.StringIO(ROUTE)), mock.patch.object(sv.sys, "byteorder", "little"):
            self.assertEqual(sv.container_gateway(), "172.18.0.1")


class Tool(unittest.TestCase):
    def test_the_first_request_is_recorded_as_one_json_line(self):
        out = io.StringIO()
        ready = threading.Event()
        result = {}
        real = rec.HTTPServer

        class Probe(real):
            def server_bind(self):
                super().server_bind()
                result["port"] = self.server_address[1]
                ready.set()

        def go():
            with mock.patch.object(rec, "HTTPServer", Probe):
                result["record"] = rec.run("127.0.0.1", 0, out=out)

        t = threading.Thread(target=go)
        t.start()
        self.assertTrue(ready.wait(5))
        c = http.client.HTTPConnection("127.0.0.1", result["port"], timeout=5)
        c.request("GET", "/")
        self.assertEqual(c.getresponse().status, 200)
        c.close()
        t.join(5)
        line = out.getvalue().strip()
        self.assertEqual(len(line.splitlines()), 1)
        data = json.loads(line)
        self.assertEqual(data["peer"], "127.0.0.1")
        self.assertTrue(data["accepted"])
        self.assertEqual(set(data), {"peer", "gateway", "container_mode", "is_gateway", "accepted"})

    def run_tool(self, requests):
        """Run the tool on a free port; send each of requests (a callable taking the port) in order. Returns (output, record)."""
        out = io.StringIO()
        ready = threading.Event()
        result = {}
        real = rec.HTTPServer

        class Probe(real):
            def server_bind(self):
                super().server_bind()
                result["port"] = self.server_address[1]
                ready.set()

        def go():
            with mock.patch.object(rec, "HTTPServer", Probe):
                result["record"] = rec.run("127.0.0.1", 0, out=out)

        t = threading.Thread(target=go)
        t.start()
        self.assertTrue(ready.wait(5))
        for send in requests:
            send(result["port"])
        t.join(10)
        self.assertFalse(t.is_alive())
        return out.getvalue(), result.get("record")

    @staticmethod
    def get(path):
        def send(port):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            c.request("GET", path)
            c.getresponse().read()
            c.close()
        return send

    @staticmethod
    def empty(port):
        socket.create_connection(("127.0.0.1", port), timeout=5).close()

    def test_the_healthcheck_request_is_answered_but_is_not_the_recorded_request(self):
        out, record = self.run_tool([self.get("/health"), self.get("/")])
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertEqual(json.loads(out)["peer"], record["peer"])

    def test_health_paths_are_skipped_and_only_another_path_is_recorded(self):
        """Only the healthcheck arrives, then a real request: the line is printed once, for the real one."""
        out, record = self.run_tool([self.get("/health?x=1"), self.get("/health"), self.get("/anything")])
        self.assertEqual(len(out.strip().splitlines()), 1)

    def test_an_empty_first_connection_does_not_raise(self):
        out, record = self.run_tool([self.empty, self.get("/")])
        self.assertEqual(len(out.strip().splitlines()), 1)
        self.assertEqual(record["peer"], "127.0.0.1")

    def test_the_compose_healthcheck_path_is_the_one_the_tool_skips(self):
        text = (ROOT / "docker/compose.yaml").read_text(encoding="utf-8")
        self.assertIn("8766" + rec.HEALTH_PATH, text)

    def test_the_tool_listens_where_the_container_does(self):
        self.assertEqual(rec.sv.CONTAINER_BIND, "0.0.0.0")

    def test_the_documented_command_names_files_that_exist(self):
        doc = (ROOT / "docs/handoff/design-427-docker-first-start.md").read_text(encoding="utf-8")
        self.assertIn("dev/tools/record_container_peer.py", doc)
        self.assertTrue((ROOT / "dev/tools/record_container_peer.py").is_file())
        self.assertTrue((ROOT / "docker/compose.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
