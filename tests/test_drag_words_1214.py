"""Row 1214: the words of a section drag (src/clark/page/src/logic/dragWords.js), the pure part.

Run: cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_drag_words_1214
No Chrome. The module is bundled with the pinned esbuild and run in node. Each of the five targets has a status line ("Release to ...",
under the page while the pointer is down) and the words said after the drop; X is the dragged title, Y the other one.
Also checks drag.js asks these words for what it draws and says, and keeps the line and ghost out of what a screen reader reads.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
from test_title_limit import bundle  # noqa: E402


def sec(id, title, beside=0):
    return {"id": id, "type": "text", "title": title, "beside": beside, "hidden": 0}


ALONE = [sec("a", "Summary"), sec("b", "Milestones"), sec("c", "This week"), sec("d", "Next week")]
PAIR = [sec("a", "Summary"), sec("b", "Milestones", 1), sec("c", "This week"), sec("d", "Next week")]       # b and c share a row


class DragWords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.out = bundle('export { dragWords } from "@src/logic/dragWords.js";', Path(cls._tmp.name), None, "dragwords.cjs")

    def words(self, sections, id, target):
        js = ("const m = require(process.argv[1]);"
              f"console.log(JSON.stringify(m.dragWords({json.dumps(sections)}, {json.dumps(id)}, {json.dumps(target)})));")
        done = subprocess.run(["node", "-e", js, str(self.out)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])
        return json.loads(done.stdout)

    def test_beside(self):
        got = self.words(ALONE, "a", {"beside": "c", "side": "right"})
        self.assertEqual(got["line"], 'Release to put "Summary" beside "This week", half width each.')
        self.assertEqual(got["said"], 'Moved "Summary" beside "This week", half width each.')

    def test_above(self):
        got = self.words(ALONE, "d", {"before": "a"})
        self.assertEqual(got["line"], 'Release to put "Next week" above "Summary".')
        self.assertEqual(got["said"], 'Moved "Next week" above "Summary".')

    def test_above_a_section_in_the_middle(self):
        got = self.words(ALONE, "a", {"before": "d"})
        self.assertEqual(got["line"], 'Release to put "Summary" above "Next week".')
        self.assertEqual(got["said"], 'Moved "Summary" above "Next week".')

    def test_below_is_the_end(self):
        got = self.words(ALONE, "a", {"before": None})
        self.assertEqual(got["line"], 'Release to put "Summary" below "Next week".')
        self.assertEqual(got["said"], 'Moved "Summary" below "Next week".')

    def test_below_a_pair_at_the_end_names_the_last_section(self):
        pair_end = [sec("a", "Summary"), sec("b", "Milestones"), sec("c", "This week", 1), sec("d", "Next week")]
        got = self.words(pair_end, "a", {"before": None})
        self.assertEqual(got["line"], 'Release to put "Summary" below "Next week".')

    def test_full_width(self):
        got = self.words(PAIR, "c", {"before": "d"})
        self.assertEqual(got["line"], 'Release to make "This week" full width.')
        self.assertEqual(got["said"], '"This week" is now full width.')
        got = self.words(PAIR, "b", {"before": "c"})
        self.assertEqual(got["line"], 'Release to make "Milestones" full width.', "the first half too: the pair ends, both stay")

    def test_own_place(self):
        for target in (None, {"before": "b"}, {"beside": "a", "side": "left"}):          # nowhere, where it already is, on itself
            with self.subTest(target=target):
                got = self.words(ALONE, "a", target)
                self.assertEqual(got["line"], 'Release to leave "Summary" where it is.')
                self.assertEqual(got["said"], '"Summary" stays where it is.')

    def test_a_target_that_changes_nothing_is_the_own_place(self):
        got = self.words(ALONE, "b", {"before": "c"})
        self.assertEqual(got["line"], 'Release to leave "Milestones" where it is.', "b already sits right before c")

    def test_a_long_title_is_cut_as_the_other_messages_cut_it(self):
        long = "L" * 60
        got = self.words([sec("a", long), sec("b", "Milestones")], "a", {"beside": "b", "side": "left"})
        self.assertIn('"' + "L" * 39 + '…"', got["line"])

    def test_drag_js_uses_the_words_and_keeps_them_from_the_screen_reader_while_dragging(self):
        src = (SRC / "clark" / "page" / "src" / "edit" / "drag.js").read_text(encoding="utf-8")
        self.assertIn("dragWords(sections(), id, t).line", src, "the line comes from the target the slot uses")
        self.assertIn('line.setAttribute("aria-hidden", "true")', src)
        self.assertIn('ghost.setAttribute("aria-hidden", "true")', src)
        self.assertIn('live.setAttribute("aria-live", "polite")', src)
        self.assertEqual(src.count("line.remove()"), 1, "the line goes in the one place everything of a drag is wiped")


if __name__ == "__main__":
    unittest.main()
