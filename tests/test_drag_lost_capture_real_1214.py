"""Row 1214: a drag whose grip leaves the page ends with nothing dropped, checked in real headless Chrome at 1400 and 900 px.
Real Chrome fires the lost capture on Linux when the element that holds the pointer is removed, and macOS fires none, so the test does not wait for the event: a move after the removal ends the drag either way; no stub stands in here.
Run: python3 dev/run_tests.py test_drag_lost_capture_real_1214
"""
import unittest

import test_report_editor as tre
from test_server import chrome

ORDER = "[...document.querySelectorAll('.secs > .sec')].map(e => e.dataset.id)"
LEFT = "document.querySelector('.sec-ghost, .drag-from, .drag-slot, .sec-was')"
GRIPS = "document.querySelectorAll('.secs > .sec[data-id=\"ABC-S-001\"] [data-drag]').length"


class DragLostCaptureReal(tre.Base):
    def test_a_grip_removed_mid_drag_ends_the_drag_and_a_later_release_drops_nothing(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = tre.Pg.at(self, cdp, self.s.port, "#dashboard&p=ABC")
                p.ready()
                p.tall(cdp, width)
                p.edit()
                before = p.js(ORDER)
                hx, hy, _ = p.box('[data-id="ABC-S-001"] [data-drag]')
                _, _, bottom = p.box('[data-id="ABC-S-003"]')
                ty = bottom - 3
                p.mouse("mousePressed", hx, hy, 1)
                for step in range(1, 9):
                    p.mouse("mouseMoved", hx + 40, hy + (ty - hy) * step / 8, 1)
                p.until("!!document.querySelector('.sec-ghost')", "the drag is on")
                p.js("window.__lost = 0; document.addEventListener('lostpointercapture', () => { window.__lost++; }, true);"
                     "document.querySelectorAll('[data-id=\"ABC-S-001\"] [data-drag]').forEach(g => g.remove());")
                # Linux Chrome fires the lost capture at once; headless Chrome on macOS fires nothing (PR 1864 shard 6/6), so the next move must end the drag too
                p.mouse("mouseMoved", hx + 40, ty - 1, 1)
                p.until(f"!{LEFT}", "the drag ends: no ghost, slot or outline stays")
                self.assertEqual(p.js(GRIPS), 0, "the grip is gone, the page did not draw it back")
                p.mouse("mouseReleased", hx + 40, ty, 0)
                self.assertEqual(p.js(ORDER), before, "the release after it drops nothing")
                self.assertIsNone(p.js(LEFT))


if __name__ == "__main__":
    unittest.main()
