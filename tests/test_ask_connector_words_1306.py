"""Row 1306 step 3: the sentence the owner decided is where mail, Teams, calendars or SharePoint are mentioned in the ask clark first-run card and in
Help, and the old 'never reads' wording is nowhere, because with a connector turned on it would be false. Source files only (no browser).

Run: python3 dev/run_tests.py test_ask_connector_words_1306
"""
import json
import re
import unittest

from _paths import SRC

SENTENCE = "Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings."
OLD = re.compile(r"never (?:reads? )?(?:your )?mail, Teams or calendars|Mail, Teams and calendars are never", re.I)
PAGE = SRC / "clark" / "page" / "src"


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from strings(v)


class Words(unittest.TestCase):
    def test_the_first_run_card_says_the_decided_sentence(self):
        words = (PAGE / "edit" / "askWords.js").read_text(encoding="utf-8")
        self.assertIn(SENTENCE, words)
        self.assertFalse(OLD.search(words))

    def test_help_says_it_wherever_it_names_mail_teams_and_calendars_and_never_the_old_words(self):
        texts = list(strings(json.loads((PAGE / "help" / "helpContent.json").read_text(encoding="utf-8"))))
        self.assertFalse([t for t in texts if OLD.search(t)])
        naming = [t for t in texts if re.search(r"\bTeams\b", t) and re.search(r"calendars", t)]
        self.assertTrue(naming and all(SENTENCE in t for t in naming), naming)

    def test_no_other_source_file_has_the_old_words(self):
        bad = [str(p) for p in PAGE.rglob("*") if p.suffix in (".js", ".jsx", ".json") and "shown" not in p.parts
               and OLD.search(p.read_text(encoding="utf-8", errors="replace"))]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
