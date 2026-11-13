"""Row glance-words: the tile word and colour the page draws match glance.py's colour, on every route a tile takes to the screen.

Run: python3 dev/run_tests.py test_glance_words_wiring
glanceTiles.js tileWord() has its own table test (test_glance_tiles); glance.py has colours but no words. This pins the wiring: the
word on an Edit tile (allTiles) and on a published tile (fileTiles) is tileWord of the colour shown, and the automatic colour of
each tile is the colour glance.py gives it. Required: fails, never skips, without Chrome.
"""
import json
import unittest

from _paths import SRC  # noqa: F401

from clark import glance
from test_glance import action, data, decision, raid
from test_glance_parity import CASES, TODAY, page_rows
from test_server import chrome
from test_work_filters import need_chrome
from test_work_items import bundled, page_target

LETTER = {"green": "g", "amber": "a", "red": "r", "": "n", None: "n"}
WORD = {"g": "On track", "a": "At risk", "r": "Off track", "n": ""}
EXACT = {("overdue", "r"): "Overdue", ("decisions", "a"): "Waiting", ("risks", "a"): "Watch", ("risks", "r"): "High"}
OUTLINES = ["", "G", "A", "R", "N"]
ALL = {**CASES, "a pending decision is no risk": ([], [], [("Pending", None)])}   # risks counts risks, issues, assumptions, dependencies only


def ref_colours(case):
    dues, risks, decs = case
    d = data(actions=[action(n + 1, due) for n, due in enumerate(dues)], raid_=[raid(n + 1, t, pr, st) for n, (t, pr, st) in enumerate(risks)],
             decisions=[decision(n + 1, st, nb) for n, (st, nb) in enumerate(decs)])
    return {t["tile"]: LETTER[t["colour"]] for t in glance.tiles(d, TODAY, tile_order=["overdue", "risks", "decisions"], hidden=set(), outlines={}) if t["tile"] != "health"}


class Wiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.names = list(ALL)
        rows = [page_rows(c) for c in ALL.values()]
        script = (bundled(SRC / "clark" / "page" / "src" / "glanceTiles.js", "GT") + ";\n((rs, os) => ({"
                  + " auto: rs.map((r) => GT.tiles(r, '" + TODAY + "').map((t) => [t.key, t.rag])),"
                  + " edit: os.map((o) => GT.allTiles(rs[2], '" + TODAY + "', { health: 'On track' }, ['overdue', 'risks', 'decisions', 'health'].map((tile) => ({ tile, hidden: 0, outline: o, sort_order: 1 }))).map((t) => [t.key, t.rag, t.word])),"
                  + " file: os.map((o) => ['health', 'overdue', 'risks', 'decisions'].flatMap((k) => ['g', 'a', 'r', 'n', ''].map((c) =>"
                  + " { const t = GT.fileTiles({ tiles: [{ tile: k, label: k, value: 1, detail: '', colour: c.toUpperCase(), outline: o }] }, { health: 'On track' })[0]; return [k, c, o, t.rag, t.word]; })))"
                  + " }))(" + json.dumps(rows) + "," + json.dumps(OUTLINES) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            cls.out = res["result"]["value"]

    def test_the_page_colour_of_each_tile_is_the_colour_glance_py_gives_it(self):
        for i, name in enumerate(self.names):
            page = {k: r for k, r in self.out["auto"][i]}
            for k, want in ref_colours(list(ALL.values())[i]).items():
                with self.subTest(case=name, tile=k):
                    self.assertEqual(page[k], want)

    def test_an_edit_tile_says_the_word_of_the_colour_it_shows(self):
        for o, tiles in zip(OUTLINES, self.out["edit"]):
            for k, rag, word in tiles:
                with self.subTest(outline=o, tile=k):
                    if k == "health":
                        self.assertEqual(word, "" if o in ("", "N") or o.lower() == "g" else "Tile colour: " + WORD[rag])
                    else:
                        self.assertEqual(word, EXACT.get((k, rag), WORD[rag]))

    def test_a_published_tile_says_the_word_of_its_colour_and_health_says_none(self):
        for o, tiles in zip(OUTLINES, self.out["file"]):
            for k, c, outline, rag, word in tiles:
                with self.subTest(tile=k, colour=c, outline=o):
                    self.assertEqual(rag, ("g" if not o else c or "n") if k == "health" else c or "n")   # health with no outline shows its pill
                    want = "" if k == "health" or o == "N" else EXACT.get((k, c or "n"), WORD[c or "n"])   # No colour by hand: no word
                    self.assertEqual(word, want)


if __name__ == "__main__":
    unittest.main()
