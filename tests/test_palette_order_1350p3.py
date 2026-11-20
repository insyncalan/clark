"""Row 1350 part 3: the order of the groups in the quick bar when words are typed.

Run: python3 dev/run_tests.py test_palette_order_1350p3
With words typed: Command, Page, Project, then the data (a work item such as a Risk, Milestone), then Action, and the ask row last (a question first). Where Action rows go
with words typed is not in the agreed table: they keep their place after the data. With nothing typed the order stays Page, Action, Project, Command.
Classic only: the page here carries the <style id="theme"> layer; without it (Cards) the order is main's, see test_classic_gate_1350.
Chrome is required: it fails, never skips, without it (set CLARK_CHROME).
"""
import unittest

import test_palette as tp
from test_palette import Base, project
from test_server import chrome


def runs(kinds):
    return [k for i, k in enumerate(kinds) if i == 0 or k != kinds[i - 1]]


class Order(Base):
    def setUp(self):
        tp.DATA["DEF"] = project("DEF", "Pilot supplier programme")          # one project that matches both words below
        tp.LIST[1] = {"code": "DEF", "name": "Pilot supplier programme"}
        self.addCleanup(lambda: (tp.DATA.__setitem__("DEF", project("DEF", "Second Programme")), tp.LIST.__setitem__(1, {"code": "DEF", "name": "Second Programme"})))
        super().setUp()

    def visit(self, cdp, *a, **k):
        p = super().visit(cdp, *a, **k)
        p.js("(function(){var s=document.createElement('style'); s.id='theme'; document.head.appendChild(s);})()")          # the Classic layer: classicTheme() reads it when the bar searches
        return p

    def kinds(self, p, q):
        p.find(q)
        return [r[0] for r in p.rows(True)]

    def test_a_project_comes_before_the_work_item_and_the_milestone_it_matches_with_the_ask_row_last(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                p.width(w)
                p.show()
                got = runs(self.kinds(p, "supplier"))
                self.assertEqual([k for k in got if k in ("Project", "Risk", "ask clark")], ["Project", "Risk", "ask clark"], f"at {w} px: {got}")
                self.assertEqual(got[-1], "ask clark", f"at {w} px: {got}")
                p.key("Escape", 0, "Escape", 27)
                p.show()
                got = runs(self.kinds(p, "pilot"))
                self.assertEqual([k for k in got if k in ("Command", "Page", "Project", "Milestone", "ask clark")], ["Project", "Milestone", "ask clark"], f"at {w} px: {got}")
                self.assertLess(got.index("Project"), got.index("Milestone"), f"at {w} px")
                p.key("Escape", 0, "Escape", 27)

    def test_command_and_page_stay_ahead_of_the_project_and_actions_follow_the_data(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                p.width(w)
                p.show()
                got = runs(self.kinds(p, "work"))
                self.assertEqual(got[:2], ["Command", "Page"], f"at {w} px: {got}")
                got = runs(self.kinds(p, "add"))
                self.assertEqual(got[-2:], ["Action", "ask clark"], f"at {w} px: {got}")
                p.key("Escape", 0, "Escape", 27)

    def test_an_empty_bar_keeps_its_order_and_a_question_is_first(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                p.width(w)
                p.show()
                self.assertEqual(runs([r[0] for r in p.rows(True)]), ["Page", "Action", "Project", "Command"], f"at {w} px")
                self.assertEqual(self.kinds(p, "what is a supplier?")[0], "ask clark", f"at {w} px")
                p.key("Escape", 0, "Escape", 27)


if __name__ == "__main__":
    unittest.main()
