"""Row 1297, killers from the full mutation sweep (page side): what the click on the mail link sends, which answers count as a failure,
that the plain link is held back and that a change in the Draft email editor clears the note. Reuses the browser harness of the Draft email editor."""
import json
import unittest

import test_draft_email_editor as DE
from test_server import chrome  # noqa: F401  (the harness: this file drives Chrome through the base classes above, so the tier reader sees it)

NOTE = "No mail app opened. Use Copy as text and paste it into your mail."


class Shared:
    def answer(self, status, body, reject=False):
        self.js("window.__posts = []; window.__prevented = []; document.addEventListener('click', (e) => window.__prevented.push(e.defaultPrevented));"
                "window.fetch = (u, i) => { window.__posts.push([String(u), i]); " + ("return Promise.reject(new Error('down'));" if reject else
                "return Promise.resolve(new Response(JSON.stringify(%s), {status: %d}));" % (json.dumps(body), status)) + " };")

    def notes(self):
        return self.val("document.querySelectorAll('[data-mail-note]').length")

    def watch_nav(self):
        self.js("const had = !!window.__nav; window.__nav = []; if (!had && window.navigation) window.navigation.addEventListener('navigate', (e) => window.__nav.push(e.destination.url + '|' + e.navigationType));")

    def check_follow(self, click, href):
        """The plain link is followed whenever the open fails (a refusal, as off the Mac, or no answer at all), never after a success."""
        self.assertTrue(self.val("!!window.navigation"), "the browser reports navigations")
        self.settle()
        self.watch_nav()
        self.answer(200, {"ok": True})
        click()
        self.assertEqual(self.val("window.__nav"), [], "opened by the server: the plain link is not followed as well")
        for i, (status, body, reject, why) in enumerate(((503, {"ok": False}, False, "refused without words"),
                                          (503, {"ok": False, "message": "x"}, False, "refused with words (off the Mac)"), (0, {}, True, "no answer at all")), 1):
            self.settle()
            self.answer(status, body, reject=reject)
            click()
            self.settle()
            nav = self.val("window.__nav")   # the browser may re-encode a character or two, so compare the start
            self.assertEqual(len(nav), i, why + ": the plain link is followed " + repr([n[-12:] for n in nav]))
            self.assertEqual(nav[0][:60], href[:60], why)

    def check_post(self, href):
        self.assertEqual(self.val("window.__posts.length"), 1)
        url, init = self.val("window.__posts[0]")
        self.assertEqual(url, "/api/open-mail")
        self.assertEqual(init["method"], "POST")
        self.assertTrue(init["headers"]["X-Clark-Token"] is not None and "X-Clark-Token" in init["headers"])
        self.assertEqual(json.loads(init["body"]), {"link": href})
        self.assertEqual(self.val("window.__prevented"), [True], "the plain link is held back while the server opens it")

    def check_failures(self, click):
        for status, body in ((500, {"ok": True, "message": "x"}), (200, {"ok": False, "message": "x"}), (503, {"message": "x"})):
            self.answer(status, body)
            click()
            self.assertEqual(self.notes(), 1, f"{status} {body} is a failed open")
        self.answer(503, {"ok": False})
        click()
        self.assertEqual(self.notes(), 0, "no words from the server: no note")
        self.answer(0, {}, reject=True)
        click()
        self.assertEqual(self.notes(), 0, "no answer at all: no note")


class Draft(Shared, DE.InBrowser):
    def test_the_post_and_the_failures(self):
        self.mount()
        href = self.js("document.querySelector('.pk-foot a').getAttribute('href')")
        self.answer(200, {"ok": True})
        self.click(".pk-foot a")
        self.check_post(href)
        self.check_failures(lambda: self.click(".pk-foot a"))
        self.check_follow(lambda: self.click(".pk-foot a"), href)

    def test_a_change_clears_the_note_and_the_note_is_a_muted_note_line(self):
        self.mount()
        self.answer(503, {"ok": False, "message": "x"})
        self.click(".pk-foot a")
        self.assertEqual(self.notes(), 1)
        self.assertEqual(self.val("document.querySelector('[data-mail-note]').className"), "muted de-note")
        self.click("input[value=chase]")
        self.assertEqual(self.notes(), 0)


if __name__ == "__main__":
    unittest.main()
