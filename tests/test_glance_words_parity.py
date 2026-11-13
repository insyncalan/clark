"""Risks, decisions and overdue tiles: the page's glanceTiles.js and glance.py (the reference) agree on value, colour and word.

Run: python3 dev/run_tests.py test_glance_words_parity
test_glance_parity compares the detail line only. Here the same cases go through the page's tiles() / tileWord() / fileTiles()
(headless Chrome) and glance.tiles(), and the number, the automatic colour and the plain word under each tile must match, so a
change to either side alone fails. The words are also pinned as literals, so both sides drifting together fails too.
"""
import json
import unittest

from _paths import SRC  # noqa: F401

from clark import glance
from test_glance import action, data, decision, raid
from test_server import chrome
from test_work_filters import need_chrome
from test_work_items import bundled, page_target

TODAY = "2026-10-28"
# name -> (action dues, [(type, priority, status)], [(status, needed_by)])
CASES = {
    "empty": ([], [], []),
    "one open assumption, not high": ([], [("Assumption", "Low", "Open")], []),
    "one high dependency": ([], [("Dependency", "High", "Open")], []),
    "urgent risk plus two low": ([], [("Risk", "Urgent", "Open"), ("Risk", "Low", "Open"), ("Issue", "Medium", "Open")], []),
    "high but closed": ([], [("Risk", "High", "Closed"), ("Risk", "High", "Cancelled")], []),
    "delayed is open": ([], [("Risk", "High", "Delayed")], []),
    "due today is not overdue": ([TODAY], [], []),
    "late and not late": (["2026-10-27", "2026-10-28", "2027-01-01"], [], []),
    "pending decisions, one date bad": ([], [], [("Pending", "not a date"), ("Pending", "2029-03-01"), ("Pending", "2030-01-15")]),
    "pending undated": ([], [], [("Pending", None)]),
    "made and withdrawn only": ([], [], [("Made", "2030-01-15"), ("Withdrawn", None)]),
}
# The words, as literals: (tile, colour letter) -> word.
WORDS = {("overdue", "r"): "Overdue", ("overdue", "g"): "On track", ("risks", "r"): "High", ("risks", "a"): "Watch",
         ("risks", "g"): "On track", ("decisions", "a"): "Waiting", ("decisions", "g"): "On track"}


def page_rows(case):
    dues, risks, decs = case
    rows = [{"id": f"A-{n}", "kind": "action", "status": "Open", "due_date": d, "priority": "Medium"} for n, d in enumerate(dues)]
    rows += [{"id": f"R-{n}", "kind": t.lower(), "status": st, "priority": pr, "due_date": None} for n, (t, pr, st) in enumerate(risks)]
    rows += [{"id": f"D-{n}", "kind": "decision", "status": st, "needed_by": nb, "date": None} for n, (st, nb) in enumerate(decs)]
    return rows


def reference(case):
    dues, risks, decs = case
    d = data(actions=[action(n + 1, due) for n, due in enumerate(dues)], raid_=[raid(n + 1, t, pr, st) for n, (t, pr, st) in enumerate(risks)],
             decisions=[decision(n + 1, st, nb) for n, (st, nb) in enumerate(decs)])
    shown = glance.tiles(d, TODAY, tile_order=["health", "overdue", "risks", "decisions"], hidden=set(), outlines={}, for_client=True)
    return {t["tile"]: t for t in shown if t["tile"] != "health"}


class WordsParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.names = list(CASES)
        cls.ref = [reference(c) for c in CASES.values()]
        inputs = [{"rows": page_rows(c), "file": [{"tile": k, "label": t["title"], "value": t["value"], "detail": t["detail"], "colour": t["class"].upper()}
                                                   for k, t in r.items()]} for c, r in zip(CASES.values(), cls.ref)]
        script = (bundled(SRC / "clark" / "page" / "src" / "glanceTiles.js", "GT") + ";\n((cs) => ({"
                  + " page: cs.map((c) => GT.tiles(c.rows, '" + TODAY + "').map((t) => [t.key, t.value, t.rag, t.detail])),"
                  + " file: cs.map((c) => GT.fileTiles({ tiles: c.file }, {}).map((t) => [t.key, t.word])),"
                  + " words: GT.TILE_WORDS_OF })"
                  + ")(" + json.dumps(inputs) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            cls.out = res["result"]["value"]

    def test_value_colour_and_detail_match_the_reference_for_every_case(self):
        for i, name in enumerate(self.names):
            for key, value, rag, detail in self.out["page"][i]:
                with self.subTest(case=name, tile=key):
                    ref = self.ref[i][key]
                    self.assertEqual((value, rag, detail), (ref["value"], ref["class"], ref["detail"]))

    def test_the_word_under_each_tile_follows_the_colour_the_reference_gives(self):
        for i, name in enumerate(self.names):
            for key, word in self.out["file"][i]:
                with self.subTest(case=name, tile=key):
                    self.assertEqual(word, WORDS.get((key, self.ref[i][key]["class"]), ""))

    def test_the_word_table_is_pinned_on_the_page_side(self):
        got = {(k, c): w for k, m in self.out["words"].items() for c, w in m.items()}
        self.assertEqual(got, {k: w for k, w in WORDS.items() if w != "On track"})

    def test_the_cases_cover_every_colour_of_every_tile(self):
        seen = {(k, t["class"]) for r in self.ref for k, t in r.items()}
        self.assertEqual(seen, {("overdue", "r"), ("overdue", "g"), ("risks", "r"), ("risks", "a"), ("risks", "g"), ("decisions", "a"), ("decisions", "g")})


if __name__ == "__main__":
    unittest.main()
