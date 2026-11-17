"""Row 1257 (v1.2), item 4, mutation check of the Latest update card: seven edits of the card's rules that tests/test_peek_latest_box_1257.py let through
(the focus background, the footer's side, the hidden editor key line, the resting background, the heading gap, the open editor's height, the line height).
Measured at 1400 and 900 for an action, a risk and an issue; colours are read from the tokens, not typed.
Run: python3 dev/run_tests.py test_peek_latest_box_survivors_1257
"""
import unittest

import test_peek_latest
import test_server  # noqa: F401  (a test that drives Chrome carries this import)
from test_server import chrome

_B = test_peek_latest.Browser
ITEMS = (("TUL-A-002", "action"), ("TUL-007", "risk"), ("TUL-010", "issue"))
TOKEN = "(v => { const p = document.createElement('i'); p.style.background = 'var(' + v + ')'; document.body.appendChild(p); const c = getComputedStyle(p).backgroundColor; p.remove(); return c; })"
BOX = "document.querySelector('#peek [data-pk-lbox]')"


class Survivors(unittest.TestCase):
    load, open_box, type_in, save_key, toast, fresh, refused = (_B.load, _B.open_box, _B.type_in, _B.save_key, _B.toast, _B.fresh, _B.refused)
    HOLD, SHOWN, BOX = _B.HOLD, _B.SHOWN, _B.BOX
    setUp = _B.setUp

    def each(self):
        for width in (1400, 900):
            for ref, kind in ITEMS:
                with self.subTest(width=width, kind=kind), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    yield cdp, sid

    def test_the_resting_card_is_the_soft_tint_and_the_focused_card_is_the_surface(self):
        for cdp, sid in self.each():
            rest = cdp.js(f"getComputedStyle({BOX}).backgroundColor", sid)
            soft, surface = cdp.js(f"[{TOKEN}('--grey-50'), {TOKEN}('--surface')]", sid)
            self.assertEqual(rest, soft, "at rest the card is the soft tint")
            self.assertNotEqual(soft, surface)
            self.open_box(cdp, sid)
            self.assertEqual(cdp.js(f"getComputedStyle({BOX}).backgroundColor", sid), surface, "focused, the card turns to the surface")

    def test_the_save_key_sits_at_the_right_end_of_the_footer(self):
        for cdp, sid in self.each():
            r = cdp.js(f"(() => {{ const b = ({BOX}).getBoundingClientRect(), k = ({BOX}).querySelector('[data-pk-latest-hint] kbd').getBoundingClientRect(); return {{ left: k.left - b.left, right: b.right - k.right, w: b.width }}; }})()", sid)
            self.assertGreater(r["left"], r["w"] / 3, "the key and its words are in the right half, not at the left edge")

    def test_the_editors_own_key_line_is_hidden_while_the_box_is_open(self):
        for cdp, sid in self.each():
            self.open_box(cdp, sid)
            n = cdp.js(f"Array.from(({BOX}).querySelectorAll('.rt-keys')).filter(e => getComputedStyle(e).display !== 'none').length", sid)
            self.assertEqual(n, 0, "the footer strip says how to save, so the editor's own key line is not shown")

    def test_the_heading_is_8_px_above_the_card(self):
        for cdp, sid in self.each():
            gap = cdp.js(f"({BOX}).getBoundingClientRect().top - document.querySelector('#peek .pk-lab').getBoundingClientRect().bottom", sid)
            self.assertAlmostEqual(gap, 8, delta=1)

    def test_the_open_editor_is_at_least_84_px_high_and_the_text_has_the_line_height(self):
        for cdp, sid in self.each():
            rest = cdp.js(f"(() => {{ const v = ({BOX}).querySelector('.rt-view'), c = getComputedStyle(v); return parseFloat(c.lineHeight) / parseFloat(c.fontSize); }})()", sid)
            self.assertAlmostEqual(rest, 1.45, delta=0.01, msg="the resting text")
            self.open_box(cdp, sid)
            r = cdp.js(f"(() => {{ const p = ({BOX}).querySelector('.ProseMirror'), c = getComputedStyle(p); return {{ h: p.getBoundingClientRect().height, ratio: parseFloat(c.lineHeight) / parseFloat(c.fontSize) }}; }})()", sid)
            self.assertGreaterEqual(r["h"], 84, r)
            self.assertAlmostEqual(r["ratio"], 1.45, delta=0.01, msg="the open text")


del _B


if __name__ == "__main__":
    unittest.main()
