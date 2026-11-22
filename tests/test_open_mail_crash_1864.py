"""PR 1864: a lone surrogate is refused like a control character, and an OSError from the opener gives the same 503 as a refusal."""
import unittest

from clark import mail_open, platform


class CrashPaths(unittest.TestCase):
    def test_a_lone_surrogate_is_refused_and_never_reaches_the_system(self):
        for ch in ("\ud800", "\udbff", "\udc00", "\udfff"):
            seen = []
            with self.assertRaises(platform.PlatformError, msg=repr(ch)):
                platform.open_mail("mailto:a@b.c?subject=x" + ch + "y", run=lambda *a, **k: seen.append(a), on=platform.MAC)
            self.assertEqual(seen, [])

    def test_a_surrogate_through_the_route_is_a_503(self):
        opener = lambda l: platform.open_mail(l, run=lambda *a, **k: self.fail("opened"), on=platform.MAC)
        status, body = mail_open.MailOpen(opener).handle({"link": "mailto:a@b.c?body=\ud800"})
        self.assertEqual((status, body["code"]), (503, "not_opened"))

    def test_an_oserror_from_the_opener_is_the_same_503(self):
        def boom(link):
            raise OSError(7, "Argument list too long")
        status, body = mail_open.MailOpen(boom).handle({"link": "mailto:a@b.c"})
        self.assertEqual((status, body["ok"], body["code"]), (503, False, "not_opened"))
        self.assertTrue(body["message"].startswith("The mail app could not be opened."))
        self.assertNotIn("Argument", body["message"])

    def test_a_valid_link_still_opens(self):
        seen = []
        self.assertEqual(mail_open.MailOpen(seen.append).handle({"link": "mailto:a@b.c"}), (200, {"ok": True}))


if __name__ == "__main__":
    unittest.main()
