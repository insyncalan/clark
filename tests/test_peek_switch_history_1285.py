"""Row 1285 (v1.3), the two rows the ruling of 20-11 keeps: "Shown to the client" is a switch (40 by 22, knob 18) and "Show history" is a row like the others (label left,
14 px, 36 px tall, no underline). Classic only, Edit, measured at 1400 and 900. The switch's label is the table's own words; the Show history row's value side is not in the table, so it stays empty.
Run: python3 dev/run_tests.py test_peek_switch_history_1285
"""
import unittest

import test_peek_gaps_1285 as g
from test_server import chrome, wait

ITEMS = (("TUL-A-002", "action"), ("TUL-007", "risk"), ("TUL-010", "issue"), ("TUL-D-016", "decision"))
TOKEN = ("(name) => { const p = document.createElement('i'); p.style.background = 'var(' + name + ')'; document.body.appendChild(p);"
         " const v = getComputedStyle(p).backgroundColor; p.remove(); return v; }")
SWITCH = ("(() => { const b = document.querySelector('#peek [data-pk-client-row] .pk-client'); if (!b) return null;"
          " const t = b.querySelector('.pk-sw'), k = b.querySelector('.pk-sw-knob'); if (!t || !k) return {text: b.textContent.trim(), pressed: b.getAttribute('aria-pressed'), track: false};"
          " const tr = t.getBoundingClientRect(), kr = k.getBoundingClientRect(), tc = getComputedStyle(t), kc = getComputedStyle(k);"
          " return {text: b.textContent.trim(), pressed: b.getAttribute('aria-pressed'), track: true, w: tr.width, h: tr.height, radius: tc.borderTopLeftRadius, bg: tc.backgroundColor,"
          " kw: kr.width, kh: kr.height, kbg: kc.backgroundColor, inside: kr.left >= tr.left && kr.right <= tr.right, eye: !!b.querySelector('svg'), label: b.getBoundingClientRect().left <= tr.left}; })()")
HIST = ("(() => { const b = document.querySelector('#peek [data-pk-lh-btn]'); if (!b) return null; const c = getComputedStyle(b), r = b.getBoundingClientRect(), p = document.querySelector('#peek').getBoundingClientRect();"
        " return {text: b.textContent.trim(), size: c.fontSize, h: r.height, deco: c.textDecorationLine, align: c.textAlign, left: r.left - p.left, ml: c.marginLeft, colour: c.color}; })()")


class Rows(g.Focus):
    def token(self, cdp, sid, name):
        return cdp.js(f"({TOKEN})('{name}')", sid)

    def test_shown_to_the_client_is_a_switch_40_by_22_with_an_18_knob(self):
        for width in (1400, 900):
            for ref, kind in ITEMS:
                with self.subTest(width=width, kind=kind), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    self.assertTrue(wait(lambda: cdp.js(SWITCH, sid) is not None), "the client row drew")
                    got = cdp.js(SWITCH, sid)
                    self.assertTrue(got["track"], got)
                    self.assertEqual(got["text"], "Shown to the client", got)
                    self.assertEqual((got["w"], got["h"], got["kw"], got["kh"]), (40, 22, 18, 18), got)
                    self.assertEqual(got["radius"][:3], "999", "a pill track")
                    self.assertTrue(got["inside"], "the knob stays inside the track")
                    self.assertEqual(got["kbg"], self.token(cdp, sid, "--white"), "a white knob")
                    on = got["pressed"] == "true"
                    self.assertEqual(got["bg"], self.token(cdp, sid, "--brand-blue" if on else "--grey-300"), got)
                    self.assertTrue(got["eye"] and got["label"], "the eye and the label sit left of the switch")

    def test_the_knob_sits_at_the_end_of_the_track_that_matches_the_state(self):
        knob = ("(() => { const b = document.querySelector('#peek [data-pk-client-row] .pk-client'); const t = b.querySelector('.pk-sw').getBoundingClientRect(),"
                " k = b.querySelector('.pk-sw-knob').getBoundingClientRect(); return {pressed: b.getAttribute('aria-pressed'), left: k.left - t.left, right: t.right - k.right}; })()")
        for width in (1400, 900):
            for ref, kind in ITEMS:
                with self.subTest(width=width, kind=kind), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    self.assertTrue(wait(lambda: cdp.js(SWITCH, sid) is not None))
                    for _ in range(2):
                        got = cdp.js(knob, sid)
                        self.assertTrue(wait(lambda: (lambda g: (g["right"] if g["pressed"] == "true" else g["left"]) == 2)(cdp.js(knob, sid))), f"the knob rests 2 px from the {'right' if got['pressed'] == 'true' else 'left'} end: {got}")
                        cdp.js("document.querySelector('#peek [data-pk-client-row] .pk-client').click()", sid)
                        wait(lambda: cdp.js(knob, sid)["pressed"] != got["pressed"])

    def test_one_click_flips_the_switch_and_the_colour(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, "TUL-007", edit=True)
            self.assertTrue(wait(lambda: cdp.js(SWITCH, sid) is not None))
            before = cdp.js(SWITCH, sid)
            cdp.js("document.querySelector('#peek [data-pk-client-row] .pk-client').click()", sid)
            self.assertTrue(wait(lambda: cdp.js(SWITCH, sid)["pressed"] != before["pressed"]), "the switch flipped")
            self.assertTrue(wait(lambda: cdp.js(SWITCH, sid)["bg"] != before["bg"]), "the track colour changed (after its short transition)")
            after = cdp.js(SWITCH, sid)
            self.assertEqual(after["text"], "Shown to the client")

    def test_show_history_is_a_row_like_the_others(self):
        for width in (1400, 900):
            for ref, kind in ITEMS:
                with self.subTest(width=width, kind=kind), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    self.assertTrue(wait(lambda: cdp.js(HIST, sid) is not None), "the Show history control drew")
                    got = cdp.js(HIST, sid)
                    self.assertEqual(got["text"], "Show history", got)
                    self.assertEqual(got["size"], "14px", got)
                    self.assertGreaterEqual(got["h"], 36, got)
                    self.assertEqual(got["deco"], "none", "no underline: a row, not a link")
                    self.assertEqual(got["align"], "left", got)
                    self.assertEqual(got["ml"], "0px", "the label starts at the left, as every row's label does")
                    self.assertEqual(got["colour"], self.token(cdp, sid, "--text-muted"), got)

    def test_show_history_still_opens_the_list(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, "TUL-007", edit=True)
            self.assertTrue(wait(lambda: cdp.js(HIST, sid) is not None))
            cdp.js("document.querySelector('#peek [data-pk-lh-btn]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-lh-panel]')", sid)), "the history opened")
            self.assertEqual(cdp.js("document.querySelector('#peek [data-pk-lh-btn]').textContent.trim()", sid), "Hide history")


if __name__ == "__main__":
    unittest.main()
