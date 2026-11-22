"""Row 1366: Help describes the index of source folders, in the words the status line really uses.

Run: python3 dev/run_tests.py test_help_ask_index
"""
import json
import unittest

from _paths import ROOT, SRC  # noqa: F401  (puts src/ on the path)

from clark import ask_index

HELP = ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"


def paragraphs():
    ref = json.loads(HELP.read_text(encoding="utf-8"))["reference"]["sections"]
    sec = next(s for s in ref if s["id"] == "ask-clark")
    return [b[1] for b in sec["b"] if b[0] == "p"]


class HelpDescribesTheIndex(unittest.TestCase):
    def para(self, start):
        got = [p for p in paragraphs() if p.startswith(start)]
        self.assertEqual(len(got), 1)
        return got[0]

    def test_index_paragraph_says_what_where_when_and_nothing_sent(self):
        t = self.para("The index of your source folders.")
        for words in ("ask-index", "one file for each project", "it is only a copy", "in the background",
                      "added, changed or removed", "Nothing is sent anywhere when the index is made"):
            self.assertIn(words, t)
        for kind in ("Word", "PDF", "Excel", "PowerPoint", "web pages", "text", "Markdown", "CSV"):
            self.assertIn(kind, t)

    def test_status_paragraph_quotes_the_lines_clark_shows(self):
        t = self.para("The line under each folder")
        self.assertIn(ask_index.line_for(None, (180, 422)), t)
        self.assertIn(ask_index.done_line({"indexed": 180}), t)
        self.assertIn(ask_index.done_line({"indexed": 180, "type": 242}), t)
        self.assertIn(ask_index.done_line({"type": 2}), t)
        self.assertIn("(why)", t)
        self.assertIn(ask_index.answer_note({"not_yet": 120}).rstrip("."), t)

    def test_index_path_is_the_real_one(self):
        self.assertEqual(ask_index.path_for("D", "P1").parent.name, "ask-index")


if __name__ == "__main__":
    unittest.main()
