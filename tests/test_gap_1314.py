"""Row 1314 gap: the + New view link is brand blue and at the far right of the tab row (Classic)."""
import unittest

from test_work_items_classic_1314 import Browser
from test_server import chrome


class NewView(Browser):
    def test_new_view_is_blue_and_at_the_far_right(self):
        probe = ("(() => { const v = document.querySelector('#viewNew'), b = document.querySelector('#newBtn'), r = document.querySelector('#work .fvrow').getBoundingClientRect(), "
                 "e = document.createElement('i'); e.style.color = 'var(--brand-blue)'; document.body.append(e); const want = getComputedStyle(e).color; e.remove(); "
                 "const a = v.getBoundingClientRect(), c = b.getBoundingClientRect(); return {color: getComputedStyle(v).color, want, vRight: Math.round(a.right), btnLeft: Math.round(c.left), btnRight: Math.round(c.right), rowRight: Math.round(r.right)}; })()")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                got = cdp.js(probe, sid)
                self.assertEqual(got["color"], got["want"], got)
                self.assertEqual(got["btnRight"], got["rowRight"], got)
                self.assertLessEqual(got["btnLeft"] - got["vRight"], 8, got)
                # measured: vRight 1273 / 833, btnLeft 1281 / 841, btnRight = rowRight 1309 / 869
                self.assertEqual((got["vRight"], got["btnLeft"], got["rowRight"]), (1273, 1281, 1309) if width == 1400 else (833, 841, 869), got)


if __name__ == "__main__":
    unittest.main()
