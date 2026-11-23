"""Row 1214, the Live layout end to end in headless Chrome (1400 px and 900 px, the real page over the fictional demo report).

One section is dragged beside another (half width), then up, then down; the layout is read from the page and from the store after
each drop; the page is reloaded and shows the same layout; a drag made after the reload is put back by one Undo, to the layout
that was saved before it.
Run: python3 dev/run_tests.py test_live_layout_e2e_1214
The browser parts are required: they fail, never skip, without Chrome (set CLARK_CHROME to its path).
"""
import unittest

from test_report_editor import Base, IDS  # noqa: E402
from test_server import chrome, wait  # noqa: E402

WIDTHS = (1400, 900)
MOVER, HOST = "ABC-S-008", "ABC-S-002"
BESIDE = IDS[:2] + [MOVER] + IDS[2:7] + IDS[8:]                       # the mover sits right after its host, as the right half
UP = [MOVER] + [i for i in IDS if i != MOVER]                          # the top quarter of the first section: a row of its own above it
DOWN = [i for i in IDS if i != MOVER]
DOWN = DOWN[:6] + [MOVER] + DOWN[6:]                                   # the bottom quarter of Milestones (S-006, on its own): a row of its own below it


class LiveLayout(Base):
    def flags(self):
        """The pairs the person made: the demo report's own pair (004 and 005) is left out."""
        return {k: v for k, v in self.beside_flags().items() if v and k != "ABC-S-004"}

    def classes(self, p):
        return p.js("Object.fromEntries([...document.querySelectorAll('.secs > .sec[data-id]')].map(s => [s.dataset.id, "
                    "['slot-left', 'slot-right', 'slot-full'].filter(c => s.classList.contains(c))[0] || '']))")

    def settled(self, p, want, what):
        p.order_is(want, what)
        self.assertTrue(wait(lambda: self.ids_in_store() == want, 5), f"{what}: the store has the order")
        p.until("!document.querySelector('.drag-slot, .sec-ghost, .sec-was')", f"{what}: no slot is left")
        p.until(p.IDLE, f"{what}: the sections have stopped gliding, so the rectangles are where they are")

    def one(self, cdp, width):
        p = self.visit(cdp)
        p.tall(cdp, width)
        p.until(f"window.innerWidth === {width}", "resized")
        p.edit()
        w = f"{width} px"
        # 1. beside: the right half of a section on its own. Up to 900 px the pairs stack (drag.js), so no half is offered there:
        # the same drop makes a row of its own above it, and the menu's Place beside makes the pair
        r = p.rect(HOST)
        stacked = width <= 900
        if not stacked:
            p.drag(MOVER, r["left"] + (r["right"] - r["left"]) * 0.75, (r["top"] + r["bottom"]) / 2)
            self.settled(p, BESIDE, f"{w}: beside")
            self.assertEqual(self.flags(), {HOST: 1}, f"{w}: the host leads a pair")
            p.until(f"document.querySelector('[data-id=\"{HOST}\"]').classList.contains('slot-left') && "
                    f"document.querySelector('[data-id=\"{MOVER}\"]').classList.contains('slot-right')", f"{w}: two columns")
            a, b = p.rect(HOST), p.rect(MOVER)
            self.assertLess(abs(a["top"] - b["top"]), 2, f"{w}: the pair is on one row")
            self.assertLess(a["right"], b["left"] + 1, f"{w}: host left, mover right")
            full = p.rect("ABC-S-001")
            for half in (a, b):
                self.assertLess((half["right"] - half["left"]) / (full["right"] - full["left"]), 0.55, f"{w}: half width")
        else:
            p.drag(MOVER, r["left"] + (r["right"] - r["left"]) * 0.75, r["top"] + (r["bottom"] - r["top"]) * 0.4)
            self.settled(p, IDS[:1] + [MOVER] + IDS[1:7] + IDS[8:], f"{w}: the stacked middle gives a row, not a half")
            self.assertEqual(self.flags(), {}, f"{w}: no pair from a drag")
            p.menu(MOVER, "beside")
            p.until(f"document.querySelector('[data-id=\"{MOVER}\"]').classList.contains('slot-left')", f"{w}: Place beside pairs it")
        # 2. up: the top quarter of the first section leaves the pair for a row of its own above everything
        r = p.rect("ABC-S-001")
        p.drag(MOVER, (r["left"] + r["right"]) / 2, r["top"] + 3)
        self.settled(p, UP, f"{w}: up")
        self.assertEqual(self.flags(), {}, f"{w}: the host is on its own again")
        p.until(f"document.querySelector('[data-id=\"{MOVER}\"]').classList.contains('slot-full')", f"{w}: full width")
        self.assertLess(p.rect(MOVER)["top"], p.rect("ABC-S-001")["top"], f"{w}: above the first section")
        # 3. down: the bottom quarter of Milestones
        r = p.rect("ABC-S-006")
        p.drag(MOVER, (r["left"] + r["right"]) / 2, r["bottom"] - 2)
        self.settled(p, DOWN, f"{w}: down")
        self.assertEqual(self.flags(), {}, f"{w}: no pair")
        self.assertGreater(p.rect(MOVER)["top"], p.rect("ABC-S-006")["bottom"] - 1, f"{w}: below Milestones")
        # a pair again, so the reload has both a half and a row to keep
        r = p.rect(HOST)
        if not stacked:
            p.drag(MOVER, r["left"] + (r["right"] - r["left"]) * 0.25, (r["top"] + r["bottom"]) / 2)
        else:
            p.drag(MOVER, r["left"] + (r["right"] - r["left"]) * 0.75, r["top"] + (r["bottom"] - r["top"]) * 0.4)
            self.settled(p, IDS[:1] + [MOVER] + IDS[1:7] + IDS[8:], f"{w}: before the host")
            p.menu(MOVER, "beside")
        saved = [i for i in IDS if i != MOVER]
        saved = saved[:1] + [MOVER] + saved[1:]
        self.settled(p, saved, f"{w}: beside on the left")
        self.assertTrue(wait(lambda: self.flags() == {MOVER: 1}, 5), f"{w}: the mover leads the pair, stored")
        p.until(f"document.querySelector('[data-id=\"{MOVER}\"]').classList.contains('slot-left') && "
                f"document.querySelector('[data-id=\"{HOST}\"]').classList.contains('slot-right')", f"{w}: the pair is drawn")
        want_classes = self.classes(p)
        self.assertEqual((want_classes[MOVER], want_classes[HOST]), ("slot-left", "slot-right"))
        # reload: the same layout from the store
        p.reload()
        p.edit()
        p.order_is(saved, f"{w}: after the reload")
        self.assertEqual(self.classes(p), want_classes, f"{w}: the same columns after the reload")
        self.assertEqual(self.flags(), {MOVER: 1}, f"{w}: the store is unchanged by the reload")
        # a drag after the reload, and one Undo puts the saved layout back
        r = p.rect("ABC-S-011")
        p.drag("ABC-S-001", (r["left"] + r["right"]) / 2, r["bottom"] - 2)
        later = [i for i in saved if i != "ABC-S-001"]
        later = later[:later.index("ABC-S-011") + 1] + ["ABC-S-001"] + later[later.index("ABC-S-011") + 1:]
        self.settled(p, later, f"{w}: a drag after the reload")
        p.saved()
        n = len(self.sent)
        p.js("document.querySelector('[data-undo]').click()")
        p.order_is(saved, f"{w}: Undo")
        self.assertTrue(wait(lambda: self.ids_in_store() == saved and self.flags() == {MOVER: 1}, 5), f"{w}: Undo reached the store")
        self.assertEqual(self.classes(p), want_classes, f"{w}: Undo gives back the columns")
        self.assertEqual(len([k for k, _ in self.sent[n:] if k == "undo"]), 1, f"{w}: one Undo")

    def test_1400(self):
        with chrome() as cdp:
            self.one(cdp, 1400)

    def test_900(self):
        with chrome() as cdp:
            self.one(cdp, 900)


if __name__ == "__main__":
    unittest.main()
