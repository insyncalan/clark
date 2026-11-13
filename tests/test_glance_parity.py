"""The Edit tiles and the published file say the same words, and show the same colour, under each At a glance tile.

Run: python3 dev/run_tests.py test_glance_parity
The same cases go through the page's own tiles() / allTiles() / fileTiles() (glanceTiles.js, bundled by the pinned esbuild, run in
headless Chrome) and through glance.py's tiles() (the reference: the published file's words), and the detail line under each tile
must be the same string. A colour set by hand on Project health must show the same in Edit and in the file. Required: fails,
never skips, without Chrome.
"""
import json
import unittest

from _paths import SRC  # noqa: F401

from clark import glance
from test_glance import action, by_name, data, decision, raid
from test_server import chrome
from test_work_filters import need_chrome
from test_work_items import bundled, page_target

TODAY = "2026-10-28"
# name -> (open-action dues, [(type, priority, status)], [(status, needed_by)])
CASES = {
    "nothing at all": ([], [], []),
    "open action not late, one low risk, one undated decision": (["2026-12-01"], [("Risk", "Low", "Open")], [("Pending", None)]),
    "late action, one high risk, one dated decision": (["2026-10-01"], [("Issue", "High", "Open")], [("Pending", "2030-01-15")]),
    "two risks none high, two dated decisions": (["2026-12-01", "2026-12-02"], [("Risk", "Low", "Open"), ("Risk", "Medium", "Open")],
                                                  [("Pending", "2030-01-15"), ("Pending", "2029-03-01")]),
    "two high risks, only closed actions": ([], [("Risk", "High", "Open"), ("Risk", "Urgent", "Open")], [("Made", "2030-01-15")]),
    "only closed risks": ([], [("Risk", "High", "Closed")], []),
}


def page_rows(case):
    dues, risks, decs = case
    rows = [{"id": f"ABC-A-{n + 1:03d}", "kind": "action", "status": "Open", "due_date": d, "priority": "Medium"} for n, d in enumerate(dues)]
    rows += [{"id": f"ABC-{n + 1:03d}", "kind": t.lower(), "status": st, "priority": pr, "due_date": None} for n, (t, pr, st) in enumerate(risks)]
    rows += [{"id": f"ABC-D-{n + 1:03d}", "kind": "decision", "status": st, "needed_by": nb, "date": None} for n, (st, nb) in enumerate(decs)]
    return rows


def file_tiles(case, health="On track", outline=None):
    dues, risks, decs = case
    d = data(actions=[action(n + 1, due) for n, due in enumerate(dues)], raid_=[raid(n + 1, t, pr, st) for n, (t, pr, st) in enumerate(risks)],
             decisions=[decision(n + 1, st, nb) for n, (st, nb) in enumerate(decs)])
    d["project"]["health"] = health
    shown = glance.tiles(d, TODAY, tile_order=["health", "overdue", "risks", "decisions"], hidden=set(), outlines=outline or {}, for_client=True)
    return [{"tile": t["tile"], "label": t["title"], "value": t["value"], "detail": t["detail"], "colour": t["class"].upper(),
             "outline": (outline or {}).get(t["tile"]) or ""} for t in shown]


class SameWords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        names = list(CASES)
        hand = [("On track", {"health": "R"}), ("Off track", {"health": "G"}), ("At risk", {"health": "N"}), ("At risk", {})]
        inputs = [{"rows": page_rows(c), "file": file_tiles(c)} for c in CASES.values()]
        hands = [{"health": h, "outline": o, "file": file_tiles(CASES[names[0]], h, o)} for h, o in hand]
        script = (bundled(SRC / "clark" / "page" / "src" / "glanceTiles.js", "GT") + ";\n((cs, hs) => ({"
                  + " details: cs.map((c) => GT.tiles(c.rows, '" + TODAY + "').map((t) => [t.key, t.detail])),"
                  + " fromFile: cs.map((c) => GT.fileTiles({ tiles: c.file }, { health: 'On track' }).map((t) => [t.key, t.detail])),"
                  + " hand: hs.map((h) => [GT.allTiles([], '" + TODAY + "', { health: h.health }, Object.entries(h.outline).map(([tile, outline]) => ({ tile, hidden: 0, outline, sort_order: 1 })))"
                  + ".find((t) => t.key === 'health').rag, GT.fileTiles({ tiles: h.file }, { health: h.health }).find((t) => t.key === 'health').rag]) })"
                  + ")(" + json.dumps(inputs) + "," + json.dumps(hands) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            cls.out = res["result"]["value"]
        cls.names, cls.inputs, cls.hand = names, inputs, hands

    def test_edit_says_the_words_the_file_says_under_every_tile(self):
        for i, name in enumerate(self.names):
            edit = dict(self.out["details"][i])
            ref = {t["tile"]: t["detail"] for t in self.inputs[i]["file"] if t["tile"] != "health"}
            for key, want in ref.items():
                with self.subTest(case=name, tile=key):
                    self.assertEqual(edit[key], want)

    def test_the_file_drawn_by_the_page_keeps_the_words_it_was_given(self):
        for i, name in enumerate(self.names):
            ref = {t["tile"]: t["detail"] for t in self.inputs[i]["file"] if t["tile"] != "health"}
            with self.subTest(case=name):
                self.assertEqual(dict(self.out["fromFile"][i]), {**ref, "health": ""})

    def test_a_colour_set_by_hand_on_project_health_shows_the_same_in_edit_and_in_the_file(self):
        for (edit, file), h in zip(self.out["hand"], self.hand):
            with self.subTest(health=h["health"], outline=h["outline"]):
                self.assertEqual(edit, file)
        self.assertEqual([e for e, _ in self.out["hand"]][:3], ["r", "g", "n"])


if __name__ == "__main__":
    unittest.main()
