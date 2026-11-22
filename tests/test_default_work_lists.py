"""Row 1189 (epic), part 1193: what the three default Work items lists will need, pinned before the defaults change. Quick tier, no browser.

The ruling of 14-11: Risks and issues, Open actions and Decisions start as a Work items list on the saved views Risks and issues, Actions
and Decisions. The swap waits for row 1268 (Word, workbook and published file print the lists), so the built-ins stay the
defaults here. This pins the part that does not wait: each saved view (page/src/templates/workItemsList.js VIEWS) is a filter
the server's checker accepts as it is, and the server's matcher lists exactly that view's items, open ones only, none of the others.

Run: python3 dev/run_tests.py test_default_work_lists
"""
import json
import re
import unittest

from _paths import SRC
from clark import default_sections, store as store_module
from clark.section_kinds import workitems as wi

PAGE = SRC / "clark" / "page" / "src"
TODAY = "2030-01-15"
ROWS = [
    {"id": "A-1", "kind": "action", "title": "a", "status": "Open", "due": "2030-01-10"},
    {"id": "A-2", "kind": "action", "title": "b", "status": "Closed", "due": "2030-01-01"},
    {"id": "R-1", "kind": "risk", "title": "c", "status": "Open", "due": "2030-03-01"},
    {"id": "I-1", "kind": "issue", "title": "d", "status": "Open", "due": "2030-03-02"},
    {"id": "I-2", "kind": "issue", "title": "e", "status": "Closed", "due": "2030-03-03"},
    {"id": "D-1", "kind": "decision", "title": "f", "status": "Pending", "due": "2030-03-04"},
    {"id": "D-2", "kind": "decision", "title": "g", "status": "Made", "due": "2030-02-04"},
]
# the three views of the ruling: view id on the page -> (built-in type it replaces, the ids it must list)
DEFAULT_VIEWS = {
    "risks-issues": ("raid", ["R-1", "I-1"]),
    "actions": ("actions", ["A-1"]),
    "decisions": ("decisions", ["D-1"]),
}


def page_views():
    text = (PAGE / "templates" / "workItemsList.js").read_text(encoding="utf-8")
    block = text[text.index("export const VIEWS"):text.index("];", text.index("export const VIEWS"))]
    out = {}
    for m in re.finditer(r'\{ id: "([a-z-]+)", name: "([^"]+)", patch: \{(.*?)\} \}', block):
        kinds = re.search(r'kinds: \[(.*?)\]', m.group(3))
        out[m.group(1)] = {"name": m.group(2), "kinds": re.findall(r'"([a-z]+)"', kinds.group(1)) if kinds else []}
    return out


class DefaultWorkLists(unittest.TestCase):
    def test_the_page_has_the_three_saved_views_of_the_ruling(self):
        views = page_views()
        self.assertEqual(views["risks-issues"], {"name": "Risks and issues", "kinds": ["risk", "issue"]})
        self.assertEqual(views["actions"], {"name": "Actions", "kinds": ["action"]})
        self.assertEqual(views["decisions"], {"name": "Decisions", "kinds": ["decision"]})

    def test_each_view_is_a_filter_the_server_accepts_and_lists_only_its_own_open_items(self):
        views = page_views()
        for view, (_, want) in DEFAULT_VIEWS.items():
            with self.subTest(view=view):
                value = wi.check({"kinds": views[view]["kinds"]}, store_module.BODY_RULES)
                self.assertEqual(value["mode"], "open")
                self.assertEqual(wi.matching(value, ROWS, TODAY), want)
                self.assertEqual(wi.check(value, store_module.BODY_RULES), value, "canonical: checking it again changes nothing")

    def test_the_built_ins_stay_the_defaults_until_the_lists_print_everywhere(self):
        types = [s["type"] for s in default_sections.DEFAULT_SECTIONS]
        for view, (builtin, _) in DEFAULT_VIEWS.items():
            if view in ("risks-issues", "actions", "decisions"):
                continue                                            # rows 8, 9 and 10 of item 1193: Risks and issues, Open actions and Decisions are Work items lists now (tests below)
            self.assertIn(builtin, types, "%s is no longer a default: update tests/test_dashboard_template_built.py PENDING and this file together" % builtin)
        self.assertEqual(types.count("workitems"), 3, "the Risks and issues, Open actions and Decisions lists are the default lists")
        by_title = {x["title"]: x for x in default_sections.DEFAULT_SECTIONS}
        for title in ("Risks and issues", "Open actions", "Decisions"):
            self.assertEqual(by_title[title]["type"], "workitems", title)      # rows 1193-8, 9 and 10


if __name__ == "__main__":
    unittest.main()
