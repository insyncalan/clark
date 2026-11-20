"""Row 1267 close list: the grip's focus ring, the grip zoom kept for each place, and the Cards grip in dark.

Run: python3 dev/run_tests.py test_ms_grip_keep_1267
Chrome launches at 1400 and 900 px. The Classic grip is the full-width bottom edge (row 1315); the Cards grip is the centred 64x24 one.
"""
import unittest

import test_ms_header_1230 as H
import test_ms_timeline_classic_1315 as C
from test_server import chrome, wait

GRIP = "document.querySelector('.mv-wrap [data-grip], [data-grip]')"
RING = """(() => { const g = document.querySelector('[data-grip]'), s = getComputedStyle(g), p = document.createElement('i');
  p.style.color = 'var(--focus)'; document.body.appendChild(p); const want = getComputedStyle(p).color; p.remove();
  return { on: document.activeElement === g, visible: g.matches(':focus-visible'), style: s.outlineStyle, width: s.outlineWidth, color: s.outlineColor, want }; })()"""
PCT = "document.querySelector('[data-place] .mv-wrap').dataset.zoomPct"


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


STORED = "Object.fromEntries(Object.keys(localStorage).filter((k) => k.startsWith('clark.tlZoom.')).map((k) => [k, localStorage.getItem(k)]))"


class ZoomPerPlace(H.Base):
    """The grip zoom (tlZoom.<place>, not the Week/Month/Quarter scale tlScale.<place>): the Milestones page and the Dashboard section keep their own."""

    def drag_grip(self, cdp, sid, scope, dy):
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid), 10))
        cdp.js(f"document.querySelector('{scope} [data-grip]').scrollIntoView({{block: 'center', behavior: 'instant'}})", sid)
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid), 10))
        x, y = cdp.js(f"(() => {{ const r = document.querySelector('{scope} [data-grip]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }})()", sid)
        mouse = lambda kind, py, **kw: cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": py, **kw}, sid)
        mouse("mousePressed", y, button="left", clickCount=1)
        for i in range(1, 7):
            mouse("mouseMoved", y + dy * i // 6, button="left", buttons=1)
        mouse("mouseReleased", y + dy, button="left", clickCount=1)

    def pct(self, cdp, sid, scope):
        return cdp.js(f"document.querySelector('{scope} .mv-wrap').dataset.zoomPct", sid)

    def stored(self, cdp, sid):
        return cdp.js(STORED, sid)

    def test_a_dragged_zoom_comes_back_for_that_place_and_the_other_place_is_not_touched(self):
        PAGE, SEC = ".msv[data-place=page]", ".msv[data-place^=sec-]"
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, "#milestones&p=ABC", width, False, f"{PAGE} .mv-wrap")
                self.assertEqual(self.pct(cdp, sid, PAGE), "100")
                self.drag_grip(cdp, sid, PAGE, 100)
                self.assertTrue(wait(lambda: int(self.pct(cdp, sid, PAGE)) > 130), f"{width}: dragged down to a bigger zoom")
                page_zoom = self.pct(cdp, sid, PAGE)
                self.assertTrue(wait(lambda: list(self.stored(cdp, sid)) == ["clark.tlZoom.page"]), f"{width}: only the page's own key is written: {self.stored(cdp, sid)}")
                kept = self.stored(cdp, sid)["clark.tlZoom.page"]
                self.assertEqual(round(float(kept) * 100), int(page_zoom), f"{width}: the number kept is the zoom shown")
                cdp.call("Page.reload", {}, sid)
                self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{PAGE} .mv-wrap')", sid)), f"{width}: redrawn")
                self.assertEqual(self.pct(cdp, sid, PAGE), page_zoom, f"{width}: after a reload the page zoom is back")
                cdp.js("location.hash = '#dashboard&p=ABC'", sid)
                self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{SEC} .mv-wrap')", sid), 10), f"{width}: the Dashboard section drew")
                self.assertEqual(self.pct(cdp, sid, SEC), "100", f"{width}: the section does not take the page's zoom")
                self.drag_grip(cdp, sid, SEC, 60)
                self.assertTrue(wait(lambda: int(self.pct(cdp, sid, SEC)) > 100), f"{width}: the section zooms on its own")
                sec_zoom = self.pct(cdp, sid, SEC)
                self.assertTrue(wait(lambda: len(self.stored(cdp, sid)) == 2), f"{width}: the section keeps its own key: {self.stored(cdp, sid)}")
                stored = self.stored(cdp, sid)
                self.assertEqual(stored["clark.tlZoom.page"], kept, f"{width}: the page's kept zoom is not changed by the section")
                cdp.js("location.hash = '#milestones&p=ABC'", sid)
                self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{PAGE} .mv-wrap')", sid), 10))
                self.assertEqual(self.pct(cdp, sid, PAGE), page_zoom, f"{width}: back on the page, its own zoom")
                cdp.js("location.hash = '#dashboard&p=ABC'", sid)
                self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{SEC} .mv-wrap')", sid), 10))
                self.assertEqual(self.pct(cdp, sid, SEC), sec_zoom, f"{width}: back on the Dashboard, the section's own zoom")

    def test_the_scale_and_the_grip_zoom_are_two_keys(self):
        PAGE = ".msv[data-place=page]"
        with chrome() as cdp:
            sid = self.visit(cdp, "#milestones&p=ABC", 1400, False, f"{PAGE} .mv-wrap")
            cdp.js(f"document.querySelector('{PAGE} [data-scale-b=week]').click()", sid)
            self.assertTrue(wait(lambda: sorted(cdp.js("Object.keys(localStorage).filter((k) => k.startsWith('clark.tl'))", sid)) == ["clark.tlScale.page"]))
            self.assertEqual(self.pct(cdp, sid, PAGE), "100", "a changed scale leaves the grip zoom at 100%")


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
