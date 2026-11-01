"""#79: the At a glance tiles open Work items filtered to exactly what they count, and Project health fills the row.

Run: python3 dev/run_tests.py test_glance_tiles
#140: `Words` runs glanceTiles.js's own tileWord (bundled by the pinned esbuild, as test_work_items does) in headless Chrome: each
tile's status in plain words, by colour and kind, never a colour name.
Drives the real server and the committed page in headless Chrome over the demo store at CLARK_NOW=2026-10-28. Required: fails,
never skips, without Chrome (set CLARK_CHROME).
"""
import copy
import json
import re
import tempfile
import unittest

from _paths import ROOT, SRC  # noqa: F401

from clark import page  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402
from test_work_filters import click, need_chrome  # noqa: E402
from test_work_items import FIXED_DATE, bundled, load_demo, page_target  # noqa: E402

CLOSED = {"Closed", "Cancelled", "Made", "Withdrawn"}
TODAY = "2026-10-28"


def expected(data):
    """Each tile's number, worked out here again in plain Python from the stored rows."""
    rows = [("action", r) for r in data["actions"]] + [(str(r["type"]).lower(), r) for r in data["raid"]] + [("decision", r) for r in data["decisions"]]
    opened = [(k, r) for k, r in rows if r["status"] not in CLOSED]
    return {
        "overdue": sum(1 for k, r in opened if k == "action" and r.get("due_date") and r["due_date"] < TODAY),
        "risks": sum(1 for k, r in opened if k not in ("action", "decision") and r.get("priority") in ("Urgent", "High")),
        "decisions": sum(1 for k, r in rows if k == "decision" and r["status"] == "Pending"),
    }


class Tiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.store, cls.folder, cls.ids = load_demo()
        cls.projects = cls.store.read("projects")
        cls.data = {p["code"]: cls.store.data_for(p["code"]) for p in cls.projects}
        for code, d in cls.data.items():     # Decisions needed is hidden until shown (#45): these tests count it, so its row says shown
            d["glance_tiles"] = [{"project": code, "tile": t, "hidden": 0, "outline": "", "sort_order": n * 10} for n, t in enumerate(("health", "overdue", "risks", "decisions"), 1)]

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def load(self, cdp, port, code, width=1400):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/#dashboard&p={code}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.glance .fig').length", sid) == 4), "four tiles")
        return sid

    def serve(self):
        s = Running(data_for=lambda code: copy.deepcopy(self.data.get(code)), projects=lambda: self.projects,
                    page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        return s

    def test_each_tile_number_is_the_list_it_opens_and_the_chips_say_what_it_counts(self):
        s = self.serve()
        # what the line shows for each tile: the chips, in the order the line writes them
        words = {"overdue": ["is:open", "type:action", "due:overdue"], "risks": ["is:open", "type:risk,issue,assumption,dependency", "priority:Urgent,High"],
                 "decisions": ["is:open", "type:decision", "status:Pending"]}
        for code in self.data:
            want = expected(self.data[code])
            for key in ("overdue", "risks", "decisions"):
                with self.subTest(project=code, tile=key), chrome() as cdp:
                    sid = self.load(cdp, s.port, code)
                    self.assertEqual(int(cdp.js(f"document.querySelector('[data-fig={key}] .v').textContent", sid)), want[key])
                    name = cdp.js(f"document.querySelector('[data-fig={key}]').getAttribute('aria-label')", sid)
                    label = cdp.js(f"document.querySelector('[data-fig={key}] .k').textContent", sid)
                    self.assertTrue(name.startswith(label), "the spoken name starts with the visible words")
                    self.assertTrue(name.endswith("Opens Work items showing these"), name)
                    click(cdp, sid, f"[data-fig={key}]")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work')", sid)), "Work items opened")
                    self.assertTrue(wait(lambda: cdp.js("location.hash", sid).startswith("#work&p=" + code + "&f=")))
                    count = cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid)
                    self.assertEqual(count, want[key], "the list holds exactly what the tile counted")
                    chips = cdp.js("[...document.querySelectorAll('.fline .fchip .ft')].map(c => c.textContent)", sid)
                    self.assertEqual(chips, words[key], "the line shows what the tile counted")
                    self.assertEqual(cdp.js("document.querySelector('#work-count').textContent", sid), f"{count} open item" + ("" if count == 1 else "s"))
                    cdp.js("history.back()", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.glance')", sid)), "Back returns to the Dashboard")

    def test_the_published_file_has_no_clickable_tile(self):
        """A published file is view-only: its tiles are not buttons and open nothing."""
        from pathlib import Path
        from clark import publish
        from test_report_editor import DemoStore, EMPTY_BRANDING, USER
        demo = DemoStore()
        self.addCleanup(demo.close)
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(__import__("shutil").rmtree, folder, True)
        done = publish.publish(demo.store, "ABC", folder, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.glance')", sid)), "the file drew its tiles")
            self.assertEqual(cdp.js("document.querySelectorAll('.fig.go, .glance button').length", sid), 0)

    def test_project_health_is_two_tile_widths_and_the_tiles_follow_it_from_the_left(self):
        s = self.serve()
        code = next(iter(self.data))
        with chrome() as cdp:
            sid = self.load(cdp, s.port, code)
            box = lambda sel: cdp.js(f"(() => {{ const b = document.querySelector('{sel}').getBoundingClientRect(); return [b.left, b.right, b.width]; }})()", sid)
            row = cdp.js("(() => { const b = document.querySelector('.glance').getBoundingClientRect(); return [b.left, b.right]; })()", sid)
            gap = cdp.js("parseFloat(getComputedStyle(document.querySelector('.glance')).columnGap)", sid)
            health, first = box("[data-tile=health]"), box("[data-tile=overdue]")
            self.assertAlmostEqual(health[0], row[0], delta=1)
            self.assertAlmostEqual(health[2], 2 * first[2] + gap, delta=1.5, msg="health spans two tile widths")
            tiles = [box(f"[data-tile={k}]") for k in ("overdue", "risks", "decisions")]
            self.assertTrue(all(abs(t[2] - 190) < 2 for t in tiles), "the other tiles keep their own width")


KINDS = ("health", "overdue", "risks", "decisions")
COLOURS = ("g", "a", "r", "n", "")
PLAIN = {"On track", "At risk", "Off track", "Overdue", "Waiting", "Watch", "High"}
LABEL = "Tile colour: "   # Project health's word, beside a pill that may say something else
# the word for each colour shown, and the tiles that say it more exactly (the prototype's C.tileWord, views.js, #140)
WANT = {"g": "On track", "a": "At risk", "r": "Off track", "n": "", "": ""}
EXACT = {("overdue", "r"): "Overdue", ("decisions", "a"): "Waiting", ("risks", "a"): "Watch", ("risks", "r"): "High"}


class Words(unittest.TestCase):
    """#140: tileWord(key, rag, outline, pill), the page's own function, called in Chrome for every case."""

    @classmethod
    def setUpClass(cls):
        need_chrome()
        cases = [[k, c, o, p] for k in KINDS for c in COLOURS + ("G", "A", "R", "N") for o in ("", "G", "A", "R", "N")
                 for p in ("g", "a", "r", "n", "")]
        script = (bundled(SRC / "clark" / "page" / "src" / "glanceTiles.js", "GT") + ";\n("
                  + "(cs) => ({ words: cs.map((c) => GT.tileWord(...c)), table: GT.TILE_WORDS, of: GT.TILE_WORDS_OF, label: GT.HEALTH_WORD_LABEL,"
                  + " health: GT.HEALTH_WORDS,"
                  + " bare: [GT.tileWord('risks', 'g'), GT.tileWord('overdue', 'r'), GT.tileWord('decisions', 'a'), GT.tileWord('risks'),"
                  + " GT.tileWord('health', 'r')] })" + ")(" + json.dumps(cases) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            out = res["result"]["value"]
        cls.word = {tuple(c): w for c, w in zip(cases, out["words"])}
        cls.out = out

    def test_each_colour_and_kind_has_its_word_when_the_colour_is_automatic(self):
        for k in ("overdue", "risks", "decisions"):
            for c in COLOURS:
                with self.subTest(tile=k, colour=c):
                    self.assertEqual(self.word[(k, c, "", "")], EXACT.get((k, c), WANT[c]))
                    self.assertEqual(self.word[(k, c.upper(), "", "")], EXACT.get((k, c), WANT[c]), "capitals are the same colour")
        self.assertEqual(self.out["bare"][:4], ["On track", "Overdue", "Waiting", ""])

    def test_the_two_exact_words_are_only_for_their_own_tile_and_colour(self):
        self.assertEqual(self.word[("overdue", "a", "", "")], "At risk")
        self.assertEqual(self.word[("overdue", "g", "", "")], "On track")
        self.assertEqual(self.word[("decisions", "r", "", "")], "Off track")
        self.assertEqual(self.word[("decisions", "g", "", "")], "On track")
        self.assertEqual(self.word[("risks", "r", "", "")], "High", "a count of risks never reads as late")
        self.assertEqual(self.word[("risks", "a", "", "")], "Watch", "not the same words as the risks it counts")
        self.assertEqual(self.word[("risks", "g", "", "")], "On track")

    def test_a_colour_set_by_hand_has_its_word_and_no_colour_has_none(self):
        for k in ("overdue", "risks", "decisions"):
            for o in "GAR":
                with self.subTest(tile=k, outline=o):
                    self.assertEqual(self.word[(k, o.lower(), o, "")], EXACT.get((k, o.lower()), WANT[o.lower()]))
            for c in COLOURS:
                with self.subTest(tile=k, colour=c, outline="N"):
                    self.assertEqual(self.word[(k, c, "N", "")], "", "No colour by hand: no word, whatever the automatic colour")

    def test_project_health_has_a_word_only_when_set_by_hand_to_another_colour_than_its_pill(self):
        for c in COLOURS:
            for p in ("g", "a", "r", "n", ""):
                with self.subTest(colour=c, pill=p):
                    self.assertEqual(self.word[("health", c, "", p)], "", "automatic: the pill says it")
                    self.assertEqual(self.word[("health", c, "N", p)], "", "No colour by hand: no word")
        for o in "GAR":
            for p in ("g", "a", "r", "n", ""):
                with self.subTest(outline=o, pill=p):
                    want = "" if o.lower() == p else LABEL + WANT[o.lower()]
                    self.assertEqual(self.word[("health", o.lower(), o, p)], want)
        self.assertEqual(self.word[("health", "r", "R", "g")], "Tile colour: Off track", "red by hand beside an On track pill says what it is")
        self.assertEqual(self.word[("health", "a", "A", "a")], "", "the same colour as the pill: no second word")
        self.assertEqual(self.out["bare"][4], "", "health with no outline given: no word")

    def test_the_words_are_plain_and_never_a_colour_name(self):
        said = {w for w in self.word.values() if w}
        self.assertEqual(said, PLAIN | {LABEL + w for w in ("On track", "At risk", "Off track")})
        self.assertEqual(self.out["label"], LABEL)
        self.assertEqual(self.out["of"], {"overdue": {"r": "Overdue"}, "decisions": {"a": "Waiting"}, "risks": {"a": "Watch", "r": "High"}},
                         "the same table as the prototype's TILE_WORD_OF")
        for w in said:
            self.assertIsNone(re.search(r"\b(red|amber|green|rag)\b", w, re.I), w)
            self.assertEqual(w, w.strip())
        self.assertEqual(self.out["table"], {"g": "On track", "a": "At risk", "r": "Off track"})
        self.assertEqual({v: k for k, v in self.out["health"].items()}, self.out["table"], "the same words as the health pill")


if __name__ == "__main__":
    unittest.main()
