"""#1292 S11: the quick bar's ask row, askRow() and search() in src/clark/page/src/edit/palette.js, on the real source.

Run: python3 dev/run_tests.py test_palette_ask_row_logic
palette.js is bundled the way the page is and run in headless Chrome (as test_palette_search_logic does). Covers each question word on its own
(first), a word that only starts with one (not first), the case of the word, a question mark only at the end, the 60 character cut of the label
(the whole text at 60, one character fewer and an ellipsis at 61, no space left before the ellipsis), nothing typed (no row), and the order
in the list when other results match too. Chrome is required: it fails, never skips, without it (set CLARK_CHROME).
"""
import json
import unittest
from pathlib import Path

from test_help_logic import page_target  # noqa: E402
from test_palette_search_logic import bundled  # noqa: E402
from test_server import CHROME, chrome  # noqa: E402

WORDS = "what who whom whose when where why how which is are was were can could do does did should will would has have".split()


class AskRowLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert Path(CHROME).is_file(), f"Chrome is needed for the required browser tests: set CLARK_CHROME ({CHROME!r})"
        cls.code = bundled()

    def js(self, expr):
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": self.code + ";\n(() => { " + expr + " })()", "returnByValue": True}, sid)
            self.assertNotIn("exceptionDetails", res, res)
            return res["result"]["value"]

    def test_every_question_word_makes_it_first_in_any_case_and_only_as_a_whole_word(self):
        got = self.js("const o = {}; for (const w of " + json.dumps(WORDS) + ") o[w] = [PAL.askRow(w + ' zzqx').first, PAL.askRow(w.toUpperCase() + ' zzqx').first,"
                      " PAL.askRow(w + 'zzqx').first, PAL.askRow(w).first]; return o;")
        for w in WORDS:
            self.assertEqual(got[w], [True, True, False, False], w)

    CLASSIC = "const t = document.createElement('div'); t.id = 'theme'; document.body.appendChild(t); "

    def test_summar_check_and_draft_make_it_first_in_classic_as_the_prototype_lists_them(self):
        # row 1350, Classic only (the #theme element is present); summar is a stem, so summarise and summary count; the word must stand whole as the others do
        got = self.js(self.CLASSIC + "const f = (q) => PAL.askRow(q).first; return [f('summarise zzqx'), f('Summary zzqx'), f('SUMMARIZE zzqx'), f('check zzqx'), f('Draft zzqx'), f('drafts zzqx'), f('checkpoint zzqx'), f('zzqx draft'), f('draftzzqx'), f('summarise the plan'), f('check the plan'), f('draft a note')];")
        self.assertEqual(got, [True, True, True, True, True, False, False, False, False, True, True, True])

    def test_summar_check_and_draft_do_not_make_it_first_in_cards_and_the_base_words_still_do_in_both(self):
        # Cards (no #theme element) keeps the old list
        cards = self.js("const f = (q) => PAL.askRow(q).first; return [f('summarise the plan'), f('check the plan'), f('draft a note'), f('what zzqx'), f('is zzqx')];")
        self.assertEqual(cards, [False, False, False, True, True])
        classic = self.js(self.CLASSIC + "const f = (q) => PAL.askRow(q).first; return [f('what zzqx'), f('is zzqx'), f('zzqx?')];")
        self.assertEqual(classic, [True, True, True])

    def test_a_question_mark_counts_only_at_the_end(self):
        got = self.js("return [PAL.askRow('zzqx?').first, PAL.askRow('zzqx? yes').first, PAL.askRow('zzqx').first, PAL.askRow('  zzqx?  ').first];")
        self.assertEqual(got, [True, False, False, True])

    def test_nothing_or_only_spaces_has_no_row_and_the_question_is_the_trimmed_text(self):
        got = self.js("return [PAL.askRow('') , PAL.askRow('   '), PAL.askRow(null), PAL.askRow(undefined), PAL.askRow('  zzqx ').question];")
        self.assertEqual(got, [None, None, None, None, "zzqx"])

    def test_the_label_is_cut_after_sixty_characters(self):
        s60, s61 = "a" * 59 + "b", "a" * 59 + "bc"
        spaced = "a" * 58 + "   bcd"
        got = self.js("return [PAL.askRow(" + json.dumps(s60) + ").label, PAL.askRow(" + json.dumps(s61) + ").label, PAL.askRow(" + json.dumps(spaced) + ").label,"
                      " PAL.askRow(" + json.dumps(s61) + ").question];")
        self.assertEqual(got[0], f"Ask “{s60}” in ask clark", "60 characters are shown whole")
        self.assertEqual(got[1], f"Ask “{'a' * 59}…” in ask clark", "61 are cut to 59 and an ellipsis")
        self.assertEqual(got[2], f"Ask “{'a' * 58}…” in ask clark", "spaces before the cut are dropped")
        self.assertEqual(got[3], s61, "the whole text is handed over")

    def test_a_question_is_first_in_the_list_and_anything_else_last_even_when_other_results_match(self):
        got = self.js("const f = (q) => PAL.search(q).map((r) => r.id); const a = f('is publish'), b = f('publish');"
                      " return [a[0], a.length, b[b.length - 1], b.length];")
        self.assertEqual(got[0], "ask-row")
        self.assertGreater(got[1], 1, "the Publish command matches too")
        self.assertEqual(got[2], "ask-row")
        self.assertGreater(got[3], 1)


if __name__ == "__main__":
    unittest.main()
