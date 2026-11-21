"""Row 1267 close list: the grip's focus ring when reached by keyboard (Classic and Cards), and the Cards grip bar in dark (seen against what is behind it, and on hover).

Run: python3 dev/run_tests.py test_ms_grip_keep_1267
Chrome launches at 1400 and 900 px. The Classic grip is the full-width bottom edge (row 1315); the Cards grip is the centred 64x24 one.
"""
import unittest

import test_ms_timeline_classic_1315 as C
from test_server import chrome, wait

GRIP = "document.querySelector('.mv-wrap [data-grip], [data-grip]')"
RING = """(() => { const g = document.querySelector('[data-grip]'), s = getComputedStyle(g), p = document.createElement('i');
  p.style.color = 'var(--focus)'; document.body.appendChild(p); const want = getComputedStyle(p).color; p.remove();
  return { on: document.activeElement === g, visible: g.matches(':focus-visible'), style: s.outlineStyle, width: s.outlineWidth, offset: s.outlineOffset, color: s.outlineColor, want }; })()"""


def tab(cdp, sid):
    for kind in ("keyDown", "keyUp"):
        cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9}, sid)


def ring_by_keyboard(test, cdp, sid, width, look):
    cdp.js("(() => { const t = [...document.querySelectorAll('.mv-wrap button, .mv-wrap [tabindex=\\'0\\']')].pop() || document.querySelector('.mv-wrap'); t.focus(); })()", sid)   # the last stop inside the strip: the next Tab is the grip
    before = cdp.js(RING, sid)
    test.assertFalse(before["on"], f"{width} {look}: the strip holds the focus, not the grip")
    test.assertEqual(before["style"], "none", f"{width} {look}: no ring until the grip is focused")
    tab(cdp, sid)
    test.assertTrue(wait(lambda: cdp.js(RING, sid)["on"]), f"{width} {look}: Tab reaches the grip")
    got = cdp.js(RING, sid)
    test.assertTrue(got["visible"], f"{width} {look}: focused by keyboard, so :focus-visible")
    test.assertEqual((got["style"], got["width"]), ("solid", "2px"), f"{width} {look}: the 2px ring of the design, not the browser's own")
    test.assertEqual(got["offset"], "1px", f"{width} {look}: the ring sits 1px off the grip")
    test.assertEqual(got["color"], got["want"], f"{width} {look}: in the focus colour")
    test.assertNotIn(got["color"], ("rgba(0, 0, 0, 0)", "transparent"), f"{width} {look}: seen")


class FocusRing(C.Base, unittest.TestCase):
    THEME = "prototype-2.0"

    def test_the_grip_shows_the_ring_when_reached_by_keyboard_in_classic(self):
        for cdp, sid, w in self.every():
            self.assertEqual(cdp.js("document.querySelector('.mv').dataset.look", sid), "classic")
            ring_by_keyboard(self, cdp, sid, w, "classic")


class FocusRingCards(C.Base, unittest.TestCase):
    THEME = None

    def test_the_grip_shows_the_ring_when_reached_by_keyboard_in_cards(self):
        for cdp, sid, w in self.every():
            self.assertEqual(cdp.js("document.querySelector('.mv').dataset.look || ''", sid), "")
            ring_by_keyboard(self, cdp, sid, w, "cards")


class CardsDark(C.Base, unittest.TestCase):
    THEME = None
    PEEK = """(() => { const g = document.querySelector('.mv-grip'), s = getComputedStyle(g.querySelector('span'));
      const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 4).map(Number), lum = (c) => { const [r, gg, b] = c.slice(0, 3).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * r + 0.7152 * gg + 0.0722 * b; };
      let e = g.parentElement, bg = [255, 255, 255, 1], under = null;
      for (; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c.length < 4) c.push(1); if (c[3] > 0) { bg = c; under = e.className || e.tagName; break; } }
      const bar = rgb(s.borderTopColor), a = lum(bar), b = lum(bg);
      return { bar: s.borderTopColor, bg: getComputedStyle(e || document.body).backgroundColor, under, thick: s.borderTopWidth, width: g.getBoundingClientRect().width, contrast: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05), barAlpha: bar.length < 4 ? 1 : bar[3] }; })()"""

    def test_the_cards_grip_bar_is_seen_against_what_is_behind_it_in_dark(self):
        seen = {}
        for cdp, sid, w in self.every():
            mode = cdp.js("document.documentElement.dataset.theme", sid)
            g = cdp.js(self.PEEK, sid)
            seen[(w, mode)] = g["bar"]
            self.assertEqual(g["thick"], "2px", f"{w} {mode}: two lines of 2px")
            self.assertAlmostEqual(g["width"], 64, delta=1, msg=f"{w} {mode}: the centred 64px target")
            self.assertEqual(g["barAlpha"], 1, f"{w} {mode}: the bar is solid")
            self.assertGreaterEqual(g["contrast"], 3.0, f"{w} {mode}: the bar {g['bar']} against {g['bg']} ({g['under']}) is a 3:1 control mark: {g['contrast']:.2f}")
        for w in (1400, 900):
            self.assertNotEqual(seen[(w, "light")], seen[(w, "dark")], f"{w}: dark draws its own bar colour, not the light one")

    def test_hovering_the_cards_grip_in_dark_darkens_to_the_muted_text_colour_and_stays_seen(self):
        for cdp, sid, w in self.every():
            mode = cdp.js("document.documentElement.dataset.theme", sid)
            x, y = cdp.js(C.GRIP, sid)
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('.mv-grip').matches(':hover')", sid)))
            g = cdp.js(self.PEEK, sid)
            want = cdp.js("(() => { const p = document.createElement('i'); p.style.color = 'var(--text-muted)'; document.body.appendChild(p); const c = getComputedStyle(p).color; p.remove(); return c; })()", sid)
            self.assertEqual(g["bar"], want, f"{w} {mode}: hover uses --text-muted")
            self.assertGreaterEqual(g["contrast"], 3.0, f"{w} {mode}: still a 3:1 mark on hover: {g['contrast']:.2f}")


if __name__ == "__main__":
    unittest.main()
