"""Row 1214: while a section is dragged by its handle, a ghost (a copy of its title) follows the pointer, its old place keeps a faint
dashed outline, the place it would land in is drawn dashed, and these glide in over about 160 ms (not at all when motion is reduced).
Run: python3 dev/run_tests.py test_drag_ghost_1214. Checked at 1400 and 900 px; the real page in headless Chrome.
"""
import base64
import os
import unittest

import test_enrichments as te
import test_report_editor as tre
from test_motion import ALLOW, MODES, OWN
from test_server import chrome

SHOTS = os.environ.get("GHOST_SHOTS")       # a folder to keep screenshots in, to look at; unset: none are written


class DragGhost(tre.Base):
    def go(self, cdp, mode):
        _, media, own = mode
        p = tre.Pg.at(self, cdp, self.s.port, "#dashboard&p=ABC")
        cdp.call("Emulation.setEmulatedMedia", {"features": te.REDUCE if media else ALLOW}, p.sid)
        if not media and not own:
            p.js("delete document.documentElement.dataset.motion")
        p.ready()
        if own:
            p.js(OWN)
        return p

    def shot(self, cdp, p, name):
        if SHOTS:
            png = cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]
            with open(os.path.join(SHOTS, name + ".png"), "wb") as f:
                f.write(base64.b64decode(png))

    def test_the_ghost_follows_the_pointer_the_old_place_is_outlined_and_all_goes_at_the_drop(self):
        for width in (1400, 900):
            for mode in MODES:
                with self.subTest(width=width, mode=mode[0]), chrome() as cdp:
                    p = self.go(cdp, mode)
                    p.tall(cdp, width)
                    p.edit()
                    hx, hy, _ = p.box('[data-id="ABC-S-001"] [data-drag]')
                    _, _, bottom = p.box('[data-id="ABC-S-003"]')
                    title = p.js("document.querySelector('[data-id=\"ABC-S-001\"] .sec-h').textContent")
                    ty = bottom - 3
                    self.assertIsNone(p.js("document.querySelector('.sec-ghost')"), "no ghost before a drag")
                    p.mouse("mousePressed", hx, hy, 1)
                    for step in range(1, 9):
                        p.mouse("mouseMoved", hx + 40, hy + (ty - hy) * step / 8, 1)
                    p.until("!!document.querySelector('.sec-ghost')", "the ghost")
                    self.assertEqual(p.js("document.querySelector('.sec-ghost').textContent"), title, "a copy of the title")
                    self.assertEqual(p.js("document.querySelector('.sec-ghost').getAttribute('aria-hidden')"), "true")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.sec-ghost')).pointerEvents"), "none")
                    if mode[0] == "allowed":
                        p.until("document.getAnimations().length === 0", "the glide ends by itself", 3)
                    r = p.js("(function(){var r=document.querySelector('.sec-ghost').getBoundingClientRect();return [r.left,r.top];})()")
                    self.assertAlmostEqual(r[0], hx + 40 + 12, delta=1, msg="it follows the pointer across")
                    self.assertAlmostEqual(r[1], ty + 12, delta=1, msg="and down")
                    p.until("!!document.querySelector('.sec-was')", "the old place is outlined")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.sec-was')).borderTopStyle"), "dashed")
                    p.until("(function(){var s=document.querySelector('.sec.drag-slot[data-id=\"ABC-S-001\"]');return !!s && !!s.previousElementSibling && s.previousElementSibling.dataset.id === 'ABC-S-003';})()", "the slot sits right after the third section")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.sec.drag-slot')).borderTopStyle"), "dashed")
                    after = p.js("[...document.querySelectorAll('.secs > .sec')].map(e => e.dataset.id)")
                    self.assertEqual(after[after.index("ABC-S-001") - 1], "ABC-S-003", "the others made room: it sits right after the third section")
                    if mode[0] == "allowed":
                        p.until("document.getAnimations().length === 0", "the glide ends by itself", 3)
                    glide = p.js("getComputedStyle(document.querySelector('.sec.drag-slot')).animationDuration")
                    self.assertEqual(glide, "0.16s" if mode[0] == "allowed" else "0s")
                    gname = p.js("getComputedStyle(document.querySelector('.sec-ghost')).animationName")
                    self.assertEqual(gname, "none", "the ghost has no animation of its own, it would hold it at the corner while it plays")
                    self.shot(cdp, p, f"ghost-{width}-{mode[0]}")
                    p.key("Escape", code="Escape", vk=27)
                    p.mouse("mouseReleased", hx + 40, ty, 0)
                    p.until("!document.querySelector('.sec-ghost')", "the ghost goes")
                    self.assertIsNone(p.js("document.querySelector('.drag-from, .drag-slot, .sec-was')"))

    def test_a_click_with_no_travel_draws_no_ghost(self):
        with chrome() as cdp:
            p = self.go(cdp, MODES[0])
            p.edit()
            hx, hy, _ = p.box('[data-id="ABC-S-001"] [data-drag]')
            p.mouse("mousePressed", hx, hy, 1)
            p.mouse("mouseMoved", hx + 1, hy, 1)
            self.assertIsNone(p.js("document.querySelector('.sec-ghost')"))
            p.mouse("mouseReleased", hx + 1, hy, 0)


if __name__ == "__main__":
    unittest.main()
