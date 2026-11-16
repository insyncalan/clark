"""Row 1251: only the exact Plan summary skeleton is left out of the published file; any typed word makes the section show.

Run: python3 dev/run_tests.py test_published_plan_summary_empty
Headless Chrome. The stored body of the Plan summary template (two headings, an empty paragraph, an empty bullet), unedited,
counts as empty (logic/emptyBody.js, read from templates.js). A typed word in a heading, the paragraph or the bullet, a plain
Text section with only a typed heading, and a normal heading-and-text section all show. The published file is opened from disk
at 1400 and 900 px; the View side ("Nothing recorded.") is read from the same function in Section.jsx.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from clark import publish
from test_gantt_table_section import Base
from test_published_work_no_add import EMPTY_BRANDING, TODAY, open_page
from test_server import chrome, wait

UNFILLED = "<h2>Where we are</h2><p></p><h2>What is next</h2><ul><li></li></ul>"
UNFILLED_SPACED = "<h2>Where we are</h2>\n<p></p>\n<h2>What is next</h2>\n<ul>\n<li></li>\n</ul>"
TYPED_HEADING = "<h2>Where we are now</h2><p></p><h2>What is next</h2><ul><li></li></ul>"
TYPED_P = "<h2>Where we are</h2><p>On track.</p><h2>What is next</h2><ul><li></li></ul>"
TYPED_LI = "<h2>Where we are</h2><p></p><h2>What is next</h2><ul><li>Sign off</li></ul>"
ONLY_HEADING = "<h2>Just a heading</h2>"
NORMAL = "<h2>A heading</h2><p>Plain words under it.</p>"
TITLE = "ZQ plan summary row 1251"


class PublishedPlanSummary(Base):
    def published_text(self, body, width):
        self.s.con.execute("DELETE FROM report_sections WHERE project = 'ABC' AND title = ?", (TITLE,))
        self.s.con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES ('ABC', 'ABC-S-091', 'text', ?, ?, 0, 0, 91)", (TITLE, body))
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        path = Path(publish.publish(self.s, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        with chrome() as cdp:
            sid = open_page(cdp, path.as_uri() + "#dashboard", width, "light")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tabs .tab')", sid)))
            self.assertTrue(wait(lambda: cdp.js("document.body.innerText.length > 200", sid)))
            return cdp.js(f"document.body.innerText.includes({TITLE!r})", sid)

    def test_skeleton_is_left_out(self):
        for w in (1400, 900):
            self.assertFalse(self.published_text(UNFILLED, w), w)
            self.assertFalse(self.published_text(UNFILLED_SPACED, w), w)

    def test_skeleton_with_a_typed_word_shows(self):
        for w in (1400, 900):
            for body in (TYPED_HEADING, TYPED_P, TYPED_LI):
                self.assertTrue(self.published_text(body, w), (w, body))

    def test_plain_text_with_only_a_heading_shows(self):
        for w in (1400, 900):
            self.assertTrue(self.published_text(ONLY_HEADING, w), w)

    def test_a_normal_text_section_shows(self):
        for w in (1400, 900):
            self.assertTrue(self.published_text(NORMAL, w), w)

    def test_view_side_uses_the_same_rule(self):
        src = (Path(__file__).resolve().parent.parent / "src/clark/page/src/logic/emptyBody.js").read_text(encoding="utf-8")
        self.assertIn('find("plan-summary").body', src)
        self.assertNotIn("Where we are", src.replace("// ", ""), "the skeleton is read from the template, not copied")


if __name__ == "__main__":
    unittest.main()
