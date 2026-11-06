"""#645 steps 3 to 5: the Help peek's pure rules (src/clark/page/src/help/peekLogic.js), and what the shipped build does without text.

Run: python3 dev/run_tests.py test_help_peek_logic
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (the tests skip when node is not on the machine).
The rules that need the page (opening, closing, focus, the two other panels) are in test_help_peek.py, in a browser. The context
TEXT is another part of the work: the cases here use made-up text that exists only in this file.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)

HELP = SRC / "clark" / "page" / "src" / "help"
LIVE_SCREENS = json.loads(re.search(r"LIVE_SCREENS = (\[.*?\]);", (HELP / "helpStore.js").read_text(encoding="utf-8")).group(1))


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "pl.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=PL", str(HELP / "peekLogic.js"), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"      # the bundle may hold the Help content: a file, never one argument (Linux allows 128 KB for one)
        script.write_text(out.read_text(encoding="utf-8") + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


class Screens(unittest.TestCase):
    def test_the_screen_is_the_view_and_the_dashboard_is_its_edit_view_while_editing(self):
        r = run_node("({ d: PL.screenOf('dashboard', 'view'), e: PL.screenOf('dashboard', 'edit'), w: PL.screenOf('work', 'edit'), m: PL.screenOf('milestones', 'view'), s: PL.screenOf('settings', 'edit') })")
        self.assertEqual(r, {"d": "dashboard", "e": "dashboard+edit", "w": "work", "m": "milestones", "s": "settings"})

    def test_every_screen_it_can_name_is_a_live_screen(self):
        names = run_node("[['dashboard','view'],['dashboard','edit'],['work','view'],['milestones','view'],['settings','view']].map(([v, m]) => PL.screenOf(v, m))")
        self.assertEqual(set(names), set(LIVE_SCREENS))


class Shape(unittest.TestCase):
    def shape(self, t):
        return run_node("PL.shapeContext(" + json.dumps(t) + ")")

    def test_a_title_and_sentences(self):
        self.assertEqual(self.shape({"title": "Zebra", "sentences": ["One.", " Two. "], "full": "ref-keys"}),
                         {"title": "Zebra", "lines": ["One.", "Two."], "cards": [], "full": "ref-keys"})

    def test_lines_is_read_as_sentences_and_a_lone_string_is_one_line(self):
        self.assertEqual(self.shape({"title": "Zebra", "lines": ["One."]})["lines"], ["One."])
        self.assertEqual(self.shape({"title": "Zebra", "sentences": "Just one."})["lines"], ["Just one."])

    def test_cards_may_be_strings_or_a_name_with_a_line(self):
        r = self.shape({"title": "Zebra", "sentences": ["One."], "cards": ["Quokka. A line.", {"name": "Numbat", "line": "Another."}, {"title": "Wombat", "text": "Third."}, "", {}]})
        self.assertEqual(r["cards"], [{"name": "", "line": "Quokka. A line."}, {"name": "Numbat", "line": "Another."}, {"name": "Wombat", "line": "Third."}])

    def test_cards_alone_are_enough(self):
        self.assertEqual(self.shape({"title": "Zebra", "cards": ["A line."]})["lines"], [])

    def test_nothing_to_draw_is_none(self):
        for t in (None, {}, "text", 5, [], {"title": "Zebra"}, {"title": "Zebra", "sentences": [], "cards": []}, {"sentences": ["One."]},
                  {"title": "", "sentences": ["One."]}, {"title": "Zebra", "sentences": ["", "  "]}):
            self.assertIsNone(self.shape(t), json.dumps(t))

    def test_everything_is_read_as_text_never_as_markup(self):
        r = self.shape({"title": "<b>Zebra</b>", "sentences": ["<i>One</i>", 5, None], "full": 7})
        self.assertEqual((r["title"], r["lines"], r["full"]), ("<b>Zebra</b>", ["<i>One</i>", "5"], "7"))


class Shipped(unittest.TestCase):
    """The build as it stands without the text: nothing opens, so "?" and the button do what they did."""

    def test_helplogic_has_no_context_text_yet_on_this_branch(self):
        src = (HELP / "helpLogic.js").read_text(encoding="utf-8")
        if "export function contextText" in src or "export const contextText" in src:
            self.skipTest("the context text is in: the peek opens in the shipped build")
        self.assertNotIn('"context"', (HELP / "helpContent.json").read_text(encoding="utf-8"))

    def test_the_stand_in_is_never_in_the_shipped_source(self):
        store = (HELP / "helpStore.js").read_text(encoding="utf-8")
        self.assertIn("a test-only override of contextText", store)
        self.assertIn("contextText, articlesFor, placeOf", store, "the peek reads the real contextText from helpLogic.js")
        self.assertNotIn("lookup(", store)
        self.assertNotIn("useContextText", (SRC / "clark" / "page" / "src" / "edit" / "index.js").read_text(encoding="utf-8"))
        for f in HELP.glob("*.js*"):
            if f.name != "helpStore.js":
                self.assertNotIn("useContextText(", f.read_text(encoding="utf-8"), f.name)

    def test_a_published_file_has_no_peek(self):
        view = (SRC / "clark" / "page" / "page-view.html")
        if view.is_file():
            html = view.read_text(encoding="utf-8")
            for needle in ("help-peek", "Open full Help", "data-hpk-full"):
                self.assertNotIn(needle, html)


if __name__ == "__main__":
    unittest.main()
