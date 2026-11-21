"""Row 1214: while a section is dragged by its handle a status line under the page says what a release would do, and after the drop a
live region says what was done. Five lines and five announcements: beside, above, below, full width, own place.

Run: cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_drag_status_1214
The real page in headless Chrome, at 1400 and 900 px (at 900 a pair stacks, so there is no half to drop beside: that line is checked at
1400 only). The line is drawn from the target the slot uses, changes as it changes, is hidden from a screen reader (so is the ghost) and
goes with the drag; the announcement is in a polite live region that stays on the page.
"""
import json
import unittest

import test_report_editor as tre
from test_server import chrome

IDS = tre.IDS
T = dict(zip(IDS, tre.TITLES))                 # id -> title, the order the demo store gives
LINE = "document.querySelector('[data-drag-line]')"
SAY = "(document.querySelector('[data-drag-say]') || {}).textContent || ''"


class DragStatus(tre.Base):
    def at(self, cdp, width):
        p = tre.Pg.at(self, cdp, self.s.port, "#dashboard&p=ABC")
        p.ready()
        p.tall(cdp, width)
        p.edit()
        p.until(p.IDLE, "the sections have stopped gliding")
        return p

    def hold(self, p, ref, x, y, line):
        """Press the grip of `ref`, move to (x, y) and wait until the status line says `line`."""
        hx, hy, _ = p.box(f'[data-id="{ref}"] [data-drag]')
        p.mouse("mousePressed", hx, hy, 1)
        for step in range(1, 9):
            p.mouse("mouseMoved", hx + (x - hx) * step / 8, hy + (y - hy) * step / 8, 1)
        p.until(f"(({LINE}) || {{}}).textContent === {json.dumps(line)}", f"the line says: {line}")

    def release_and_hear(self, p, x, y, said, sends=1):
        n0 = len(self.sent)
        p.mouse("mouseReleased", x, y, 0)
        p.until(f"!{LINE}", "the line goes with the drag")
        if sends:
            p.stored(n0)
        p.until(f"({SAY}) === {json.dumps(said)}", f"the live region says: {said}")
        self.assertEqual(len(self.sent) - n0, sends)
        self.assertEqual(p.js("document.querySelector('[data-drag-say]').getAttribute('aria-live')"), "polite")
        self.assertEqual(p.js("document.querySelector('[data-drag-say]').getAttribute('role')"), "status")
        if sends:
            self.quiet_toast(p)
            p.js("document.querySelector('[data-undo]').click()")
            p.order_is(IDS, "Undo puts it back")

    def quiet_toast(self, p):
        """The drop's toast is on the page with its Undo, but its region does not announce: only the drag's own live region speaks."""
        self.assertEqual(p.js("document.querySelector('.toasts').getAttribute('aria-live')"), "off")
        self.assertIsNone(p.js("document.querySelector('.toasts').getAttribute('role')"))
        self.assertEqual(p.js("document.querySelectorAll('.toast [data-undo]').length"), 1, "Undo is still there")
        self.assertGreater(p.js("document.querySelector('.toast [data-undo]').getBoundingClientRect().width"), 0, "and drawn")
        self.assertGreater(len(p.js("document.querySelector('.toast .toast-text').textContent")), 0, "the toast still has its words")

    def edge(self, p, ref, where):
        r = p.rect(ref)
        return (r["left"] + r["right"]) / 2, (r["top"] + 2 if where == "top" else r["bottom"] - 2)

    def check_line(self, p):
        self.assertEqual(p.js(f"{LINE}.getAttribute('aria-hidden')"), "true", "the line is not read out while dragging")
        self.assertEqual(p.js("document.querySelector('.sec-ghost').getAttribute('aria-hidden')"), "true")
        self.assertEqual(p.js(f"getComputedStyle({LINE}).pointerEvents"), "none")
        r = p.js(f"(function(){{var r={LINE}.getBoundingClientRect();return [r.left, r.right, r.bottom, innerWidth, innerHeight];}})()")
        self.assertGreaterEqual(r[0], 0)
        self.assertLessEqual(r[1], r[3])
        self.assertLessEqual(r[2], r[4], "under the page, inside the window")

    def test_above(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.at(cdp, width)
                x, y = self.edge(p, IDS[1], "top")
                self.hold(p, IDS[3], x, y, f'Release to put "{T[IDS[3]]}" above "{T[IDS[1]]}".')
                self.check_line(p)
                self.release_and_hear(p, x, y, f'Moved "{T[IDS[3]]}" above "{T[IDS[1]]}".')

    def test_below(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.at(cdp, width)
                x, y = self.edge(p, IDS[-1], "bottom")
                self.hold(p, IDS[0], x, y, f'Release to put "{T[IDS[0]]}" below "{T[IDS[-1]]}".')
                self.release_and_hear(p, x, y, f'Moved "{T[IDS[0]]}" below "{T[IDS[-1]]}".')

    def test_beside(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            r = p.rect(IDS[5])
            x, y = r["left"] + (r["right"] - r["left"]) * 0.2, (r["top"] + r["bottom"]) / 2
            self.hold(p, IDS[0], x, y, f'Release to put "{T[IDS[0]]}" beside "{T[IDS[5]]}", half width each.')
            self.release_and_hear(p, x, y, f'Moved "{T[IDS[0]]}" beside "{T[IDS[5]]}", half width each.')

    def test_no_beside_at_900_where_a_pair_stacks(self):
        with chrome() as cdp:
            p = self.at(cdp, 900)
            r = p.rect(IDS[3])
            x, y = r["left"] + (r["right"] - r["left"]) * 0.2, r["top"] + (r["bottom"] - r["top"]) * 0.4
            hx, hy, _ = p.box(f'[data-id="{IDS[0]}"] [data-drag]')
            p.mouse("mousePressed", hx, hy, 1)
            for step in range(1, 9):
                p.mouse("mouseMoved", hx + (x - hx) * step / 8, hy + (y - hy) * step / 8, 1)
            p.until(f"/ (above|below) /.test(({LINE} || {{}}).textContent || '')", "a line for a row of its own")
            self.assertNotIn("beside", p.js(f"{LINE}.textContent"))
            p.key("Escape", code="Escape", vk=27)
            p.mouse("mouseReleased", x, y, 0)

    def test_full_width(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.at(cdp, width)
                six, seven = IDS[3], IDS[4]                              # This week sits beside Next week
                x, y = self.edge(p, seven, "bottom")
                self.hold(p, seven, x, y, f'Release to make "{T[seven]}" full width.')
                self.release_and_hear(p, x, y, f'"{T[seven]}" is now full width.')

    def test_a_toast_that_is_not_a_drop_is_still_polite(self):
        for width, ref in ((1400, IDS[3]), (900, IDS[4])):      # each width leaves out a section of its own: the store keeps the first one's change
            with self.subTest(width=width), chrome() as cdp:
                p = self.at(cdp, width)
                p.menu(ref, "hide")
                p.saved()
                self.assertEqual(p.js("document.querySelector('.toasts').getAttribute('aria-live')"), "polite")
                self.assertEqual(p.js("document.querySelector('.toasts').getAttribute('role')"), "status")
                self.assertEqual(p.js(SAY), "", "the drag's region said nothing")

    def test_own_place(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.at(cdp, width)
                hx, hy, _ = p.box(f'[data-id="{IDS[3]}"] [data-drag]')
                line = f'Release to leave "{T[IDS[3]]}" where it is.'
                self.hold(p, IDS[3], hx + 12, hy + 12, line)
                self.release_and_hear(p, hx + 12, hy + 12, f'"{T[IDS[3]]}" stays where it is.', sends=0)

    def test_the_line_follows_the_target_and_esc_says_nothing(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            x, y = self.edge(p, IDS[1], "top")
            x2, y2 = self.edge(p, IDS[7], "top")                       # both measured before the drag: the preview then moves the sections
            self.hold(p, IDS[3], x, y, f'Release to put "{T[IDS[3]]}" above "{T[IDS[1]]}".')
            for step in range(1, 5):
                p.mouse("mouseMoved", x + (x2 - x) * step / 4, y + (y2 - y) * step / 4, 1)
            p.until(f"({LINE}).textContent === {json.dumps(f'Release to put {chr(34)}{T[IDS[3]]}{chr(34)} above {chr(34)}{T[IDS[7]]}{chr(34)}.')}", "the line changed with the target")
            p.key("Escape", code="Escape", vk=27)
            p.mouse("mouseReleased", x2, y2, 0)
            p.until(f"!{LINE}", "the line goes at Esc")
            self.assertEqual(p.js(SAY), "", "Esc says nothing: nothing moved")
            self.assertEqual(len(self.sent), 0)

    def test_a_click_with_no_travel_draws_no_line(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            hx, hy, _ = p.box(f'[data-id="{IDS[3]}"] [data-drag]')
            p.mouse("mousePressed", hx, hy, 1)
            p.mouse("mouseMoved", hx + 1, hy, 1)
            self.assertIsNone(p.js(f"{LINE}"))
            p.mouse("mouseReleased", hx + 1, hy, 0)
            self.assertEqual(p.js(SAY), "")


if __name__ == "__main__":
    unittest.main()
