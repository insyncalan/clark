"""Row 1184: tests that close three gaps a mutation run found in the milestone peek (survivors S7, S8 and S9 of the run on PR 1708 head 84052e16).
Real store, real change route, real browser at 1400 and 900 px. All rows are fictional.

S7  MilestonePeek.jsx UseCase pick: the add (msadd) is sent even when the picked use case is already a direct link.
S8  MilestonePeek.jsx UseCase pick: the end of the shown use case (msremove) is sent even when it is only reached through a work item.
S9  PeekMilestoneChips.jsx overdueWords: a forecast date equal to today reads "overdue 0 days" (`a >= b` became `a > b`).

Run: python3 dev/run_tests.py test_peek_milestone_survivors_c_1184
"""
import re
from datetime import date, timedelta

from _demo import USER

from test_movement_page import PILOT  # noqa: E402
import test_peek_milestone_1184 as rig  # noqa: E402     (the module, not the class: a class imported by name would be run again here)
from test_server import chrome  # noqa: E402
from clark import store as sm  # noqa: E402

UCS = "#peek [data-ms-row=use_cases] [data-ms-ucs]"


class UseCasePickSendsOnlyWhatIsNeeded(rig.Milestone):
    def ops(self):
        return [(r["op"], r["id"]) for w, r in self.sent if w in ("change", "refused") and r.get("kind") == "use_cases"]

    def test_picking_a_use_case_that_is_already_linked_ends_only_the_shown_one(self):         # S7
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                a, b = self.two_use_cases()
                with self.store.step("dashboard", USER) as st:
                    sm.link_use_case_milestone(st, a, PILOT)
                    sm.link_use_case_milestone(st, b, PILOT)
                self.assertEqual(sorted(self.links()), sorted([a, b]))
                p = self.visit(cdp, width=width)
                shown = p.js(f"document.querySelector({UCS!r}).textContent")
                shown_id, other = (a, b) if "Invoice matching" in shown else (b, a)
                self.assertIn("Invoice matching" if shown_id == a else "Badge printing", shown)
                self.click(p, UCS)
                self.click(p, f"[data-pop] [role=menuitemradio][data-value='{other}']")
                self.assertTrue(self.until_store(lambda: self.links() == [other]), f"the shown link ended, the picked one kept: {self.links()}")
                self.assertEqual(self.ops(), [("msremove", shown_id)], "no msadd for a link that is already there")
                self.undo(p)
                self.assertTrue(self.until_store(lambda: sorted(self.links()) == sorted([a, b])), "one Undo puts the ended link back")

    def test_picking_a_use_case_when_the_shown_one_is_only_reached_through_a_work_item_ends_nothing(self):    # S8
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.setUp()
                a, b = self.two_use_cases()
                with self.store.step("dashboard", USER) as st:
                    st.create("actions", {"project": "ABC", "description": "Reach the milestone", "owner": "TBC", "raised": "2026-10-01",
                                          "milestone": PILOT, "use_case": a, "source": "demo"})
                self.assertEqual(self.links(), [], "no direct link: the use case reaches the milestone only through the action")
                p = self.visit(cdp, width=width)
                p.until(f"document.querySelector({UCS!r}).textContent.includes('Invoice matching')", "the row shows the use case reached through the work item")
                self.click(p, UCS)
                values = p.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(e => e.dataset.value)")
                self.assertNotIn("", values, "no direct link to end, so None is not offered")
                self.click(p, f"[data-pop] [role=menuitemradio][data-value='{b}']")
                self.assertTrue(self.until_store(lambda: self.links() == [b]), f"linked: {self.links()}")
                self.assertEqual(self.ops(), [("msadd", b)], "only the add: the work item's use case has no direct link to end")


class OverdueWordsAtTheEdge(rig.Milestone):
    def forecast(self, p_width, days_back):
        d = (date.today() - timedelta(days=days_back)).isoformat()
        with self.store.step("dashboard", USER) as st:
            st.update("milestones", PILOT, {"forecast_date": d})
        return d

    def test_a_forecast_of_today_is_not_overdue_and_one_and_two_days_back_use_the_right_words(self):         # S9
        for width in (1400, 900):
            for back, words in ((0, ""), (1, "overdue 1 day"), (2, "overdue 2 days")):
                with self.subTest(width=width, days_back=back), chrome() as cdp:
                    self.setUp()
                    self.forecast(width, back)
                    p = self.visit(cdp, width=width)
                    got = self.chips(p)["forecast"]
                    self.assertEqual((got["sub"] or ""), words, got)
                    late = p.js("(() => { const r = document.querySelector('#peek .pk-chips [data-row=forecast]'); return r.classList.contains('late') || !!r.querySelector('.pkc.late'); })()")
                    self.assertEqual(late, bool(words), f"the red tint only when overdue: {got}")
                    self.assertNotRegex(got["text"], r"overdue 0" if back == 0 else r"^$")


# The two classes borrow the Milestone rig (a real store, server and browser helpers); they must not run its 37 tests again.
for _cls in (UseCasePickSendsOnlyWhatIsNeeded, OverdueWordsAtTheEdge):
    for _name in dir(rig.Milestone):
        if _name.startswith("test_") and _name not in _cls.__dict__:
            setattr(_cls, _name, None)
