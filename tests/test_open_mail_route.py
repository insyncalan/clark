"""Row 1297: POST /api/open-mail hands a finished mailto: link to the system's open; nothing else is opened."""
import json
import threading
import unittest
import urllib.request
from unittest import mock

from clark import mail_open, platform, server


class Seam(unittest.TestCase):
    def test_a_good_link_is_opened_once(self):
        seen = []
        status, body = mail_open.MailOpen(seen.append).handle({"link": "mailto:a@b.c?subject=Hi"})
        self.assertEqual((status, body, seen), (200, {"ok": True}, ["mailto:a@b.c?subject=Hi"]))

    def test_a_refusal_carries_the_platform_words(self):
        def refuse(link):
            raise platform.PlatformError("The mail app could not be opened. " + platform.TRY_AGAIN)
        status, body = mail_open.MailOpen(refuse).handle({"link": "mailto:a@b.c"})
        self.assertEqual((status, body["code"]), (503, "not_opened"))
        self.assertTrue(body["message"].startswith("The mail app could not be opened."))

    def test_a_body_that_is_not_a_link_never_reaches_the_system(self):
        for req in (None, [], {}, {"link": 5}, {"link": None}):
            seen = []
            mail_open.MailOpen(lambda l, s=seen: platform.open_mail(l, run=lambda *a, **k: s.append(a), on=platform.MAC)).handle(req)
            self.assertEqual(seen, [], req)

    def test_only_mailto_and_no_option_reaches_the_system(self):
        for link in ("https://x.example", "-a Calculator", "mailto:a b", "file:///etc/passwd", "mailto:a\nb"):
            ran = []
            with self.assertRaises(platform.PlatformError):
                platform.open_mail(link, run=lambda *a, **k: ran.append(a), on=platform.MAC)
            self.assertEqual(ran, [], link)


class Route(unittest.TestCase):
    def setUp(self):
        self.seen = []
        self.httpd = server.LocalServer(("127.0.0.1", 0), data_for=lambda c, archived="hide": None, mail=mail_open.MailOpen(self.seen.append))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def post(self, body, token):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/open-mail", json.dumps(body).encode(), {"Content-Type": "application/json", "X-Clark-Token": token})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_the_route_is_listed_and_needs_the_token(self):
        self.assertIn("/api/open-mail", server.POST_ROUTES)
        self.assertEqual(self.post({"link": "mailto:a@b.c"}, "wrong"), 403)
        self.assertEqual(self.seen, [])


if __name__ == "__main__":
    unittest.main()
