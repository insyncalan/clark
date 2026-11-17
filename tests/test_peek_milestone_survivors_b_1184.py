"""Item 1184: killing tests for the mutation survivors S4, S5 and S6 of the Milestone peek (report WO-M4030-stark, PR 1708).
S4 MilestonePeek.jsx ProgressPop: the hover preview (`upto = hover || was`).
S5 PeekMilestoneChips.jsx shownPercent: a Done milestone with no percent shows 100, in the chip and in the progress popover.
S6 MilestonePeek.jsx UseCase pick: picking the use case already shown (and linked straight) sends nothing and says nothing.
Run: python3 dev/run_tests.py test_peek_milestone_survivors_b_1184
Real browser at 1400 and 900 px on the fictional demo project (ABC).
"""
import unittest

from _demo import USER
from _paths import SRC

from test_movement_page import PILOT  # noqa: E402
import test_peek_milestone_1184 as base  # noqa: E402
from clark import store as sm  # noqa: E402
from test_server import chrome  # noqa: E402

BLOCKS = "[...document.querySelectorAll('[data-pop] [data-ms-block]')]"
HOVER = "(n) => { const b = document.querySelector(`[data-pop] [data-ms-block='${n}']`); b.dispatchEvent(new MouseEvent('mouseenter', {bubbles: false})); }"


class SurvivorsB(base.Milestone):

    def marks(self, p):
        """The blocks that read 'on' and the ones that read 'pv' (the hover preview), as lists of their numbers."""
        return p.js(f"(() => {{ const bs = {BLOCKS}; const f = (c) => bs.filter(b => b.classList.contains(c)).map(b => Number(b.dataset.msBlock)); return {{ on: f('on'), pv: f('pv') }}; }})()")

    # S4: the hover preview
    def test_hovering_a_block_previews_the_progress_up_to_it_and_leaving_goes_back(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                with self.store.step("dashboard", USER) as st:
                    st.update("milestones", PILOT, {"percent_complete": 20})
                p = self.visit(cdp, width=width)
                self.chip(p, "progress")
                p.until("document.activeElement && document.activeElement.dataset.msBlock === '20'", "the block of the current progress has the focus")
                self.assertEqual(self.marks(p), {"on": [10, 20], "pv": [10, 20]}, "opened: the focus on the 20 block previews up to 20")
                p.js(f"({HOVER})(70)")
                p.until(f"{BLOCKS}.filter(b => b.classList.contains('on')).length === 7", "the blocks up to 70 read on")
                self.assertEqual(self.marks(p), {"on": [10, 20, 30, 40, 50, 60, 70], "pv": [10, 20, 30, 40, 50, 60, 70]}, "hovering 70 previews up to 70")
                self.assertEqual(p.js(f"{BLOCKS}.map(b => b.getAttribute('aria-pressed') === 'true').filter(Boolean).length"), 2, "a preview is not the saved progress")
                p.js("document.querySelector('[data-pop] [data-ms-blocks]').dispatchEvent(new MouseEvent('mouseleave', {bubbles: false}))")
                p.until(f"{BLOCKS}.filter(b => b.classList.contains('on')).length === 2", "leaving puts the saved progress back")
                self.assertEqual(self.marks(p), {"on": [10, 20], "pv": []}, "no preview left after the mouse leaves")
                self.assertEqual(self.sent, [], "a hover sends nothing")

    # S5: Done with no percent shows 100
    def test_a_done_milestone_with_no_percent_shows_100_in_the_chip_and_the_popover(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                with self.store.step("dashboard", USER) as st:
                    st.update("milestones", PILOT, {"status": "Done", "state": "Achieved", "state_set": 1, "actual_date": "2026-03-04", "percent_complete": None})
                self.assertIsNone(self.row(PILOT)["percent_complete"])
                p = self.visit(cdp, width=width)
                self.assertEqual(self.chips(p)["progress"]["text"], "100%", "the chip says 100%, not 0%")
                self.chip(p, "progress")
                p.until("document.activeElement && document.activeElement.dataset.msBlock === '100'", "the 100 block has the focus on open")
                self.assertEqual(p.js(f"{BLOCKS}.filter(b => b.getAttribute('aria-pressed') === 'true').length"), 10, "all ten blocks read as reached")
                self.assertEqual(self.marks(p)["on"], list(range(10, 101, 10)), "all ten blocks are filled")
                self.assertEqual(self.sent, [])

    # S6: the use case that is already shown
    def test_picking_the_use_case_already_shown_and_linked_sends_nothing_and_says_nothing(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                a, b = self.two_use_cases()
                with self.store.step("dashboard", USER) as st:
                    sm.link_use_case_milestone(st, a, PILOT)
                p = self.visit(cdp, width=width)
                self.assertEqual(self.links(), [a])
                self.click(p, "#peek [data-ms-row=use_cases] [data-ms-ucs]")
                p.until("!!document.querySelector('[data-pop][role=menu]')", "the menu opened")
                self.click(p, f"[data-pop] [role=menuitemradio][data-value='{a}']")
                p.until("!document.querySelector('[data-pop]')", "the menu closed")
                p.js("window.__drawn = 0; requestAnimationFrame(() => requestAnimationFrame(() => { window.__drawn = 1; }))")
                p.until("window.__drawn === 1", "the page drew")
                self.assertEqual([r for w, r in self.sent if r.get("kind") == "use_cases"], [], "no add and no remove was asked for")
                self.assertEqual(self.sent, [], "nothing was sent at all")
                self.assertEqual(p.js("document.querySelectorAll('.toast').length"), 0, "no toast, so no Undo for nothing")
                self.assertEqual(self.links(), [a])
                self.assertEqual(p.js("document.activeElement && document.activeElement.dataset.msUcs !== undefined"), True, "the focus went back to the use case button")

    def test_the_pick_of_the_shown_use_case_has_an_early_return_before_the_change(self):
        src = (SRC / "clark" / "page" / "src" / "edit" / "MilestonePeek.jsx").read_text(encoding="utf-8")
        pick = src[src.index("function UseCase"):src.index("function MsClientLine")]
        self.assertIn("if (shownUc && shownUc.id === value && direct.has(value)) return;", pick)


for _name in dir(base.Milestone):      # the tests of the first file run there, not again here
    if _name.startswith("test") and _name not in SurvivorsB.__dict__:
        setattr(SurvivorsB, _name, None)


if __name__ == "__main__":
    unittest.main()
