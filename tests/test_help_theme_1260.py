"""Row 1260: Help says the Theme changes the pages and not the Word, Excel and email files or the installed app.
The sentence is pinned word for word in the real helpContent.json, and the claim is checked against its subject, the
tests of test_theme_other_outputs (which pin that those outputs are the same under either Theme); they are run here, not repeated.
Run: python3 dev/run_tests.py test_help_theme_1260
"""
import json
import unittest

import _paths
import test_theme_other_outputs as subject

HELP = _paths.ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"
SENTENCE = "The Theme changes the pages. Word, Excel and email files, and the installed app, keep clark’s own colours."


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, list):
        for i in x:
            yield from _strings(i)
    elif isinstance(x, dict):
        for i in x.values():
            yield from _strings(i)


class HelpSaysThemeScope(unittest.TestCase):
    def test_the_sentence_is_in_help_once_in_the_theme_article(self):
        data = json.loads(HELP.read_text(encoding="utf-8"))
        hits = [s for s in _strings(data) if SENTENCE in s]
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0].startswith("Choose the look of your pages"))
        self.assertTrue(hits[0].endswith(SENTENCE))

    def test_the_line_is_the_approved_one_and_the_old_clause_is_gone(self):
        data = json.loads(HELP.read_text(encoding="utf-8"))
        hits = [s for s in _strings(data) if SENTENCE in s]
        self.assertTrue(hits[0].startswith("Choose the look of your pages. Your choice applies"))
        self.assertFalse([s for s in _strings(data) if "from the two the card offers" in s])

    def test_the_claim_is_true_the_other_outputs_ignore_the_theme(self):
        suite = unittest.defaultTestLoader.loadTestsFromModule(subject)
        self.assertGreater(suite.countTestCases(), 0)
        result = unittest.TestResult()
        suite.run(result)
        self.assertEqual([str(e[0]) for e in result.errors + result.failures], [])


if __name__ == "__main__":
    unittest.main()
