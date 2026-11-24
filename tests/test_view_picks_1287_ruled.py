"""Row 1287, the ruled points: the View rule of the Dashboard is changed on purpose and says so; a published file has no pickers;
a pick made in View or in Edit shows one message (one toast) and no more. In a real browser at 1400 and 900 px. Fictional data only.

Run: python3 dev/run_tests.py test_view_picks_1287_ruled   (headless Chrome; fails, never skips, without it)
"""
import re
import unittest
from pathlib import Path

import test_tpl_workitems as T
from test_view_picks_1287_more import classic
from _publish import PublishedFile
from test_report_editor import Pg, tearDownModule  # noqa: F401
from test_server import chrome

SRC = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "components"


class TheRuleSaysItIsChanged(unittest.TestCase):
    def test_the_dashboard_comment_says_the_view_rule_is_changed_on_purpose(self):
        head = "\n".join((SRC / "Dashboard.jsx").read_text(encoding="utf-8").splitlines()[:8])
        self.assertIn("on purpose", head, "the View rule of the Dashboard says it is changed on purpose")
        self.assertIn("M10041", head, "and names the ruling")
        for word in ("priority", "due", "owner", "status"):
            self.assertIn(word, head, f"and names the cell {word}")
        self.assertIn("published file", head)
        self.assertNotIn("renders no edit component at all", head, "the old absolute wording is gone")
        self.assertIsNone(re.search(r"row #\d|ruling #\d", head), "no digits behind a hash in the comment")


class InTheToasts(T.InThePage):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", T.USER) as st:
            st.create("report_sections", {"project": "ABC", "type": "actions", "title": "Open actions", "sort_order": 50, "hidden": 0})

    WATCH = """window.__toast = {max: 0, seen: 0, undo: 0};
      new MutationObserver(() => { const n = document.querySelectorAll('.toast').length; window.__toast.max = Math.max(window.__toast.max, n);
        window.__toast.seen += n ? 1 : 0; window.__toast.undo += document.querySelector('.toast [data-undo]') ? 1 : 0; })
        .observe(document.body, {childList: true, subtree: true, attributes: true}); true"""

    def press(self, p, selector):
        p.js(f"document.querySelector('{selector}').scrollIntoView({{block: 'center'}})")
        x, y, _ = p.box(selector)
        p.mouse("mouseMoved", x, y)
        p.mouse("mousePressed", x, y, 1)
        p.mouse("mouseReleased", x, y)

    def pick(self, p, cell, value):
        self.press(p, cell)
        p.until(f"!!document.querySelector('[data-pop] [data-value={value}]')", "the menu opened")
        self.press(p, f"[data-pop] [data-value={value}]")

    def test_a_pick_shows_one_toast_in_view_and_one_in_edit(self):
        classic(self)
        cell = f".wl-row[data-id=\"{self.a_due}\"] .c-ico .cell-pick"
        for mode in ("view", "edit"):
            for width in (1400, 900):
                with self.subTest(width=width, mode=mode), chrome() as cdp:
                    with self.store.step("dashboard", T.USER) as st:
                        st.update("actions", self.a_due, {"status": "Open"})       # each pass starts from Open: a pick that changes nothing makes no message
                    p = self.show(cdp, width)
                    if mode == "edit":
                        p.edit()
                    p.until(f"!!document.querySelector('{cell}')", f"the actions list drew in {mode}")
                    p.js(self.WATCH)
                    self.pick(p, cell, "Delayed")
                    p.until("window.__toast.undo > 0", "the pick said what it did, with Undo")
                    self.assertEqual(self.store.read("actions", ref=self.a_due)["status"], "Delayed")
                    self.assertEqual(p.js("window.__toast.max"), 1, f"{mode} showed one toast at a time, never Edit's and the View one together")


class InTheFile(PublishedFile, T.InThePage):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", T.USER) as st:
            st.create("report_sections", {"project": "ABC", "type": "actions", "title": "Open actions", "sort_order": 50, "hidden": 0})

    def test_a_published_file_has_the_rows_and_no_pickers(self):
        self.add({"mode": "all", "columns": ["id", "owner", "due", "status", "priority"]})
        path = self.publish()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, path, width)
                p.until("document.querySelectorAll('.wl-row').length > 0", "the file drew the actions rows")
                self.assertGreater(p.js("document.querySelectorAll('.wil-table tbody tr').length"), 0, "and the work items list rows")
                self.assertEqual(p.js("document.querySelectorAll('.cell-pick, [data-cell], .wl-open, button.idl').length"), 0, "no picker, no editable cell, no open row in the file")
                self.assertEqual(p.js("document.querySelectorAll('input, select, textarea, [contenteditable=true]').length"), 0, "no input in the file")


if __name__ == "__main__":
    unittest.main()
