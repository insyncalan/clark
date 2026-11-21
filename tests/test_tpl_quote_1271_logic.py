"""Row 1271, Quote: the page's reading of a stored quote (templates/notes.js tidyQuote, quoteLook, quoteEmpty, sectionShows), run in node.

Run: python3 dev/run_tests.py test_tpl_quote_1271_logic
Quick tier: no browser. The module is bundled by the pinned esbuild (skips without node). Fictional data only.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)

NOTES = SRC / "clark" / "page" / "src" / "templates" / "notes.js"


_BUNDLE = []      # the bundle of notes.js, made once for the whole run


def _bundle():
    if not _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "m.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=N", str(NOTES), f"--outfile={out}"], capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE.append(out.read_text(encoding="utf-8"))
    return _BUNDLE[0]


def probe(expr):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(_bundle() + f";\nconsole.log(JSON.stringify({expr}));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


Q = lambda t, by="", role="": {"quote": t, "by": by, "role": role}


class Tidy(unittest.TestCase):
    def test_the_older_shape_is_one_quote_and_stores_nothing_new(self):
        got = probe('N.tidyQuote({quote: " Fictional. ", by: "Sam", role: "R"})')
        self.assertEqual(got, {"quotes": [Q("Fictional.", "Sam", "R")], **Q("Fictional.", "Sam", "R")})
        self.assertNotIn("align", got)
        self.assertNotIn("tile", got)

    def test_the_list_keeps_six_and_the_first_quote_fields_are_the_first_quotes(self):
        got = probe('N.tidyQuote({quotes: [1,2,3,4,5,6,7].map((i) => ({quote: "Q" + i, by: "B" + i, role: "R" + i}))})')
        self.assertEqual([q["quote"] for q in got["quotes"]], [f"Q{i}" for i in range(1, 7)])
        self.assertEqual((got["quote"], got["by"], got["role"]), ("Q1", "B1", "R1"))

    def test_the_list_wins_over_top_level_fields(self):
        got = probe('N.tidyQuote({quote: "Top", by: "Top", role: "Top", quotes: [{quote: "In list"}]})')
        self.assertEqual(got["quotes"], [Q("In list")])
        self.assertEqual(got["quote"], "In list")

    def test_fields_are_cut_at_their_limits_and_non_text_is_empty(self):
        got = probe('N.tidyQuote({quotes: [{quote: "x".repeat(700), by: "y".repeat(200), role: 5}]})')
        self.assertEqual((len(got["quotes"][0]["quote"]), len(got["quotes"][0]["by"]), got["quotes"][0]["role"]), (600, 120, ""))
        got = probe('N.tidyQuote({quotes: [{quote: "a", role: "z".repeat(200)}]})')
        self.assertEqual(len(got["quotes"][0]["role"]), 120)

    def test_nothing_or_an_empty_list_is_one_empty_quote_or_none(self):
        self.assertEqual(probe("N.tidyQuote(null).quotes"), [Q("")])
        self.assertEqual(probe("N.tidyQuote({quotes: []}).quotes"), [])
        self.assertEqual(probe("N.tidyQuote({quotes: []}).quote"), "")

    def test_align_per_row_tile_and_heading_are_kept_only_when_valid(self):
        got = probe('N.tidyQuote({quote: "a", align: "centre", perRow: 3, tile: false, heading: false})')
        self.assertEqual((got["align"], got["perRow"], got["tile"], got["heading"]), ("centre", 3, False, False))
        for bad in ('align: "right"', 'align: 1', 'perRow: 4', 'perRow: "2"', 'tile: "no"', 'heading: 0'):
            with self.subTest(bad=bad):
                got = probe("N.tidyQuote({quote: 'a', %s})" % bad)
                self.assertFalse({"align", "perRow", "tile", "heading"} & set(got), got)
        for bad in ('tile: "no"', 'tile: 0', 'heading: "no"', 'heading: null'):
            with self.subTest(bad=bad):
                self.assertFalse({"tile", "heading"} & set(probe("N.tidyQuote({quote: 'a', %s})" % bad)))
        left = probe('N.tidyQuote({quote: "a", align: "left", perRow: 2, tile: true, heading: true})')
        self.assertEqual((left["align"], left["perRow"], left["tile"], left["heading"]), ("left", 2, True, True))


class Look(unittest.TestCase):
    def test_empty_is_no_quote_with_words(self):
        self.assertTrue(probe('N.quoteEmpty(N.tidyQuote({quotes: [{quote: ""}, {quote: "", by: "Sam"}]}))'))
        self.assertFalse(probe('N.quoteEmpty(N.tidyQuote({quotes: [{quote: ""}, {quote: "x"}]}))'))
        self.assertFalse(probe('N.quoteEmpty(N.tidyQuote({quote: "x"}))'))

    def test_look_draws_only_quotes_with_words_and_the_defaults(self):
        got = probe('N.quoteLook(N.tidyQuote({quotes: [{quote: ""}, {quote: "a", by: "Sam"}, {quote: "", by: "Z"}, {quote: "b"}]}))')
        self.assertEqual(got, {"quotes": [Q("a", "Sam"), Q("b")], "align": "left", "perRow": 2, "tile": True, "heading": True})

    def test_look_gives_what_is_stored(self):
        got = probe('N.quoteLook(N.tidyQuote({quote: "a", align: "centre", perRow: 3, tile: false, heading: false}))')
        self.assertEqual((got["align"], got["perRow"], got["tile"], got["heading"]), ("centre", 3, False, False))

    def test_a_section_shows_its_tile_and_heading_unless_stored_off(self):
        self.assertEqual(probe('N.sectionShows({type: "quote", body: JSON.stringify({v: 1, quote: "a"})})'), {"tile": True, "heading": True})
        self.assertEqual(probe('N.sectionShows({type: "quote", body: JSON.stringify({v: 1, quote: "a", tile: false})})'), {"tile": False, "heading": True})
        self.assertEqual(probe('N.sectionShows({type: "quote", body: JSON.stringify({v: 1, quote: "a", heading: false})})'), {"tile": True, "heading": False})


if __name__ == "__main__":
    unittest.main()
