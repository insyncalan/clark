"""Item 391: the High risks and issues tile has ONE colour rule, the page's (glanceTiles.js tiles()), and the published file follows it.

Run: python3 dev/run_tests.py test_glance_rule
Red when any OPEN risk or issue is Urgent or High, amber when any risk or issue is open, green when none is. The same cases go
through the page's own tiles() (bundled by the pinned esbuild, run in headless Chrome) and through glance.py's tiles(), for the
editor and for the client's file (for_client=True), and the colours must be the same. Required: fails, never skips, without Chrome.
"""
import json
import unittest

from _paths import SRC  # noqa: F401

from clark import glance
from test_glance import by_name, data, raid
from test_server import chrome
from test_work_filters import need_chrome
from test_work_items import bundled, page_target

TODAY = "2026-10-28"
# name -> (expected colour letter, [(type, priority, status), ...])
CASES = {
    "no items": ("g", []),
    "Low only": ("a", [("Risk", "Low", "Open"), ("Issue", "Low", "Open")]),
    "open Medium": ("a", [("Risk", "Medium", "Open")]),
    "open High": ("r", [("Issue", "High", "Open")]),
    "open Urgent": ("r", [("Risk", "Urgent", "Open")]),
    "closed High only": ("g", [("Risk", "High", "Closed")]),
    "closed High and open Low": ("a", [("Risk", "High", "Closed"), ("Risk", "Low", "Open")]),
    "open with no priority": ("a", [("Risk", None, "Open")]),
    "Low, Medium and High": ("r", [("Risk", "Low", "Open"), ("Risk", "Medium", "Open"), ("Issue", "High", "Open")]),
}
# Known gap, not part of the rule (it says risks and issues only): the page's tiles() counts open assumptions and dependencies
# as risks and issues, glance.py does not. Pinned so a change on either side is seen.
ASSUMPTIONS = {"assumption only": [("Assumption", "Low", "Open")], "dependency only": [("Dependency", "Medium", "Open")]}
WORDS = {"g": "green", "a": "amber", "r": "red"}


def rows_of(case):
    return [{"id": f"ABC-{n + 1:03d}", "kind": t.lower(), "status": st, "priority": pr, "due_date": None, "owner": None}
            for n, (t, pr, st) in enumerate(case)]


def published(case, for_client):
    d = data(raid_=[raid(n + 1, t, pr, st) for n, (t, pr, st) in enumerate(case)])
    return by_name(glance.tiles(d, TODAY, for_client=for_client))["risks"]["colour"]


class OneRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        names = list(CASES) + list(ASSUMPTIONS)
        cases = [c for _, c in CASES.values()] + list(ASSUMPTIONS.values())
        script = (bundled(SRC / "clark" / "page" / "src" / "glanceTiles.js", "GT") + ";\n((cs) => cs.map((rows) => GT.tiles(rows, '"
                  + TODAY + "').find((x) => x.key === 'risks').rag))(" + json.dumps([rows_of(c) for c in cases]) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            cls.page = dict(zip(names, res["result"]["value"]))

    def test_the_page_gives_the_ruled_colour(self):
        for name, (want, _) in CASES.items():
            with self.subTest(case=name):
                self.assertEqual(self.page[name], want)

    def test_the_published_file_gives_the_same_colour_as_the_page(self):
        for name, (_, case) in CASES.items():
            for for_client in (False, True):
                with self.subTest(case=name, for_client=for_client):
                    self.assertEqual(published(case, for_client), WORDS[self.page[name]])

    def test_a_project_whose_open_risks_are_all_low_is_amber_on_both(self):
        self.assertEqual(self.page["Low only"], "a")
        self.assertEqual(published(CASES["Low only"][1], True), "amber")

    def test_assumptions_and_dependencies_alone_are_the_known_gap(self):
        self.assertEqual([self.page[n] for n in ASSUMPTIONS], ["a", "a"], "the page")
        self.assertEqual([published(c, True) for c in ASSUMPTIONS.values()], ["green", "green"], "the file")


if __name__ == "__main__":
    unittest.main()
