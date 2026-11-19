"""Tech-debt row 1342 part 2 (Feedback tag, Classic): the empty-send error as the 1298 mockup draws it (red 13px, 4px above the box, the mockup's words).
Measured in Chrome at 1400. The icon tag and the Proposed tag are not built (the mock-up gives no trigger for the first and the second is its review note).

Run: python3 dev/run_tests.py test_td_1342_part2
"""
import unittest

from test_ms_timeline_classic_1315 import Base
from test_server import chrome, wait

ERR = "Please write a line first."
OPEN = "document.querySelector('#feedback-tag').click()"
E_ = """(() => { const e = document.querySelector('#fbt-error'), c = getComputedStyle(e), t = document.querySelector('#fbt-message').getBoundingClientRect();
  return { text: e.textContent, size: c.fontSize, color: c.color, mt: c.marginTop, gap: Math.round(e.getBoundingClientRect().top - t.bottom), mailHref: document.querySelector('[data-fbt-mail]').hasAttribute('href') }; })()"""


class FeedbackTagPart2(Base, unittest.TestCase):
    def opened(self, cdp, width):
        sid = self.visit(cdp, width, "#settings&p=appearance", self.serve(), ready="#feedback-tag")
        return sid

    def test_the_dialog_heading_takes_the_heading_colour(self):
        with chrome() as cdp:
            sid = self.opened(cdp, 1400)
            cdp.js(OPEN, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.fbt-dlg')", sid)))
            got = cdp.js("(() => { const h = getComputedStyle(document.querySelector('.fbt-head h2')).color, p = document.createElement('i'); p.style.color = 'var(--heading)'; document.body.appendChild(p); const t = getComputedStyle(p).color; p.remove(); return [h, t]; })()", sid)
            self.assertEqual(got[0], got[1], "the h2 is drawn in --heading")

    def test_empty_send_error(self):
        for button in ("[data-fbt-copy]", "[data-fbt-mail]"):
            with self.subTest(button=button), chrome() as cdp:
                sid = self.opened(cdp, 1400)
                cdp.js(OPEN, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.fbt-dlg')", sid)))
                self.assertFalse(cdp.js("!!document.querySelector('#fbt-error')", sid))
                cdp.js(f"document.querySelector('{button}').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fbt-error')", sid)))
                m = cdp.js(E_, sid)
                self.assertEqual((m["text"], m["size"], m["mt"], m["mailHref"]), (ERR, "13px", "4px", False))
                self.assertEqual(m["color"], "rgb(163, 48, 31)")
                cdp.js("(() => { const t = document.querySelector('#fbt-message'); t.focus(); document.execCommand('insertText', false, 'The page is slow'); })()", sid)
                self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#fbt-error')", sid)))
                self.assertTrue(cdp.js("document.querySelector('[data-fbt-mail]').hasAttribute('href')", sid))



if __name__ == "__main__":
    unittest.main()
