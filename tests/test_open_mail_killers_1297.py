"""Row 1297, killers from the full mutation sweep (server side): the route opens a good link once, answers not found without its seam, the
default opener is platform.open_mail, and platform.open_mail refuses a link that only contains mailto: or starts with a dash, and a non-Mac."""
import json
import threading
import unittest
import urllib.request
from unittest import mock

from clark import mail_open, platform, server


class Calls:
    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append(a)
        return mock.Mock(returncode=0, stdout="", stderr="")


class Platform(unittest.TestCase):
    def test_a_link_that_only_contains_mailto_or_starts_with_a_dash_is_refused(self):
        for link in ("x-mailto:a@b.c", "-mailto:a@b.c", "-psn_0_1", "https://x.example/?u=mailto:a@b.c", "--help", "Mailto:a@b.c"):
            run = Calls()
            with self.assertRaises(platform.PlatformError, msg=link):
                platform.open_mail(link, run=run, on=platform.MAC)
            self.assertEqual(run.calls, [], link)

    def test_a_control_character_is_the_same_refusal_and_nothing_is_run(self):
        for bad in ("mailto:a@b.c\x00", "mailto:a\x00b", "mailto:a@b.c?body=x\ny", "mailto:a@b.c\x1f", "mailto:a@b.c\x7f", "mailto:a\rb"):
            run = Calls()
            with self.assertRaisesRegex(platform.PlatformError, "Only a mail link starting mailto: can be opened here", msg=repr(bad)):
                platform.open_mail(bad, run=run, on=platform.MAC)
            self.assertEqual(run.calls, [], repr(bad))
        self.assertEqual(mail_open.MailOpen(opener=lambda l: platform.open_mail(l, run=Calls(), on=platform.MAC)).handle({"link": "mailto:a\x00b"})[0], 503)

    def test_off_the_mac_nothing_is_run(self):
        for on in (platform.WINDOWS, "linux"):
            run = Calls()
            with self.assertRaises(platform.PlatformError):
                platform.open_mail("mailto:a@b.c", run=run, on=on)
            self.assertEqual(run.calls, [], on)

    def test_a_value_that_is_not_text_is_a_platform_refusal(self):
        with self.assertRaises(platform.PlatformError):
            platform.open_mail(None, run=Calls(), on=platform.MAC)

    def test_the_default_opener_is_open_mail(self):
        with mock.patch.object(platform, "open_mail") as om:
            mail_open.MailOpen().handle({"link": "mailto:a@b.c"})
        om.assert_called_once_with("mailto:a@b.c")


class Route(unittest.TestCase):
    def serve(self, mail):
        httpd = server.LocalServer(("127.0.0.1", 0), data_for=lambda c, archived="hide": None, mail=mail)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        return httpd

    def post(self, httpd, body):
        req = urllib.request.Request(f"http://127.0.0.1:{httpd.server_address[1]}/api/open-mail", json.dumps(body).encode(),
                                     {"Content-Type": "application/json", "X-Clark-Token": server.TOKEN})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")

    def test_a_good_post_opens_the_link_once_and_answers_ok(self):
        seen = []
        httpd = self.serve(mail_open.MailOpen(seen.append))
        self.assertEqual(self.post(httpd, {"link": "mailto:a@b.c?subject=Hi"}), (200, {"ok": True}))
        self.assertEqual(seen, ["mailto:a@b.c?subject=Hi"])

    def test_a_refusal_is_a_503_with_the_words(self):
        def refuse(link):
            raise platform.PlatformError("No.")
        status, body = self.post(self.serve(mail_open.MailOpen(refuse)), {"link": "mailto:a@b.c"})
        self.assertEqual((status, body["message"]), (503, "No."))

    def test_without_its_seam_the_route_is_not_found(self):
        status, body = self.post(self.serve(None), {"link": "mailto:a@b.c"})
        self.assertEqual(status, 404)


class Wiring(unittest.TestCase):
    def test_the_server_keeps_its_seam_and_serve_and_main_pass_it_on(self):
        seam = mail_open.MailOpen(lambda l: None)
        httpd = server.LocalServer(("127.0.0.1", 0), mail=seam)
        self.addCleanup(httpd.server_close)
        self.assertIs(httpd.mail, seam)
        import inspect
        self.assertIn("mail=mail)", inspect.getsource(server.serve))
        from clark import __main__ as m
        self.assertIn("mail=mail_open.MailOpen()", inspect.getsource(m))


if __name__ == "__main__":
    unittest.main()
