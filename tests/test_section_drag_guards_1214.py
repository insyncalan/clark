"""Row 1214, what src/clark/page/src/edit/drag.js does when a drag is not the only thing going on, pinned.

Run: python3 dev/run_tests.py test_section_drag_guards_1214
Three things, each checked in headless Chrome (1400 px and 900 px, the real page over the fictional demo report):
- a second finger is not the drag: it neither starts a second drag, nor moves the first one, nor ends it when it lifts;
- while a drop is being stored no new drag starts, and one can start again once it is stored;
- a drop that fails says the page's plain sentence in the toast, and the page goes back to the stored order.
The browser parts are required: they fail, never skip, without Chrome (set CLARK_CHROME to its path).
"""
import threading
import time
import unittest

from test_report_editor import Base, IDS  # noqa: E402
from test_server import chrome, wait  # noqa: E402

WIDTHS = (1400, 900)
TOUCH = "Input.dispatchTouchEvent"
GHOSTS = "document.querySelectorAll('.sec-ghost').length"
MARKS = "document.querySelector('.drag-slot, .sec-ghost, .sec-was')"
FAILED = "That change could not be made, and nothing was changed. Reload the page and try again."


class Fingers(Base):
    def at(self, cdp, width):
        p = self.visit(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 2400, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(f"window.innerWidth === {width}", "resized")
        p.edit()
        return p

    def touch(self, p, kind, points):
        p.cdp.call(TOUCH, {"type": kind, "touchPoints": [{"x": x, "y": y, "id": i} for i, (x, y) in points.items()]}, p.sid)

    def hold(self, p, ref, toward):
        """Finger 1 goes down on the grip of `ref`, moves to `toward` (x, y); returns its grip point."""
        hx, hy, _ = p.box(f'[data-id="{ref}"] [data-drag]')
        self.touch(p, "touchStart", {1: (hx, hy)})
        time.sleep(0.1)
        x, y = toward
        for step in range(1, 9):
            self.touch(p, "touchMove", {1: (hx + (x - hx) * step / 8, hy + (y - hy) * step / 8)})
        p.until(f"!!document.querySelector('.drag-slot') && {GHOSTS} === 1", "finger 1 is dragging")
        return hx, hy

    def free_grip(self, p):
        """The centre of a grip that the pointer reaches now (the dragged section's own grip is hidden while the slot is drawn)."""
        return p.js("(function(){for (var g of document.querySelectorAll('.sec[data-id] [data-drag]')) { var r = g.getBoundingClientRect();"
                    " var x = r.left + r.width / 2, y = r.top + r.height / 2; if (y > 0 && y < innerHeight && (document.elementFromPoint(x, y) || document.body).closest('[data-drag]') === g) return [x, y]; } })()")

    def aim(self, p, ref, side):
        r = p.rect(ref)
        return (r["left"] + r["right"]) / 2, (r["bottom"] - 2 if side == "bottom" else r["top"] + 2)

    def test_a_second_finger_starts_no_second_drag(self):
        with chrome() as cdp:
            for width in WIDTHS:
                p = self.at(cdp, width)
                one = self.aim(p, "ABC-S-004", "bottom")
                self.hold(p, "ABC-S-001", one)
                gx, gy = self.free_grip(p)
                self.touch(p, "touchStart", {1: one, 2: (gx, gy)})
                time.sleep(0.6)                          # the second finger moves
                for step in range(1, 9):
                    self.touch(p, "touchMove", {1: one, 2: (gx + 6 * step, gy + 10 * step)})
                time.sleep(0.3)
                self.assertEqual(p.js(GHOSTS), 1, f"{width} px: still one ghost, the second finger drew none (measured count)")
                self.assertEqual(p.js("document.querySelectorAll('.drag-slot').length"), 1, f"{width} px: one slot")
                self.touch(p, "touchEnd", {})
                self.assertTrue(wait(lambda: self.ids_in_store() == IDS[1:4] + ["ABC-S-001"] + IDS[4:], 5), f"{width} px: finger 1 dropped where it was")
                p.saved()
                p.js("document.querySelector('[data-undo]').click()")
                p.order_is(IDS, f"{width} px: Undo")

    def test_a_second_finger_neither_moves_nor_ends_the_drag(self):
        with chrome() as cdp:
            for width in WIDTHS:
                p = self.at(cdp, width)
                one = self.aim(p, "ABC-S-004", "bottom")
                self.hold(p, "ABC-S-001", one)
                top = self.free_grip(p)
                self.touch(p, "touchStart", {1: one, 2: top})
                for step in range(3):
                    self.touch(p, "touchMove", {1: one, 2: (top[0] + step, top[1] + 4 * step)})
                time.sleep(0.3)                          # past the rest rule: a followed finger 2 would have moved the slot
                self.touch(p, "touchMove", {1: one})     # finger 2 is no longer among the points: it lifts, finger 1 stays down
                p.js("['pointerup', 'pointercancel'].forEach(t => document.dispatchEvent(new PointerEvent(t, {pointerId: 77, pointerType: 'touch', bubbles: true})))")      # and a pointer that never began a drag lets go
                time.sleep(0.3)
                self.assertEqual(p.js(GHOSTS), 1, f"{width} px: finger 2 lifting did not end the drag")
                self.assertEqual(self.ids_in_store(), IDS, f"{width} px: and dropped nothing")
                self.touch(p, "touchEnd", {})            # finger 1 lifts
                self.assertTrue(wait(lambda: self.ids_in_store() == IDS[1:4] + ["ABC-S-001"] + IDS[4:], 5),
                                f"{width} px: the drop is where finger 1 was, not where finger 2 went")
                self.assertIsNone(p.js(MARKS), f"{width} px: nothing is left on the page")
                p.saved()
                p.js("document.querySelector('[data-undo]').click()")
                p.order_is(IDS, f"{width} px: Undo")


class Gated(Base):
    """The server holds every request until `gate` is set, so a drop stays 'being stored' as long as the test wants."""
    def setUp(self):
        self.gate = threading.Event()
        self.gate.set()
        self.arrived = []
        super().setUp()

    def seam(self, real, which):
        inner = super().seam(real, which)

        def call(req):
            self.arrived.append(which)
            self.gate.wait(20)
            return inner(req)
        return call

    def tearDown(self):
        self.gate.set()

    def at(self, cdp, width):
        p = self.visit(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 2400, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(f"window.innerWidth === {width}", "resized")
        p.edit()
        return p


class Saving(Gated):
    def test_no_new_drag_starts_while_a_drop_is_being_stored(self):
        with chrome() as cdp:
            for width in WIDTHS:
                p = self.at(cdp, width)
                self.gate.clear()
                self.arrived.clear()
                r = p.rect("ABC-S-004")
                x, y = (r["left"] + r["right"]) / 2, r["bottom"] - 2
                p.drag("ABC-S-001", x, y, release=False)
                time.sleep(0.3)
                p.mouse("mouseReleased", x, y, 0)
                self.assertTrue(wait(lambda: len(self.arrived) == 1, 5), f"{width} px: the drop was sent")
                self.assertEqual(self.ids_in_store(), IDS, f"{width} px: and is not stored yet")
                p.until(f"!{GHOSTS}", "the first ghost went")
                hx, hy, _ = p.box('[data-id="ABC-S-002"] [data-drag]')
                p.mouse("mousePressed", hx, hy, 1)
                for step in range(1, 9):
                    p.mouse("mouseMoved", hx, hy + 60 * step, 1)
                time.sleep(0.3)
                p.mouse("mouseReleased", hx, hy + 480, 0)
                time.sleep(0.3)
                self.assertEqual(len(self.arrived), 1, f"{width} px: no second request")
                self.gate.set()
                want = IDS[1:4] + ["ABC-S-001"] + IDS[4:]
                self.assertTrue(wait(lambda: self.ids_in_store() == want, 5), f"{width} px: the first drop was stored, and only it")
                p.order_is(want, f"{width} px: the page shows what was stored")
                self.assertEqual(len(self.arrived), 1, f"{width} px: one request in all")
                p.js("document.querySelector('[data-undo]').click()")
                p.order_is(IDS, f"{width} px: Undo")

    def test_a_drag_starts_again_once_the_drop_is_stored(self):
        with chrome() as cdp:
            for width in WIDTHS:
                p = self.at(cdp, width)
                r = p.rect("ABC-S-004")
                p.drag("ABC-S-001", (r["left"] + r["right"]) / 2, r["bottom"] - 2, release=False)
                time.sleep(0.3)
                p.mouse("mouseReleased", (r["left"] + r["right"]) / 2, r["bottom"] - 2, 0)
                p.saved()
                p.order_is(IDS[1:4] + ["ABC-S-001"] + IDS[4:], f"{width} px: stored")
                p.js("document.querySelector('[data-undo]').click()")
                p.order_is(IDS, f"{width} px: Undo")
                hx, hy, _ = p.box('[data-id="ABC-S-002"] [data-drag]')
                p.mouse("mousePressed", hx, hy, 1)
                for step in range(1, 9):
                    p.mouse("mouseMoved", hx, hy + 60 * step, 1)
                p.until(f"{GHOSTS} === 1", f"{width} px: a second drag starts after the first was stored")
                p.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))")
                p.mouse("mouseReleased", hx, hy + 480, 0)


class Failed(Gated):
    def broken(self, req):
        return (200, {"ok": True, "sections": [None]})   # the page takes it as an answer, then cannot draw it: the drop's promise rejects, change() does not catch that

    def test_a_drop_that_fails_says_so_and_the_page_goes_back(self):
        with chrome() as cdp:
            for width in WIDTHS:
                p = self.at(cdp, width)
                self.failure = self.broken
                r = p.rect("ABC-S-004")
                x, y = (r["left"] + r["right"]) / 2, r["bottom"] - 2
                p.drag("ABC-S-001", x, y, release=False)
                time.sleep(0.3)
                p.mouse("mouseReleased", x, y, 0)
                p.until("!!document.querySelector('.toast.problem')", f"{width} px: a problem toast")
                self.assertEqual(p.js("document.querySelector('.toast.problem .toast-text').textContent"), FAILED, f"{width} px: the page's own sentence")
                p.order_is(IDS, f"{width} px: the preview is gone, the page shows the stored order")
                self.assertEqual(self.ids_in_store(), IDS)
                self.assertIsNone(p.js(MARKS), f"{width} px: nothing of the drag is left")
                self.failure = None
                p.clear_toast()
                r = p.rect("ABC-S-004")
                p.drag("ABC-S-001", (r["left"] + r["right"]) / 2, r["bottom"] - 2, release=False)
                time.sleep(0.3)
                p.mouse("mouseReleased", (r["left"] + r["right"]) / 2, r["bottom"] - 2, 0)
                self.assertTrue(wait(lambda: self.ids_in_store() == IDS[1:4] + ["ABC-S-001"] + IDS[4:], 5), f"{width} px: the next drag works")
                p.saved()
                p.js("document.querySelector('[data-undo]').click()")
                p.order_is(IDS, f"{width} px: Undo")


if __name__ == "__main__":
    unittest.main()
