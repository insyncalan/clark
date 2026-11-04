"""#643 slice 1: the HTTPS caller. No real network: `connect` is a seam that returns a fake connection, so no socket is opened.

Run: python3 dev/run_tests.py test_ai_https
"""
import io
import logging
import socket
import ssl
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401
from clark import ai_https as h

KEY = "sk-ant-api03-" + "A1b2C3d4" * 4
HEADERS = {"x-api-key": KEY, "content-type": "application/json"}
PATH = "/v1/messages-private-path"


class Reply:
    def __init__(self, status=200, body=b'{"ok":true}'):
        self.status, self.stream = status, io.BytesIO(body)

    def read(self, n=-1):
        return self.stream.read(n)


class Conn:
    """A connection-like object: records the request, returns `reply`, or raises `error` where `where` says."""

    def __init__(self, reply=None, error=None, where="getresponse"):
        self.reply, self.error, self.where, self.sent, self.closed = reply or Reply(), error, where, None, False

    def request(self, method, path, body=None, headers=None):
        self.sent = (method, path, body, headers)
        if self.error and self.where == "request":
            raise self.error

    def getresponse(self):
        if self.error and self.where == "getresponse":
            raise self.error
        return self.reply

    def close(self):
        self.closed = True


def seam(conn):
    made = []

    def connect(host, timeout):
        made.append((host, timeout))
        return conn
    connect.made = made
    return connect


class Pinning(unittest.TestCase):
    def test_other_hosts_are_refused_before_any_connection_or_socket(self):
        connect = mock.Mock()
        with mock.patch.object(socket, "socket") as sock, mock.patch.object(socket, "create_connection") as cc, mock.patch.object(ssl, "create_default_context") as ctx:
            for host in ("example.com", "api.anthropic.com.evil.test", "API.ANTHROPIC.COM", "api.openai.com:443", "", "evil.test/api.openai.com"):
                with self.subTest(host), self.assertRaises(h.HttpsError) as caught:
                    h.post_json(host, PATH, HEADERS, b"{}", connect=connect)
                self.assertEqual(caught.exception.code, "refused_host")
            sock.assert_not_called(), cc.assert_not_called(), ctx.assert_not_called()
        connect.assert_not_called()

    def test_the_two_pinned_hosts_work(self):
        for host in ("api.anthropic.com", "api.openai.com"):
            conn = Conn()
            self.assertEqual(h.post_json(host, PATH, HEADERS, b"{}", connect=seam(conn)), (200, b'{"ok":true}'))
            self.assertEqual(conn.sent, ("POST", PATH, b"{}", HEADERS))
            self.assertTrue(conn.closed)


class TheSecureConnection(unittest.TestCase):
    def test_the_default_connect_verifies_certificates_and_hostnames(self):
        with mock.patch.object(h.http.client, "HTTPSConnection") as make:
            h._connect("api.openai.com", 7)
        context = make.call_args.kwargs["context"]
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(make.call_args.kwargs["timeout"], 7)

    def test_the_timeout_is_passed_to_the_connection(self):
        connect = seam(Conn())
        h.post_json("api.openai.com", PATH, HEADERS, b"{}", timeout=5, connect=connect)
        self.assertEqual(connect.made, [("api.openai.com", 5)])

    def test_the_module_never_relaxes_verification(self):
        text = open(h.__file__, encoding="utf-8").read()
        for bad in ("_create_unverified_context", "CERT_NONE", "check_hostname = False", "verify=False"):
            self.assertNotIn(bad, text)


class Refusals(unittest.TestCase):
    def code(self, conn, **kw):
        with self.assertRaises(h.HttpsError) as caught:
            h.post_json("api.anthropic.com", PATH, HEADERS, b"{}", connect=seam(conn), **kw)
        self.assertTrue(conn.closed)
        return caught.exception

    def test_a_redirect_is_refused_not_followed(self):
        for status in (301, 302, 307, 308):
            conn = Conn(Reply(status, b""))
            self.assertEqual(self.code(conn).code, "redirect")
            self.assertEqual(conn.sent[0], "POST")             # one request only

    def test_an_oversize_reply_is_refused(self):
        self.assertEqual(self.code(Conn(Reply(200, b"x" * 1001)), max_reply=1000).code, "too_big")
        self.assertEqual(h.post_json("api.openai.com", PATH, HEADERS, b"{}", max_reply=1000, connect=seam(Conn(Reply(200, b"x" * 1000))))[1], b"x" * 1000)

    def test_a_reply_is_read_in_chunks_not_all_at_once(self):
        reply = mock.Mock(status=200)
        reply.read.side_effect = [b"a" * 10, b"b" * 10, b""]
        h.post_json("api.openai.com", PATH, HEADERS, b"{}", connect=seam(Conn(reply)))
        for call in reply.read.call_args_list:
            self.assertEqual(call.args, (h.CHUNK,))

    def test_a_timeout_in_either_step_is_the_timeout_code(self):
        for where in ("request", "getresponse"):
            self.assertEqual(self.code(Conn(error=socket.timeout("slow " + KEY), where=where)).code, "timeout")

    def test_a_timeout_while_connecting_is_the_timeout_code(self):
        def connect(host, timeout):
            raise socket.timeout("slow " + KEY)
        with self.assertRaises(h.HttpsError) as caught:
            h.post_json("api.anthropic.com", PATH, HEADERS, b"{}", connect=connect)
        self.assertEqual(caught.exception.code, "timeout")

    def test_a_timeout_while_reading_the_reply_is_the_timeout_code(self):
        reply = mock.Mock(status=200)
        reply.read.side_effect = [b"a" * 10, socket.timeout("slow")]
        self.assertEqual(self.code(Conn(reply)).code, "timeout")

    def test_the_timeout_classes_cover_a_python_39_socket_timeout(self):
        self.assertIn(socket.timeout, h.TIMEOUTS)            # on 3.9 this is a different class from TimeoutError
        self.assertIn(TimeoutError, h.TIMEOUTS)

    def test_the_reply_cap_is_exact_no_read_asks_for_more_than_one_byte_past_it(self):
        reply = mock.Mock(status=200)
        reply.read.side_effect = lambda n: b"x" * n
        with self.assertRaises(h.HttpsError) as caught:
            h.post_json("api.openai.com", PATH, HEADERS, b"{}", max_reply=100_000, connect=seam(Conn(reply)))
        self.assertEqual(caught.exception.code, "too_big")
        self.assertEqual([c.args[0] for c in reply.read.call_args_list], [h.CHUNK, 100_000 - h.CHUNK + 1])

    def test_the_overall_deadline_ends_a_slow_trickle_with_the_timeout_code(self):
        ticks = iter([0, 1, 2, 3, 99, 100, 101])              # the clock: start, then a check before each chunk
        reply = mock.Mock(status=200)
        reply.read.side_effect = lambda n: b"x"
        with self.assertRaises(h.HttpsError) as caught:
            h.post_json("api.openai.com", PATH, HEADERS, b"{}", deadline=10, clock=lambda: next(ticks), connect=seam(Conn(reply)))
        self.assertEqual(caught.exception.code, "timeout")
        self.assertEqual(reply.read.call_count, 3)

    def test_every_other_failure_is_the_connection_code(self):
        for error in (ConnectionRefusedError("no"), ssl.SSLCertVerificationError("bad cert api.anthropic.com"), OSError("x"), ValueError("y")):
            self.assertEqual(self.code(Conn(error=error)).code, "connection")

    def test_a_status_error_is_returned_not_raised(self):
        self.assertEqual(h.post_json("api.openai.com", PATH, HEADERS, b"{}", connect=seam(Conn(Reply(401, b"no")))), (401, b"no"))


class NothingSecretLeaks(unittest.TestCase):
    def test_no_exception_or_log_holds_the_headers_the_path_or_the_cause(self):
        errors = [socket.timeout("t " + KEY), ConnectionResetError("reset " + KEY + PATH), ssl.SSLError("tls " + KEY), RuntimeError(str(HEADERS))]
        with self.assertLogs(level="DEBUG") as logs:
            logging.getLogger("clark").debug("start")
            seen = []
            for error in errors:
                for where in ("request", "getresponse"):
                    with self.assertRaises(h.HttpsError) as caught:
                        h.post_json("api.anthropic.com", PATH, HEADERS, b"{}", connect=seam(Conn(error=error, where=where)))
                    seen += [str(caught.exception), repr(caught.exception), repr(caught.exception.args)]
                    self.assertTrue(caught.exception.__suppress_context__)
            for status in (302, 200):
                body = b"x" * 9_000_000 if status == 200 else b""
                with self.assertRaises(h.HttpsError) as caught:
                    h.post_json("api.anthropic.com", PATH, HEADERS, b"{}", connect=seam(Conn(Reply(status, body))))
                seen += [str(caught.exception), repr(caught.exception)]
            with self.assertRaises(h.HttpsError) as caught:
                h.post_json("evil.test", PATH, HEADERS, b"{}")
            seen.append(repr(caught.exception))
        text = " ".join(seen) + " ".join(logs.output)
        for secret in (KEY, PATH, "x-api-key", "api.anthropic.com"):
            self.assertNotIn(secret, text)
        for item in seen:
            self.assertTrue(any(code in item for code in h.CODES))

    def test_the_caller_headers_are_not_changed(self):
        before = dict(HEADERS)
        h.post_json("api.openai.com", PATH, HEADERS, b"{}", connect=seam(Conn()))
        self.assertEqual(HEADERS, before)


if __name__ == "__main__":
    unittest.main()
