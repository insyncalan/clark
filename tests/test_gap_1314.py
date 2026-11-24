"""Row 1314 gap: the + New view link is brand blue and at the far right of the tab row (Classic)."""
import unittest

import test_work_items_classic_1314 as classic
from test_server import chrome


class NewView(classic.Browser):
    # This file only needs the Classic page set-up of Browser. Importing the class by name and subclassing it ran its six
    # browser tests twice more in this file (13 tests, each starting Chrome, in one file under the 900 s file limit), so
    # the inherited tests are switched off here; they run in test_work_items_classic_1314 itself.
    for _name in [n for n in dir(classic.Browser) if n.startswith("test_")]:
        locals()[_name] = None
    del _name

    def test_new_view_is_blue_and_at_the_far_right(self):
        probe = ("(() => { const v = document.querySelector('#viewNew'), b = document.querySelector('#newBtn'), r = document.querySelector('#work .fvrow').getBoundingClientRect(), "
                 "e = document.createElement('i'); e.style.color = 'var(--brand-blue)'; document.body.append(e); const want = getComputedStyle(e).color; e.remove(); "
                 "const a = v.getBoundingClientRect(), c = b.getBoundingClientRect(); return {color: getComputedStyle(v).color, want, vRight: Math.round(a.right), btnLeft: Math.round(c.left), btnRight: Math.round(c.right), rowRight: Math.round(r.right)}; })()")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                # the fonts are in and the page has stopped moving before the boxes are measured (a bar measured early gives other numbers)
                ready = "document.fonts.status === 'loaded' && !!document.querySelector('#viewNew') && !!document.querySelector('#newBtn') && !!document.querySelector('#work .fvrow')"
                self.until(cdp, sid, ready, "the + New view link, the New button and the filter row",
                           why=lambda: cdp.js("JSON.stringify({fonts: document.fonts.status, viewNew: !!document.querySelector('#viewNew'), newBtn: !!document.querySelector('#newBtn'), fvrow: !!document.querySelector('#work .fvrow'), hash: location.hash})", sid))
                self.settle(cdp, sid)
                got = cdp.js(probe, sid)
                self.assertEqual(got["color"], got["want"], got)
                self.assertEqual(got["btnRight"], got["rowRight"], got)
                self.assertLessEqual(got["btnLeft"] - got["vRight"], 8, got)
                # measured: vRight 1273 / 833, btnLeft 1281 / 841, btnRight = rowRight 1309 / 869
                self.assertEqual((got["vRight"], got["btnLeft"], got["rowRight"]), (1273, 1281, 1309) if width == 1400 else (833, 841, 869), got)


if __name__ == "__main__":
    unittest.main()
