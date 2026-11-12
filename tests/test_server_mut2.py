"""Mutation-check survivors in server.py: each test pins a behaviour a hand-made mutant got past (dev marker, Host header,
peer table, page-load rule).

Run: python3 dev/run_tests.py test_server_mut2
"""
import os
import sys
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src on the path)
from clark import server as sv


def dev(html):
    with mock.patch.dict(os.environ, {"CLARK_DEV": "1"}):
        return sv.with_boot(html)


class DevMarkerShape(unittest.TestCase):
    def test_ribbon_goes_right_after_the_body_tag_with_attributes(self):
        out = dev('<!doctype html><html><head><title>clark</title></head><body class="a">x</body></html>')
        self.assertIn('<body class="a">' + sv.DEV_RIBBON + "x", out)

    def test_ribbon_not_put_in_the_head_or_doctype(self):
        out = dev("<!doctype html><html><head><title>clark</title></head><body>x</body></html>")
        self.assertTrue(out.startswith("<!doctype html><html><head><title>DEV clark</title></head><body>" + sv.DEV_RIBBON))

    def test_no_body_tag_means_no_ribbon_and_nothing_cut(self):
        out = sv.dev_marked("<p>no body</p>")
        self.assertEqual(out, "<p>no body</p>")

    def test_only_the_first_title_is_marked(self):
        out = sv.dev_marked("<html><title>clark</title><body><svg><title>clark</title></svg></body></html>")
        self.assertEqual(out.count("<title>DEV clark"), 1)
        self.assertIn("<svg><title>clark</title>", out)

    def test_a_title_that_is_not_clark_is_left_alone(self):
        self.assertIn("<title>Other</title>", sv.dev_marked("<title>Other</title><body>x</body>"))


class BootPlacement(unittest.TestCase):
    def test_boot_goes_before_the_last_closing_body(self):
        out = sv.with_boot("<body><script>var s='</body>';</script></body>")
        self.assertLess(out.index("var s='</body>'"), out.index('id="clark-boot"'))
        self.assertTrue(out.endswith("</body>"))

    def test_boot_goes_in_even_when_the_page_starts_with_closing_body(self):
        out = sv.with_boot("</body>")
        self.assertTrue(out.startswith('<script type="application/json" id="clark-boot">'))
        self.assertTrue(out.endswith("</body>"))


class HostHeader(unittest.TestCase):
    def test_host_name_parts(self):
        self.assertEqual(sv.host_name("localhost:8766"), "localhost")
        self.assertEqual(sv.host_name("[::1]:8766"), "::1")
        self.assertEqual(sv.host_name(" 127.0.0.1:80 "), "127.0.0.1")
        self.assertEqual(sv.host_name(" [::1]:80"), "::1")

    def test_port_edges(self):
        self.assertTrue(sv.host_allowed("localhost:65535"))
        self.assertTrue(sv.host_allowed("localhost:1"))
        self.assertFalse(sv.host_allowed("localhost:0"))
        self.assertFalse(sv.host_allowed("localhost:65536"))

    def test_port_of_six_digits_is_refused_even_with_leading_zero(self):
        self.assertFalse(sv.host_allowed("localhost:065535"))
        self.assertFalse(sv.host_allowed("127.0.0.1:000080"))

    def test_bare_ipv6_without_brackets_is_refused(self):
        self.assertFalse(sv.host_allowed("::1"))
        self.assertFalse(sv.host_allowed("::1:8766"))
        self.assertTrue(sv.host_allowed("[::1]"))

    def test_trailing_text_is_refused(self):
        self.assertFalse(sv.host_allowed("localhost.evil.com"))
        self.assertFalse(sv.host_allowed("localhost:80x"))


class GatewayTable(unittest.TestCase):
    HEAD = "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT\n"

    def hexip(self, a, b, c, d):
        return format(int.from_bytes(bytes([a, b, c, d]), sys.byteorder), "08X")

    def row(self, dest, gw, flags, mask):
        return f"eth0\t{dest}\t{gw}\t{flags}\t0\t0\t0\t{mask}\t0\t0\t0\n"

    def gateway(self, *rows):
        with mock.patch("builtins.open", mock.mock_open(read_data=self.HEAD + "".join(rows))):
            return sv.container_gateway()

    def test_a_default_route_gives_its_gateway(self):
        gw = self.hexip(172, 18, 0, 1)
        self.assertEqual(self.gateway(self.row("00000000", gw, "0003", "00000000")), "172.18.0.1")

    def test_a_row_with_a_destination_is_not_the_default(self):
        gw = self.hexip(172, 18, 0, 1)
        self.assertIsNone(self.gateway(self.row(self.hexip(10, 0, 0, 0), gw, "0003", "00000000")))

    def test_a_row_with_a_mask_is_not_the_default(self):
        gw = self.hexip(172, 18, 0, 1)
        self.assertIsNone(self.gateway(self.row("00000000", gw, "0003", "00FFFFFF")))

    def test_a_row_without_the_gateway_flag_is_not_the_default(self):
        gw = self.hexip(172, 18, 0, 1)
        self.assertIsNone(self.gateway(self.row("00000000", gw, "0001", "00000000")))


class PageLoadIsOurs(unittest.TestCase):
    def test_header_values_are_case_and_space_insensitive(self):
        for v in ("None", " SAME-ORIGIN ", "same-origin", "none"):
            self.assertTrue(sv.page_load_is_ours({"Sec-Fetch-Site": v}, 8766), v)
        for v in ("same-site", "cross-site", ""):
            self.assertFalse(sv.page_load_is_ours({"Sec-Fetch-Site": v}, 8766), v)

    def test_origin_may_be_either_loopback_name_on_this_port_only(self):
        self.assertTrue(sv.page_load_is_ours({"Origin": "http://localhost:8766"}, 8766))
        self.assertTrue(sv.page_load_is_ours({"Origin": "http://127.0.0.1:8766"}, 8766))
        self.assertFalse(sv.page_load_is_ours({"Origin": "http://localhost:9"}, 8766))
        self.assertFalse(sv.page_load_is_ours({"Origin": "http://evil.com"}, 8766))


if __name__ == "__main__":
    unittest.main()
