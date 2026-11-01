"""#107: the server's own error pages (odd methods, garbage request lines, oversized requests) are the same plain JSON
error as the rest of the server, not Python's technical HTML, and never echo the method or the request's bytes.

Run: python3 dev/run_tests.py test_server_error_pages
A real server on 127.0.0.1 (a free port) in a thread; raw sockets send the requests that http.client would not.
It starts its own server and no browser, so it stays in the quick tier.
"""
import http.client
import io
import json
import logging
import socket
import threading
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import changes
from clark import server as sv

PLAIN_501 = "That is not something clark can do. Go back to the page you were on."
PYTHON_WORDS = ("Unsupported", "Bad request", "Error response", "Error code", "Message:", "Python", "BaseHTTP",
                "<html", "<!DOCTYPE", "Request line", "Bad HTTP", "Header fields", "Request header")


def raw_reply(port, raw):
    """Send raw bytes and read the whole reply as (status, reason, headers, body)."""
    with socket.create_connection((sv.HOST, port), timeout=10) as s:
        s.sendall(raw)
        data = b""
        while True:
            try:
                chunk = s.recv(65536)
            except ConnectionResetError:
                break
            if not chunk:
                break
            data += chunk
    head, _, body = data.partition(b"\r\n\r\n")
    lines = head.decode("iso-8859-1").split("\r\n")
    msg = http.client.parse_headers(io.BytesIO(("\r\n".join(lines[1:]) + "\r\n\r\n").encode("iso-8859-1")))
    parts = lines[0].split(" ", 2)
    return int(parts[1]), parts[2] if len(parts) > 2 else "", msg, body


class PlainPages(unittest.TestCase):
    def setUp(self):
        self.httpd = sv.LocalServer((sv.HOST, 0))
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def host(self):
        return f"Host: 127.0.0.1:{self.port}\r\n"

    def plain(self, raw, status, code, head=False, label=""):
        """The reply is `status` with the server's plain JSON error for `code`, and nothing of the request in it."""
        got, reason, msg, body = raw_reply(self.port, raw)
        self.assertEqual(got, status, label)
        self.assertEqual(msg.get("Content-Type"), "application/json; charset=utf-8", label)
        self.assertEqual(msg.get("Content-Length"), str(len(json.dumps(sv.error_body(code)))), label)
        for header in [k for k, _ in sv.SECURITY_HEADERS if k != "Content-Security-Policy"] + ["Cache-Control"]:
            self.assertEqual(len(msg.get_all(header) or []), 1, f"{label}: {header}")
        self.assertEqual(msg.get("Connection"), "close", f"{label}: the connection is closed after an error")
        if head:
            self.assertEqual(body, b"", f"{label}: a HEAD reply has no body")
        else:
            self.assertEqual(json.loads(body), sv.error_body(code), label)
            for word in PYTHON_WORDS:
                self.assertNotIn(word, body.decode(), f"{label}: {word}")
        return reason, body

    def test_the_wording_is_plain(self):
        self.assertEqual(sv.error_body("not_supported")["message"], PLAIN_501)
        for text in (PLAIN_501, sv.MESSAGES["bad_request"], sv.MESSAGES["too_large"]):
            for word in PYTHON_WORDS + ("method", "syntax", "header", "request line", "HTTP"):
                self.assertNotIn(word, text)

    def test_an_unsupported_method_is_not_told_to_reload(self):
        # Reloading never helps: the server does not do that kind of request at all. The line says what does help.
        text = sv.MESSAGES["not_supported"]
        self.assertEqual(text, PLAIN_501)
        self.assertNotIn("Reload", text)
        self.assertNotIn("try again", text.lower())
        self.assertIn("Go back to the page you were on", text)

    def test_no_message_starts_with_the_product_name_and_the_jargon_is_gone(self):
        for key, text in sv.MESSAGES.items():
            self.assertFalse(text.lower().startswith("clark"), key)
            for word in ("request", "run", "Port", "proposal", "stage", "apply", "refused", "invalid"):
                self.assertNotIn(word, text.split(), f"{key}: {word}")
        self.assertEqual(sv.MESSAGES["not_allowed"], "That was not accepted. Reload the page and try again.")
        self.assertEqual(sv.MESSAGES["stale"], "This page is out of date because clark was restarted. Reload the page and try again.")
        self.assertEqual(sv.STALE_PAGE, sv.MESSAGES["stale"])
        for key in ("bad_request", "send_json", "length_required", "unsupported_type"):
            self.assertEqual(sv.MESSAGES[key], "That could not be read. Reload the page and try again.", key)
        self.assertEqual(sv.MESSAGES["not_found"], "That could not be found. Reload the page and try again.")

    def test_a_project_that_is_not_there_says_what_to_check(self):
        text = "There is no project with that code. Check the code in the address, or choose a project from the list."
        self.assertEqual(sv.MESSAGES["project_not_found"], text)
        self.assertEqual(changes.NO_PROJECT, text)
        self.assertEqual(sv.error_body("project_not_found")["message"], text)

    def test_a_bad_project_code_says_what_to_use(self):
        text = "Use a project code of 3 to 7 capital letters or digits."
        self.assertEqual(sv.MESSAGES["bad_project_code"], text)
        self.assertEqual(changes.BAD_PROJECT, text)
        source = (SRC / "clark" / "page" / "src" / "stores" / "report.js").read_text(encoding="utf-8")
        self.assertIn(f'const BAD_CODE = "{text}";', source)
        self.assertIn("known: { [BAD_CODE]: BAD_CODE } },", source)

    def test_the_page_maps_the_not_found_message_to_its_own_words(self):
        source = (SRC / "clark" / "page" / "src" / "stores" / "report.js").read_text(encoding="utf-8")
        text = sv.MESSAGES["project_not_found"]
        self.assertIn(f'const NO_PROJECT = "{text}";', source)
        self.assertIn("known: { [NO_PROJECT]: NO_PROJECT,", source)          # the new message is a known key and shows as itself
        self.assertIn('"There is no project with that code.": NO_PROJECT', source)    # an older server's line gets the same words

    def test_saving_off_says_what_to_do_next(self):
        self.assertEqual(sv.MESSAGES["saving_off"],
                         "Saving is switched off, so that change was not kept. Restart clark the usual way to turn it on.")

    def test_put_delete_patch_and_odd_methods_are_501_in_plain_json(self):
        for method in ("PUT", "DELETE", "PATCH", "PROPFIND", "FOO", "TRACE", "CONNECT"):
            raw = f"{method} /api/data HTTP/1.1\r\n{self.host()}Connection: close\r\n\r\n".encode()
            _, body = self.plain(raw, 501, "not_supported", label=method)
            self.assertNotIn(method.encode(), body, method)

    def test_head_gets_the_plain_status_and_headers_and_no_body(self):
        raw = f"HEAD /health HTTP/1.1\r\n{self.host()}Connection: close\r\n\r\n".encode()
        self.plain(raw, 501, "not_supported", head=True, label="HEAD")

    def test_the_status_line_does_not_echo_the_method_either(self):
        for method in ("PUT", "XYZZY"):
            raw = f"{method} / HTTP/1.1\r\n{self.host()}\r\n".encode()
            reason, _ = self.plain(raw, 501, "not_supported", label=method)
            self.assertNotIn(method, reason)

    def test_a_garbage_request_line_is_400_in_plain_json_and_does_not_echo_it(self):
        for raw in (b"\x00\xff\xfe\r\n\r\n", b"GARBAGE\r\n\r\n", b"GET / HTTP/1.1 extra\r\n\r\n", b"\x16\x03\x01\x00\xa5\x01\r\n\r\n"):
            _, body = self.plain(raw, 400, "bad_request", label=repr(raw))
            self.assertNotIn(b"GARBAGE", body)
            self.assertNotIn(b"\xff", body)

    def test_an_unknown_http_version_keeps_its_505_and_is_plain(self):
        self.plain(b"GET / HTTP/9.9\r\n\r\n", 505, "bad_request", label="HTTP/9.9")

    def test_a_very_long_request_line_is_414_in_plain_json(self):
        self.plain(b"GET /" + b"a" * 70000 + b" HTTP/1.1\r\n\r\n", 414, "too_large", label="long line")

    def test_oversized_headers_are_431_in_plain_json(self):
        many = "".join(f"X-{i}: v\r\n" for i in range(150))
        self.plain(f"GET /health HTTP/1.1\r\n{self.host()}{many}\r\n".encode(), 431, "too_large", label="many headers")
        long_one = b"GET /health HTTP/1.1\r\nX-Long: " + b"a" * 70000 + b"\r\n\r\n"
        self.plain(long_one, 431, "too_large", label="long header")

    def test_any_other_status_sent_through_send_error_is_plain_too(self):
        """Nothing the standard library or a route sends through send_error keeps Python's page or the text it was given."""
        for code, key in ((404, "bad_request"), (408, "bad_request"), (418, "bad_request"), (500, "server_error"),
                          (503, "server_error")):
            def route(handler, code=code):
                handler.send_error(code, "leak: /Users/x/secret.txt", "explain: traceback")
            with mock.patch.dict(sv.GET_ROUTES, {"/api/odd": route}):
                raw = (f"GET /api/odd HTTP/1.1\r\n{self.host()}{sv.TOKEN_HEADER}: {sv.TOKEN}\r\n"
                       "Connection: close\r\n\r\n").encode()
                _, body = self.plain(raw, code, key, label=str(code))
                self.assertNotIn(b"secret", body)

    def test_a_second_request_pipelined_behind_an_error_is_not_answered(self):
        """The connection closes after the error: a request sent behind it on the same connection gets no reply."""
        raw = (f"PUT / HTTP/1.1\r\n{self.host()}\r\nGET /health HTTP/1.1\r\n{self.host()}\r\n").encode()
        with socket.create_connection((sv.HOST, self.port), timeout=10) as s:
            s.sendall(raw)
            data = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
        self.assertEqual(data.count(b"HTTP/1."), 1)
        self.assertNotIn(b'"ok": true', data)

    def test_the_server_still_answers_after_all_of_them(self):
        raw_reply(self.port, b"\x00\xff\xfe\r\n\r\n")
        self.assertEqual(raw_reply(self.port, f"GET /health HTTP/1.1\r\n{self.host()}Connection: close\r\n\r\n".encode())[0], 200)

    def test_nothing_raw_reaches_the_log_or_the_screen(self):
        """A request line with control and binary bytes, as an authorised path under /api/ (logged, escaped) and as garbage or a
        request without the token (#234: counted, never a line of its own), logs nothing unescaped."""
        evil = b"/api/\x1b[31m\x07\x00\xff"
        with mock.patch("sys.stderr", io.StringIO()) as err, self.assertLogs(sv.LOG, level=logging.DEBUG) as logs:
            raw_reply(self.port, b"GET " + evil + b" HTTP/1.1\r\n" + self.host().encode() + f"{sv.TOKEN_HEADER}: {sv.TOKEN}\r\n".encode() + b"Connection: close\r\n\r\n")   # authorised (#234): the only API call that is logged
            raw_reply(self.port, b"\x00\xff\xfe\x1b[31m\r\n\r\n")
            raw_reply(self.port, b"PUT " + evil + b" HTTP/1.1\r\n" + self.host().encode() + b"Connection: close\r\n\r\n")
            logging.getLogger(sv.LOG.name).info("end")
        text = "\n".join(logs.output) + err.getvalue()
        for bad in ("\x1b", "\x07", "\x00", "\xff"):
            self.assertNotIn(bad, text)
        self.assertIn("\\x1b", text, "the API call is still logged, escaped")


if __name__ == "__main__":
    unittest.main()
