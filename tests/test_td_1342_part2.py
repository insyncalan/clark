"""Tech-debt row 1342 part 2 (Feedback tag, Classic): the empty-send error, the icon tag and the Proposed tag as the 1298 mockup draws them.
Measured in Chrome at 1400 (icon tag at 600, the narrow window); values are the mockup's: error red 13px, 4px above; Proposed 11px / 500, pad 1 7, pill, 4 left;
icon tag horizontal, pad 10 8, radius 12 0 0 12, 18px.

Run: python3 dev/run_tests.py test_td_1342_part2
"""
import unittest

from test_ms_timeline_classic_1315 import Base
from test_server import chrome, wait

ERR = "Please write a line first."
OPEN = "document.querySelector('#feedback-tag').click()"
P = """(() => { const c = (e, p) => getComputedStyle(e)[p], a = [...document.querySelectorAll('.fbt-proposed')];
  return { n: a.length, size: c(a[0], 'fontSize'), weight: c(a[0], 'fontWeight'), pad: c(a[0], 'padding'), radius: c(a[0], 'borderRadius'), ml: c(a[0], 'marginLeft'),
    inKinds: !!document.querySelector('.fbt-kinds .fbt-proposed'), inAdded: !!document.querySelector('.fbt-added .fbt-proposed'), text: a[0].textContent }; })()"""
E_ = """(() => { const e = document.querySelector('#fbt-error'), c = getComputedStyle(e), t = document.querySelector('#fbt-message').getBoundingClientRect();
  return { text: e.textContent, size: c.fontSize, color: c.color, mt: c.marginTop, gap: Math.round(e.getBoundingClientRect().top - t.bottom), mailHref: document.querySelector('[data-fbt-mail]').hasAttribute('href') }; })()"""
I = """(() => { const t = document.querySelector('#feedback-tag'), c = getComputedStyle(t); return { icon: t.classList.contains('icon'), text: t.textContent, mode: c.writingMode, pad: c.padding, radius: c.borderRadius, size: c.fontSize, label: t.getAttribute('aria-label') }; })()"""


class FeedbackTagPart2(Base, unittest.TestCase):
    def opened(self, cdp, width):
        sid = self.visit(cdp, width, "#settings&p=appearance", self.serve(), ready="#feedback-tag")
        return sid

    def test_proposed_tag(self):
        with chrome() as cdp:
            sid = self.opened(cdp, 1400)
            cdp.js(OPEN, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.fbt-dlg')", sid)))
            m = cdp.js(P, sid)
            self.assertEqual((m["n"], m["inKinds"], m["inAdded"], m["text"]), (2, True, True, "Proposed"))
            self.assertEqual((m["size"], m["weight"], m["pad"], m["radius"], m["ml"]), ("11px", "500", "1px 7px", "999px", "4px"))

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

    def test_icon_tag_when_narrow(self):
        with chrome() as cdp:
            sid = self.opened(cdp, 1400)
            m = cdp.js(I, sid)
            self.assertEqual((m["icon"], m["text"], m["mode"]), (False, "Feedback", "vertical-rl"))
        with chrome() as cdp:
            sid = self.opened(cdp, 600)
            m = cdp.js(I, sid)
            self.assertEqual((m["icon"], m["text"], m["mode"], m["label"]), (True, "✉", "horizontal-tb", "Give feedback"))
            self.assertEqual((m["pad"], m["radius"], m["size"]), ("10px 8px", "12px 0px 0px 12px", "18px"))


if __name__ == "__main__":
    unittest.main()
