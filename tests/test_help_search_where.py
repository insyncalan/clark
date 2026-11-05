"""#642 step 4, Search shows where: a search result names the guide, the step and the part of the screen it is about.

Run: python3 dev/run_tests.py test_help_search_where
The pure part (buildIndex, resultsView) is bundled by the pinned esbuild and run in node (skips with no node), as in test_help_guides.py.
The panel as drawn is driven in headless Chrome (a page built with a fixture guide: the real source ships no guide yet), at 1400 and 900 px,
in the light and the dark theme. The words are the signed mockup's (docs/handoff/v1.0/mockups/help-search.html): "N results for “q”", the
sentence under it, "Step N: title" and "Screen part: ...". A step may carry `t` (its short title) and `part` (its screen part): both are data
and both are optional; a chip with nothing to say is left off, never filled with invented words.
"""
import base64
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import TOOLS  # noqa: F401  (puts dev/tools on the path)
import _testpage as testpage
from _help_shown import RAW
from test_help_guides import run_node
from test_help_panel import full_help_from_menu
from test_help_nav_page import set_size, set_theme, SIZES, THEMES
from test_report_editor import Base
import build_page  # noqa: E402

LEAD = "Each result names the guide and the step it is about."
SHOTS = os.environ.get("CLARK_HELP_SHOTS", "")       # a folder: the browser test saves a screenshot of each search into it

# Fixture guides (test only). The first has a title and a screen part on every step; the second has neither.
FIXTURES = [
    {"id": "fx-template", "t": "Fixture template guide", "job": "Start a quokka from a ready-made layout.",
     "steps": [{"d": "Open the **Zebra** screen.", "t": "Open the zebra", "part": "Zebra toolbar"},
               {"d": "Choose a wombat on the list.", "t": "Pick a wombat", "part": "Wombat list"}],
     "result": "A numbat arrives.", "next": ["ref-keys"]},
    {"id": "fx-plain", "t": "Fixture plain guide", "job": "Check that an ocelot can read it.",
     "steps": [{"d": "Press the ocelot button."}, {"d": "Wait for the lemur."}],
     "result": "A tapir arrives.", "next": ["ref-keys"]},
]


def fixture_content():
    c = copy.deepcopy(RAW)
    c["guides"] = copy.deepcopy(FIXTURES)
    return c


PROBE = """(() => {
  const idx = HL.buildIndex(), out = {};
  for (const q of ["wombat", "zebra", "quokka", "ocelot", "lemur", "numbat", "Fixture", "undo", "zzzqq"]) {
    const v = HL.resultsView(idx, q);
    out[q] = { kind: v.kind, line: v.line, lead: v.lead, rows: v.groups.flatMap((g) => g.results.map((r) => ({ id: r.id, tab: r.tab, where: r.where, text: r.text, labels: HL.whereLabels(r.where) }))) };
  }
  return out;
})()"""


class Logic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = run_node(fixture_content(), PROBE)
        cls.shipped = run_node(RAW, "(() => { const v = HL.resultsView(HL.buildIndex(), 'undo'); return { kind: v.kind, lead: v.lead }; })()")

    def row(self, q, gid):
        return next(x for x in self.r[q]["rows"] if x["id"] == gid)

    def test_a_word_in_a_step_gives_the_guide_the_step_and_its_screen_part(self):
        x = self.row("wombat", "guide-fx-template")
        self.assertEqual(x["where"], {"step": {"n": 2, "title": "Pick a wombat"}, "part": "Wombat list"})
        self.assertEqual(x["labels"], {"step": "Step 2: Pick a wombat", "part": "Screen part: Wombat list"})
        self.assertEqual(x["text"], "Choose a wombat on the list.", "the number is in the chip, so the snippet drops it")

    def test_the_first_step_is_step_one(self):
        self.assertEqual(self.row("zebra", "guide-fx-template")["labels"]["step"], "Step 1: Open the zebra")

    def test_a_step_with_no_title_or_part_shows_no_invented_words(self):
        x = self.row("lemur", "guide-fx-plain")
        self.assertEqual(x["labels"], {"step": "Step 2", "part": None})

    def test_a_match_in_the_job_or_the_result_names_no_step(self):
        for q, gid in (("quokka", "guide-fx-template"), ("numbat", "guide-fx-template"), ("Fixture", "guide-fx-plain")):
            x = self.row(q, gid)
            self.assertEqual(x["where"], {"step": None, "part": None}, q)
            self.assertEqual(x["labels"], {"step": None, "part": None}, q)

    def test_a_how_to_step_has_no_part_chip_of_its_own_not_the_tasks_whole_where(self):
        task = next(t for t in RAW["howto"]["tasks"] if t["id"] == "undo-a-mistake")
        rows = [x for x in self.r["undo"]["rows"] if x["id"] == "howto-undo-a-mistake"]
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["where"]["part"])
        self.assertIsNone(rows[0]["labels"]["part"])
        if rows[0]["where"]["step"]:
            self.assertTrue(1 <= rows[0]["where"]["step"]["n"] <= len(task["s"]))

    def test_the_lead_names_the_guide_so_it_is_shown_only_when_a_guide_ships(self):
        self.assertEqual(self.shipped["kind"], "results")
        self.assertEqual(self.shipped["lead"], LEAD if RAW["guides"] else None, "the sentence that says 'the guide' is shown when guides ship (nine do)")
        self.assertEqual(self.r["wombat"]["lead"], LEAD)

    def test_the_count_line_and_the_lead_are_the_signed_words(self):
        v = self.r["wombat"]
        self.assertEqual(v["lead"], LEAD)
        n = len(v["rows"])
        self.assertEqual(v["line"], f"{n} result{'' if n == 1 else 's'} for “wombat”")

    def test_an_empty_search_has_no_where(self):
        self.assertEqual(self.r["zzzqq"]["rows"], [])


class Page(Base):
    """The panel as drawn, on a page built with the fixture guides."""
    html = None

    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "helpContent.json"
            path.write_text(json.dumps(fixture_content(), ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(build_page, "help_content_path", lambda held=True: path):
                cls.html = build_page.build("main-test.jsx")

    def setUp(self):
        patch = mock.patch.object(testpage, "html", lambda branding=None: self.html)
        patch.start()
        self.addCleanup(patch.stop)
        super().setUp()

    def search(self, cdp, p, q):
        p.js("document.querySelector('#hpQ').focus()")
        p.js("(function(){var i=document.querySelector('#hpQ'); i.value=''; })()")
        p.type(q)
        p.until(f"document.querySelector('#hpQ').value === {json.dumps(q)} && !!document.querySelector('#hpRes a.hp-r')", f"results for {q}")

    def test_a_result_shows_its_guide_step_and_screen_part_in_every_size_and_theme(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.visit(cdp)
            full_help_from_menu(p)
            self.search(cdp, p, "wombat")
            for scheme in THEMES:
                set_theme(cdp, p, scheme)
                for w in SIZES:
                    set_size(cdp, p, w)
                    tag = f"{scheme} {w}"
                    hit = "document.querySelector('#hpRes a.hp-r[data-hit=\"guide-fx-template\"]')"
                    p.until(f"!!{hit}", f"{tag}: the guide is a result")
                    self.assertEqual(p.js(f"{hit}.querySelector('.hp-rt').textContent"), "Fixture template guide", tag)
                    self.assertEqual(p.js(f"{hit}.querySelector('[data-where=step]').textContent"), "Step 2: Pick a wombat", tag)
                    self.assertEqual(p.js(f"{hit}.querySelector('[data-where=part]').textContent"), "Screen part: Wombat list", tag)
                    self.assertEqual(p.js(f"{hit}.querySelector('.hp-rl').textContent"), "Choose a wombat on the list.", tag)
                    self.assertEqual(p.js("document.querySelector('.hp-resn').textContent"), "1 result for “wombat”", tag)
                    self.assertEqual(p.js("document.querySelector('.hp-resl').textContent"), LEAD, tag)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), f"{tag}: no sideways scroll")
                    self.assertNotEqual(p.js(f"getComputedStyle({hit}.querySelector('[data-where=step]')).backgroundColor"),
                                        p.js(f"getComputedStyle({hit}.querySelector('[data-where=part]')).backgroundColor"), f"{tag}: the two chips differ")
                    if SHOTS:
                        shot = cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]
                        (Path(SHOTS) / f"search-where-{scheme}-{w}.png").write_bytes(base64.b64decode(shot))

    def test_a_step_with_nothing_to_say_has_no_part_chip_and_a_job_match_has_no_chips(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.visit(cdp)
            full_help_from_menu(p)
            self.search(cdp, p, "lemur")
            hit = "document.querySelector('#hpRes a.hp-r[data-hit=\"guide-fx-plain\"]')"
            self.assertEqual(p.js(f"{hit}.querySelector('[data-where=step]').textContent"), "Step 2")
            self.assertEqual(p.js(f"!!{hit}.querySelector('[data-where=part]')"), False)
            self.search(cdp, p, "ocelot button")
            self.assertEqual(p.js("document.querySelector('#hpRes a.hp-r[data-hit=\"guide-fx-plain\"] [data-where=step]').textContent"), "Step 1")
            self.search(cdp, p, "tapir")
            self.assertEqual(p.js("!!document.querySelector('#hpRes a.hp-r[data-hit=\"guide-fx-plain\"] [data-where]')"), False, "the result line names no step")

    def test_a_result_still_opens_its_guide(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.visit(cdp)
            full_help_from_menu(p)
            self.search(cdp, p, "wombat")
            p.js("document.querySelector('#hpRes a.hp-r[data-hit=\"guide-fx-template\"]').click()")
            p.until("!!document.querySelector('#hp-guide-fx-template')", "the guide opened")


if __name__ == "__main__":
    unittest.main()
