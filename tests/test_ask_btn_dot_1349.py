"""Item 1349: the ask clark button in the Classic Theme. The badge is a 9 by 9 dot at the top right of the button (amber while an answer is
made, cyan when one is ready, the words only in the aria-label), and the button stays in the bar at 900 px, icon only. Cards (no Theme layer)
keeps its count badge, its dots and the profile-menu entry at 900. Sizes and colours as Chrome computes them at 1400 and 900 px.

Run: python3 dev/run_tests.py test_ask_btn_dot_1349
Headless Chrome, the real page, a stub for the server's ask. Fails, never skips, without Chrome.
"""
import json
import unittest

from clark import page, theme
from test_ask_panel import Stub
from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome
import _testpage as testpage
import test_report_editor as tre

READY = "!!document.querySelector('#ask-panel') && !document.querySelector('#ask-send').disabled"
LOOK = """(() => { const b = document.querySelector('#ask-btn'), br = b.getBoundingClientRect(), tok = (v) => { const i = document.createElement('i'); i.style.backgroundColor = v;
  document.body.appendChild(i); const c = getComputedStyle(i).backgroundColor; i.remove(); return c; };
  const d = b.querySelector('.tb-ask-ready, .tb-ask-dots'); if (!d) return JSON.stringify({dot: false, btn: [Math.round(br.width), Math.round(br.height)]});
  const s = getComputedStyle(d), anim = [s.animationName, s.animationDuration, s.animationIterationCount, s.animationTimingFunction]; d.style.animation = 'none';      /* the corner is measured at rest, the pulse moves it by up to 3 px */
  const r = d.getBoundingClientRect(), w = getComputedStyle(b.querySelector('.tb-ask-w'));
  return JSON.stringify({dot: true, cls: d.className, size: [Math.round(r.width), Math.round(r.height)], top: Math.round(r.top - br.top), right: Math.round(br.right - r.right),
    bg: s.backgroundColor, cyan: tok('var(--brand-cyan)'), amber: tok('var(--status-amber)'), ring: s.boxShadow, navy: tok('var(--brand-navy)'), pos: s.position, anim, radius: s.borderTopLeftRadius,
    inner: [...d.children].map((e) => getComputedStyle(e).display), text: d.textContent.trim(), fs: s.fontSize, word: w.display, label: b.getAttribute('aria-label'), btn: [Math.round(br.width), Math.round(br.height)]}); })()"""
IN_BAR = "(function(){var e=document.querySelector('.top #ask-btn'); return !!e && e.getClientRects().length > 0 && e.getBoundingClientRect().width > 0;})()"


class Dot(Base):
    classic = True

    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub
        if self.classic:
            self.s.close()
            self.s = tre.real_server(self.store.path, self.store.data_for, seam=self.seam,
                                     page_html=lambda: page.layer_theme(testpage.html(), theme.css("prototype-2.0")))
            self.addCleanup(self.s.close)
            self.s.httpd.ask = self.stub

    def at(self, cdp, width):
        p = self.visit(cdp)
        size(cdp, p, width, 700)
        p.until(f"window.innerWidth === {width}", f"the window is {width} wide")
        p.until("!!document.querySelector('#profile-btn')", "the header is drawn")
        p.until("window.matchMedia('(max-width: 900px)').matches === %s" % ("true" if width <= 900 else "false"), "the width query")
        return p

    def out_and_closed(self, p):
        p.key("/", code="Slash", vk=191)
        p.until(READY, "the panel is ready")
        p.js("document.querySelector('#ask-box').focus()")
        p.type("When is go-live?")
        p.js("document.querySelector('#ask-send').click()")
        p.until("!!document.querySelector('#ask-stop')", "the question is out")
        p.key("Escape", code="Escape", vk=27)
        p.until("document.querySelector('#ask-panel') === null", "closed")

    def look(self, p):
        return json.loads(p.js(LOOK))

    def run_states(self, width):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.at(cdp, width)
            idle = self.look(p)
            self.out_and_closed(p)
            p.until("document.querySelector('#ask-btn').getAttribute('aria-label') === 'ask clark, working'", "working")
            working = self.look(p)
            self.stub.hold.set()
            p.until("document.querySelector('#ask-btn').getAttribute('aria-label') === 'ask clark, 1 answer ready'", "one answer ready")
            ready = self.look(p)
            return idle, working, ready, p.js(IN_BAR)


class Classic1400(Dot):
    def test_idle_has_no_dot_working_is_amber_ready_is_cyan_both_9_by_9_at_the_corner(self):
        idle, working, ready, _ = self.run_states(1400)
        self.assertFalse(idle["dot"], "no dot before any question")
        for got, colour, cls in ((working, working["amber"], "tb-ask-dots"), (ready, ready["cyan"], "tb-ask-ready")):
            self.assertEqual(got["cls"], cls)
            self.assertEqual(got["size"], [9, 9])
            self.assertEqual((got["top"], got["right"]), (5, 5))
            self.assertEqual(got["bg"], colour)
            self.assertEqual(got["pos"], "absolute")
            self.assertEqual(got["radius"], "50%")
            self.assertEqual(got["text"] if got is working else got["fs"], "" if got is working else "0px", "no number is drawn in the dot")
            self.assertIn("2px", got["ring"])
            self.assertIn(got["navy"], got["ring"])
        self.assertEqual(working["anim"], ["tb-ask-pulse", "1s", "infinite", "cubic-bezier(0.65, 0, 0.35, 1)"], "the working dot pulses as the prototype's does")
        self.assertEqual(ready["anim"][0], "none", "the ready dot is still")
        self.assertEqual(working["inner"], ["none"] * 3, "the three small dots inside the working dot are not drawn: the dot is one amber circle")
        self.assertNotEqual(working["amber"], working["cyan"])
        self.assertEqual(ready["label"], "ask clark, 1 answer ready")
        self.assertEqual(working["label"], "ask clark, working")

    def test_at_1400_the_button_keeps_its_words(self):
        _, _, ready, _ = self.run_states(1400)
        self.assertNotEqual(ready["word"], "none")


class Classic900(Dot):
    def test_at_900_the_button_stays_in_the_bar_icon_only_with_the_same_dot(self):
        idle, working, ready, in_bar = self.run_states(900)
        self.assertTrue(in_bar, "item 1349: at 900 the ask clark button is in the header row")
        self.assertEqual(ready["word"], "none", "the words are hidden at 900")
        self.assertEqual(ready["size"], [9, 9])
        self.assertEqual((ready["top"], ready["right"]), (5, 5))
        self.assertEqual(ready["bg"], ready["cyan"])
        self.assertEqual(working["bg"], working["amber"])
        self.assertEqual(ready["label"], "ask clark, 1 answer ready")
        self.assertGreater(idle["btn"][0], 0)


class Cards(Dot):
    classic = False

    def test_cards_keeps_the_count_badge_the_dots_and_the_menu_entry_at_900(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.at(cdp, 900)
            self.assertFalse(p.js(IN_BAR), "Cards at 900: the button is still in the profile menu only")
        idle, working, ready, _ = self.run_states(1400)
        self.assertEqual(working["cls"], "tb-ask-dots")
        self.assertEqual(ready["text"], "1", "Cards: the badge still shows the number")
        self.assertEqual(ready["size"][1], 16, "Cards: the badge is 16 high")
        self.assertEqual(ready["pos"], "static")


if __name__ == "__main__":
    unittest.main()
