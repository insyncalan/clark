"""Row 1076, loose end: server.host_allowed and server.page_load_is_ours against hostile Host and Origin headers (tests only).

The spellings a browser never sends but a hand-made request can: dots that are not dots (U+3002, U+FF0E, U+2024), IDN and
look-alike letters, percent-encoding, NUL and other controls, 64 KB values, every IPv6 form but the one allowed, port 0 and
ports with leading noughts, double colons. Each pins what the two functions answer today: host_allowed is a full match of one
regular expression (nothing else passes); page_load_is_ours is an exact comparison with three spellings. A test marked
expectedFailure records a wrong answer of no consequence (page_load_is_ours reads only the first of two Origin or
Sec-Fetch-Site headers where csp_local reads every one; a plain load from a browser sends one or none, and a hand-made request
that wants to count as a window needs no token anyway): recorded, not fixed; it flips to "unexpected success" when hardened.
The real server (test_server.Running) answers the same headers over a socket, so the HTTP layer's own limits are seen too.

Run: python3 dev/run_tests.py test_server_host_hostile
"""
import http.client
import time
import unittest

import _paths  # noqa: F401
from clark import server as sv
import importlib

# Taken by name, not by an import line: Running and raw_reply start no browser, so this file is quick tier, and
# tests/test_run_tests reads an import line of test_server as a browser file.
_harness = importlib.import_module("test_server")
Running, raw_reply = _harness.Running, _harness.raw_reply

PORT = 8766
ALLOWED = ("127.0.0.1", "localhost", "clark.localhost", "[::1]")
OURS = tuple(f"http://{h}:{PORT}" for h in ("127.0.0.1", "localhost", "clark.localhost"))
BIG = 1 << 16

ODD_DOTS = ("。", "．", "․", "։", "۔", "・")       # ideographic full stop, fullwidth stop, one dot leader, Armenian and Arabic stops, katakana middle dot


def with_odd_dots(name):
    return [name.replace(".", d) for d in ODD_DOTS]


class HostAllowed(unittest.TestCase):
    def refused(self, *hosts):
        for host in hosts:
            with self.subTest(host=host if host is None or len(host) < 60 else f"<{len(host)} chars> {host[:20]!r}"):
                self.assertFalse(sv.host_allowed(host))

    def test_the_allowed_spellings_with_or_without_a_port(self):
        for host in ALLOWED:
            self.assertTrue(sv.host_allowed(host), host)
            self.assertTrue(sv.host_allowed(f"{host}:{PORT}"), host)
            self.assertTrue(sv.host_allowed(f"{host}:1"), host)
            self.assertTrue(sv.host_allowed(f"{host}:65535"), host)

    def test_a_dot_that_is_not_a_dot(self):
        self.refused(*with_odd_dots("127.0.0.1"), *with_odd_dots("clark.localhost"), *with_odd_dots(f"clark.localhost:{PORT}"),
                     "127。0.0.1", "clark。localhost")

    def test_idn_and_look_alike_letters(self):
        self.refused("xn--clark-xyz.localhost", "xn--localhost", "xn--clark.localhost", "xn--lcalhost-6ya", "clärk.localhost",
                     "lоcalhost", "clark.lоcalhost", "ⅼocalhost", "localhoѕt", "clark.localhost​", "clark​.localhost",
                     "locаlhost", "clark.localhosт", "﻿127.0.0.1", "127.0.0.1⁠", "ⅼocalhost", "ℓocalhost")

    def test_percent_encoding(self):
        self.refused("127%2E0%2E0%2E1", "clark%2Elocalhost", "localhost%00", "localhost%2E", "%6Cocalhost", "127.0.0.1%3A8766",
                     f"clark.localhost:%3{PORT}", "%5B::1%5D", "[::1]%3A8766", "localhost%20", "%0Alocalhost")

    def test_nul_and_other_controls(self):
        self.refused("localhost\x00", "localhost\x00.evil.example", "\x00localhost", "clark.localhost\x00:8766", "localhost:\x008766",
                     "127.0.0.1\x00", "[::1]\x00", "localhost\n", "localhost\r\n", "localhost\r", "localhost\t", "\tlocalhost",
                     "localhost\x0b", "localhost\x0c", "localhost\x1b", "localhost\x7f", "localhost:8766\n", "localhost\n:8766",
                     " localhost", "localhost ", "127.0.0.1 :8766", "127.0.0.1: 8766", " localhost", "localhost ")

    def test_sixty_four_kilobyte_values_are_refused_at_once(self):
        for host in ("a" * BIG, "localhost:" + "9" * BIG, "localhost" + "\x00" * BIG, "127.0.0.1" + " " * BIG, "[" + ":" * BIG + "]",
                     "localhost:" + "0" * (BIG - 1) + "1", "localhost" * (BIG // 9), f"clark.localhost:{PORT}" + "." * BIG, "." * BIG,
                     "127.0.0.1" * (BIG // 9), "[::1]" * (BIG // 5), ":" * BIG, "。" * BIG, "%" * BIG):
            t0 = time.monotonic()
            self.assertFalse(sv.host_allowed(host))
            self.assertLess(time.monotonic() - t0, 0.5, "a full match that fails early, not a scan")

    def test_only_the_one_ipv6_spelling(self):
        self.assertTrue(sv.host_allowed("[::1]"))
        self.refused("[0:0:0:0:0:0:0:1]", "[::ffff:127.0.0.1]", "[::ffff:7f00:1]", "[::1%lo0]", "[::1%25lo0]", "::1", "[::1]:", "[::1]]",
                     "[[::1]]", "[::01]", "[::0001]", "[0::1]", "[::1]:8766:", "[::1", "::1]", "[::1]::8766", "[::1].", "[::1]:8766]",
                     "[::1]x:8766", "[::1]:8766x", "[ ::1]", "[::1 ]", "[::2]", "[::]", "[]", "[", "]", "[::1]:[8766]", "[::1]:80:80",
                     "[fe80::1]", "[::1.evil.example]", "[::1]:8766@evil.example", "[::1]:8766/", "[::1]@evil.example")

    def test_port_nought_and_ports_out_of_range(self):
        for host in ALLOWED:
            self.refused(f"{host}:0", f"{host}:00", f"{host}:00000", f"{host}:65536", f"{host}:99999", f"{host}:100000", f"{host}:",
                         f"{host}:-1", f"{host}:+8766", f"{host}:8766.0", f"{host}:0x2240", f"{host}:8766 ", f"{host}: 8766")

    def test_a_port_with_leading_noughts_is_read_as_its_number(self):
        # pinned as it is: "08766" is five digits naming 8766 (one to five digits, 1 to 65535); a browser never spells a port so, and the
        # name is still this machine's, so nothing is let in that was not already. Not the same for page_load_is_ours (exact spelling).
        for host in ALLOWED:
            self.assertTrue(sv.host_allowed(f"{host}:0{PORT}"), host)
            self.assertTrue(sv.host_allowed(f"{host}:00080"), host)
            self.assertTrue(sv.host_allowed(f"{host}:01"), host)
            self.assertFalse(sv.host_allowed(f"{host}:000080"), "six digits: never")

    def test_digits_that_are_not_ascii_digits(self):
        self.refused("localhost:٨٧٦٦", "localhost:８７６６", "localhost:8٧٦٦",
                     "localhost:²", "localhost:①", "localhost:8766​", "127.0.0.١", "١٢٧.0.0.1")

    def test_double_colons_and_colons_alone(self):
        self.refused("localhost::8766", "localhost:8766:8766", "127.0.0.1::", "localhost::", "clark.localhost::8766", "127.0.0.1:8766:",
                     ":8766", "::", ":", "localhost:8766:", "::localhost", ":localhost", "127.0.0.1:8766:80", "clark.localhost:::8766")

    def test_case_trailing_dots_and_other_spellings_of_this_machine(self):
        self.refused("LOCALHOST", "Localhost", "CLARK.LOCALHOST", "Clark.Localhost", "127.0.0.1".replace("0", "O"), "localhost.",
                     "clark.localhost.", "127.0.0.1.", ".localhost", "localhost..", ".clark.localhost", "127.1", "127.000.000.001",
                     "0177.0.0.1", "2130706433", "0x7f000001", "127.0.0.1.1", "127.0.0.01", "127.0.0.1.localhost", "127.0.0.2",
                     "0.0.0.0", "localhost.localdomain", "clark", "www.clark.localhost", "a.clark.localhost")

    def test_a_path_a_scheme_or_a_user_part(self):
        self.refused("http://localhost", "localhost/", "localhost/x", "localhost?x", "localhost#x", "user@localhost", "localhost@evil.example",
                     "localhost:8766@evil.example", "evil.example@localhost", "localhost\\evil.example", "localhost;x", "localhost,localhost")

    def test_nothing_at_all(self):
        self.refused("", None)


class PageLoadIsOurs(unittest.TestCase):
    def ours(self, **headers):
        return sv.page_load_is_ours(headers, PORT)

    def refused(self, *origins):
        for origin in origins:
            with self.subTest(origin=origin if len(origin) < 60 else f"<{len(origin)} chars> {origin[:24]!r}"):
                self.assertFalse(self.ours(Origin=origin))

    def test_the_three_spellings_and_none(self):
        for origin in OURS:
            self.assertTrue(self.ours(Origin=origin), origin)
        self.assertTrue(self.ours())

    def test_the_ipv6_loopback_is_not_among_them(self):
        # pinned as it is: a page opened by hand at http://[::1]:PORT sends no Origin on a plain load (and Sec-Fetch-Site none or same-origin),
        # so it still counts; only a load that carries that Origin (a form post, a cross-origin navigation) does not
        self.refused(f"http://[::1]:{PORT}", f"http://[0:0:0:0:0:0:0:1]:{PORT}", f"http://[::ffff:127.0.0.1]:{PORT}")

    def test_a_dot_that_is_not_a_dot_idn_look_alikes_and_percent_encoding(self):
        self.refused(*[f"http://{h}:{PORT}" for h in with_odd_dots("clark.localhost") + with_odd_dots("127.0.0.1")],
                     f"http://xn--clark-xyz.localhost:{PORT}", f"http://clärk.localhost:{PORT}", f"http://lоcalhost:{PORT}",
                     f"http://clark%2Elocalhost:{PORT}", f"http://127%2E0%2E0%2E1:{PORT}", f"http://localhost%00:{PORT}", f"http%3A//localhost:{PORT}")

    def test_nul_controls_and_whitespace(self):
        for origin in OURS:
            self.refused(origin + "\x00", origin.replace(":" + str(PORT), "\x00:" + str(PORT)), "\x00" + origin, origin + "\n", origin + "\t",
                         origin + " ", " " + origin, origin + "\r\n", origin.replace("//", "//\x00"), origin + "​")

    def test_sixty_four_kilobyte_values(self):
        for origin in (OURS[0] + "\x00" * BIG, "http://" + "a" * BIG + f":{PORT}", "a" * BIG, OURS[0] + "/" + "x" * BIG, OURS[0] * (BIG // 20),
                       "http://" + "clark.localhost" * (BIG // 15) + f":{PORT}"):
            t0 = time.monotonic()
            self.assertFalse(self.ours(Origin=origin))
            self.assertLess(time.monotonic() - t0, 0.5)
        self.assertFalse(sv.page_load_is_ours({"Sec-Fetch-Site": "a" * BIG}, PORT))

    def test_port_nought_leading_noughts_double_colons_and_no_port(self):
        for host in ("127.0.0.1", "localhost", "clark.localhost"):
            self.refused(f"http://{host}:0", f"http://{host}:0{PORT}", f"http://{host}", f"http://{host}::{PORT}", f"http://{host}:{PORT}:{PORT}",
                         f"http://{host}:{PORT}:", f"http://{host}:{PORT + 1}", f"http://{host}:{PORT}0", f"http://{host}:{PORT}.0")

    def test_case_scheme_path_user_part_and_a_list(self):
        for origin in OURS:
            self.refused(origin.upper(), origin.replace("http", "HTTP"), origin.replace("http", "https"), origin.replace("http://", "//"),
                         origin.replace("http://", "http:/"), origin.replace("http://", "http:///"), origin + "/", origin + "/x", origin + "?x",
                         origin + "#", origin.replace("//", "//user@"), origin + "@evil.example", origin + ", https://evil.example",
                         f"https://evil.example, {origin}", origin + "." , "null", "")

    def test_sec_fetch_site_spellings(self):
        for site in ("none", "None", "NONE", " none ", "same-origin", "Same-Origin", " same-origin ", "none\n"):
            self.assertTrue(sv.page_load_is_ours({"Sec-Fetch-Site": site}, PORT), site)
        for site in ("cross-site", "same-site", "same-origin, cross-site", "same-origin,", ",same-origin", "", " ", "\x00", "none\x00",
                     "nonе", "same‐origin", "same_origin", "sameorigin", "no ne", "none none", "null"):
            with self.subTest(site=site):
                self.assertFalse(sv.page_load_is_ours({"Sec-Fetch-Site": site}, PORT))

    def test_an_own_origin_with_a_cross_site_mark_is_not_ours(self):
        for origin in OURS:
            self.assertFalse(sv.page_load_is_ours({"Origin": origin, "Sec-Fetch-Site": "cross-site"}, PORT), origin)
            self.assertTrue(sv.page_load_is_ours({"Origin": origin, "Sec-Fetch-Site": "same-origin"}, PORT), origin)

    def test_a_foreign_origin_first_is_refused_whatever_follows(self):
        m = http.client.HTTPMessage()
        m["Origin"] = "https://evil.example"
        m["Origin"] = OURS[0]
        self.assertFalse(sv.page_load_is_ours(m, PORT))
        m = http.client.HTTPMessage()
        m["Sec-Fetch-Site"] = "cross-site"
        m["Sec-Fetch-Site"] = "none"
        self.assertFalse(sv.page_load_is_ours(m, PORT))

    @unittest.expectedFailure
    def test_a_second_origin_header_counts_as_csp_local_counts_every_one(self):
        # today: headers.get("Origin") is the first value only, so own-then-foreign passes; csp_local reads get_all. A browser sends one Origin
        # at most, and this answer only decides whether a launcher-started server stays up, which any local request may ask for without a token.
        m = http.client.HTTPMessage()
        m["Origin"] = OURS[0]
        m["Origin"] = "https://evil.example"
        self.assertFalse(sv.page_load_is_ours(m, PORT))

    @unittest.expectedFailure
    def test_a_second_sec_fetch_site_header_counts_too(self):
        # today: the first value only (none, then cross-site passes); csp_local splits every value on commas and reads them all
        m = http.client.HTTPMessage()
        m["Sec-Fetch-Site"] = "none"
        m["Sec-Fetch-Site"] = "cross-site"
        self.assertFalse(sv.page_load_is_ours(m, PORT))


class OverTheWire(unittest.TestCase):
    """The same headers sent to a real server: the HTTP layer's limits (a 64 KB line is refused before any route) and the 403s."""

    @classmethod
    def setUpClass(cls):
        cls.s = Running()

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def raw(self, host_bytes, path=b"/health", extra=b""):
        return raw_reply(self.s.port, b"GET " + path + b" HTTP/1.1\r\nHost: " + host_bytes + b"\r\n" + extra + b"\r\n")

    def test_a_sixty_four_kilobyte_host_or_origin_is_refused_and_the_server_goes_on(self):
        status, _, body = self.raw(b"localhost:" + b"9" * BIG)
        self.assertIn(status, (400, 431))
        self.assertNotEqual(status, 200)
        status, _, _ = self.raw(f"127.0.0.1:{self.s.port}".encode(), extra=b"Origin: http://" + b"a" * BIG + b"\r\n")
        self.assertIn(status, (400, 431))
        self.assertEqual(self.s.ask("GET", "/health")[0], 200, "the server still answers")

    def test_a_host_with_a_nul_or_an_odd_dot_is_403(self):
        for host in (b"localhost\x00", b"localhost\x00.evil.example", f"127.0.0.1:{self.s.port}".encode() + b"\x00",
                     "clark。localhost".encode("utf-8"), "127．0．0．1".encode("utf-8"), "lоcalhost".encode("utf-8"),
                     b"clark%2Elocalhost", b"localhost:0", f"localhost::{self.s.port}".encode(), b"[0:0:0:0:0:0:0:1]", b"[::1]:0"):
            with self.subTest(host=host):
                status, _, _ = self.raw(host)
                self.assertEqual(status, 403)
                status, _, _ = self.raw(host, path=b"/api/data?project=DEMO", extra=f"{sv.TOKEN_HEADER}: {sv.TOKEN}\r\n".encode())
                self.assertEqual(status, 403)

    def test_an_odd_origin_on_an_api_call_is_403_and_a_true_one_is_not(self):
        here = f"127.0.0.1:{self.s.port}"
        for origin in (f"http://127．0．0．1:{self.s.port}", f"http://127.0.0.1:0{self.s.port}", f"http://127.0.0.1::{self.s.port}",
                       f"http://127.0.0.1:{self.s.port}​", f"http://lоcalhost:{self.s.port}", "http://127.0.0.1:0"):
            with self.subTest(origin=origin):
                status, _, _ = raw_reply(self.s.port, (f"GET /api/data?project=DEMO HTTP/1.1\r\nHost: {here}\r\n{sv.TOKEN_HEADER}: {sv.TOKEN}\r\n"
                                                      f"Origin: {origin}\r\n\r\n").encode("utf-8"))
                self.assertEqual(status, 403)
        self.assertEqual(self.s.api("GET", "/api/data?project=DEMO", extra={"Origin": f"http://{here}"})[0], 200)


if __name__ == "__main__":
    unittest.main()
