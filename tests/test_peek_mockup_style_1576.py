"""Row 1576 (v1.3): the peek's 'Shown to the client' label and 'Show history' link drawn in the mock-up's style, in Classic, at 1400 and 900.
Run: python3 dev/run_tests.py test_peek_mockup_style_1576

AP1 the label (12px, 500, #55677A, a #0A8F9C eye at 18px, an 8px gap), AP2 the link (13px, 600, #5B47D8, no underline, the 16px chevron),
AP3 hover (the link row takes #ECE9FF with radius 8px; the label has no hover), AP4 keyboard focus (2px solid #5B47D8, offset 1px, not clipped),
AP5 the dark theme (4.5 for the two words, 3 for the eye and the chevron, the hover tint and the ring seen), AP6 the 940 px peek (one line each,
inside the peek), AP7 the Issue Activity row reads a due date day first.
How AP6 sets the width: the peek's own saved width (localStorage clark.peekWidth) is 940 before the page loads; the page keeps it between its
minimum and the window minus 32 px, so at 1400 the peek is 940 and at 900 it is the widest the window gives it (measured 885, not 940: the window is 900).
"""
import json
import re
import unittest
from unittest import mock

import _testpage
from clark import activity_read, changes, page, theme as themes

import test_peek_latest
import test_server  # noqa: F401  (a test that drives Chrome carries this import)
from test_server import chrome, wait
from test_peek import key

_B = test_peek_latest.Browser
del test_peek_latest
ITEM = "TUL-A-002"
LABEL, BTN = "#peek [data-pk-latest-client]", "#peek [data-pk-lh-btn]"
CONTRAST = ("const lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]); };"
            " const rgb = s => (s.match(/[\\d.]+/g) || []).map(Number);"
            " const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };"
            " const under = e => { for (let n = e; n; n = n.parentElement) { const c = rgb(getComputedStyle(n).backgroundColor); if (c.length === 3 || (c.length === 4 && c[3] > .9)) return c; } return [255, 255, 255]; };")


def classic():
    """The test page with the Classic theme layered on, as the served page draws it (Classic only: Cards is unmaintained)."""
    real = _testpage.html
    return mock.patch.object(_testpage, "html", lambda branding=None: page.layer_theme(real(), themes.css("prototype-2.0")))


class Style(unittest.TestCase):
    load, refused, kinds = _B.load, _B.refused, _B.kinds
    HOLD = _B.HOLD
    _base_setup = _B.setUp

    def fresh(self):
        _B.fresh(self)
        make = changes.make_change(self.store.path, [], "Demo User")
        for day in ("2026-11-06", "2026-11-20"):          # two stored due dates, for AP7's Activity row
            self.assertEqual(make({"project": self.code, "kind": "actions", "op": "update", "id": ITEM, "changes": {"due_date": day}, "place": "peek"})[0], 200)

    def setUp(self):
        self._base_setup()
        p = classic()
        p.start()
        self.addCleanup(p.stop)

    def hover(self, cdp, sid, selector):
        """Move the pointer to the middle of `selector` once the peek has stopped sliding in and that spot holds the element."""
        sel = json.dumps(selector)
        probe = (f"(() => {{ const e = document.querySelector({sel}); e.scrollIntoView({{block: 'center'}}); const r = e.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;"
                 f" const t = document.elementFromPoint(x, y); return t && e.contains(t) ? [x, y] : null; }})()")
        self.assertTrue(wait(lambda: cdp.js(probe, sid)), f"the middle of {selector} is on screen and not covered")
        r = cdp.js(probe, sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r[0], "y": r[1]}, sid)

    def keyboard_focus(self, cdp, sid):
        key(cdp, sid, "ArrowDown")                                  # a key was pressed last: :focus-visible follows the keyboard
        cdp.js(f"document.querySelector({json.dumps(BTN)}).focus()", sid)

    def test_the_shown_to_the_client_label_is_12px_muted_with_a_cyan_eye(self):
        shown, internal = self.kinds()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, shown, edit=True)
                got = cdp.js("(() => { const l = document.querySelector('#peek [data-pk-latest-client]'), c = getComputedStyle(l), s = l.querySelector('svg'), sc = getComputedStyle(s),"
                             " lab = document.querySelector('#peek .pk-lab').getBoundingClientRect(), r = l.getBoundingClientRect(), t = s.getBoundingClientRect();"
                             " return {text: l.textContent.trim(), size: c.fontSize, weight: c.fontWeight, color: c.color, gap: c.columnGap, eye: sc.color, w: sc.width, h: sc.height,"
                             " eyeGap: Math.round(l.lastChild.nodeType === 3 ? (() => { const g = document.createRange(); g.selectNodeContents(l.lastChild); return g.getBoundingClientRect().left - t.right; })() : -1),"
                             " right: lab.right - r.right}; })()", sid)
                self.assertEqual(got["text"], "Shown to the client", got)
                self.assertEqual((got["size"], got["weight"], got["color"]), ("12px", "500", "rgb(85, 103, 122)"), got)       # #55677A
                self.assertEqual((got["eye"], got["w"], got["h"], got["gap"]), ("rgb(10, 143, 156)", "18px", "18px", "8px"), got)      # #0A8F9C
                self.assertEqual(got["eyeGap"], 8, got)
                self.assertLess(got["right"], 4, f"on the right of the heading line: {got}")
                sent, sid = self.load(cdp, width, internal, edit=True)
                self.assertFalse(cdp.js(f"!!document.querySelector({json.dumps(LABEL)})", sid), "an internal item has no label")

    def test_the_show_history_row_is_13px_600_in_the_mockup_blue(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, ITEM, edit=True)
                got = cdp.js("(() => { const b = document.querySelector('#peek [data-pk-lh-btn]'), c = getComputedStyle(b), r = b.getBoundingClientRect(), v = b.querySelector('.pk-lh-car').getBoundingClientRect(),"
                             " w = b.querySelector('span').getBoundingClientRect();"
                             " return {word: b.textContent.trim(), size: c.fontSize, weight: c.fontWeight, color: c.color, deco: c.textDecorationLine, h: Math.round(r.height), chev: [Math.round(v.width), Math.round(v.height)],"
                             " wordLeft: w.left - r.left, chevRight: r.right - v.right, full: Math.round(r.width)}; })()", sid)
                self.assertEqual(got["word"], "Show history", got)
                self.assertEqual((got["size"], got["weight"], got["color"], got["deco"]), ("13px", "600", "rgb(91, 71, 216)", "none"), got)       # #5B47D8
                self.assertEqual(got["chev"], [16, 16], got)
                self.assertGreaterEqual(got["h"], 36, got)
                self.assertLess(got["wordLeft"], 4, got)
                self.assertLess(got["chevRight"], 4, got)
                self.assertGreater(got["full"], 200, got)

    def test_hover_tints_the_history_row_and_not_the_label(self):
        shown, _internal = self.kinds()
        probe = "(e => { const c = getComputedStyle(e); return {bg: c.backgroundColor, radius: c.borderTopLeftRadius}; })(document.querySelector(%s))"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, shown, edit=True)
                before = cdp.js(probe % json.dumps(LABEL), sid)
                self.hover(cdp, sid, LABEL)
                self.assertTrue(wait(lambda: cdp.js(f"document.querySelector({json.dumps(LABEL)}).matches(':hover')", sid)), "the pointer is on the label")
                self.assertEqual(cdp.js(probe % json.dumps(LABEL), sid), before, "the read-only label has no hover change")
                idle = cdp.js(probe % json.dumps(BTN), sid)
                self.assertNotEqual(idle["bg"], "rgb(236, 233, 255)", idle)
                self.hover(cdp, sid, BTN)
                self.assertTrue(wait(lambda: cdp.js(f"document.querySelector({json.dumps(BTN)}).matches(':hover')", sid)))
                got = cdp.js(probe % json.dumps(BTN), sid)
                self.assertEqual((got["bg"], got["radius"]), ("rgb(236, 233, 255)", "8px"), got)          # #ECE9FF
                self.assertEqual(cdp.js(f"(v => [Math.round(v.width), Math.round(v.height)])(document.querySelector({json.dumps(BTN)} + ' .pk-lh-car').getBoundingClientRect())", sid), [16, 16])

    def test_keyboard_focus_on_show_history_draws_the_2px_ring_inside_the_peek(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, ITEM, edit=True)
                self.keyboard_focus(cdp, sid)
                got = cdp.js("(() => { const b = document.querySelector('#peek [data-pk-lh-btn]'), c = getComputedStyle(b), r = b.getBoundingClientRect(), p = document.querySelector('#peek').getBoundingClientRect();"
                             " const o = parseFloat(c.outlineOffset), w = parseFloat(c.outlineWidth); let clip = 0;"
                             " for (let n = b.parentElement; n; n = n.parentElement) { const s = getComputedStyle(n); if (s.overflowX === 'visible' && s.overflowY === 'visible') continue;"
                             "   const q = n.getBoundingClientRect(); clip = Math.max(clip, q.left - (r.left - o - w), (r.right + o + w) - q.right, q.top - (r.top - o - w)); if (n.id === 'peek') break; }"
                             " return {vis: b.matches(':focus-visible'), style: c.outlineStyle, w: c.outlineWidth, color: c.outlineColor, off: c.outlineOffset, clip, inside: r.left - o - w >= p.left && r.right + o + w <= p.right}; })()", sid)
                self.assertTrue(got["vis"], got)
                self.assertEqual((got["style"], got["w"], got["color"], got["off"]), ("solid", "2px", "rgb(91, 71, 216)", "1px"), got)       # #5B47D8
                self.assertTrue(got["inside"], got)
                self.assertLessEqual(got["clip"], 0, f"the ring is not clipped by any box up to the peek: {got}")

    def test_both_elements_are_readable_in_the_dark_theme(self):
        shown, _internal = self.kinds()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, shown, edit=True, dark=True)
                self.hover(cdp, sid, BTN)
                self.assertTrue(wait(lambda: cdp.js(f"document.querySelector({json.dumps(BTN)}).matches(':hover')", sid)))
                hov = cdp.js(f"(() => {{ {CONTRAST} const b = document.querySelector({json.dumps(BTN)}); return ratio(rgb(getComputedStyle(b).backgroundColor), under(b.parentElement)); }})()", sid)
                self.assertGreater(hov, 1.1, "the hover tint is seen against the dark peek")
                self.keyboard_focus(cdp, sid)
                got = cdp.js("(() => { " + CONTRAST + " const l = document.querySelector('#peek [data-pk-latest-client]'), b = document.querySelector('#peek [data-pk-lh-btn]'),"
                             " eye = getComputedStyle(l.querySelector('svg')).color, chev = getComputedStyle(b.querySelector('.pk-lh-car')).color, ring = getComputedStyle(b).outlineColor;"
                             " const bg = under(l), bb = under(b.parentElement);"
                             " return {label: ratio(rgb(getComputedStyle(l).color), bg), eye: ratio(rgb(eye), bg), link: ratio(rgb(getComputedStyle(b).color), bb), chev: ratio(rgb(chev), bb), ring: ratio(rgb(ring), bb), ringW: getComputedStyle(b).outlineWidth}; })()", sid)
                self.assertGreaterEqual(got["label"], 4.5, got)
                self.assertGreaterEqual(got["link"], 4.5, got)
                self.assertGreaterEqual(got["eye"], 3, got)
                self.assertGreaterEqual(got["chev"], 3, got)
                self.assertGreaterEqual(got["ring"], 3, got)
                self.assertEqual(got["ringW"], "2px", got)

    def test_label_and_link_fit_the_peek_at_940px(self):
        shown, _internal = self.kinds()
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    sent, sid = self.load(cdp, width, shown, edit=True, dark=dark)
                    cdp.js("localStorage.setItem('clark.peekWidth', '940')", sid)
                    cdp.js("location.reload()", sid)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0, 10))
                    cdp.js(f"clarkPage.openPeek({json.dumps(shown)})", sid)
                    self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector({json.dumps(BTN)}) && !!document.querySelector({json.dumps(LABEL)})", sid)))
                    got = cdp.js("(() => { const p = document.querySelector('#peek').getBoundingClientRect(), one = s => { const e = document.querySelector(s), r = e.getBoundingClientRect(), lh = parseFloat(getComputedStyle(e).lineHeight) || 16;"
                                 " const t = e.querySelector('span') || e; return {in: r.left >= p.left - 1 && r.right <= p.right + 1, lines: Math.round(t.getBoundingClientRect().height / Math.max(lh, 1))}; };"
                                 " return {peek: Math.round(p.width), label: one('#peek [data-pk-latest-client]'), link: one('#peek [data-pk-lh-btn]'), scroll: document.documentElement.scrollWidth > document.documentElement.clientWidth}; })()", sid)
                    self.assertEqual(got["peek"], 940, got) if width == 1400 else self.assertLessEqual(got["peek"], width, got)
                    self.assertTrue(got["label"]["in"] and got["link"]["in"], got)
                    self.assertLessEqual(got["label"]["lines"], 1, got)
                    self.assertLessEqual(got["link"]["lines"], 1, got)
                    self.assertFalse(got["scroll"], "no horizontal scroll")

    def test_the_issue_activity_row_shows_the_due_date_day_first(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ITEM, edit=True, dark=dark)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-htab=activity]')", sid)))
                    cdp.js("document.querySelector('[data-pk-htab=activity]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('[data-activity-row]').length", sid) > 0))
                    rows = cdp.js("Array.from(document.querySelectorAll('[data-activity-row] .pa-what')).map(e => e.textContent.replace(/\\s+/g, ' ').trim())", sid)
                    self.assertTrue(any(re.fullmatch(r"Due date: 06-11-2026 → (to )?20-11-2026", r) for r in rows), rows)       # "to" is the screen-reader word beside the arrow
                    self.assertFalse(any("2026-11-20" in r for r in rows), rows)


if __name__ == "__main__":
    unittest.main()
